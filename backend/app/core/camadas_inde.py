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
    {
        "tipo": "PATRIMONIO_CULTURAL", "cod": "IPHAN", "overlay": "patrimonio_cultural",
        "sev": "ALERTA", "camada": "IPHAN — patrimônio cultural/arqueológico", "buffer": 100.0,
        "nome": ["identific", "nome", "nm_bem", "sitio"],
        "detalhe": "Bem cultural / sítio arqueológico (IPHAN) na área/entorno — exige avaliação e "
                   "eventual prospecção arqueológica com anuência do IPHAN (Lei 3.924/61; IN 01/2015).",
    },
    {
        "tipo": "AREA_CONTAMINADA", "cod": "CETESB-AC", "overlay": "area_contaminada",
        "sev": "ALERTA", "camada": "Estadual (ex.: CETESB) — áreas contaminadas", "buffer": 100.0,
        "nome": ["nome", "empreend", "atividade"],
        "detalhe": "Área contaminada/em reabilitação (cadastro estadual) na área/entorno — passivo "
                   "ambiental; exige investigação e gerenciamento (Res. CONAMA 420/2009).",
    },
    {
        "tipo": "APCB", "cod": "MMA-APCB", "overlay": "apcb", "sev": "INFORMATIVO",
        "camada": "MMA — Áreas Prioritárias p/ Conservação da Biodiversidade", "buffer": 0.0,
        "nome": ["nome", "importanc", "acao"],
        "detalhe": "Área Prioritária para Conservação da Biodiversidade (MMA) — diretriz de "
                   "conservação (não é vedação); pode influenciar licenciamento e compensação.",
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


def _ler_vetor_local_bbox(path: str, bbox: BBox) -> list[tuple]:
    """Lê SÓ a JANELA (bbox da gleba) de um arquivo vetorial local via pyogrio/GDAL e devolve
    [(geom, props)] SEMPRE em WGS84. ESCALA p/ arquivos de ESTADO/BRASIL: em GeoPackage/
    FlatGeobuf/shapefile o bbox usa o ÍNDICE ESPACIAL (rápido); GeoJSON cai em varredura.

    CRS-robusto: o bbox vem em WGS84, mas o pyogrio filtra a janela no CRS DO ARQUIVO. Se o
    arquivo NÃO está em WGS84 (ex.: SICAR/CAR em UTM ou SIRGAS), reprojetamos o bbox p/ o CRS do
    arquivo ANTES de ler (senão a janela não casa e a camada SOME) e a geometria DE VOLTA p/
    WGS84 (a análise assume WGS84). Sem pyogrio → degrada (erro → camada indisponível)."""
    from pyogrio import read_info
    from pyogrio.raw import read as _ogr_read
    from shapely import wkb as _wkb

    # CRS do arquivo → decide se precisa reprojetar bbox (entrada) e geometria (saída).
    crs_arquivo = None
    try:
        crs_arquivo = read_info(path).get("crs")
    except Exception:  # noqa: BLE001 — sem info de CRS, assume WGS84 (comportamento antigo)
        crs_arquivo = None

    bbox_consulta = tuple(bbox)
    para_wgs = None
    if crs_arquivo and not _e_wgs84(crs_arquivo):
        from pyproj import Transformer
        from shapely.ops import transform as _shp_transform

        ida = Transformer.from_crs("EPSG:4326", crs_arquivo, always_xy=True)
        bbox_consulta = _reproj_bbox(bbox, ida)
        volta = Transformer.from_crs(crs_arquivo, "EPSG:4326", always_xy=True)
        para_wgs = lambda g: _shp_transform(  # noqa: E731
            lambda x, y, z=None: volta.transform(x, y), g
        )

    meta, _fids, geometry, field_data = _ogr_read(path, bbox=bbox_consulta)
    if geometry is None or len(geometry) == 0:
        return []
    fields = list(meta.get("fields") or [])
    out: list[tuple] = []
    for i in range(len(geometry)):
        raw = geometry[i]
        if raw is None:
            continue
        try:
            g = _wkb.loads(bytes(raw))
        except Exception:  # noqa: BLE001 — geometria degenerada, ignora
            continue
        if g.is_empty:
            continue
        if para_wgs is not None:
            g = para_wgs(g)
        props = {fields[j]: field_data[j][i] for j in range(len(fields))}
        out.append((g, props))
    return out


def _e_wgs84(crs) -> bool:
    """True se o CRS é WGS84 (EPSG:4326). Aceita string/objeto pyproj."""
    try:
        from pyproj import CRS

        return CRS.from_user_input(crs).to_epsg() == 4326
    except Exception:  # noqa: BLE001 — CRS exótico/ilegível → trata como não-4326 (reprojeta)
        return False


def _reproj_bbox(bbox: BBox, transformer) -> tuple:
    """Reprojeta o bbox (minx,miny,maxx,maxy) densificando as bordas — a curvatura da projeção
    pode empurrar os extremos pra fora dos 4 cantos, então amostramos uma grade e pegamos o
    envelope (cobertura segura da janela)."""
    minx, miny, maxx, maxy = bbox
    xs: list[float] = []
    ys: list[float] = []
    n = 8
    for i in range(n + 1):
        for j in range(n + 1):
            x = minx + (maxx - minx) * i / n
            y = miny + (maxy - miny) * j / n
            tx, ty = transformer.transform(x, y)
            if tx in (float("inf"), float("-inf")) or ty in (float("inf"), float("-inf")):
                continue
            xs.append(tx)
            ys.append(ty)
    if not xs:
        return tuple(bbox)
    return (min(xs), min(ys), max(xs), max(ys))


def _detalhe_erro(exc: Exception) -> str:
    """Mensagem curta e auditável do porquê a camada falhou (HTTP, parse, timeout…), com o
    arquivo:linha do último frame — pra diagnosticar sem precisar do traceback completo."""
    import traceback

    loc = ""
    tb = traceback.extract_tb(exc.__traceback__)
    if tb:
        f = tb[-1]
        loc = f" @ {f.filename.rsplit('/', 1)[-1]}:{f.lineno}"
    return f"{type(exc).__name__}: {exc}{loc}"[:230]


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
    """Primeiro valor não-vazio dentre as chaves (case-insensitive). Array-safe: nunca faz
    teste booleano direto no valor (campo lista/array do GDAL estourava 'truth value ambiguous')."""
    for k in chaves:
        for kk in (k, k.upper(), k.lower()):
            v = props.get(kk)
            if v is None:
                continue
            s = str(v).strip()
            if s and s.lower() not in ("nan", "none"):
                return s
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
                    feats = _ler_vetor_local_bbox(PATH_CAR_RL, bbox)
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
                    feats = _ler_vetor_local_bbox(path, bbox)
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
