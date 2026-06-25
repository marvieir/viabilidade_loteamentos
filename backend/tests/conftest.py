"""Fixtures determinísticas: KMZ sintéticos e clientes com/sem de-para municipal."""

import io
import os
import tempfile
import zipfile

# Fase 12 — o banco multi-tenant usa DATABASE_URL. Nos testes aponta para um SQLite
# temporário (fora do repo), criado antes de importar `app` (db.py lê a env no import).
os.environ.setdefault(
    "DATABASE_URL", "sqlite:///" + os.path.join(tempfile.gettempdir(), "viab_test.db")
)

import pytest
from fastapi.testclient import TestClient
from shapely.geometry import LineString, Point, Polygon

from app.core.camadas import Camadas, get_fonte_camadas
from app.core.extrator_luos import get_extrator_luos
from app.core.fmp import FonteFMPArquivo, get_fonte_fmp
from app.core.jurisdicao import Municipio, get_fonte_malha
from app.core.lista_municipios import FonteListaArquivo, get_fonte_lista
from app.core.perfil_municipal import get_fonte_perfil
from app.core.alertas_geo import get_provedor_alertas_geo
from app.core.extrator_documento import get_extrator_documento
from app.core.juridico_documental import AlertaGeo
from app.core.juridico_store import get_fonte_juridica
from app.core.economica_store import get_fonte_economica
from app.core.financeira_store import get_fonte_financeira
from app.core.localizacao import FonteLocalizacaoMemoria, get_fonte_localizacao
from app.core.store import STORE
from app.core.declividade import DEMRecorte, get_fonte_dem
from app.core.areas_umidas import CoberturaUmida, get_fonte_areas_umidas
from app.core.vegetacao import CoberturaVerde, get_fonte_vegetacao
from app.main import app
from app.models.schemas import FichaJuridica, PerfilMunicipal

_KML = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2"><Document>{placemarks}</Document></kml>"""
_PLACEMARK = (
    "<Placemark><Polygon><outerBoundaryIs><LinearRing>"
    "<coordinates>{coords}</coordinates>"
    "</LinearRing></outerBoundaryIs></Polygon></Placemark>"
)
_PLACEMARK_LINHA = (
    "<Placemark><LineString><coordinates>{coords}</coordinates></LineString></Placemark>"
)


def _coords(anel):
    return " ".join(f"{lon},{lat},0" for lon, lat in anel)


def _fechar(anel):
    return anel if anel[0] == anel[-1] else [*anel, anel[0]]


def _zip_kml(kml: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("doc.kml", kml)
    return buf.getvalue()


def make_kmz(aneis):
    """Gera bytes de um KMZ com um polígono por anel informado."""
    placemarks = "".join(_PLACEMARK.format(coords=_coords(_fechar(a))) for a in aneis)
    return _zip_kml(_KML.format(placemarks=placemarks))


def make_kmz_linhas(linhas):
    """Gera bytes de um KMZ com uma <LineString> por lista de coords (sem auto-fechar)."""
    placemarks = "".join(_PLACEMARK_LINHA.format(coords=_coords(l)) for l in linhas)
    return _zip_kml(_KML.format(placemarks=placemarks))


# Retângulo conhecido perto de São Roque/SP. ~0.02° lon × ~0.01° lat.
LON0, LAT0 = -47.140, -23.530
RET_RETANGULO = [
    (LON0, LAT0),
    (LON0 + 0.02, LAT0),
    (LON0 + 0.02, LAT0 + 0.01),
    (LON0, LAT0 + 0.01),
]

# Segundo polígono bem menor (para o teste de multi-polígono).
RET_PEQUENO = [
    (LON0 + 0.10, LAT0),
    (LON0 + 0.105, LAT0),
    (LON0 + 0.105, LAT0 + 0.005),
    (LON0 + 0.10, LAT0 + 0.005),
]

# "Gravata-borboleta": anel auto-interseccionado → geometria inválida.
RET_INVALIDO = [
    (LON0, LAT0),
    (LON0 + 0.02, LAT0 + 0.01),
    (LON0 + 0.02, LAT0),
    (LON0, LAT0 + 0.01),
]

# ----- Fixtures de LINHA para a camada de ingestão (Fase 1.5) -----
# Cantos do retângulo (sentido anti-horário): BL, BR, TR, TL.
_BL, _BR, _TR, _TL = (
    (LON0, LAT0),
    (LON0 + 0.02, LAT0),
    (LON0 + 0.02, LAT0 + 0.01),
    (LON0, LAT0 + 0.01),
)
# 1 grau de latitude ≈ 111.320 m.
_DLAT_GAP_OK = 2.7e-6      # ~0,30 m  (≤ 1,0 m → fecha)
_DLAT_GAP_GRANDE = 4.5e-5  # ~5,0 m   (> 1,0 m → recusa)

# LineString simples FECHADA (último == primeiro) → LINHA_FECHAVEL.
LINHA_FECHADA = [_BL, _BR, _TR, _TL, _BL]
# LineString simples ABERTA com gap pequeno → fecha + aviso.
LINHA_GAP_OK = [_BL, _BR, _TR, _TL, (LON0, LAT0 + _DLAT_GAP_OK)]
# LineString simples ABERTA com gap grande → TOPOGRAFIA_CAD / linha_aberta.
LINHA_GAP_GRANDE = [_BL, _BR, _TR, _TL, (LON0, LAT0 + _DLAT_GAP_GRANDE)]
# LineString auto-intersectada (bowtie) → TOPOGRAFIA_CAD / auto_intersecao.
LINHA_AUTOINTERSEC = [_BL, _TR, _BR, _TL]


# ----- Malha GEOMÉTRICA de TESTE (só DETECTAR; injetável) — nunca usada em produção -----
class StubMalha:
    """Malha-stub: lista de (Municipio, Polygon). Sem rede, determinística."""

    def __init__(self, municipios: list[tuple[Municipio, Polygon]]):
        self._m = municipios

    def municipio_no_ponto(self, lon, lat):
        p = Point(lon, lat)
        for mun, geom in self._m:
            if geom.contains(p):
                return mun
        return None

    def intersecoes(self, poly):
        return [
            (mun, geom.intersection(poly))
            for mun, geom in self._m
            if geom.intersects(poly)
        ]


# São Roque/SP cobrindo a região dos retângulos de teste (Fases 1/2, não-regressão).
SAO_ROQUE = Municipio(cod_ibge="3550605", municipio="São Roque", uf="SP")
SAO_ROQUE_POLY = Polygon(
    [(-47.20, -23.60), (-47.00, -23.60), (-47.00, -23.50), (-47.20, -23.50)]
)
MALHA_SAO_ROQUE = [(SAO_ROQUE, SAO_ROQUE_POLY)]

# Lista leve padrão dos testes (desacoplada da malha): cobre São Roque e Bocaina.
LISTA_PADRAO = [
    {"cod_ibge": "3550605", "municipio": "São Roque", "uf": "SP"},
    {"cod_ibge": "3506607", "municipio": "Bocaina", "uf": "SP"},
]


# ----- Fixtures de CAMADAS ambientais (Fase 2) — stubs offline e determinísticos -----
# Geometrias-stub posicionadas em relação ao RET_RETANGULO (a gleba de teste):
# gleba = (-47.140, -23.530) a (-47.120, -23.520).
DATA_REF = "2026-05-31"

# Rio horizontal que CRUZA a gleba (de ponta a ponta, em lat média).
RIO_CRUZA = LineString([(-47.145, -23.525), (-47.115, -23.525)])
# UC que cobre toda a gleba.
UC_COBRE = Polygon(
    [(-47.145, -23.535), (-47.115, -23.535), (-47.115, -23.515), (-47.145, -23.515)]
)
# Processo minerário que sobrepõe parte da gleba.
MINA_SOBREPOE = Polygon(
    [(-47.135, -23.528), (-47.125, -23.528), (-47.125, -23.522), (-47.135, -23.522)]
)
# Linha de transmissão que CRUZA a gleba (horizontal, lat média) — faixa de servidão.
LT_CRUZA = LineString([(-47.145, -23.524), (-47.115, -23.524)])
# Massa d'água (lago/represa) que sobrepõe parte da gleba — polígono.
LAGO_SOBREPOE = Polygon(
    [(-47.138, -23.529), (-47.130, -23.529), (-47.130, -23.523), (-47.138, -23.523)]
)


class StubFonte:
    """Fonte de camadas de TESTE — devolve Camadas fixas, sem rede."""

    def __init__(self, camadas: Camadas):
        self._camadas = camadas

    def coletar(self, bbox, uf):  # assinatura de FonteCamadas
        return self._camadas


@pytest.fixture
def fonte():
    """Injeta uma fonte-stub. Uso: ``fonte(Camadas(...))`` dentro do teste."""

    def _set(camadas: Camadas):
        app.dependency_overrides[get_fonte_camadas] = lambda: StubFonte(camadas)

    yield _set
    app.dependency_overrides.pop(get_fonte_camadas, None)


@pytest.fixture(autouse=True)
def _limpa_store():
    STORE.clear()
    yield
    STORE.clear()


@pytest.fixture(autouse=True)
def _limpa_banco():
    # Fase 12 — garante o schema e zera usuarios/analises entre testes (isolamento).
    from app.core.db import criar_tabelas, engine
    from app.models.db_models import Analise, Usuario

    criar_tabelas()
    with engine.begin() as conn:
        conn.execute(Analise.__table__.delete())
        conn.execute(Usuario.__table__.delete())
    yield


@pytest.fixture(autouse=True)
def _vegetacao_auto_off(monkeypatch):
    # Em produção o modo automático (ESA WorldCover via HTTP) é o padrão. Nos testes ele
    # fica DESLIGADO (sem rede/rasterio no sandbox), preservando o caminho "sem fonte →
    # degrada honesto". Testes que exercem o modo auto religam via monkeypatch.
    monkeypatch.setenv("VEGETACAO_WORLDCOVER_AUTO", "0")
    # Idem para a camada de áreas úmidas (MapBiomas via HTTP é o default em produção).
    monkeypatch.setenv("AREAS_UMIDAS_AUTO", "0")
    # Idem para o DEM da declividade (Copernicus via HTTP é o default em produção).
    monkeypatch.setenv("DEM_FONTE", "none")


class StubFonteDEM:
    """Fonte de DEM de TESTE — devolve um DEMRecorte fixo (grid métrico), sem raster/rede."""

    def __init__(self, recorte: DEMRecorte):
        self._recorte = recorte

    def amostrar(self, gleba):  # assinatura de FonteDEM
        return self._recorte


@pytest.fixture
def fonte_dem():
    """Injeta uma fonte de DEM-stub. Uso: ``fonte_dem(DEMRecorte(...))``."""

    def _set(recorte: DEMRecorte):
        app.dependency_overrides[get_fonte_dem] = lambda: StubFonteDEM(recorte)

    yield _set
    app.dependency_overrides.pop(get_fonte_dem, None)


class StubFonteVegetacao:
    """Fonte de vegetação de TESTE — devolve uma CoberturaVerde fixa, sem raster/rede."""

    def __init__(self, cobertura: CoberturaVerde):
        self._cobertura = cobertura

    def cobertura_verde(self, gleba):  # assinatura de FonteVegetacao
        return self._cobertura


@pytest.fixture
def fonte_vegetacao():
    """Injeta uma fonte de vegetação-stub. Uso: ``fonte_vegetacao(CoberturaVerde(...))``."""

    def _set(cobertura: CoberturaVerde):
        app.dependency_overrides[get_fonte_vegetacao] = lambda: StubFonteVegetacao(cobertura)

    yield _set
    app.dependency_overrides.pop(get_fonte_vegetacao, None)


class StubFonteAreasUmidas:
    """Fonte de áreas úmidas de TESTE — devolve uma CoberturaUmida fixa, sem raster/rede."""

    def __init__(self, cobertura: "CoberturaUmida"):
        self._cobertura = cobertura

    def areas_umidas(self, gleba):  # assinatura de FonteAreasUmidas
        return self._cobertura


@pytest.fixture
def fonte_areas_umidas():
    """Injeta uma fonte de áreas úmidas-stub. Uso: ``fonte_areas_umidas(CoberturaUmida(...))``."""

    def _set(cobertura: "CoberturaUmida"):
        app.dependency_overrides[get_fonte_areas_umidas] = lambda: StubFonteAreasUmidas(cobertura)

    yield _set
    app.dependency_overrides.pop(get_fonte_areas_umidas, None)


@pytest.fixture
def malha():
    """Injeta uma malha-stub. Uso: ``malha([(Municipio, Polygon), ...])`` no teste."""

    def _set(municipios):
        app.dependency_overrides[get_fonte_malha] = lambda: StubMalha(municipios)

    yield _set
    app.dependency_overrides.pop(get_fonte_malha, None)


@pytest.fixture
def fmp():
    """Injeta uma tabela FMP-stub. Uso: ``fmp({cod_ibge: m2})`` no teste."""

    def _set(tabela):
        app.dependency_overrides[get_fonte_fmp] = lambda: FonteFMPArquivo(tabela)

    yield _set
    app.dependency_overrides.pop(get_fonte_fmp, None)


@pytest.fixture
def lista():
    """Injeta uma lista leve-stub. Uso: ``lista([{cod_ibge, municipio, uf}, ...])``."""

    def _set(registros):
        app.dependency_overrides[get_fonte_lista] = lambda: FonteListaArquivo(registros)

    yield _set
    app.dependency_overrides.pop(get_fonte_lista, None)


# ----- Fase 1.8 — perfil municipal (LUOS) + extrator: stubs offline, sem rede, sem chave -----
class StubExtratorLUOS:
    """Extrator de TESTE: devolve um PerfilMunicipal fixo (proposto), sem PDF/rede/chave."""

    def __init__(self, perfil: PerfilMunicipal):
        self._perfil = perfil

    def extrair(self, pdf_bytes, cod_ibge, municipio, uf, nome_arquivo=None):
        return self._perfil.model_copy(deep=True)


class FontePerfilMemoria:
    """Fonte de perfil em memória (injetável nos testes) — sem volume/arquivo."""

    def __init__(self):
        self._m: dict[str, PerfilMunicipal] = {}

    def carregar(self, cod_ibge):
        return self._m.get(str(cod_ibge))

    def salvar(self, perfil: PerfilMunicipal):
        self._m[str(perfil.cod_ibge)] = perfil.model_copy(deep=True)

    def semear(self, perfil: PerfilMunicipal):
        """Atalho de teste: planta um perfil direto (ex.: já confirmado)."""
        self.salvar(perfil)


@pytest.fixture
def extrator_luos():
    """Injeta um extrator-stub. Uso: ``extrator_luos(PerfilMunicipal(...))``."""

    def _set(perfil: PerfilMunicipal):
        app.dependency_overrides[get_extrator_luos] = lambda: StubExtratorLUOS(perfil)

    yield _set
    app.dependency_overrides.pop(get_extrator_luos, None)


@pytest.fixture
def extrator_indisponivel():
    """Força o extrator a None (sem credencial) — simula produção sem chave de LLM."""
    app.dependency_overrides[get_extrator_luos] = lambda: None
    yield
    app.dependency_overrides.pop(get_extrator_luos, None)


@pytest.fixture
def fonte_perfil():
    """Injeta uma fonte de perfil em memória e devolve a instância (p/ semear/checar)."""
    fonte = FontePerfilMemoria()
    app.dependency_overrides[get_fonte_perfil] = lambda: fonte
    yield fonte
    app.dependency_overrides.pop(get_fonte_perfil, None)


# ----- Fase 3 — jurídico documental: extrator-stub + ficha em memória + alertas-stub -----
class StubExtratorDocumento:
    """Extrator de TESTE: devolve uma FichaJuridica fixa (proposta), sem PDF/rede/chave."""

    def __init__(self, ficha: FichaJuridica):
        self._ficha = ficha

    def extrair(self, arquivos, tipo, nome_arquivo=None):
        return self._ficha.model_copy(deep=True)


class FonteJuridicaMemoria:
    """Fonte de fichas jurídicas em memória (injetável nos testes) — sem volume/arquivo."""

    def __init__(self):
        self._m: dict[str, list[FichaJuridica]] = {}

    def carregar(self, analise_id):
        return [f.model_copy(deep=True) for f in self._m.get(str(analise_id), [])]

    def salvar(self, analise_id, ficha: FichaJuridica):
        chave = (ficha.tipo, ficha.fonte_documento)
        atuais = [
            f
            for f in self._m.get(str(analise_id), [])
            if (f.tipo, f.fonte_documento) != chave
        ]
        atuais.append(ficha.model_copy(deep=True))
        self._m[str(analise_id)] = atuais

    def semear(self, analise_id, ficha: FichaJuridica):
        self.salvar(analise_id, ficha)


class StubProvedorAlertasGeo:
    """Provedor de alertas geo de TESTE — devolve uma lista fixa, sem fontes/rede."""

    def __init__(self, alertas: list[AlertaGeo]):
        self._alertas = alertas

    def coletar(self, analise_id):
        return list(self._alertas)


@pytest.fixture
def extrator_documento():
    """Injeta um extrator documental-stub. Uso: ``extrator_documento(FichaJuridica(...))``."""

    def _set(ficha: FichaJuridica):
        app.dependency_overrides[get_extrator_documento] = lambda: StubExtratorDocumento(
            ficha
        )

    yield _set
    app.dependency_overrides.pop(get_extrator_documento, None)


@pytest.fixture
def extrator_doc_indisponivel():
    """Força o extrator documental a None (sem credencial)."""
    app.dependency_overrides[get_extrator_documento] = lambda: None
    yield
    app.dependency_overrides.pop(get_extrator_documento, None)


@pytest.fixture
def fonte_juridica():
    """Injeta a fonte de fichas jurídicas em memória e devolve a instância (semear/checar)."""
    fonte = FonteJuridicaMemoria()
    app.dependency_overrides[get_fonte_juridica] = lambda: fonte
    yield fonte
    app.dependency_overrides.pop(get_fonte_juridica, None)


class FonteFinanceiraMemoria:
    """Persistência financeira em memória (injetável nos testes)."""

    def __init__(self):
        self._m: dict[str, dict] = {}

    def carregar(self, analise_id):
        return self._m.get(str(analise_id))

    def salvar(self, analise_id, dados):
        self._m[str(analise_id)] = dados


@pytest.fixture
def fonte_financeira():
    fonte = FonteFinanceiraMemoria()
    app.dependency_overrides[get_fonte_financeira] = lambda: fonte
    yield fonte
    app.dependency_overrides.pop(get_fonte_financeira, None)


@pytest.fixture
def fonte_economica():
    """Persistência econômica em memória (Fase 5) — mesmo formato da financeira."""
    fonte = FonteFinanceiraMemoria()
    app.dependency_overrides[get_fonte_economica] = lambda: fonte
    yield fonte
    app.dependency_overrides.pop(get_fonte_economica, None)


# ----- Fase 9 — Urbanismo: gerador-stub (offline), store em memória, layout sintético -----
from app.core.urbanismo_programa import (  # noqa: E402
    get_gerador_programa,
    programa_do_preset,
)
from app.core.urbanismo_store import get_fonte_urbanismo  # noqa: E402


class StubGeradorPrograma:
    """Gerador de TESTE: devolve um Programa do preset (sem rede/chave). Pode injetar
    ``esqueleto`` para exercer a validação da fronteira. NÃO fornece nenhum número de medida."""

    def __init__(self, esqueleto=None, overrides=None):
        self._esqueleto = esqueleto
        self._overrides = overrides or {}

    def propor(self, contexto, tipo_loteamento, publico_alvo, overrides=None):
        ov = {**self._overrides, **(overrides or {})}
        if self._esqueleto is not None:
            ov.setdefault("esqueleto", self._esqueleto)
        prog = programa_do_preset(publico_alvo, ov)
        prog.origem = "proposto_llm"  # finge a borda
        prog.esqueleto_origem = "llm" if prog.esqueleto else "vazio"  # 9.9 — origem do esqueleto
        return prog


class FonteUrbanismoMemoria:
    """Snapshots versionados em memória (injetável nos testes)."""

    def __init__(self):
        self._m: dict[str, list[dict]] = {}

    def listar(self, analise_id):
        return [dict(p) for p in self._m.get(str(analise_id), [])]

    def carregar(self, analise_id, proposta_id):
        for p in self._m.get(str(analise_id), []):
            if p.get("proposta_id") == proposta_id:
                return dict(p)
        return None

    def salvar(self, analise_id, proposta):
        self._m.setdefault(str(analise_id), []).append(dict(proposta))

    def proxima_versao(self, analise_id):
        return len(self._m.get(str(analise_id), [])) + 1


@pytest.fixture
def gerador_urbanismo():
    """Injeta um gerador-stub. Uso: ``gerador_urbanismo(esqueleto=[...])``."""

    def _set(esqueleto=None, overrides=None):
        app.dependency_overrides[get_gerador_programa] = (
            lambda: StubGeradorPrograma(esqueleto, overrides)
        )

    _set()  # default já injetado
    yield _set
    app.dependency_overrides.pop(get_gerador_programa, None)


@pytest.fixture
def gerador_urbanismo_indisponivel():
    """Força o gerador a None (sem credencial) — exerce o 503."""
    app.dependency_overrides[get_gerador_programa] = lambda: None
    yield
    app.dependency_overrides.pop(get_gerador_programa, None)


@pytest.fixture
def fonte_urbanismo():
    fonte = FonteUrbanismoMemoria()
    app.dependency_overrides[get_fonte_urbanismo] = lambda: fonte
    yield fonte
    app.dependency_overrides.pop(get_fonte_urbanismo, None)


# Conversão metros (frame local) → lon/lat, ancorada em (LON0, LAT0) — para montar layouts
# sintéticos com ÁREA EXATA conhecida e medi-los pelo motor (valores-ouro de São Roque).
def _metros_para_wgs(geom_m):
    from pyproj import CRS, Transformer
    from shapely.ops import transform as _t

    local = CRS.from_proj4(
        f"+proj=aeqd +lat_0={LAT0} +lon_0={LON0} +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs"
    )
    to_wgs = Transformer.from_crs(local, "EPSG:4326", always_xy=True).transform
    return _t(to_wgs, geom_m)


def layout_sao_roque_sintetico():
    """Layout cujo quadro REPRODUZ os valores-ouro de São Roque (TIV 5.0):
    vendável 74.644,40 (167 lotes), verdes 36.686,92, arruamento 20.102,43 → líquida
    131.433,75. Retângulos disjuntos em metros, com área exata, convertidos a GeoJSON WGS84.
    """
    from shapely.geometry import box, mapping

    # 167 lotes idênticos: 17,94 m de testada × d → área = 74.644,40 / 167 (testada 17,94,
    # profundidade ~24,91). Soma exata = 74.644,40.
    n = 167
    area_lote = 74644.40 / n
    w = 17.94
    d = area_lote / w
    lotes = []
    x = 0.0
    for _ in range(n):
        lotes.append(_metros_para_wgs(box(x, 0.0, x + w, d)))
        x += w  # disjuntos lado a lado
    # Verde: retângulo de área 36.686,92, afastado dos lotes (disjunto).
    hv = 36686.92 / 200.0
    verde = _metros_para_wgs(box(0.0, 100.0, 200.0, 100.0 + hv))
    # Arruamento: retângulo de área 20.102,43, afastado (disjunto).
    ha = 20102.43 / 200.0
    arru = _metros_para_wgs(box(0.0, 400.0, 200.0, 400.0 + ha))
    return {
        "lotes": [mapping(g) for g in lotes],
        "areas_verdes": mapping(verde),
        "arruamento": mapping(arru),
    }


@pytest.fixture
def alertas_geo():
    """Injeta um provedor de alertas geo-stub. Uso: ``alertas_geo([AlertaGeo(...), ...])``.
    Default sem alertas (lista vazia) se chamado sem argumento."""

    def _set(alertas=None):
        app.dependency_overrides[get_provedor_alertas_geo] = (
            lambda: StubProvedorAlertasGeo(alertas or [])
        )

    _set([])  # default: provedor vazio (não tenta as fontes reais nos testes)
    yield _set
    app.dependency_overrides.pop(get_provedor_alertas_geo, None)


# ----- Fase 6 — Localização: dataset embarcado de TESTE (offline) -----
# São Roque = valores-ouro IBGE; UF SP + Brasil para as razões; Mairinque = município COM
# déficit FJP (exercita o caminho preenchido); "9999999" não entra (INDISPONIVEL no router).
LOCALIZACAO_DATASET = {
    "_meta": {"data_geracao": "2026-06-12", "fontes": "IBGE/FJP (teste)"},
    "registros": {
        "3550605": {
            "nivel": "municipio", "cod": "3550605", "nome": "São Roque", "uf": "SP",
            "pop_2022": 79484, "pop_2010": 78821, "area_km2": 306.909,
            "pib_per_capita": 57024.90, "pib_ano": 2023,
            "domicilios_ocupados": 28490, "moradores_por_domicilio": 2.79,
            "deficit": None,
            "faixa_etaria": {"0-14": 0.1832, "15-29": 0.2103, "30-59": 0.4298, "60+": 0.1767},
        },
        "3528502": {  # Mairinque/SP — COM déficit FJP no fixture
            "nivel": "municipio", "cod": "3528502", "nome": "Mairinque", "uf": "SP",
            "pop_2022": 47714, "pop_2010": 43223, "area_km2": 210.0,
            "pib_per_capita": 38000.00, "pib_ano": 2023,
            "domicilios_ocupados": 16000, "moradores_por_domicilio": 2.98,
            "deficit": {"valor": 1234, "fonte": "FJP", "ano": 2022},
            "faixa_etaria": {"0-14": 0.20, "15-29": 0.22, "30-59": 0.43, "60+": 0.15},
        },
        "UF:SP": {
            "nivel": "uf", "cod": "35", "nome": "São Paulo", "uf": "SP",
            "pop_2022": 44411238, "pop_2010": 41262199, "area_km2": 248219.485,
            "pib_per_capita": 64500.00, "pib_ano": 2023,
            "domicilios_ocupados": 15273855, "moradores_por_domicilio": 2.91,
            "deficit": None,
            "faixa_etaria": {"0-14": 0.1789, "15-29": 0.2151, "30-59": 0.4318, "60+": 0.1742},
        },
        "BR": {
            "nivel": "brasil", "cod": "0", "nome": "Brasil", "uf": None,
            "pop_2022": 203080756, "pop_2010": 190755799, "area_km2": 8510295.914,
            "pib_per_capita": 50200.00, "pib_ano": 2023,
            "domicilios_ocupados": 68000000, "moradores_por_domicilio": 2.98,
            "deficit": None,
            "faixa_etaria": {"0-14": 0.1962, "15-29": 0.2238, "30-59": 0.4253, "60+": 0.1547},
        },
    },
}


@pytest.fixture
def localizacao():
    """Injeta um dataset de localização-stub. Uso: ``localizacao(LOCALIZACAO_DATASET)``.
    Default = dataset padrão (São Roque + SP + Brasil + Mairinque-com-FJP)."""

    def _set(dataset=LOCALIZACAO_DATASET):
        app.dependency_overrides[get_fonte_localizacao] = lambda: FonteLocalizacaoMemoria(
            dataset
        )

    _set()  # default já injetado
    yield _set
    app.dependency_overrides.pop(get_fonte_localizacao, None)


@pytest.fixture
def client_producao():
    """Cliente com o comportamento REAL: SEM malha geométrica configurada.

    A lista leve permanece no default (seed embarcado) → busca/override por nome ainda
    funcionam sem a malha (decisão #2). Para determinismo, os testes podem injetar ``lista``.
    """
    app.dependency_overrides.pop(get_fonte_malha, None)
    with TestClient(app) as c:
        yield c


@pytest.fixture
def client():
    """Cliente de teste com malha (São Roque/SP) e lista leve padrão injetadas."""
    app.dependency_overrides[get_fonte_malha] = lambda: StubMalha(MALHA_SAO_ROQUE)
    app.dependency_overrides[get_fonte_lista] = lambda: FonteListaArquivo(LISTA_PADRAO)
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_fonte_malha, None)
    app.dependency_overrides.pop(get_fonte_lista, None)
