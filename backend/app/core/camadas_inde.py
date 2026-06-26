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

import concurrent.futures
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
    FeicaoMassaDagua,
    FeicaoMineracao,
    FeicaoReservaLegal,
    FeicaoRestricao,
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
# Massas d'água (lagos/lagoas/reservatórios) — ANA. Curso d'água (linha) NÃO cobre represas;
# por isso consultamos as duas camadas de polígono (a "Grande" pega grandes reservatórios).
_BASE_ANA = "https://www.snirh.gov.br/arcgis/rest/services/DADOSABERTOS"
URL_MASSA_DAGUA = os.getenv("AMB_URL_MASSA_DAGUA", f"{_BASE_ANA}/Massa_d%C3%A1gua/MapServer/0/query")
URL_MASSA_DAGUA_GRANDE = os.getenv(
    "AMB_URL_MASSA_DAGUA_GRANDE", f"{_BASE_ANA}/Massa_d%C3%81gua_Grande/MapServer/0/query"
)

# Reserva Legal (SICAR/CAR) — GeoServer WFS público (geoserver.car.gov.br). PENDENTE de
# confirmação ao vivo: o egress do sandbox de desenvolvimento bloqueia o host (403), e o CAR
# distribui dados majoritariamente por recorte estadual — o typeName/axis-order do WFS varia.
# Por isso NÃO há default chumbado (evita endpoint errado): o operador confirma no deploy e
# exporta a URL COMPLETA de GetFeature em ``AMBIENTAL_URL_CAR_RL`` (placeholders disponíveis:
# ``{bbox}`` = minx,miny,maxx,maxy e ``{bbox_inv}`` = miny,minx,maxy,minx p/ WFS lat,lon). A
# resposta esperada é GeoJSON (FeatureCollection). Vazio → camada simplesmente não consultada.
URL_CAR_RL = os.getenv("AMBIENTAL_URL_CAR_RL", "").strip()
# O geoserver legado do CAR está fora do ar (timeout até de egress aberto). Caminho REALISTA:
# o operador baixa o recorte do município (consultapublica.car.gov.br) e converte p/ GeoJSON
# (``ogr2ogr -f GeoJSON rl.geojson RESERVA_LEGAL.shp``), apontando ``AMBIENTAL_CAR_RL_PATH``.
PATH_CAR_RL = os.getenv("AMBIENTAL_CAR_RL_PATH", "").strip()

# Códigos curtos de camada (para camadas_consultadas / camadas_indisponiveis — Fase 2.1).
COD_MINERACAO, COD_HIDRO, COD_UC, COD_LT = "SIGMINE", "ANA", "ICMBio", "ANEEL"
COD_MASSA = "Massa d'água"
COD_CAR_RL = "SICAR-RL"

# Restrições territoriais genéricas (interseção → alerta). Mesmo modelo dual-intake do CAR: cada
# uma lê de uma URL (WFS/ArcGIS GeoJSON, com placeholders {bbox}/{bbox_inv}) OU de um GeoJSON local
# — o operador configura no deploy a que estiver viva (muitos geoservices gov caem ou bloqueiam).
# Sem URL nem arquivo → camada não consultada (degrada honesto). Vars por ``cod`` (ex.: MATA-ATL →
# AMBIENTAL_URL_MATA_ATL / AMBIENTAL_MATA_ATL_PATH). Endpoints PENDENTES de confirmação ao vivo.
_RESTRICOES: list[dict] = [
    {
        "tipo": "MATA_ATLANTICA", "cod": "MATA-ATL", "overlay": "mata_atlantica", "sev": "ALERTA",
        "camada": "IBGE — domínio Mata Atlântica (Lei 11.428)", "buffer": 0.0,
        "nome": ["bioma", "nome", "fitofisionomia"],
        "detalhe": "Gleba no domínio da Mata Atlântica (Lei 11.428/2006) — supressão de vegetação "
                   "nativa exige compensação e anuência específica (órgão estadual/IBAMA).",
    },
    {
        "tipo": "TERRA_INDIGENA", "cod": "FUNAI-TI", "overlay": "terra_indigena", "sev": "ALERTA",
        "camada": "FUNAI — Terras Indígenas", "buffer": 0.0,
        "nome": ["terrai_nom", "nome_ti", "nome"],
        "detalhe": "Terra Indígena (FUNAI) na área/entorno — restrição fundiária forte; consultar "
                   "a FUNAI e o órgão licenciador.",
    },
    {
        "tipo": "TERRITORIO_QUILOMBOLA", "cod": "QUILOMBO", "overlay": "territorio_quilombola",
        "sev": "ALERTA", "camada": "INCRA/Fundação Palmares — Territórios Quilombolas", "buffer": 0.0,
        "nome": ["nome", "nm_comunid", "comunidade"],
        "detalhe": "Território Quilombola (INCRA/Fundação Palmares) na área/entorno — restrição "
                   "fundiária; consultar o órgão competente.",
    },
    {
        "tipo": "ASSENTAMENTO", "cod": "INCRA-PA", "overlay": "assentamento", "sev": "ALERTA",
        "camada": "INCRA — Assentamentos rurais", "buffer": 0.0,
        "nome": ["nome_proje", "nome", "projeto"],
        "detalhe": "Assentamento rural (INCRA) na área — incompatível com loteamento urbano sem "
                   "desafetação; consultar o INCRA.",
    },
    {
        "tipo": "CAVERNA", "cod": "CECAV-CAV", "overlay": "caverna", "sev": "ALERTA",
        "camada": "CECAV/ICMBio — cavidades naturais", "buffer": 250.0,
        "nome": ["nome", "nom_cav", "id"],
        "detalhe": "Cavidade natural (CECAV) com raio de influência (250 m, triagem) incidindo na "
                   "gleba — exige estudo espeleológico (Decreto 6.640/2008).",
    },
    {
        "tipo": "AREA_PROTECAO_MANANCIAL", "cod": "APM", "overlay": "area_protecao_manancial",
        "sev": "ALERTA", "camada": "Estadual — Área de Proteção de Mananciais", "buffer": 0.0,
        "nome": ["nome", "apm", "bacia"],
        "detalhe": "Área de Proteção de Mananciais (lei estadual) — restringe densidade e "
                   "impermeabilização; verificar a lei específica da bacia.",
    },
    {
        "tipo": "DUTOVIA", "cod": "ANP-DUTO", "overlay": "dutovia", "sev": "ALERTA",
        "camada": "ANP/EPE — dutovias (gás/petróleo)", "buffer": 20.0,
        "nome": ["nome", "duto", "tipo"],
        "detalhe": "Dutovia (gás/petróleo) com faixa non aedificandi (≈20 m/lado, triagem) na "
                   "gleba — afastamento de segurança; consultar a transportadora/ANP.",
    },
]

# Timeout de leitura por camada (s) — CONFIGURÁVEL por ambiente. Antes 30 fixo: como as 6
# camadas eram consultadas EM SÉRIE, uma rede ruim somava 6×30 = 180 s (3 min) só de espera.
# Agora as consultas rodam EM PARALELO (ver ``_prefetch_paralelo``) → a espera total ≈ UM
# timeout, não a soma. 15 s é folgado p/ um ArcGIS responsivo e degrada rápido quando cai.
_TIMEOUT = max(int(os.getenv("AMB_HTTP_TIMEOUT", "15")), 1)
_MAX_WORKERS = 6


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
    data = json.loads(raw.decode("utf-8"))
    # ArcGIS devolve erro como HTTP 200 com corpo {"error": {...}} — NÃO é "0 feições",
    # é falha. Levantar para a camada cair honestamente em ``indisponiveis`` com o motivo,
    # em vez de mascarar como consultada-vazia.
    if isinstance(data, dict) and "error" in data:
        raise RuntimeError(f"erro do serviço ArcGIS: {data['error']}")
    return data


def _get_json_url(full_url: str) -> dict:
    """GET de uma URL JÁ MONTADA (com query própria) — p/ endpoints que não seguem o padrão
    ArcGIS ``?{params}`` (ex.: WFS do SICAR). Mesma decodificação gzip + checagem de erro."""
    req = urllib.request.Request(
        full_url,
        headers={
            "User-Agent": "viabilidade-loteamentos/0.2",
            "Accept": "application/json",
            "Accept-Encoding": "gzip, identity",
        },
    )
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:  # noqa: S310 (URL de config)
        raw = resp.read()
    if resp.headers.get("Content-Encoding") == "gzip" or raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    data = json.loads(raw.decode("utf-8"))
    if isinstance(data, dict) and "error" in data:
        raise RuntimeError(f"erro do serviço: {data['error']}")
    return data


def _geojson_local_no_bbox(path: str, bbox: BBox) -> list[tuple]:
    """Lê um GeoJSON local (FeatureCollection) e devolve [(geom, props)] das feições que tocam
    o bbox da gleba — recorte simples p/ não carregar um estado inteiro no alerta. Sem dep nova
    (stdlib json + shapely)."""
    from shapely.geometry import box as _box

    with open(path, encoding="utf-8") as fh:
        fc = json.load(fh)
    clip = _box(*bbox)
    out: list[tuple] = []
    for ft in _features(fc):
        geom_raw = ft.get("geometry")
        if not geom_raw:
            continue
        try:
            g = shape(geom_raw)
        except Exception:  # noqa: BLE001 — feição degenerada, ignora
            continue
        if not g.is_empty and g.intersects(clip):
            out.append((g, ft.get("properties", {}) or {}))
    return out


def _detalhe_erro(exc: Exception) -> str:
    """Mensagem curta e auditável do porquê a camada falhou (HTTP, parse, timeout…)."""
    return f"{type(exc).__name__}: {exc}"[:180]


def _prefetch_paralelo(urls: list[str], params: dict) -> dict:
    """Busca todas as camadas EM PARALELO (rede é I/O-bound). Devolve ``{url: dict | Exception}``
    — a exceção é GUARDADA (não levantada) para a camada degradar exatamente como antes, com seu
    próprio aviso/`indisponiveis`. A montagem em ``coletar`` segue em ordem FIXA → determinismo
    preservado (§4): o paralelismo afeta só QUANDO a rede responde, nunca a ordem do resultado."""
    uniq = list(dict.fromkeys(urls))
    out: dict = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(uniq), _MAX_WORKERS)) as ex:
        futuros = {ex.submit(_get_json, u, params): u for u in uniq}
        for fut in concurrent.futures.as_completed(futuros):
            u = futuros[fut]
            try:
                out[u] = fut.result()
            except Exception as exc:  # noqa: BLE001 — guardado p/ a camada cair honesta
                out[u] = exc
    return out


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

        # Todas as 6 consultas EM PARALELO (mesmo envelope) — corta a espera de 6×timeout em
        # série (3 min numa rede ruim) para ≈ 1×timeout. A leitura abaixo segue em ordem fixa.
        env = _arcgis_envelope(bbox)
        cache = _prefetch_paralelo(
            [URL_MINERACAO, URL_HIDROGRAFIA, URL_UC, URL_LT, URL_MASSA_DAGUA, URL_MASSA_DAGUA_GRANDE],
            env,
        )

        def _get(url: str) -> dict:
            """Resultado pré-buscado da camada (re-levanta a exceção guardada → degrada igual)."""
            r = cache.get(url)
            if isinstance(r, BaseException):
                raise r
            return r if r is not None else _get_json(url, env)

        # Mineração (ANM/SIGMINE)
        try:
            fc = _get(URL_MINERACAO)
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
            fc = _get(URL_HIDROGRAFIA)
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
            fc = _get(URL_UC)
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
            fc = _get(URL_LT)
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

        # Massas d'água (lagos/lagoas/reservatórios) — duas camadas; consultada se UMA responder
        md_ok, md_err = False, []
        for url in (URL_MASSA_DAGUA, URL_MASSA_DAGUA_GRANDE):
            try:
                fc = _get(url)
                for ft in _features(fc):
                    geom = shape(ft["geometry"])
                    props = ft.get("properties", {}) or {}
                    c.massas_dagua.append(
                        FeicaoMassaDagua(
                            geometria=geom,
                            nome=_first(props, "nome", "NOME", "nome_corpo", "norep"),
                            tipo=_first(props, "tipo", "TIPO", "classe"),
                        )
                    )
                md_ok = True
            except Exception as exc:  # noqa: BLE001
                md_err.append(_detalhe_erro(exc))
        if md_ok:
            c.data_massa_dagua = hoje
            c.consultadas.append(COD_MASSA)
        else:
            c.indisponiveis.append(COD_MASSA)
            c.avisos.append("Camada de massas d'água (ANA) indisponível — " + "; ".join(md_err))

        # Reserva Legal (SICAR/CAR): preferimos o ARQUIVO LOCAL (o WFS do CAR está fora do ar);
        # se houver só a URL, tenta WFS. Sem nenhum → camada não consultada (degrada honesto).
        if PATH_CAR_RL or URL_CAR_RL:
            try:
                if PATH_CAR_RL:
                    feats = _geojson_local_no_bbox(PATH_CAR_RL, bbox)
                else:
                    minx, miny, maxx, maxy = bbox
                    u = URL_CAR_RL.replace(
                        "{bbox}", f"{minx},{miny},{maxx},{maxy}"
                    ).replace("{bbox_inv}", f"{miny},{minx},{maxy},{maxx}")
                    feats = [
                        (shape(ft["geometry"]), ft.get("properties", {}) or {})
                        for ft in _features(_get_json_url(u))
                    ]
                for geom, props in feats:
                    c.reserva_legal.append(
                        FeicaoReservaLegal(
                            geometria=geom,
                            cod_imovel=_first(props, "cod_imovel", "COD_IMOVEL", "cod_imove"),
                        )
                    )
                c.data_reserva_legal = hoje
                c.consultadas.append(COD_CAR_RL)
            except Exception as exc:  # noqa: BLE001 — degradar a camada, não derrubar
                c.indisponiveis.append(COD_CAR_RL)
                c.avisos.append(
                    f"Camada de Reserva Legal (SICAR/CAR) indisponível — {_detalhe_erro(exc)}"
                )

        # Restrições territoriais genéricas (Mata Atlântica, TI, quilombola, assentamento, caverna,
        # APM, dutovia) — cada uma só roda se o operador configurou URL ou arquivo local (dual-intake).
        minx, miny, maxx, maxy = bbox
        for cfg in _RESTRICOES:
            env_key = cfg["cod"].replace("-", "_")
            url = os.getenv(f"AMBIENTAL_URL_{env_key}", "").strip()
            path = os.getenv(f"AMBIENTAL_{env_key}_PATH", "").strip()
            if not (url or path):
                continue
            try:
                if path:
                    feats = _geojson_local_no_bbox(path, bbox)
                else:
                    u = url.replace("{bbox}", f"{minx},{miny},{maxx},{maxy}").replace(
                        "{bbox_inv}", f"{miny},{minx},{maxy},{maxx}"
                    )
                    feats = [
                        (shape(ft["geometry"]), ft.get("properties", {}) or {})
                        for ft in _features(_get_json_url(u))
                    ]
                for geom, props in feats:
                    c.restricoes.append(
                        FeicaoRestricao(
                            geometria=geom,
                            tipo=cfg["tipo"],
                            overlay_key=cfg["overlay"],
                            camada=cfg["camada"],
                            nome=_first(props, *cfg["nome"]),
                            detalhe=cfg["detalhe"],
                            severidade=cfg["sev"],
                            buffer_m=cfg["buffer"],
                            data_referencia=hoje,
                        )
                    )
                c.consultadas.append(cfg["cod"])
            except Exception as exc:  # noqa: BLE001 — degradar a camada, não derrubar
                c.indisponiveis.append(cfg["cod"])
                c.avisos.append(f"Camada {cfg['camada']} indisponível — {_detalhe_erro(exc)}")

        return c
