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
import threading
from typing import Optional

from shapely.geometry import shape
from shapely.strtree import STRtree

from app.core.jurisdicao import Municipio, normalizar_nome

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

    def intersecoes(self, poly) -> list[tuple[Municipio, object]]:
        if self._tree is None:
            return []
        achados: list[tuple[Municipio, object]] = []
        for idx in self._tree.query(poly):
            geom = self._geoms[idx]
            if geom.intersects(poly):
                achados.append((self._muns[idx], geom.intersection(poly)))
        return achados

    def por_codigo(self, cod_ibge: str) -> Optional[Municipio]:
        for mun in self._muns:
            if mun.cod_ibge == cod_ibge:
                return mun
        return None

    def buscar_por_nome(self, termo: str, limite: int = 10) -> list[Municipio]:
        alvo = normalizar_nome(termo)
        if not alvo:
            return []
        # prefixo primeiro, depois substring — ambos sobre o nome normalizado.
        prefixo = [m for m in self._muns if normalizar_nome(m.municipio).startswith(alvo)]
        contem = [
            m
            for m in self._muns
            if alvo in normalizar_nome(m.municipio) and m not in prefixo
        ]
        ordenados = sorted(prefixo, key=lambda m: (m.municipio, m.uf)) + sorted(
            contem, key=lambda m: (m.municipio, m.uf)
        )
        return ordenados[:limite]


def _uf_de_localidade(loc: dict) -> Optional[str]:
    """Extrai a sigla da UF de um item do IBGE /localidades/municipios (esquema aninhado)."""
    try:
        return loc["microrregiao"]["mesorregiao"]["UF"]["sigla"]
    except (KeyError, TypeError):
        pass
    # esquemas alternativos (regiao-imediata) e campos planos
    for caminho in (
        ("regiao-imediata", "regiao-intermediaria", "UF", "sigla"),
    ):
        node = loc
        ok = True
        for chave in caminho:
            if isinstance(node, dict) and chave in node:
                node = node[chave]
            else:
                ok = False
                break
        if ok and isinstance(node, str):
            return node
    return loc.get("UF") or loc.get("uf") or loc.get("sigla_uf")


def montar_geojson(localidades: list[dict], features: list[dict]) -> dict:
    """Junta a lista de municípios (id→nome,UF) à malha (features por ``codarea``).

    Função PURA (sem rede), para o pipeline de download e para teste offline. Produz
    o ``FeatureCollection`` no formato que ``FonteMalhaArquivo`` consome
    (``properties = {cod_ibge, municipio, uf}``).
    """
    por_cod = {
        str(loc["id"]): (loc.get("nome"), _uf_de_localidade(loc))
        for loc in localidades
        if loc.get("id") is not None
    }
    saida = []
    for feat in features:
        props = feat.get("properties", {}) or {}
        cod = props.get("codarea") or props.get("cod_ibge") or props.get("CD_MUN")
        if cod is None or feat.get("geometry") is None:
            continue
        cod = str(cod)
        nome, uf = por_cod.get(cod, (props.get("NM_MUN"), props.get("SIGLA_UF")))
        if not (nome and uf):
            continue
        saida.append(
            {
                "type": "Feature",
                "properties": {"cod_ibge": cod, "municipio": nome, "uf": uf},
                "geometry": feat["geometry"],
            }
        )
    return {"type": "FeatureCollection", "features": saida}


def montar_lista(localidades: list[dict]) -> list[dict]:
    """Extrai a **lista leve** (``cod_ibge + nome + UF``) das localidades do IBGE.

    Função PURA, sem geometria — é o dataset embarcado no repo que alimenta a busca/
    correção por nome (``lista_municipios.py``), desacoplado da malha pesada (decisão #2).
    """
    saida = []
    for loc in localidades:
        cod = loc.get("id")
        nome = loc.get("nome")
        uf = _uf_de_localidade(loc)
        if cod is None or not (nome and uf):
            continue
        saida.append({"cod_ibge": str(cod), "municipio": nome, "uf": uf})
    saida.sort(key=lambda r: (r["municipio"], r["uf"]))
    return saida


# MEM-1 (incidente 20-21/07): ``from_env`` era chamado POR REQUISIÇÃO (Depends) e re-parseava
# o GeoJSON do país inteiro a cada chamada — picos de RAM concorrentes + fragmentação levaram o
# processo a 3,1 GB e a instância ao swap. A malha agora é SINGLETON por processo: carrega uma
# vez e recarrega só se o arquivo mudar (caminho/mtime/tamanho).
_cache_fonte: Optional[FonteMalhaArquivo] = None
_cache_chave: Optional[tuple] = None
_cache_lock = threading.Lock()


def from_env() -> Optional[FonteMalhaArquivo]:
    """Malha de ``MALHA_IBGE_PATH`` — carregada UMA vez por processo (recarrega se o
    arquivo mudar). Sem env/arquivo → ``None`` (degradação honesta, como antes)."""
    global _cache_fonte, _cache_chave
    caminho = os.getenv("MALHA_IBGE_PATH")
    if not caminho or not os.path.exists(caminho):
        return None
    try:
        st = os.stat(caminho)
    except OSError:
        return None
    chave = (os.path.abspath(caminho), st.st_mtime_ns, st.st_size)
    with _cache_lock:
        if _cache_fonte is not None and _cache_chave == chave:
            return _cache_fonte
        try:
            with open(caminho, encoding="utf-8") as fh:
                fonte = FonteMalhaArquivo(json.load(fh))
        except (OSError, ValueError):
            return None
        _cache_fonte, _cache_chave = fonte, chave
        return fonte
