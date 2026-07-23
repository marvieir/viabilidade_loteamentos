"""Critérios de aceite da Fase 1.7 — jurisdição real + regime + rural (FMP).

Offline e determinístico: malha municipal e tabela FMP são injetadas (stubs), sem rede.
Valor-ouro: Bocaina rural = 54 parcelas (109,41 ha ÷ 2 ha).
"""

from shapely.geometry import Polygon

from app.core import aproveitamento as motor
from app.core.fmp import (
    FMP_ORIGEM_DEFAULT,
    FMP_ORIGEM_INFORMADO,
    FMP_ORIGEM_TABELA,
)
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

# Borda/gap de generalização: município que TOCA a gleba da Bocaina mas NÃO contém o
# centróide dela (cobre só a faixa oeste, x ≤ −45,722; centróide ≈ −45,720).
BORDA = Municipio(cod_ibge="3500003", municipio="Município Borda", uf="SP")
BORDA_POLY = Polygon(
    [(-45.730, -22.650), (-45.722, -22.650), (-45.722, -22.630), (-45.730, -22.630)]
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


# ---------- Critério 2: correção via override (pela LISTA LEVE, não a malha) ----------
def test_override_municipio(client, malha, lista):
    malha([*MALHA_BOCAINA, (VIZINHA, VIZINHA_POLY)])
    lista([
        {"cod_ibge": "3506607", "municipio": "Bocaina", "uf": "SP"},
        {"cod_ibge": "3500109", "municipio": "Vizinha", "uf": "SP"},
    ])
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


# ---------- Critério 4: divisa = candidatos com % de área, default no maior ----------
def test_cruza_divisa(client, malha):
    malha([(MUN_A, MUN_A_POLY), (MUN_B, MUN_B_POLY)])
    jur = _post(client, [RET_DIVISA]).json()["jurisdicao"]
    assert jur["cruza_divisa"] is True
    cands = jur["candidatos"]
    cods = {m["cod_ibge"] for m in cands}
    assert cods == {"3500001", "3500002"}
    # % de área presente, ordenado desc; default (município principal) = o de maior área.
    assert all("pct_area" in m for m in cands)
    assert cands[0]["pct_area"] >= cands[1]["pct_area"]
    assert jur["cod_ibge"] == cands[0]["cod_ibge"]
    # gleba inteiramente dentro de A∪B → soma ≈ 100%.
    assert abs(sum(m["pct_area"] for m in cands) - 100.0) < 1.0
    # A (faixa 0,020°) > B (faixa 0,015°) → A é o principal.
    assert jur["cod_ibge"] == "3500001"


# ---------- Critério 5: borda/gap → fallback nearest, origem "aproximado" ----------
def test_borda_nearest_aproximado(client, malha):
    malha([(BORDA, BORDA_POLY)])  # toca a gleba, mas não contém o centróide
    jur = _post(client, [RET_BOCAINA]).json()["jurisdicao"]
    assert jur["municipio"] == "Município Borda"
    assert jur["origem"] == "aproximado"
    assert jur["cruza_divisa"] is False


# ---------- Gleba fora de tudo → não resolvido, sem inventar ----------
def test_fora_da_malha(client, malha):
    malha([(VIZINHA, VIZINHA_POLY)])  # não toca a gleba da Bocaina
    jur = _post(client, [RET_BOCAINA]).json()["jurisdicao"]
    assert jur["municipio"] is None
    assert jur["cod_ibge"] is None
    assert jur["cruza_divisa"] is False


# ---------- Critério 6: RURAL FMP — VALOR-OURO (FMP do município, não 2 ha chumbado) ----------
def test_rural_golden_motor():
    """Valor-ouro direto no motor: floor(109,41 ha ÷ 2 ha) = 54 parcelas."""
    r = motor.aproveitamento_rural(area_total=1_094_111.1, fmp_m2=20_000)
    assert r["n_parcelas"] == 54
    assert r["fmp_m2"] == 20_000
    assert "5.868" in r["proveniencia"]  # FMP por município — Lei 5.868/72
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
    assert body["rural"]["fmp_origem"] == FMP_ORIGEM_TABELA


def test_rural_fmp_no_corpo(client, malha, fmp):
    """FMP informada no corpo tem prioridade e é rotulada como informada."""
    malha(MALHA_BOCAINA)
    fmp({})  # tabela vazia: garante que o valor veio do corpo
    aid = _post(client, [RET_BOCAINA]).json()["analise_id"]
    r = client.post(
        f"/api/analises/{aid}/aproveitamento",
        json={"regime": "RURAL", "fmp_m2": 20_000},
    )
    assert r.status_code == 200, r.text
    assert r.json()["rural"]["n_parcelas"] == 54
    assert r.json()["rural"]["fmp_origem"] == FMP_ORIGEM_INFORMADO


# ---------- Critério 7: FMP ausente → default 2 ha + aviso (não bloqueia) ----------
def test_rural_fmp_ausente_default(client, malha, fmp):
    """Município sem FMP na tabela e sem fmp_m2 → aplica piso de 2 ha e rotula a origem."""
    malha(MALHA_BOCAINA)
    fmp({})  # tabela vazia
    aid = _post(client, [RET_BOCAINA]).json()["analise_id"]
    r = client.post(
        f"/api/analises/{aid}/aproveitamento", json={"regime": "RURAL"}
    )
    assert r.status_code == 200, r.text
    rural = r.json()["rural"]
    assert rural["fmp_m2"] == 20_000  # piso legal de 2 ha
    assert rural["n_parcelas"] == 54
    assert rural["fmp_origem"] == FMP_ORIGEM_DEFAULT
    assert "CCIR" in rural["fmp_origem"]


# ---------- Critério 6: URBANO — área aproveitável + teto de lotes + premissa/origem ----------
def test_urbano_premissa_e_origem(client, malha):
    malha(MALHA_BOCAINA)
    aid = _post(client, [RET_BOCAINA]).json()["analise_id"]
    r = client.post(
        f"/api/analises/{aid}/aproveitamento",
        json={"regime": "URBANO", "modalidade": "loteamento_aberto", "lote_min_m2": 200},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["regime"] == "URBANO"
    assert "URBANO" in body["premissa"]
    assert "LUOS" in body["origem_lote"]
    # Sem fonte de restrição, aproveitável = total → teto = total / lote_min.
    assert body["area_aproveitavel_m2"] > 0
    assert body["n_lotes_teto"] == int(body["area_aproveitavel_m2"] // 200)
    assert body["pct_sobre_total"] == 1.0  # nada descontado sem fonte
    assert "vias e doação" in body["ressalva_urbano"].lower()


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


# ---------- Busca por nome (lista leve, tolerante a acento/caixa) ----------
def test_busca_municipio_por_nome(client):
    # busca "bocaina" sem acento/caixa qualquer, sobre a lista leve embarcada
    r = client.get("/api/municipios", params={"q": "BoCaInA"})
    assert r.status_code == 200, r.text
    nomes = [m["municipio"] for m in r.json()]
    assert "Bocaina" in nomes
    # o código é resolvido internamente, mas vem no payload para o override
    assert any(m["cod_ibge"] == "3506607" for m in r.json())


# ---------- Critério 2: busca por nome funciona SEM a malha (plano B sobrevive) ----------
def test_busca_por_nome_sem_malha(client_producao, lista):
    lista([{"cod_ibge": "3550605", "municipio": "São Roque", "uf": "SP"}])
    r = client_producao.get("/api/municipios", params={"q": "sao roque"})
    assert r.status_code == 200, r.text
    nomes = [m["municipio"] for m in r.json()]
    assert "São Roque" in nomes


# ---------- Modalidade obrigatória no urbano ----------
def test_urbano_sem_lote_min_422(client, malha):
    # Modalidade virou rótulo opcional; o que URBANO exige agora é o lote mínimo.
    malha(MALHA_BOCAINA)
    aid = _post(client, [RET_BOCAINA]).json()["analise_id"]
    r = client.post(
        f"/api/analises/{aid}/aproveitamento",
        json={"regime": "URBANO", "modalidade": "loteamento_aberto"},
    )
    assert r.status_code == 422
    assert r.json()["erro"] == "parametros_urbano_incompletos"


def test_urbano_sem_modalidade_ok(client, malha):
    # Sem modalidade, mas com lote mínimo → 200 (modalidade é só rótulo na premissa).
    malha(MALHA_BOCAINA)
    aid = _post(client, [RET_BOCAINA]).json()["analise_id"]
    r = client.post(
        f"/api/analises/{aid}/aproveitamento",
        json={"regime": "URBANO", "lote_min_m2": 200},
    )
    assert r.status_code == 200, r.text
    assert r.json()["n_lotes_teto"] > 0


# ---------- Critério 9: determinismo ----------
def test_determinismo_rural(client, malha, fmp):
    malha(MALHA_BOCAINA)
    fmp({"3506607": 20_000})
    aid = _post(client, [RET_BOCAINA]).json()["analise_id"]
    a1 = client.post(f"/api/analises/{aid}/aproveitamento", json={"regime": "RURAL"})
    a2 = client.post(f"/api/analises/{aid}/aproveitamento", json={"regime": "RURAL"})
    assert a1.json() == a2.json()
