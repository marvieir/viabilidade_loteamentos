"""Fixtures determinísticas: KMZ sintéticos e clientes com/sem de-para municipal."""

import io
import zipfile

import pytest
from fastapi.testclient import TestClient
from shapely.geometry import LineString, Point, Polygon

from app.core.camadas import Camadas, get_fonte_camadas
from app.core.fmp import FonteFMPArquivo, get_fonte_fmp
from app.core.jurisdicao import Municipio, get_fonte_malha
from app.core.lista_municipios import FonteListaArquivo, get_fonte_lista
from app.core.store import STORE
from app.core.vegetacao import CoberturaVerde, get_fonte_vegetacao
from app.main import app

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
