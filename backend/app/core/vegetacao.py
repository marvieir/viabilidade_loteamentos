"""Motor de vegetação (Fase 2.2) — área verde da gleba → desconto do aproveitável.

TRIAGEM, não laudo (spec `docs/fase-2.2-area-verde.md`): identifica a cobertura vegetal
sobre a gleba e a remove da área aproveitável. NÃO classifica bioma/espécie/supressão —
isso é do engenheiro ambiental. Determinístico: mesma gleba + mesma cobertura → mesma área
verde. Área em CRS MÉTRICO LOCAL (AEQD no centróide), nunca em graus.

A FONTE é injetável (padrão da malha/ambiental): produção lê um raster de uso/cobertura
(MapBiomas) montado como volume; testes injetam uma fonte-stub determinística.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional, Protocol, runtime_checkable

from pyproj import CRS, Transformer
from shapely.geometry import mapping
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform

RESSALVA_VEG = (
    "triagem conservadora — área verde removida do aproveitável; classificação e "
    "supressão dependem de laudo de engenheiro ambiental (fora do escopo da plataforma)"
)

# Classes do MapBiomas tratadas como "área verde" (formações naturais). Ajustar à legenda
# da coleção real ao validar com o raster. Sobrescrevível por env (MAPBIOMAS_CLASSES_VERDE).
CLASSES_VERDE_MAPBIOMAS = {3, 4, 5, 6, 49, 11, 12, 13, 32, 29, 50}


@dataclass
class CoberturaVerde:
    """Cobertura vegetal devolvida pela fonte. ``geometria=None`` = não consultada."""

    geometria: Optional[BaseGeometry] = None  # polígono(s) de verde (WGS84)
    fonte: Optional[str] = None
    data_referencia: Optional[str] = None
    classes: list[str] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)


@runtime_checkable
class FonteVegetacao(Protocol):
    def cobertura_verde(self, gleba: BaseGeometry) -> CoberturaVerde: ...


def _crs_local(lon: float, lat: float) -> CRS:
    return CRS.from_proj4(
        f"+proj=aeqd +lat_0={lat} +lon_0={lon} +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs"
    )


@dataclass
class ResultadoVegetacao:
    area_total_m2: float
    area_verde_m2: Optional[float]
    area_liquida_m2: Optional[float]
    percentual_verde: Optional[float]
    geojson_verde: dict
    proveniencia: Optional[dict]
    avisos: list[str]
    consultada: bool


def analisar_vegetacao(
    gleba: BaseGeometry, cobertura: Optional[CoberturaVerde]
) -> ResultadoVegetacao:
    """Mede a área verde dentro da gleba e a desconta do total (determinístico)."""
    c = gleba.centroid
    local = _crs_local(c.x, c.y)
    to_local = Transformer.from_crs("EPSG:4326", local, always_xy=True).transform
    to_wgs = Transformer.from_crs(local, "EPSG:4326", always_xy=True).transform
    gleba_l = transform(to_local, gleba)
    area_total = round(gleba_l.area, 2)

    # Sem fonte (ou sem geometria): degradação honesta — não desconta, não inventa.
    if cobertura is None or cobertura.geometria is None:
        avisos = list(cobertura.avisos) if cobertura else []
        if not avisos:
            avisos = ["Cobertura vegetal não consultada (fonte de dados não configurada)."]
        return ResultadoVegetacao(
            area_total, None, None, None, {}, None, avisos, consultada=False
        )

    verde_in = transform(to_local, cobertura.geometria).intersection(gleba_l)
    area_verde = round(verde_in.area, 2) if not verde_in.is_empty else 0.0
    area_liquida = round(area_total - area_verde, 2)
    pct = round(area_verde / area_total * 100, 2) if area_total > 0 else 0.0
    geojson = mapping(transform(to_wgs, verde_in)) if not verde_in.is_empty else {}
    prov = {
        "fonte": cobertura.fonte,
        "data_referencia": cobertura.data_referencia,
        "classes": list(cobertura.classes),
        "ressalva": RESSALVA_VEG,
    }
    return ResultadoVegetacao(
        area_total, area_verde, area_liquida, pct, geojson, prov,
        list(cobertura.avisos), consultada=True,
    )


class FonteVegetacaoRaster:
    """Produção: lê um raster de uso/cobertura (MapBiomas) e devolve a cobertura verde.

    ``rasterio.mask`` recorta pela gleba; as classes de vegetação viram polígono via
    ``rasterio.features.shapes``. Import de rasterio é tardio (dependência só de produção;
    os testes usam fonte-stub). Degrada honestamente se o raster falhar.

    PENDENTE de validação ao vivo com o raster real (legenda/CRS/classes da coleção).
    """

    def __init__(self, caminho: str, classes: Optional[set[int]] = None):
        self.caminho = caminho
        self.classes = classes or _classes_env() or CLASSES_VERDE_MAPBIOMAS

    def cobertura_verde(self, gleba: BaseGeometry) -> CoberturaVerde:
        from datetime import date

        try:
            import numpy as np
            import rasterio
            from rasterio.features import shapes as rio_shapes
            from rasterio.mask import mask as rio_mask
            from rasterio.warp import transform_geom
            from shapely.geometry import shape
            from shapely.ops import transform as shp_transform
            from shapely.ops import unary_union

            with rasterio.open(self.caminho) as src:
                geom_raster = transform_geom("EPSG:4326", src.crs, mapping(gleba))
                recorte, transf = rio_mask(src, [geom_raster], crop=True, filled=True)
                mask_verde = np.isin(recorte[0], list(self.classes))
                polys = [
                    shape(g)
                    for g, _ in rio_shapes(
                        mask_verde.astype("uint8"), mask=mask_verde, transform=transf
                    )
                ]
                if not polys:
                    return CoberturaVerde(
                        fonte="MapBiomas (uso/cobertura)",
                        data_referencia=date.today().isoformat(),
                        avisos=["Nenhuma cobertura vegetal detectada na gleba (raster)."],
                    )
                to_wgs = Transformer.from_crs(src.crs, "EPSG:4326", always_xy=True).transform
                return CoberturaVerde(
                    geometria=shp_transform(to_wgs, unary_union(polys)),
                    fonte="MapBiomas (uso/cobertura)",
                    data_referencia=date.today().isoformat(),
                    classes=[str(c) for c in sorted(self.classes)],
                )
        except Exception as exc:  # noqa: BLE001 — degradar, não derrubar
            return CoberturaVerde(
                avisos=[f"Cobertura vegetal indisponível — {type(exc).__name__}: {exc}"[:180]]
            )


def _classes_env() -> Optional[set[int]]:
    bruto = os.getenv("MAPBIOMAS_CLASSES_VERDE")
    if not bruto:
        return None
    return {int(x) for x in bruto.replace(";", ",").split(",") if x.strip()}


def get_fonte_vegetacao() -> Optional[FonteVegetacao]:
    """Liga a fonte real se ``MAPBIOMAS_RASTER_PATH`` apontar para um raster (volume)."""
    caminho = os.getenv("MAPBIOMAS_RASTER_PATH")
    if caminho:
        return FonteVegetacaoRaster(caminho)
    return None
