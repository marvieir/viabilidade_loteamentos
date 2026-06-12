"""Fase 5 — Econômica: valores-ouro sobre o fluxo do Caso Fechado A (spec §6).

Offline, determinístico. O fluxo é RELIDO da persistência da Financeira (Caso A executado
via API antes); unidades do motor (TIR trivial/degenerada, paybacks sintéticos) são puras.
"""

import re

import pytest

from app.core import economica as motor
from app.models.schemas import PremissasEconomicaIn
from tests.conftest import RET_RETANGULO, make_kmz

# Fluxo do Caso Fechado A (spec §6): m0=−390.000; m1–4=+152.560; m5–6=+192.560; m7–10=+692.560
FLUXO_A = (
    [(0, -390000.0)]
    + [(m, 152560.0) for m in range(1, 5)]
    + [(m, 192560.0) for m in range(5, 7)]
    + [(m, 692560.0) for m in range(7, 11)]
)


def _criar_analise(client):
    r = client.post(
        "/api/analises",
        files={"kmz": ("g.kmz", make_kmz([RET_RETANGULO]), "application/vnd.google-earth.kmz")},
    )
    assert r.status_code == 200
    return r.json()["analise_id"]


def _caso_a():
    return {
        "lotes": {"origem": "declarado", "n": 100},
        "preco_lote": 100000,
        "vendas": {"inicio_mes": 1, "duracao_meses": 10, "curva": "linear", "modo": "avista"},
        "aquisicao": {"modo": "permuta_vgv", "pct": 0.20},
        "custos": {
            "urbanizacao": {"base": "por_lote", "valor": 30000, "inicio_mes": 1, "duracao_meses": 6},
            "projetos_aprovacao": {"valor": 280000, "mes": 0},
            "topografia": {"valor": 100000, "mes": 0},
            "administracao_mensal": 10000,
            "marketing": {"pct_vgv_proprio": 0.02, "inicio_mes": 1, "duracao_meses": 4},
            "comissao_pct": 0.05,
        },
        "tributos": {"regime": "presumido", "aliquota_pct": 0.0593},
    }


@pytest.fixture
def analise_com_financeira(client, fonte_financeira, fonte_economica):
    """Análise com o Caso A executado e persistido — a Econômica relê esse fluxo."""
    aid = _criar_analise(client)
    r = client.post(f"/api/analises/{aid}/financeira", json=_caso_a())
    assert r.status_code == 200
    return aid


def _post_eco(client, aid, **body):
    return client.post(f"/api/analises/{aid}/economica", json=body)


# ----- 1. Conversão da TMA -----
def test_conversao_tma(client, analise_com_financeira):
    assert abs(motor.tma_mensal(0.12) - 0.0094887929) <= 1e-9
    body = _post_eco(client, analise_com_financeira, tma_aa_real=0.12).json()
    assert abs(body["tma"]["mensal"] - 0.0094887929) <= 1e-9
    assert body["tma"]["origem"] == "declarado"


# ----- 2. VPL-ouro + consistência 4×5 a 0% -----
def test_vpl_ouro(client, analise_com_financeira):
    body = _post_eco(client, analise_com_financeira, tma_aa_real=0.12).json()
    assert abs(body["vpl"]["valor"] - 3128359.33) <= 0.01
    assert body["vpl"]["valor_fmt"] == "R$ 3.128.359,33"
    p0 = next(p for p in body["curva_vpl_tma"] if p["tma_aa"] == 0.0)
    assert abs(p0["vpl"] - 3375600.00) <= 0.01  # VPL@0% = resultado nominal da 4


# ----- 3. TIR-ouro (bissecção) -----
def test_tir_ouro(client, analise_com_financeira):
    body = _post_eco(client, analise_com_financeira, tma_aa_real=0.12).json()
    tir = body["tir"]
    assert abs(tir["mensal"] - 0.49477101) <= 1e-6
    assert tir["status"] == "unica"
    assert motor.trocas_de_sinal(FLUXO_A) == 1
    assert abs(motor.vpl(FLUXO_A, tir["mensal"])) <= 0.01  # VPL@TIR = 0
    assert tir["aa"] is not None and tir["aa_fmt"] is not None  # anualizada exibida
    assert any("exposição" in a for a in tir["avisos"])  # TIR explosiva (>200% a.a.)


# ----- 3b. Horizonte longo (regressão do ZeroDivisionError no extremo do bracket) -----
def test_tir_horizonte_longo_nao_estoura():
    """Fluxo financiado real chega a ~180 meses; no extremo i=−0,99 do bracket a base
    0,01 faz 0,01**m underflow→0.0 (m≥162). vpl guardado não pode lançar ZeroDivisionError."""
    fluxo = [(0, -2_000_000.0)] + [(m, 25_000.0) for m in range(1, 181)]  # horizonte 180
    assert motor.trocas_de_sinal(fluxo) == 1
    tir, status = motor.tir_bissecao(fluxo)  # não pode estourar
    assert status == "unica" and tir is not None
    assert abs(motor.vpl(fluxo, tir)) <= 1.0  # raiz coerente
    out = motor.avaliar(
        fluxo, _acum(fluxo), PremissasEconomicaIn(tma_aa_real=0.12), proveniencia="t"
    )
    assert out.vpl.valor == out.vpl.valor  # não é NaN
    assert out.tir.status == "unica"


# ----- 4. TIR trivial -----
def test_tir_trivial():
    tir, status = motor.tir_bissecao([(0, -1000.0), (1, 1100.0)])
    assert status == "unica"
    assert abs(tir - 0.10) <= 1e-9


# ----- 5. TIR degenerada -----
def test_tir_degenerada_sem_inversao():
    tir, status = motor.tir_bissecao([(0, 100.0), (1, 200.0)])
    assert tir is None and status == "indefinida"


def test_tir_multipla_possivel():
    # 2 trocas de sinal: − + − (fluxo não-convencional)
    fluxo = [(0, -1000.0), (1, 2500.0), (2, -1560.0)]
    tir, status = motor.tir_bissecao(fluxo)
    assert status == "multipla_possivel"
    out = motor.avaliar(
        fluxo, _acum(fluxo), PremissasEconomicaIn(tma_aa_real=0.12), proveniencia="t"
    )
    assert out.tir.status == "multipla_possivel"
    assert any("prefira o VPL" in a for a in out.tir.avisos)


def _acum(fluxo):
    ac, out = 0.0, []
    for m, v in sorted(fluxo):
        ac += v
        out.append((m, ac))
    return out


# ----- 6. Paybacks -----
def test_paybacks_ouro(client, analise_com_financeira):
    body = _post_eco(client, analise_com_financeira, tma_aa_real=0.12).json()
    assert body["payback"]["simples_mes"] == 3
    assert body["payback"]["descontado_mes"] == 3


def test_payback_nao_recuperado():
    fluxo = [(0, -1000.0), (1, 100.0), (2, 100.0)]
    out = motor.avaliar(
        fluxo, _acum(fluxo), PremissasEconomicaIn(tma_aa_real=0.12), proveniencia="t"
    )
    assert out.payback.simples_mes is None and out.payback.descontado_mes is None
    assert any("não recuperado no horizonte" in a for a in out.payback.avisos)


def test_payback_renegativa_aviso():
    # Recupera no mês 1 e volta a ficar negativo no mês 2.
    fluxo = [(0, -100.0), (1, 200.0), (2, -300.0), (3, 400.0)]
    out = motor.avaliar(
        fluxo, _acum(fluxo), PremissasEconomicaIn(tma_aa_real=0.12), proveniencia="t"
    )
    assert out.payback.simples_mes == 1
    assert any("volta a ficar negativo" in a for a in out.payback.avisos)


# ----- 7. Exposição descontada + IL -----
def test_exposicao_e_il(client, analise_com_financeira):
    body = _post_eco(client, analise_com_financeira, tma_aa_real=0.12).json()
    assert body["exposicao_descontada"]["valor"] == -390000.00
    assert body["exposicao_descontada"]["mes"] == 0
    assert abs(body["indice_lucratividade"] - 8.0214) <= 0.001


# ----- 8. Curva VPL×TMA -----
def test_curva_default_41_pontos(client, analise_com_financeira):
    body = _post_eco(client, analise_com_financeira, tma_aa_real=0.12).json()
    curva = body["curva_vpl_tma"]
    assert len(curva) == 41  # 0–40% a.a., passo 1 p.p.
    assert abs(curva[0]["vpl"] - 3375600.00) <= 0.01
    assert curva[-1]["tma_aa"] == 0.40
    assert abs(curva[-1]["vpl"] - 2693174.29) <= 0.01
    assert all("vpl_fmt" in p for p in curva)


def test_curva_range_custom_e_passo_invalido(client, analise_com_financeira):
    body = _post_eco(
        client, analise_com_financeira, tma_aa_real=0.12,
        curva={"min_aa": 0.05, "max_aa": 0.15, "passo_pp": 5},
    ).json()
    assert [p["tma_aa"] for p in body["curva_vpl_tma"]] == [0.05, 0.10, 0.15]
    r = _post_eco(
        client, analise_com_financeira, tma_aa_real=0.12,
        curva={"min_aa": 0.0, "max_aa": 0.40, "passo_pp": 0},
    )
    assert r.status_code == 422


# ----- 9. Convenção + §1-A -----
def test_convencao_e_linguagem(client, analise_com_financeira):
    body = _post_eco(client, analise_com_financeira, tma_aa_real=0.12).json()
    assert "Moeda constante" in body["convencao"]
    assert any("INCC" in a for a in body["avisos"])
    assert any("juros REAL" in a for a in body["avisos"])
    chaves = {l["chave"] for l in body["leituras"]}
    assert {"vpl", "tir", "payback"} <= chaves
    assert any("sob as premissas declaradas" in l["texto"] for l in body["leituras"])
    texto = str(body).lower()
    assert not re.search(r"\binvi[aá]vel\b", texto)
    assert not re.search(r"\bvi[aá]vel\b", texto)


def test_leitura_vpl_desfavoravel():
    # TMA acima da TIR → VPL negativo → "destrói valor", nunca "inviável".
    fluxo = [(0, -1000.0), (12, 1050.0)]
    out = motor.avaliar(
        fluxo, _acum(fluxo), PremissasEconomicaIn(tma_aa_real=0.20), proveniencia="t"
    )
    vpl_l = next(l for l in out.leituras if l.chave == "vpl")
    assert vpl_l.status == "desfavoravel"
    assert "destrói valor" in vpl_l.texto


# ----- 10. Degradação + determinismo + persistência -----
def test_sem_financeira_409(client, fonte_financeira, fonte_economica):
    aid = _criar_analise(client)
    r = _post_eco(client, aid, tma_aa_real=0.12)
    assert r.status_code == 409
    assert "Execute a Financeira primeiro" in r.json()["detail"]


def test_sem_tma_422(client, analise_com_financeira):
    r = client.post(f"/api/analises/{analise_com_financeira}/economica", json={})
    assert r.status_code == 422  # TMA obrigatória — pede, não chuta


def test_determinismo(client, analise_com_financeira):
    a = _post_eco(client, analise_com_financeira, tma_aa_real=0.12).json()
    b = _post_eco(client, analise_com_financeira, tma_aa_real=0.12).json()
    assert a == b


def test_get_persistido_e_404(client, fonte_financeira, fonte_economica):
    aid = _criar_analise(client)
    assert client.get(f"/api/analises/{aid}/economica").status_code == 404
    client.post(f"/api/analises/{aid}/financeira", json=_caso_a())
    posted = _post_eco(client, aid, tma_aa_real=0.12).json()
    assert client.get(f"/api/analises/{aid}/economica").json() == posted


def test_analise_inexistente_404(client, fonte_financeira, fonte_economica):
    assert _post_eco(client, "nao-existe", tma_aa_real=0.12).status_code == 404
