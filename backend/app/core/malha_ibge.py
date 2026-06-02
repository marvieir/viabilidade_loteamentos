"""Carregador de produção da malha municipal IBGE (pipeline, não agente).

Lê um GeoJSON ``FeatureCollection`` de municípios de um caminho local e responde
point-in-polygon / interseção sobre ele. Stdlib (``json``) + ``shapely`` apenas — sem
dependência nova (mesmo princípio do downloader da Fase 2).

AQUISIÇÃO (a confirmar na operação): a malha municipal oficial é publicada pelo IBGE
(malha municipal, SIRGAS 2000). O download+conversão para GeoJSON é um passo de
pipeline offline; aqui só consumimos o arquivo cacheado apontado por
``MALHA_IBGE_PATH``. Sem o arquivo, ``from_env()`` devolve ``None`` → degradação honesta.

Propriedades aceitas por feição (tolerante a esquemas do IBGE e de exports):
- código IBGE: ``cod_ibge`` | ``CD_MUN`` | ``GEOCODIGO`` | ``geocodigo``
- nome:        ``municipio`` | ``NM_MUN`` | ``nome``
- UF:          ``uf`` | ``SIGLA_UF`` | ``UF``
"""

import json
import os
from typing import Optional

from shapely.geometry import shape
from shapely.strtree import STRtree

from app.core.jurisdicao import Municipio

_COD = ("cod_ibge", "CD_MUN", "GEOCODIGO", "geocodigo")
_NOME = ("municipio", "NM_MUN", "nome")
_UF = ("uf", "SIGLA_UF", "UF")


def _prop(props: dict, chaves) -> Optional[str]:
    for k in chaves:
        if props.get(k) not in (None, ""):
            return str(props[k])
    return None


class FonteMalhaArquivo:
    """Malha municipal a partir de um GeoJSON local. Índice espacial para consulta."""

    def __init__(self, geojson: dict):
        self._geoms: list = []
        self._muns: list[Municipio] = []
        for feat in geojson.get("features", []):
            props = feat.get("properties", {}) or {}
            cod = _prop(props, _COD)
            nome = _prop(props, _NOME)
            uf = _prop(props, _UF)
            geom = feat.get("geometry")
            if not (cod and nome and uf and geom):
                continue
            self._geoms.append(shape(geom))
            self._muns.append(Municipio(cod_ibge=cod, municipio=nome, uf=uf))
        self._tree = STRtree(self._geoms) if self._geoms else None

    def municipio_no_ponto(self, lon: float, lat: float) -> Optional[Municipio]:
        from shapely.geometry import Point

        if self._tree is None:
            return None
        p = Point(lon, lat)
        for idx in self._tree.query(p):
            if self._geoms[idx].contains(p):
                return self._muns[idx]
        return None

    def municipios_que_intersectam(self, poly) -> list[Municipio]:
        if self._tree is None:
            return []
        achados: list[Municipio] = []
        for idx in self._tree.query(poly):
            if self._geoms[idx].intersects(poly):
                achados.append(self._muns[idx])
        return achados

    def por_codigo(self, cod_ibge: str) -> Optional[Municipio]:
        for mun in self._muns:
            if mun.cod_ibge == cod_ibge:
                return mun
        return None


def from_env() -> Optional[FonteMalhaArquivo]:
    """Carrega a malha de ``MALHA_IBGE_PATH`` se definido e legível; senão ``None``."""
    caminho = os.getenv("MALHA_IBGE_PATH")
    if not caminho or not os.path.exists(caminho):
        return None
    try:
        with open(caminho, encoding="utf-8") as fh:
            return FonteMalhaArquivo(json.load(fh))
    except (OSError, ValueError):
        return None
