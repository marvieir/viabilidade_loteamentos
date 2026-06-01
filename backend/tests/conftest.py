"""Fixtures determinísticas: KMZ sintéticos e clientes com/sem de-para municipal."""

import io
import zipfile

import pytest
from fastapi.testclient import TestClient

from app.core.jurisdicao import get_resolvedor_municipio
from app.core.store import STORE
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


def resolver_sao_roque(lon, lat):
    """De-para de TESTE — nunca usado em produção."""
    return ("São Roque", "SP", "3550605")


@pytest.fixture(autouse=True)
def _limpa_store():
    STORE.clear()
    yield
    STORE.clear()


@pytest.fixture
def client_producao():
    """Cliente com o comportamento REAL: sem de-para municipal configurado."""
    app.dependency_overrides.pop(get_resolvedor_municipio, None)
    with TestClient(app) as c:
        yield c


@pytest.fixture
def client():
    """Cliente de teste com de-para municipal injetado (São Roque/SP)."""
    app.dependency_overrides[get_resolvedor_municipio] = lambda: resolver_sao_roque
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_resolvedor_municipio, None)
