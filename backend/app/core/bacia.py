"""Bacia hidrográfica (ANA) sobre a gleba — Tier 2 (paridade Urbia "Hidrografia").

Fonte injetável: lê o arquivo de bacias (ANA/SNIRH) na JANELA da gleba (reusa a leitura
CRS-robusta de ``camadas_inde``), pega o polígono que mais cobre a gleba e extrai os níveis
nomeados (região hidrográfica, bacia, sub-bacia) — com nomes de campo FLEXÍVEIS, já que variam
por arquivo. Determinístico, offline. Sem arquivo → ``None`` (degrada honesto)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional, Protocol, runtime_checkable

from pyproj import Transformer
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform as shp_transform

FONTE_ANA = "ANA/SNIRH — bacias hidrográficas"

# Nomes de campo comuns por nível (case-insensitive via _first). Ajustável por env se preciso.
_CAMPOS_REGIAO = ("rhi_nm", "nm_rh", "regiao_hidrografica", "nm_regiao", "rh", "regiao", "nome_rh")
_CAMPOS_BACIA = ("nm_bacia", "bacia", "nome_bacia", "nm_bacia_h", "nmbacia", "nome")
_CAMPOS_SUBBACIA = ("nm_sub_bac", "sub_bacia", "subbacia", "nm_subbaci", "nmsubbacia", "nome_sub")


@dataclass
class ResultadoBacia:
    consultado: bool
    regiao_hidrografica: Optional[str]
    bacia: Optional[str]
    sub_bacia: Optional[str]
    fonte: Optional[str]
    avisos: list[str] = field(default_factory=list)


@runtime_checkable
class FonteBacia(Protocol):
    def identificar(self, gleba: BaseGeometry) -> ResultadoBacia: ...


def _env_campos(env: str, default: tuple) -> tuple:
    bruto = os.getenv(env, "").strip()
    return tuple(c.strip() for c in bruto.split(",") if c.strip()) if bruto else default


class FonteBaciaArquivo:
    """Lê a bacia de um arquivo vetorial local (shapefile/gpkg/geojson da ANA)."""

    def __init__(self, path: str):
        self.path = path

    def identificar(self, gleba: BaseGeometry) -> ResultadoBacia:
        from app.core.camadas_inde import _first, _ler_vetor_local_bbox

        try:
            feats = _ler_vetor_local_bbox(self.path, gleba.bounds)
        except Exception as exc:  # noqa: BLE001 — degrada honesto
            return ResultadoBacia(
                False, None, None, None, FONTE_ANA,
                avisos=[f"Bacia indisponível — {type(exc).__name__}: {exc}"[:180]],
            )
        if not feats:
            return ResultadoBacia(
                True, None, None, None, FONTE_ANA,
                avisos=["Nenhuma bacia mapeada na janela da gleba."],
            )

        c = gleba.centroid
        proj4 = (
            f"+proj=aeqd +lat_0={c.y} +lon_0={c.x} +x_0=0 +y_0=0 "
            "+datum=WGS84 +units=m +no_defs"
        )
        to_m = Transformer.from_crs("EPSG:4326", proj4, always_xy=True).transform
        gleba_m = shp_transform(to_m, gleba)

        # Polígono que mais cobre a gleba (maior interseção).
        melhor_props, melhor_area = None, 0.0
        for geom, props in feats:
            try:
                inter = shp_transform(to_m, geom).intersection(gleba_m)
            except Exception:  # noqa: BLE001
                continue
            if not inter.is_empty and inter.area > melhor_area:
                melhor_area, melhor_props = inter.area, props
        if melhor_props is None:
            return ResultadoBacia(
                True, None, None, None, FONTE_ANA,
                avisos=["Nenhuma bacia intersecta a gleba."],
            )

        regiao = _first(melhor_props, *_env_campos("AMBIENTAL_BACIA_CAMPO_REGIAO", _CAMPOS_REGIAO))
        bacia = _first(melhor_props, *_env_campos("AMBIENTAL_BACIA_CAMPO_BACIA", _CAMPOS_BACIA))
        sub = _first(melhor_props, *_env_campos("AMBIENTAL_BACIA_CAMPO_SUBBACIA", _CAMPOS_SUBBACIA))
        avisos = []
        if not any((regiao, bacia, sub)):
            avisos.append(
                "Bacia encontrada, mas sem campo de nome reconhecido — configure "
                "AMBIENTAL_BACIA_CAMPO_* com o nome do campo do arquivo."
            )
        return ResultadoBacia(True, regiao, bacia, sub, FONTE_ANA, avisos=avisos)


def get_fonte_bacia() -> Optional[FonteBacia]:
    """Dependência FastAPI. ``AMBIENTAL_BACIA_PATH`` aponta o arquivo; sem ele → None."""
    path = os.getenv("AMBIENTAL_BACIA_PATH", "").strip()
    return FonteBaciaArquivo(path) if path else None
