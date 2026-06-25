"""Critérios de aceite — Áreas úmidas / alagadas (nova dimensão ambiental), offline.

Determinístico (mesma gleba + mesma cobertura → mesma área), cálculo só no backend, com
proveniência (fonte, classes, base legal, ressalva). Sem fonte → degradação honesta.
"""

from shapely.geometry import Polygon

from app.core.areas_umidas import (
    CLASSES_UMIDA_MAPBIOMAS,
    CLASSES_UMIDA_WORLDCOVER,
    CoberturaUmida,
    analisar_areas_umidas,
)
from tests.conftest import DATA_REF, RET_RETANGULO, make_kmz

# Metade esquerda do retângulo da gleba (mesmo recorte usado no teste de vegetação).
UMIDA_METADE = Polygon(
    [(-47.140, -23.530), (-47.130, -23.530), (-47.130, -23.520), (-47.140, -23.520)]
)


def _criar_analise(client) -> str:
    kmz = make_kmz([RET_RETANGULO])
    r = client.post(
        "/api/analises",
        files={"kmz": ("gleba.kmz", kmz, "application/vnd.google-earth.kmz")},
    )
    assert r.status_code == 200, r.text
    return r.json()["analise_id"]


# 1 — área úmida detectada é medida e marcada (com proveniência/APP) -----------------
def test_area_umida_detectada(client, fonte_areas_umidas):
    fonte_areas_umidas(
        CoberturaUmida(
            geometria=UMIDA_METADE,
            fonte="MapBiomas (teste)",
            data_referencia=DATA_REF,
            classes=["11", "33"],
        )
    )
    aid = _criar_analise(client)
    data = client.get(f"/api/analises/{aid}/areas-umidas").json()

    assert data["consultada"] is True
    assert data["area_umida_m2"] > 0
    assert 45 <= data["pct_da_gleba"] <= 55, data          # ~metade da gleba é úmida
    assert data["geojson_umidas"]                          # overlay p/ o mapa
    assert "app" in data["proveniencia"]["base_legal"].lower()
    assert "ambiental" in data["proveniencia"]["ressalva"].lower()
    assert data["proveniencia"]["classes"] == ["11", "33"]


# 2 — sem fonte: degradação honesta (não marca, não inventa) -----------------------
def test_sem_fonte_nao_marca(client):
    aid = _criar_analise(client)
    data = client.get(f"/api/analises/{aid}/areas-umidas").json()
    assert data["consultada"] is False
    assert data["area_umida_m2"] is None
    assert data["pct_da_gleba"] is None
    assert data["area_total_m2"] > 0  # total sempre medido
    assert any("não consultad" in a.lower() for a in data["avisos"]), data["avisos"]


# 3 — gleba sem área úmida: consultada, porém zero (não degrada) -------------------
def test_consultada_sem_umida(client, fonte_areas_umidas):
    fonte_areas_umidas(
        CoberturaUmida(geometria=None, fonte="WorldCover (teste)", data_referencia=DATA_REF)
    )
    aid = _criar_analise(client)
    data = client.get(f"/api/analises/{aid}/areas-umidas").json()
    # geometria None ⇒ tratamos como não consultada (sem marcação) — degradação honesta.
    assert data["consultada"] is False
    assert data["area_total_m2"] > 0


# 4 — determinismo do motor: mesma entrada → mesma saída ---------------------------
def test_determinismo_motor():
    gleba = Polygon(RET_RETANGULO)
    a = analisar_areas_umidas(gleba, CoberturaUmida(geometria=UMIDA_METADE, classes=["11"]))
    b = analisar_areas_umidas(gleba, CoberturaUmida(geometria=UMIDA_METADE, classes=["11"]))
    assert a.area_umida_m2 == b.area_umida_m2
    assert a.pct_da_gleba == b.pct_da_gleba


# 5 — conjuntos de classes default coerentes (WorldCover 90 / MapBiomas 11+33) -----
def test_classes_default():
    assert CLASSES_UMIDA_WORLDCOVER == {90}
    assert CLASSES_UMIDA_MAPBIOMAS == {11, 33}
