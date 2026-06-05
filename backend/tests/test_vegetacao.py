"""Critérios de aceite da Fase 2.2 — Área verde (desconto do aproveitável), offline."""

from shapely.geometry import Polygon

from app.core.camadas import Camadas, FeicaoMassaDagua
from app.core.vegetacao import CoberturaVerde
from tests.conftest import DATA_REF, LAGO_SOBREPOE, RET_RETANGULO, make_kmz


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


# 6 — Fase 2.3: severidade do verde no endpoint /vegetacao -----------------------
def _camadas_com_massa():
    return Camadas(
        massas_dagua=[FeicaoMassaDagua(LAGO_SOBREPOE, nome="Represa Teste", tipo="artificial")],
        consultadas=["ANA"],
    )


def test_severidade_no_endpoint(client, fonte_vegetacao, fonte):
    fonte_vegetacao(CoberturaVerde(geometria=VERDE_METADE, fonte="WorldCover (teste)"))
    fonte(_camadas_com_massa())
    aid = _criar_analise(client)
    sev = client.get(f"/api/analises/{aid}/vegetacao").json()["severidade"]
    assert sev is not None
    # conservação: dura + a_verificar = verde_total
    soma = sev["restricao_dura"]["area_m2"] + sev["a_verificar"]["area_m2"]
    assert abs(soma - sev["verde_total_m2"]) / sev["verde_total_m2"] < 0.005
    assert sev["restricao_dura"]["area_m2"] > 0  # verde encosta na APP da represa
    assert "app_massa_dagua" in sev["restricao_dura"]["fontes"]
    assert "laudo" in sev["ressalva"].lower()


def test_severidade_null_sem_camadas(client, fonte_vegetacao):
    # Só vegetação, sem ambiental → severidade null + aviso honesto.
    fonte_vegetacao(CoberturaVerde(geometria=VERDE_METADE, fonte="WorldCover (teste)"))
    aid = _criar_analise(client)
    data = client.get(f"/api/analises/{aid}/vegetacao").json()
    assert data["severidade"] is None
    assert any("severidade" in a.lower() for a in data["avisos"])


# 7 — Fase 2.3: cenário otimista no aproveitamento ------------------------------
def test_cenario_otimista(client, fonte_vegetacao, fonte):
    fonte_vegetacao(CoberturaVerde(geometria=VERDE_METADE, fonte="WorldCover (teste)"))
    fonte(_camadas_com_massa())
    aid = _criar_analise(client)
    out = client.post(f"/api/analises/{aid}/aproveitamento", json=_BODY_URBANO).json()
    co = out["cenario_otimista"]
    assert co is not None
    # otimista = conservador + potencial desbloqueável ≥ headline
    assert co["area_aproveitavel_m2"] >= out["area_aproveitavel_m2"]
    assert co["n_lotes_teto"] >= out["n_lotes_teto"]
    assert "hipot" in co["ressalva"].lower()


def test_cenario_otimista_null_sem_camadas(client, fonte_vegetacao):
    fonte_vegetacao(CoberturaVerde(geometria=VERDE_METADE, fonte="WorldCover (teste)"))
    aid = _criar_analise(client)
    out = client.post(f"/api/analises/{aid}/aproveitamento", json=_BODY_URBANO).json()
    assert out["cenario_otimista"] is None  # severidade indisponível sem ambiental
