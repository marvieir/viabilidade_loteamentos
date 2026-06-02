"""Critérios de aceite da Fase 1.7 — jurisdição real + regime + rural (FMP).

Offline e determinístico: malha municipal e tabela FMP são injetadas (stubs), sem rede.
Valor-ouro: Bocaina rural = 54 parcelas (109,41 ha ÷ 2 ha).
"""

from shapely.geometry import Polygon

from app.core import aproveitamento as motor
from app.core.jurisdicao import Municipio
from tests.conftest import make_kmz

# ----- Geometrias de teste (região da Serra da Bocaina, ~−45,72 / −22,64) -----
# Retângulo ~109,28 ha (54 parcelas a 2 ha) — área geodésica conferida.
RET_BOCAINA = [
    (-45.725, -22.645),
    (-45.7154, -22.645),
    (-45.7154, -22.635),
    (-45.725, -22.635),
]
# Gleba que cavalga a divisa entre dois municípios (x = −45,72).
RET_DIVISA = [
    (-45.74, -22.645),
    (-45.705, -22.645),
    (-45.705, -22.635),
    (-45.74, -22.635),
]

BOCAINA = Municipio(cod_ibge="3506607", municipio="Bocaina", uf="SP")
BOCAINA_POLY = Polygon(
    [(-45.80, -22.70), (-45.65, -22.70), (-45.65, -22.58), (-45.80, -22.58)]
)
MALHA_BOCAINA = [(BOCAINA, BOCAINA_POLY)]

# Vizinha distante (para o teste de override; não cobre a gleba).
VIZINHA = Municipio(cod_ibge="3500109", municipio="Vizinha", uf="SP")
VIZINHA_POLY = Polygon(
    [(-46.50, -23.00), (-46.40, -23.00), (-46.40, -22.90), (-46.50, -22.90)]
)

# Divisa: dois municípios adjacentes ao longo de x = −45,72.
MUN_A = Municipio(cod_ibge="3500001", municipio="Município A", uf="SP")
MUN_A_POLY = Polygon(
    [(-45.80, -22.70), (-45.72, -22.70), (-45.72, -22.58), (-45.80, -22.58)]
)
MUN_B = Municipio(cod_ibge="3500002", municipio="Município B", uf="SP")
MUN_B_POLY = Polygon(
    [(-45.72, -22.70), (-45.64, -22.70), (-45.64, -22.58), (-45.72, -22.58)]
)


def _post(client, aneis):
    kmz = make_kmz(aneis)
    return client.post(
        "/api/analises",
        files={"kmz": ("gleba.kmz", kmz, "application/vnd.google-earth.kmz")},
    )


# ---------- Critério 1: detecção real ----------
def test_bocaina_detectado(client, malha):
    malha(MALHA_BOCAINA)
    jur = _post(client, [RET_BOCAINA]).json()["jurisdicao"]
    assert jur["municipio"] == "Bocaina"
    assert jur["uf"] == "SP"
    assert jur["cod_ibge"] == "3506607"
    assert jur["origem"] == "detectado"
    assert jur["cruza_divisa"] is False


# ---------- Critério 2: correção via override ----------
def test_override_municipio(client, malha):
    malha([*MALHA_BOCAINA, (VIZINHA, VIZINHA_POLY)])
    aid = _post(client, [RET_BOCAINA]).json()["analise_id"]
    r = client.post(f"/api/analises/{aid}/municipio", json={"cod_ibge": "3500109"})
    assert r.status_code == 200, r.text
    jur = r.json()
    assert jur["municipio"] == "Vizinha"
    assert jur["origem"] == "informado"


def test_override_codigo_inexistente_422(client, malha):
    malha(MALHA_BOCAINA)
    aid = _post(client, [RET_BOCAINA]).json()["analise_id"]
    r = client.post(f"/api/analises/{aid}/municipio", json={"cod_ibge": "0000000"})
    assert r.status_code == 422


# ---------- Critério 3: alerta de divisa ----------
def test_cruza_divisa(client, malha):
    malha([(MUN_A, MUN_A_POLY), (MUN_B, MUN_B_POLY)])
    jur = _post(client, [RET_DIVISA]).json()["jurisdicao"]
    assert jur["cruza_divisa"] is True
    cods = {m["cod_ibge"] for m in jur["municipios_candidatos"]}
    assert cods == {"3500001", "3500002"}


# ---------- Critério 4: centróide fora da malha ----------
def test_fora_da_malha(client, malha):
    malha([(VIZINHA, VIZINHA_POLY)])  # não cobre a gleba da Bocaina
    jur = _post(client, [RET_BOCAINA]).json()["jurisdicao"]
    assert jur["municipio"] is None
    assert jur["cod_ibge"] is None
    assert jur["cruza_divisa"] is False


# ---------- Critério 5: RURAL FMP — VALOR-OURO ----------
def test_rural_golden_motor():
    """Valor-ouro direto no motor: 109,41 ha ÷ 2 ha = 54 parcelas."""
    r = motor.aproveitamento_rural(area=1_094_111.1, fmp_m2=20_000)
    assert r["n_parcelas"] == 54
    assert r["fmp_m2"] == 20_000
    assert "INCRA" in r["proveniencia"]
    assert "conversão" in r["flag_conversao"]


def test_rural_fmp_da_tabela(client, malha, fmp):
    """RURAL puxando a FMP da tabela do município (sem fmp_m2 no corpo)."""
    malha(MALHA_BOCAINA)
    fmp({"3506607": 20_000})
    aid = _post(client, [RET_BOCAINA]).json()["analise_id"]
    r = client.post(
        f"/api/analises/{aid}/aproveitamento", json={"regime": "RURAL"}
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["regime"] == "RURAL"
    assert body["rural"]["n_parcelas"] == 54
    assert body["rural"]["fmp_m2"] == 20_000
    assert "INCRA" in body["rural"]["proveniencia"]


def test_rural_fmp_no_corpo(client, malha):
    """FMP informada no corpo (município sem tabela): editável."""
    malha(MALHA_BOCAINA)
    aid = _post(client, [RET_BOCAINA]).json()["analise_id"]
    r = client.post(
        f"/api/analises/{aid}/aproveitamento",
        json={"regime": "RURAL", "fmp_m2": 20_000},
    )
    assert r.status_code == 200, r.text
    assert r.json()["rural"]["n_parcelas"] == 54


def test_rural_fmp_indisponivel_422(client, malha, fmp):
    """Município sem FMP na tabela e sem fmp_m2 no corpo → 422 honesto, não inventa."""
    malha(MALHA_BOCAINA)
    fmp({})  # tabela vazia (sobrescreve o seed de produção)
    aid = _post(client, [RET_BOCAINA]).json()["analise_id"]
    r = client.post(
        f"/api/analises/{aid}/aproveitamento", json={"regime": "RURAL"}
    )
    assert r.status_code == 422
    assert r.json()["erro"] == "fmp_indisponivel"


# ---------- Critério 6: URBANO mantém números + premissa/origem ----------
def test_urbano_premissa_e_origem(client, malha):
    malha(MALHA_BOCAINA)
    aid = _post(client, [RET_BOCAINA]).json()["analise_id"]
    r = client.post(
        f"/api/analises/{aid}/aproveitamento",
        json={
            "regime": "URBANO",
            "modalidade": "loteamento_aberto",
            "lote_min_m2": 200,
            "loteamento": {
                "vias_m2": 11500,
                "doacao_pct": 0.20,
                "base_doacao": "combinada",
                "combinado_pct": 0.35,
            },
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["regime"] == "URBANO"
    assert "URBANO" in body["premissa"]
    assert "LUOS" in body["origem_lote"]
    # base combinada → 65% independente da área (não-regressão do motor)
    assert body["loteamento"]["pct_aproveitamento"] == 0.65
    assert body["desmembramento"] is not None


# ---------- Critério 7: regime obrigatório ----------
def test_sem_regime_422(client, malha):
    malha(MALHA_BOCAINA)
    aid = _post(client, [RET_BOCAINA]).json()["analise_id"]
    r = client.post(f"/api/analises/{aid}/aproveitamento", json={"lote_min_m2": 200})
    assert r.status_code == 422
    assert r.json()["erro"] == "regime_obrigatorio"


# ---------- Critério 8: proveniência completa ----------
def test_proveniencia_completa(client, malha, fmp):
    malha(MALHA_BOCAINA)
    fmp({"3506607": 20_000})
    aid = _post(client, [RET_BOCAINA])
    jur = aid.json()["jurisdicao"]
    assert "origem" in jur and jur["origem"] in ("detectado", "informado")
    r = client.post(
        f"/api/analises/{aid.json()['analise_id']}/aproveitamento",
        json={"regime": "RURAL"},
    )
    assert "premissa" in r.json() and r.json()["regime"] == "RURAL"


# ---------- Critério 9: determinismo ----------
def test_determinismo_rural(client, malha, fmp):
    malha(MALHA_BOCAINA)
    fmp({"3506607": 20_000})
    aid = _post(client, [RET_BOCAINA]).json()["analise_id"]
    a1 = client.post(f"/api/analises/{aid}/aproveitamento", json={"regime": "RURAL"})
    a2 = client.post(f"/api/analises/{aid}/aproveitamento", json={"regime": "RURAL"})
    assert a1.json() == a2.json()
