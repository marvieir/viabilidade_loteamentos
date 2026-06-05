"""Critérios de aceite da Fase 2.2 — Área verde (desconto do aproveitável), offline."""

from shapely.geometry import Polygon

from app.core.vegetacao import CoberturaVerde
from tests.conftest import DATA_REF, RET_RETANGULO, make_kmz


def _criar_analise(client) -> str:
    kmz = make_kmz([RET_RETANGULO])
    r = client.post(
        "/api/analises",
        files={"kmz": ("gleba.kmz", kmz, "application/vnd.google-earth.kmz")},
    )
    assert r.status_code == 200, r.text
    return r.json()["analise_id"]


# Metade esquerda do retângulo da gleba (LON0=-47.140..-47.120; corta no meio -47.130).
VERDE_METADE = Polygon(
    [(-47.140, -23.530), (-47.130, -23.530), (-47.130, -23.520), (-47.140, -23.520)]
)


# 1 — verde detectado é descontado do total ------------------------------------
def test_verde_descontado_do_aproveitavel(client, fonte_vegetacao):
    fonte_vegetacao(
        CoberturaVerde(
            geometria=VERDE_METADE,
            fonte="MapBiomas (teste)",
            data_referencia=DATA_REF,
            classes=["3"],
        )
    )
    aid = _criar_analise(client)
    data = client.get(f"/api/analises/{aid}/vegetacao").json()

    assert data["consultada"] is True
    assert data["area_verde_m2"] > 0
    # área líquida = total − verde (coerência aritmética determinística)
    assert abs(
        data["area_liquida_m2"] - (data["area_total_m2"] - data["area_verde_m2"])
    ) < 0.5
    # metade da gleba é verde → ~50%
    assert 45 <= data["percentual_verde"] <= 55, data
    assert data["geojson_verde"]
    assert "ambiental" in data["proveniencia"]["ressalva"].lower()


# 2 — sem fonte: degradação honesta (não desconta, não inventa) ----------------
def test_sem_fonte_nao_desconta(client):
    aid = _criar_analise(client)
    data = client.get(f"/api/analises/{aid}/vegetacao").json()
    assert data["consultada"] is False
    assert data["area_verde_m2"] is None
    assert data["area_liquida_m2"] is None
    assert data["area_total_m2"] > 0  # total sempre medido
    assert any("não consultad" in a.lower() for a in data["avisos"]), data["avisos"]


# 3 — gleba sem verde: 0 descontado, líquida == total --------------------------
def test_gleba_sem_verde(client, fonte_vegetacao):
    # verde longe da gleba → interseção vazia
    longe = Polygon([(-40.0, -10.0), (-39.9, -10.0), (-39.9, -9.9), (-40.0, -9.9)])
    fonte_vegetacao(CoberturaVerde(geometria=longe, fonte="MapBiomas (teste)"))
    aid = _criar_analise(client)
    data = client.get(f"/api/analises/{aid}/vegetacao").json()
    assert data["consultada"] is True
    assert data["area_verde_m2"] == 0.0
    assert abs(data["area_liquida_m2"] - data["area_total_m2"]) < 0.5


# 4 — determinismo -------------------------------------------------------------
def test_determinismo(client, fonte_vegetacao):
    fonte_vegetacao(CoberturaVerde(geometria=VERDE_METADE, fonte="MapBiomas (teste)"))
    aid = _criar_analise(client)
    r1 = client.get(f"/api/analises/{aid}/vegetacao")
    r2 = client.get(f"/api/analises/{aid}/vegetacao")
    assert r1.json() == r2.json()


def test_vegetacao_analise_inexistente_404(client):
    assert client.get("/api/analises/nao-existe/vegetacao").status_code == 404


# 5 — integração: verde desconta a área aproveitável do APROVEITAMENTO (Fase 2.2) ----
_BODY_URBANO = {"regime": "URBANO", "modalidade": "loteamento_aberto", "lote_min_m2": 200.0}


def test_aproveitamento_desconta_verde(client, fonte_vegetacao):
    aid = _criar_analise(client)
    sem = client.post(f"/api/analises/{aid}/aproveitamento", json=_BODY_URBANO).json()
    assert sem["descontos"] is None  # sem fonte → sem desconto
    aprov_sem = sem["area_aproveitavel_m2"]

    # liga a fonte: metade da gleba é verde
    fonte_vegetacao(CoberturaVerde(geometria=VERDE_METADE, fonte="MapBiomas (teste)"))
    com = client.post(f"/api/analises/{aid}/aproveitamento", json=_BODY_URBANO).json()
    d = com["descontos"]
    assert d is not None
    assert d["area_restritiva_m2"] > 0
    assert abs(d["area_base_m2"] - (d["area_total_m2"] - d["area_restritiva_m2"])) < 0.5
    assert any(i["tipo"] == "verde" for i in d["itens"])
    # metade verde → aproveitável cai ~50% e o teto de lotes acompanha
    assert com["area_aproveitavel_m2"] < aprov_sem
    assert com["n_lotes_teto"] < sem["n_lotes_teto"]
    assert com["pct_sobre_total"] < 1.0
