"""Fase 4.1 — venda financiada (PRICE) + correções de UX. Valores-ouro verificados.

Caso Fechado B: 100 lotes × 100.000, vendas 10/mês meses 1–10, financiado 100% num único
perfil (60×, 1% a.m., entrada 15%), permuta 0, inadimplência 0, custos/tributo zerados.
"""

import pytest

from tests.conftest import RET_RETANGULO, make_kmz

from app.core.financeira import pmt_price


def _criar_analise(client):
    r = client.post(
        "/api/analises",
        files={"kmz": ("g.kmz", make_kmz([RET_RETANGULO]), "application/vnd.google-earth.kmz")},
    )
    assert r.status_code == 200
    return r.json()["analise_id"]


def _custos_zerados():
    return {
        "urbanizacao": {"base": "por_lote", "valor": 0},
        "projetos_aprovacao": {"valor": 0, "mes": 0},
        "topografia": {"valor": 0, "mes": 0},
        "administracao_mensal": 0,
        "marketing": {"pct_vgv_proprio": 0},
        "comissao_pct": 0,
    }


def _premissas_caso_b(**over):
    p = {
        "lotes": {"origem": "declarado", "n": 100},
        "preco_lote": 100000,
        "vendas": {
            "inicio_mes": 1, "duracao_meses": 10, "curva": "linear",
            "modo": "financiado", "entrada_pct": 0.15,
            "mesa": [{"participacao": 1.0, "prazo_meses": 60, "taxa_am": 0.01}],
        },
        "aquisicao": {"modo": "nenhuma"},
        "custos": _custos_zerados(),
        "tributos": {"aliquota_pct": 0},
    }
    p.update(over)
    return p


def _post(client, aid, premissas):
    return client.post(f"/api/analises/{aid}/financeira", json=premissas)


def _linha(body, mes):
    return next(l for l in body["fluxo"] if l["mes"] == mes)


# ----- 1. PRICE-ouro unitário -----
def test_pmt_price_ouro():
    pmt = pmt_price(85000, 0.01, 60)
    assert abs(pmt - 1890.78) <= 0.01
    assert abs(60 * pmt - 113446.68) <= 0.01
    assert abs(60 * pmt - 85000 - 28446.68) <= 0.01  # receita financeira do lote
    assert abs(15000 + 60 * pmt - 128446.68) <= 0.01  # recebimento total do lote


def test_pmt_price_taxa_zero_e_validacoes():
    assert pmt_price(85000, 0.0, 60) == pytest.approx(85000 / 60)
    from app.core.financeira import CurvaInvalida

    with pytest.raises(CurvaInvalida):
        pmt_price(85000, 0.01, 0)
    with pytest.raises(CurvaInvalida):
        pmt_price(85000, -0.01, 60)


# ----- 2. Caso Fechado B (agregado) -----
def test_caso_b_vgv_e_receita_financeira(client, fonte_financeira):
    aid = _criar_analise(client)
    body = _post(client, aid, _premissas_caso_b()).json()
    assert body["vgv"]["bruto"] == 10000000  # nominal
    assert abs(body["vgv"]["receita_financeira"] - 2844668.32) <= 0.10
    assert abs(body["vgv"]["geral"] - 12844668.32) <= 0.10
    assert body["vgv"]["proprio"] == 10000000  # permuta 0


def test_caso_b_recebimento_mes_30_e_horizonte(client, fonte_financeira):
    aid = _criar_analise(client)
    body = _post(client, aid, _premissas_caso_b()).json()
    m30 = _linha(body, 30)
    # Regime pleno (10 safras ativas): só parcelas, sem entradas.
    assert m30["entradas"] == 189077.81
    assert m30["entradas_fmt"] == "R$ 189.077,81"
    # Entradas (15%) só nos meses de venda; mês 1 = 150.000 (sem parcela ainda).
    assert _linha(body, 1)["entradas"] == 150000
    # Última parcela: venda mês 10 + 60 parcelas = mês 70.
    assert body["indicadores"]["horizonte_meses"] == 70
    assert _linha(body, 70)["entradas"] > 0


def test_caso_b_consistencia_fluxo(client, fonte_financeira):
    """Σ fluxo.entradas == nominal + receita financeira (permuta 0, inad 0).

    Tolerância: a emissão mensal arredonda a centavos (contrato de moeda) e o pmt PRICE
    não é múltiplo exato de centavo → deriva de poucos centavos no Σ das linhas. O valor
    AUTORITATIVO da identidade é o agregado `vgv.geral` (calculado do fluxo cru, exato).
    """
    aid = _criar_analise(client)
    body = _post(client, aid, _premissas_caso_b()).json()
    soma = sum(l["entradas"] for l in body["fluxo"])
    assert abs(soma - body["vgv"]["geral"]) <= 0.50  # deriva de arredondamento mensal
    # fluxo de vendas soma o NOMINAL (≠ recebimento).
    soma_vendas = sum(fv["valor_nominal"] for fv in body["fluxo_vendas"])
    assert soma_vendas == 10000000


# ----- 3. Taxa 0 ≡ parcelado (equivalência) -----
def test_financiado_taxa_zero_equivale_a_parcelado(client, fonte_financeira):
    aid = _criar_analise(client)
    base = {
        "lotes": {"origem": "declarado", "n": 100},
        "preco_lote": 100000,
        "aquisicao": {"modo": "nenhuma"},
        "custos": {**_custos_zerados(), "comissao_pct": 0.05, "comissao_base": "venda"},
        "tributos": {"aliquota_pct": 0.0593},
    }
    parcelado = dict(base)
    parcelado["vendas"] = {
        "inicio_mes": 1, "duracao_meses": 10, "curva": "linear",
        "modo": "parcelado", "entrada_pct": 0.15, "n_parcelas": 60,
    }
    financiado = dict(base)
    financiado["vendas"] = {
        "inicio_mes": 1, "duracao_meses": 10, "curva": "linear",
        "modo": "financiado", "entrada_pct": 0.15,
        "mesa": [{"participacao": 1.0, "prazo_meses": 60, "taxa_am": 0.0}],
    }
    a = _post(client, aid, parcelado).json()
    b = _post(client, aid, financiado).json()
    assert a["fluxo"] == b["fluxo"]
    assert a["indicadores"] == b["indicadores"]
    assert b["vgv"]["receita_financeira"] == 0  # taxa 0 → sem juros


# ----- 4. Mesa validada -----
def test_mesa_nao_soma_1_422(client, fonte_financeira):
    aid = _criar_analise(client)
    p = _premissas_caso_b()
    p["vendas"]["mesa"] = [
        {"participacao": 0.5, "prazo_meses": 60, "taxa_am": 0.01},
        {"participacao": 0.4, "prazo_meses": 30, "taxa_am": 0.005},
    ]
    r = _post(client, aid, p)
    assert r.status_code == 422
    assert "somar 1,0" in r.json()["detail"]


def test_mesa_prazo_invalido_422(client, fonte_financeira):
    aid = _criar_analise(client)
    p = _premissas_caso_b()
    p["vendas"]["mesa"] = [{"participacao": 1.0, "prazo_meses": 0, "taxa_am": 0.01}]
    r = _post(client, aid, p)
    assert r.status_code == 422


# ----- 5. Fluxo de vendas ≠ recebimento -----
def test_fluxo_vendas_separado(client, fonte_financeira):
    aid = _criar_analise(client)
    body = _post(client, aid, _premissas_caso_b()).json()
    assert len(body["fluxo_vendas"]) == 10
    fv1 = body["fluxo_vendas"][0]
    assert fv1["mes"] == 1
    assert fv1["lotes"] == 10
    assert fv1["valor_nominal"] == 1000000
    # No mês 1 vendeu 1M mas só recebeu a entrada (150k) — vendas ≠ caixa.
    assert _linha(body, 1)["entradas"] == 150000


# ----- 6. Inadimplência segura (a lição do −19M) -----
def test_inadimplencia_alta_sem_confirmacao_422(client, fonte_financeira):
    aid = _criar_analise(client)
    p = _premissas_caso_b(inadimplencia_pct=0.5)
    r = _post(client, aid, p)
    assert r.status_code == 422
    assert "confirme explicitamente" in r.json()["detail"]


def test_inadimplencia_alta_confirmada_roda_com_aviso(client, fonte_financeira):
    aid = _criar_analise(client)
    p = _premissas_caso_b(inadimplencia_pct=0.5, confirmar_inadimplencia_alta=True)
    r = _post(client, aid, p)
    assert r.status_code == 200
    assert any("Inadimplência ALTA" in a for a in r.json()["avisos"])


def test_inadimplencia_total_gera_alerta_critico(client, fonte_financeira):
    aid = _criar_analise(client)
    p = _premissas_caso_b(inadimplencia_pct=1.0, confirmar_inadimplencia_alta=True)
    body = _post(client, aid, p).json()
    assert body["alerta_critico"] is not None
    assert "TODAS as entradas são zero" in body["alerta_critico"]


def test_fluxo_normal_sem_alerta_critico(client, fonte_financeira):
    aid = _criar_analise(client)
    body = _post(client, aid, _premissas_caso_b()).json()
    assert body["alerta_critico"] is None


# ----- 7. Comissão sobre recebimento (financiado) -----
def test_comissao_sobre_recebimento_no_financiado(client, fonte_financeira):
    aid = _criar_analise(client)
    p = _premissas_caso_b()
    p["custos"] = {**_custos_zerados(), "comissao_pct": 0.05}  # base default por modo
    body = _post(client, aid, p).json()
    com = next(b for b in body["blocos"] if b["bloco"] == "comissao")
    assert "recebimento" in com["proveniencia"]
    # 5% × recebimento total (12.844.668,32) ≈ 642.233,42 — diluída pela carteira.
    assert abs(com["total"] - 642233.42) <= 0.50
    # Mês 30: comissão = 5% × 189.077,81.
    assert _linha(body, 30)["saidas"] == 9453.89


# ----- 8. Não-regressão (Caso A byte a byte coberto em test_financeira.py) -----
def test_avista_sem_receita_financeira(client, fonte_financeira):
    aid = _criar_analise(client)
    p = _premissas_caso_b()
    p["vendas"] = {"inicio_mes": 1, "duracao_meses": 10, "curva": "linear", "modo": "avista"}
    body = _post(client, aid, p).json()
    assert body["vgv"]["receita_financeira"] == 0
    assert body["vgv"]["geral"] == body["vgv"]["bruto"]


# ----- 9. Resumo anual consistente -----
def test_resumo_anual_consistente(client, fonte_financeira):
    aid = _criar_analise(client)
    body = _post(client, aid, _premissas_caso_b()).json()
    anual = body["fluxo_resumo_anual"]
    assert anual[0]["ano"] == 1
    assert len(anual) == 6  # meses 0–70 → anos 1–6
    soma_liquido = round(sum(a["liquido"] for a in anual), 2)
    assert abs(soma_liquido - body["fluxo"][-1]["acumulado"]) <= 0.02
    assert anual[-1]["acumulado"] == body["fluxo"][-1]["acumulado"]


# ----- 10. Proveniência/avisos -----
def test_mesa_default_rotulada_tiv(client, fonte_financeira):
    aid = _criar_analise(client)
    p = _premissas_caso_b()
    del p["vendas"]["mesa"]  # sem mesa → default ROTULADO
    body = _post(client, aid, p).json()
    assert any("TIV 5.0" in a for a in body["avisos"])
    assert any("juros" in a for a in body["avisos"])  # tributação sobre juros: contador


def test_aviso_juros_presente_no_financiado(client, fonte_financeira):
    aid = _criar_analise(client)
    body = _post(client, aid, _premissas_caso_b()).json()
    assert any("Receita financeira" in a and "contador" in a for a in body["avisos"])
