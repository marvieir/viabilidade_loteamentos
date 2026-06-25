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

# Legenda ESA WorldCover (fonte PADRÃO — pública, 10 m, sem login): classes tratadas como
# "área verde". 10=árvores, 20=arbustiva, 90=área úmida herbácea, 95=mangue. NÃO incluímos
# 30=pastagem/campo por padrão (costuma ser aproveitável); adicione via env se quiser.
# Sobrescrevível por env VEGETACAO_CLASSES_VERDE (ex.: "10,20,30,90,95").
CLASSES_VERDE_WORLDCOVER = {10, 20, 90, 95}
# Referência, caso use MapBiomas (legenda diferente!): formações naturais.
CLASSES_VERDE_MAPBIOMAS = {3, 4, 5, 6, 49, 11, 12, 13, 32, 29, 50}
# Default da plataforma = WorldCover (sem autenticação).
CLASSES_VERDE_PADRAO = CLASSES_VERDE_WORLDCOVER


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


def _extrair_cobertura(
    fontes: list[str],
    gleba: BaseGeometry,
    classes: set[int],
    fonte_nome: str,
    assunto: str = "cobertura vegetal",
) -> CoberturaVerde:
    """Lê uma ou mais fontes raster (arquivo local OU ``/vsicurl/`` COG remoto) e devolve a
    cobertura verde da gleba (união, WGS84). ``rasterio.mask`` recorta pela gleba; as classes
    de vegetação viram polígono via ``rasterio.features.shapes``. Import de rasterio é tardio
    (só produção; testes usam stub). Degrada honesto se TODA fonte falhar — nunca derruba.
    """
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
    except Exception as exc:  # noqa: BLE001 — sem rasterio → degrada
        Assunto = assunto[:1].upper() + assunto[1:]
        return CoberturaVerde(
            avisos=[f"{Assunto} indisponível — {type(exc).__name__}: {exc}"[:200]]
        )

    polys_wgs = []
    erros: list[str] = []
    for fonte in fontes:
        try:
            with rasterio.open(fonte) as src:
                geom_raster = transform_geom("EPSG:4326", src.crs, mapping(gleba))
                recorte, transf = rio_mask(src, [geom_raster], crop=True, filled=True)
                mask_verde = np.isin(recorte[0], list(classes))
                to_wgs = Transformer.from_crs(src.crs, "EPSG:4326", always_xy=True).transform
                for g, _ in rio_shapes(
                    mask_verde.astype("uint8"), mask=mask_verde, transform=transf
                ):
                    polys_wgs.append(shp_transform(to_wgs, shape(g)))
        except Exception as exc:  # noqa: BLE001 — tile pode não cobrir/existir; tenta o próximo
            erros.append(f"{type(exc).__name__}: {exc}")
            continue

    if polys_wgs:
        return CoberturaVerde(
            geometria=unary_union(polys_wgs),
            fonte=fonte_nome,
            data_referencia=date.today().isoformat(),
            classes=[str(c) for c in sorted(classes)],
        )

    # Sem polígono detectado. Se TODAS as fontes falharam é erro real (não "gleba sem a classe").
    Assunto = assunto[:1].upper() + assunto[1:]
    if erros and len(erros) == len(fontes):
        bruto = erros[0]
        if "do not overlap" in bruto:
            aviso = (
                f"{Assunto} indisponível — o recorte não cobre esta gleba (foi gerado para "
                "outra área). Use o modo automático (COG por HTTP, sem recorte) ou gere o "
                "recorte deste KMZ."
            )
        elif any(k in bruto for k in ("curl", "HTTP", "Connection", "timed out", "403", "404")):
            aviso = (
                f"{Assunto} indisponível — não foi possível ler o raster por HTTP (egress "
                "bloqueado?). Libere o acesso ao bucket público ou aponte um recorte local."
            )
        else:
            aviso = f"{Assunto} indisponível — {bruto}"
        return CoberturaVerde(avisos=[aviso[:200]])

    # Fonte(s) lida(s) com sucesso, mas sem a classe na gleba — degrada honesto.
    return CoberturaVerde(
        fonte=fonte_nome,
        data_referencia=date.today().isoformat(),
        avisos=[f"Nenhuma {assunto} detectada na gleba (raster)."],
    )


class FonteVegetacaoRaster:
    """Lê um recorte raster LOCAL (arquivo) e devolve a cobertura verde da gleba.

    Modo offline / override: útil quando o egress para o COG público está bloqueado. O
    recorte é gerado por ``scripts/baixar_worldcover.py`` para uma gleba específica.
    """

    def __init__(
        self,
        caminho: str,
        classes: Optional[set[int]] = None,
        fonte: Optional[str] = None,
    ):
        self.caminho = caminho
        self.classes = classes or _classes_env() or CLASSES_VERDE_PADRAO
        self.fonte = fonte or os.getenv("VEGETACAO_FONTE_NOME") or "ESA WorldCover 10m (2021)"

    def cobertura_verde(self, gleba: BaseGeometry) -> CoberturaVerde:
        return _extrair_cobertura([self.caminho], gleba, self.classes, self.fonte)


# COG público do ESA WorldCover (AWS Open Data, anônimo, SEM login).
WORLDCOVER_COG_URL = (
    "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/"
    "ESA_WorldCover_10m_2021_v200_{tile}_Map.tif"
)


def _tile_worldcover(lon: float, lat: float) -> str:
    """Tile de 3°×3° pelo canto inferior-esquerdo (ex.: gleba em SP → 'S24W048')."""
    import math

    lat3 = math.floor(lat / 3) * 3
    lon3 = math.floor(lon / 3) * 3
    ns = f"{'N' if lat3 >= 0 else 'S'}{abs(lat3):02d}"
    ew = f"{'E' if lon3 >= 0 else 'W'}{abs(lon3):03d}"
    return ns + ew


def _tiles_da_gleba(bounds: tuple[float, float, float, float]) -> list[str]:
    """Tiles WorldCover distintos que cobrem o bbox da gleba (cantos + centróide). Quase
    sempre 1; >1 só quando a gleba cruza uma linha do grid de 3° (raro)."""
    minx, miny, maxx, maxy = bounds
    cantos = [
        (minx, miny), (maxx, miny), (minx, maxy), (maxx, maxy),
        ((minx + maxx) / 2, (miny + maxy) / 2),
    ]
    tiles: list[str] = []
    for lon, lat in cantos:
        t = _tile_worldcover(lon, lat)
        if t not in tiles:
            tiles.append(t)
    return tiles


def _gdal_anon_http_env() -> None:
    """Liga acesso anônimo e leitura por janela (range requests) ao COG público."""
    os.environ.setdefault("AWS_NO_SIGN_REQUEST", "YES")
    os.environ.setdefault("GDAL_HTTP_MULTIRANGE", "YES")
    os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
    os.environ.setdefault("CPL_VSIL_CURL_ALLOWED_EXTENSIONS", ".tif")


class FonteVegetacaoWorldCoverAuto:
    """Lê o ESA WorldCover DIRETO do COG público por HTTP, escolhendo o tile pela posição
    da gleba. Funciona para QUALQUER KMZ **sem recorte manual** — rasterio/GDAL lê só a
    janela da gleba (range requests). Único requisito: egress ao bucket público no deploy.
    """

    def __init__(self, classes: Optional[set[int]] = None, fonte: Optional[str] = None):
        self.classes = classes or _classes_env() or CLASSES_VERDE_PADRAO
        self.fonte = (
            fonte or os.getenv("VEGETACAO_FONTE_NOME") or "ESA WorldCover 10m (2021, COG)"
        )

    def cobertura_verde(self, gleba: BaseGeometry) -> CoberturaVerde:
        _gdal_anon_http_env()
        fontes = [
            f"/vsicurl/{WORLDCOVER_COG_URL.format(tile=t)}"
            for t in _tiles_da_gleba(gleba.bounds)
        ]
        return _extrair_cobertura(fontes, gleba, self.classes, self.fonte)


def _classes_env() -> Optional[set[int]]:
    # VEGETACAO_CLASSES_VERDE (preferido) ou MAPBIOMAS_CLASSES_VERDE (compat).
    bruto = os.getenv("VEGETACAO_CLASSES_VERDE") or os.getenv("MAPBIOMAS_CLASSES_VERDE")
    if not bruto:
        return None
    return {int(x) for x in bruto.replace(";", ",").split(",") if x.strip()}


def get_fonte_vegetacao() -> Optional[FonteVegetacao]:
    """Escolhe a fonte de vegetação (degrada honesto se nenhuma servir):

    1. ``VEGETACAO_RASTER_PATH`` / ``MAPBIOMAS_RASTER_PATH`` → recorte LOCAL (offline/override).
    2. senão, modo AUTOMÁTICO (WorldCover via COG/HTTP) — funciona para qualquer KMZ sem
       recorte manual; desligável com ``VEGETACAO_WORLDCOVER_AUTO=0`` (ex.: egress fechado).
    3. senão → ``None`` (não desconta, não inventa).
    """
    caminho = os.getenv("VEGETACAO_RASTER_PATH") or os.getenv("MAPBIOMAS_RASTER_PATH")
    if caminho:
        return FonteVegetacaoRaster(caminho)
    auto = os.getenv("VEGETACAO_WORLDCOVER_AUTO", "1").strip().lower()
    if auto not in ("0", "false", "no", "off"):
        return FonteVegetacaoWorldCoverAuto()
    return None
