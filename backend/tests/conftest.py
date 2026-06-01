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


def _coords(anel):
    return " ".join(f"{lon},{lat},0" for lon, lat in anel)


def _fechar(anel):
    return anel if anel[0] == anel[-1] else [*anel, anel[0]]


def make_kmz(aneis):
    """Gera bytes de um KMZ com um polígono por anel informado."""
    placemarks = "".join(_PLACEMARK.format(coords=_coords(_fechar(a))) for a in aneis)
    kml = _KML.format(placemarks=placemarks)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("doc.kml", kml)
    return buf.getvalue()


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
