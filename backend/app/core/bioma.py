"""Identificação de BIOMA (IBGE) sobre a gleba — Tier 2 (paridade Urbia "Bioma").

Fonte injetável: lê o arquivo de biomas (IBGE 1:250.000) na JANELA da gleba (reusa a leitura
CRS-robusta de ``camadas_inde``), intersecta cada polígono com a gleba (em CRS métrico) e
devolve o(s) bioma(s) incidente(s) + o dominante. Determinístico, offline. Sem arquivo →
``None`` (degrada honesto). Nada de inventar bioma.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional, Protocol, runtime_checkable

from pyproj import Transformer
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform as shp_transform

FONTE_IBGE = "IBGE — Biomas (1:250.000)"


@dataclass
class BiomaIncidente:
    nome: str
    area_m2: float
    pct: float  # fração da gleba


@dataclass
class ResultadoBioma:
    consultado: bool
    dominante: Optional[str]
    biomas: list[BiomaIncidente]
    fonte: Optional[str]
    avisos: list[str] = field(default_factory=list)


@runtime_checkable
class FonteBioma(Protocol):
    def identificar(self, gleba: BaseGeometry) -> ResultadoBioma: ...


class FonteBiomaArquivo:
    """Lê o bioma de um arquivo vetorial local (shapefile/gpkg/geojson IBGE)."""

    def __init__(self, path: str):
        self.path = path

    def identificar(self, gleba: BaseGeometry) -> ResultadoBioma:
        from app.core.camadas_inde import _first, _ler_vetor_local_bbox

        try:
            feats = _ler_vetor_local_bbox(self.path, gleba.bounds)  # geoms WGS84 + props
        except Exception as exc:  # noqa: BLE001 — degrada honesto
            return ResultadoBioma(
                consultado=False, dominante=None, biomas=[], fonte=FONTE_IBGE,
                avisos=[f"Bioma indisponível — {type(exc).__name__}: {exc}"[:180]],
            )
        if not feats:
            return ResultadoBioma(
                consultado=True, dominante=None, biomas=[], fonte=FONTE_IBGE,
                avisos=["Nenhum bioma mapeado na janela da gleba."],
            )

        c = gleba.centroid
        proj4 = (
            f"+proj=aeqd +lat_0={c.y} +lon_0={c.x} +x_0=0 +y_0=0 "
            "+datum=WGS84 +units=m +no_defs"
        )
        to_m = Transformer.from_crs("EPSG:4326", proj4, always_xy=True).transform
        gleba_m = shp_transform(to_m, gleba)
        total = gleba_m.area
        por_nome: dict[str, float] = {}
        for geom, props in feats:
            nome = _first(props, "Bioma", "bioma", "NOM_BIOMA", "nom_bioma") or "Não classificado"
            try:
                inter = shp_transform(to_m, geom).intersection(gleba_m)
            except Exception:  # noqa: BLE001 — geometria degenerada, ignora
                continue
            if not inter.is_empty and inter.area > 0:
                por_nome[nome] = por_nome.get(nome, 0.0) + inter.area
        if not por_nome:
            return ResultadoBioma(
                consultado=True, dominante=None, biomas=[], fonte=FONTE_IBGE,
                avisos=["Nenhum bioma intersecta a gleba."],
            )
        biomas = sorted(
            (
                BiomaIncidente(
                    nome=n, area_m2=round(a, 2),
                    pct=round(a / total, 4) if total else 0.0,
                )
                for n, a in por_nome.items()
            ),
            key=lambda b: b.area_m2, reverse=True,
        )
        return ResultadoBioma(
            consultado=True, dominante=biomas[0].nome, biomas=biomas, fonte=FONTE_IBGE,
        )


def get_fonte_bioma() -> Optional[FonteBioma]:
    """Dependência FastAPI. ``AMBIENTAL_BIOMA_PATH`` aponta o arquivo de biomas; sem ele → None."""
    path = os.getenv("AMBIENTAL_BIOMA_PATH", "").strip()
    return FonteBiomaArquivo(path) if path else None
