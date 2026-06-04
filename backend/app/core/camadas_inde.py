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

  STATUS DOS ENDPOINTS (2026-06-04):
  - ✅ SIGMINE (mineração) e ✅ ANEEL (linhas de transmissão) → confirmados HTTP 200.
  - Hidrografia e UC: o catálogo da ANA não expõe WFS usável (só metadados/download), mas o
    servidor ArcGIS da ANA (`/arcgis/rest/services/DADOSABERTOS`) serve ambos como REST —
    `Curso_dÁgua` (cursos d'água) e `Unidade_de_Conservação` (UC). Agora são os defaults
    (ArcGIS, mesmo formato do SIGMINE). **Pendente confirmar ao vivo** o índice da camada
    (`/0`) e os nomes de atributos.

  Todos os endpoints são SOBRESCREVÍVEIS por env (AMB_URL_MINERACAO, AMB_URL_HIDROGRAFIA,
  AMB_URL_UC, AMB_URL_LT) → se um caminho mudar, basta exportar a URL certa, sem deploy.
  Os testes não dependem destes endpoints (smoke ao vivo gated por RUN_LIVE_SMOKE).
"""

from __future__ import annotations

import gzip
import json
import os
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

# --- Endpoints oficiais — SOBRESCREVÍVEIS por ambiente (sem mexer em código) ---
# Confirmados ao vivo (HTTP 200): SIGMINE e ANEEL. ANA e ICMBio são endpoints que
# MIGRAM com frequência — quando a URL correta for confirmada no geoportal, basta exportar
# a env var (AMB_URL_HIDROGRAFIA / AMB_URL_UC / AMB_UC_TYPENAME) — zero deploy de código.
URL_MINERACAO = os.getenv(
    "AMB_URL_MINERACAO",
    "https://geo.anm.gov.br/arcgis/rest/services/SIGMINE/dados_anm/MapServer/0/query",
)
# Hidrografia (ANA) — rede de cursos d'água do servidor ArcGIS da ANA (DADOSABERTOS).
# Nome do serviço acentuado → caminho percent-encoded (Curso_dÁgua → Curso_d%C3%81gua).
URL_HIDROGRAFIA = os.getenv(
    "AMB_URL_HIDROGRAFIA",
    "https://www.snirh.gov.br/arcgis/rest/services/DADOSABERTOS/Curso_d%C3%81gua/MapServer/0/query",
)
# Unidades de conservação — também servido pela ANA (ArcGIS), o que dispensa o ICMBio WFS.
# Unidade_de_Conservação → Unidade_de_Conserva%C3%A7%C3%A3o.
URL_UC = os.getenv(
    "AMB_URL_UC",
    "https://www.snirh.gov.br/arcgis/rest/services/DADOSABERTOS/Unidade_de_Conserva%C3%A7%C3%A3o/MapServer/0/query",
)
# Linhas de transmissão (ANEEL/SIGEL) — ArcGIS REST (confirmado HTTP 200).
URL_LT = os.getenv(
    "AMB_URL_LT",
    "https://sigel.aneel.gov.br/arcgis/rest/services/PORTAL/WFS/MapServer/0/query",
)

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

        # Unidades de conservação (ArcGIS — servido pela ANA; dispensa o ICMBio WFS)
        try:
            fc = _get_json(URL_UC, _arcgis_envelope(bbox))
            for ft in _features(fc):
                geom = shape(ft["geometry"])
                props = ft.get("properties", {}) or {}
                c.unidades_conservacao.append(
                    FeicaoUC(
                        geometria=geom,
                        nome=_first(props, "nome_uc", "nome", "nm_uc", "nome_da_uc")
                        or "UC não identificada",
                        grupo=_first(props, "grupo", "categoria", "tipo", "esfera"),
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
