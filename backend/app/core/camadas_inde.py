"""Fonte de camadas em PRODUÇÃO — pipeline de download (NÃO agente) + cache local.

Cada camada vem de um endpoint OFICIAL que devolve GeoJSON (ArcGIS REST ``f=geojson`` ou
WFS ``outputFormat=application/json``), recortado pelo bounding box da gleba. O parse é
``json`` + ``shapely.geometry.shape`` — **zero dependência nova** (stdlib ``urllib``).
Falha de rede/parse em UMA camada degrada só aquela (aviso "não consultada"), nunca inventa.

Esta fonte NÃO é o default (ver `camadas.get_fonte_camadas`): ligá-la é injetá-la via
``app.dependency_overrides[get_fonte_camadas] = lambda: FonteCamadasINDE()``. Decisão
idêntica à do resolvedor de jurisdição (Fase 1): mantém determinismo e testes offline.

PROVENIÊNCIA DOS ENDPOINTS (estado em 2026-06-01):
- Mineração (ANM/SIGMINE): ArcGIS REST `dados_anm/MapServer` — endpoint da spec/Fase 2.
  Alternativa documentada: shapefile `app.anm.gov.br/dadosabertos/SIGMINE/.../{UF}.zip`.
- Hidrografia (ANA — Base Hidrográfica Ottocodificada): WFS oficial via INDE/ANA.
- Unidades de conservação (ICMBio/CNUC): WFS oficial via INDE/ICMBio.

  ⚠️ Os endpoints de ANA e ICMBio abaixo são os OFICIAIS conhecidos por documentação,
  mas NÃO foram validados ao vivo neste ambiente (a política de rede bloqueia o egress —
  HTTP 403). Confirmar/ajustar `URL`, `typeName`/layer e nomes de atributos contra o
  serviço real ao habilitar a aquisição. Os testes da fase não dependem deles.
"""

from __future__ import annotations

import gzip
import json
import urllib.parse
import urllib.request
from datetime import date
from typing import Optional

from shapely.geometry import shape

from app.core.camadas import (
    BBox,
    Camadas,
    FeicaoHidrografia,
    FeicaoLinhaTransmissao,
    FeicaoMineracao,
    FeicaoUC,
)

# --- Endpoints oficiais (ver proveniência no docstring do módulo) ---
URL_MINERACAO = (
    "https://geo.anm.gov.br/arcgis/rest/services/SIGMINE/dados_anm/MapServer/0/query"
)
# DECLARADOS — validar em rede ao habilitar:
URL_HIDROGRAFIA = "https://www.snirh.gov.br/arcgis/rest/services/HIDRO/Hidrografia/MapServer/0/query"
URL_UC = "https://geoservicos.inde.gov.br/geoserver/ICMBio/ows"
UC_TYPENAME = "ICMBio:lim_unidade_conservacao_a"
# Linhas de transmissão (ANEEL/SIGEL) — ArcGIS REST. DECLARADO: confirmar o índice da
# camada "Linhas de Transmissão - Base Existente" e o campo de tensão no serviço real.
URL_LT = "https://sigel.aneel.gov.br/arcgis/rest/services/PORTAL/WFS/MapServer/0/query"

# Códigos curtos de camada (para camadas_consultadas / camadas_indisponiveis — Fase 2.1).
COD_MINERACAO, COD_HIDRO, COD_UC, COD_LT = "SIGMINE", "ANA", "ICMBio", "ANEEL"

_TIMEOUT = 30


def _get_json(url: str, params: dict) -> dict:
    query = urllib.parse.urlencode(params)
    req = urllib.request.Request(
        f"{url}?{query}",
        headers={
            "User-Agent": "viabilidade-loteamentos/0.2",
            "Accept": "application/json",
            "Accept-Encoding": "gzip, identity",
        },
    )
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:  # noqa: S310 (URL fixa de config)
        raw = resp.read()
    # Alguns serviços oficiais devolvem gzip (assinatura 1f 8b) — descomprime antes de
    # decodificar (mesmo bug que travava o IBGE; ler cru como UTF-8 quebrava).
    if resp.headers.get("Content-Encoding") == "gzip" or raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    return json.loads(raw.decode("utf-8"))


def _detalhe_erro(exc: Exception) -> str:
    """Mensagem curta e auditável do porquê a camada falhou (HTTP, parse, timeout…)."""
    return f"{type(exc).__name__}: {exc}"[:180]


def _features(fc: dict) -> list[dict]:
    return fc.get("features", []) if isinstance(fc, dict) else []


def _first(props: dict, *chaves: str) -> Optional[str]:
    for k in chaves:
        for kk in (k, k.upper(), k.lower()):
            if props.get(kk) not in (None, ""):
                return str(props[kk])
    return None


def _arcgis_envelope(bbox: BBox) -> dict:
    min_lon, min_lat, max_lon, max_lat = bbox
    return {
        "where": "1=1",
        "geometry": f"{min_lon},{min_lat},{max_lon},{max_lat}",
        "geometryType": "esriGeometryEnvelope",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "*",
        "outSR": "4326",
        "f": "geojson",
    }


def _wfs_bbox(typename: str, bbox: BBox) -> dict:
    min_lon, min_lat, max_lon, max_lat = bbox
    return {
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "typeNames": typename,
        "outputFormat": "application/json",
        "srsName": "EPSG:4326",
        # WFS 2.0 com EPSG:4326 espera ordem lat,lon no bbox.
        "bbox": f"{min_lat},{min_lon},{max_lat},{max_lon},EPSG:4326",
    }


class FonteCamadasINDE:
    """Pipeline real de aquisição. Cada camada degrada isoladamente em caso de falha."""

    def coletar(self, bbox: BBox, uf: Optional[str]) -> Camadas:
        hoje = date.today().isoformat()
        c = Camadas()

        # Mineração (ANM/SIGMINE)
        try:
            fc = _get_json(URL_MINERACAO, _arcgis_envelope(bbox))
            for ft in _features(fc):
                geom = shape(ft["geometry"])
                props = ft.get("properties", {}) or {}
                c.mineracao.append(
                    FeicaoMineracao(
                        geometria=geom,
                        processo=_first(props, "PROCESSO", "NUMERO", "numero_pro")
                        or "processo não identificado",
                        fase=_first(props, "FASE", "fase"),
                    )
                )
            c.data_mineracao = hoje
            c.consultadas.append(COD_MINERACAO)
        except Exception as exc:  # noqa: BLE001 — degradar a camada, não derrubar o endpoint
            c.indisponiveis.append(COD_MINERACAO)
            c.avisos.append(f"Camada de mineração (SIGMINE/ANM) indisponível — {_detalhe_erro(exc)}")

        # Hidrografia (ANA)
        try:
            fc = _get_json(URL_HIDROGRAFIA, _arcgis_envelope(bbox))
            for ft in _features(fc):
                geom = shape(ft["geometry"])
                props = ft.get("properties", {}) or {}
                largura = _first(props, "LARGURA", "largura", "width")
                c.hidrografia.append(
                    FeicaoHidrografia(
                        geometria=geom,
                        largura_m=float(largura) if largura else None,
                        nome=_first(props, "NOME", "nome", "noriocomp"),
                    )
                )
            c.data_hidrografia = hoje
            c.consultadas.append(COD_HIDRO)
        except Exception as exc:  # noqa: BLE001
            c.indisponiveis.append(COD_HIDRO)
            c.avisos.append(f"Camada de hidrografia (ANA) indisponível — {_detalhe_erro(exc)}")

        # Unidades de conservação (ICMBio/CNUC)
        try:
            fc = _get_json(URL_UC, _wfs_bbox(UC_TYPENAME, bbox))
            for ft in _features(fc):
                geom = shape(ft["geometry"])
                props = ft.get("properties", {}) or {}
                c.unidades_conservacao.append(
                    FeicaoUC(
                        geometria=geom,
                        nome=_first(props, "nome_uc", "NOME_UC", "nome")
                        or "UC não identificada",
                        grupo=_first(props, "grupo", "categoria"),
                    )
                )
            c.data_uc = hoje
            c.consultadas.append(COD_UC)
        except Exception as exc:  # noqa: BLE001
            c.indisponiveis.append(COD_UC)
            c.avisos.append(f"Camada de unidades de conservação (ICMBio) indisponível — {_detalhe_erro(exc)}")

        # Linhas de transmissão (ANEEL/SIGEL) → faixa de servidão
        try:
            fc = _get_json(URL_LT, _arcgis_envelope(bbox))
            for ft in _features(fc):
                geom = shape(ft["geometry"])
                props = ft.get("properties", {}) or {}
                tensao = _first(props, "TENSAO", "tensao", "tensao_kv", "kv")
                c.linhas_transmissao.append(
                    FeicaoLinhaTransmissao(
                        geometria=geom,
                        tensao_kv=float(tensao) if tensao else None,
                        nome=_first(props, "NOME", "nome", "denominacao"),
                    )
                )
            c.data_lt = hoje
            c.consultadas.append(COD_LT)
        except Exception as exc:  # noqa: BLE001
            c.indisponiveis.append(COD_LT)
            c.avisos.append(f"Camada de linhas de transmissão (ANEEL) indisponível — {_detalhe_erro(exc)}")

        return c
