"""Fase 4.2 — split incorporador/terrenista + semáforo de leituras + linguagem §1-A.

Offline, determinístico. Reusa os Casos A (à vista) e B (financiado) das fases 4/4.1.
"""

import re

from tests.conftest import RET_RETANGULO, make_kmz


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


def _caso_a(**over):
    p = {
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
    p.update(over)
    return p


def _caso_b(**over):
    p = {
        "lotes": {"origem": "declarado", "n": 100},
        "preco_lote": 100000,
        "vendas": {
            "inicio_mes": 1, "duracao_meses": 10, "curva": "linear",
            "modo": "financiado", "entrada_pct": 0.15,
            "mesa": [{"participacao": 1.0, "prazo_meses": 60, "taxa_am": 0.01}],
        },
        "aquisicao": {"modo": "permuta_vgv", "pct": 0.20},
        "custos": _custos_zerados(),
        "tributos": {"aliquota_pct": 0},
    }
    p.update(over)
    return p


def _post(client, aid, premissas):
    return client.post(f"/api/analises/{aid}/financeira", json=premissas)


# ----- 1. Split-ouro (Caso A + terrenista 20%) -----
def test_split_caso_a(client, fonte_financeira):
    aid = _criar_analise(client)
    body = _post(client, aid, _caso_a()).json()
    inc = body["participantes"]["incorporador"]
    ter = body["participantes"]["terrenista"]
    assert inc["vgv"]["nominal"] == 8000000
    assert ter["vgv"]["nominal"] == 2000000
    assert ter["modo"] == "parceria_vgv"
    # Terrenista recebe 200.000/mês meses 1–10 (20% do bruto à vista).
    for l in ter["fluxo"]:
        if 1 <= l["mes"] <= 10:
            assert l["entradas"] == 200000
    # Resultado do incorporador = Caso A (custos 100% nele).
    assert inc["resultado_nominal"] == 3375600
    # Σ dos dois fluxos de entradas = recebimento total do empreendimento.
    soma_inc = sum(l["entradas"] for l in inc["fluxo"])
    soma_ter = sum(l["entradas"] for l in ter["fluxo"])
    assert abs((soma_inc + soma_ter) - 10000000) <= 0.01


# ----- 2. Split no financiado (Caso B + 20%) -----
def test_split_caso_b_financiado(client, fonte_financeira):
    aid = _criar_analise(client)
    body = _post(client, aid, _caso_b()).json()
    inc = body["participantes"]["incorporador"]
    ter = body["participantes"]["terrenista"]
    # Terrenista leva 20% do nominal E 20% da receita financeira (pro-rata).
    assert ter["vgv"]["nominal"] == 2000000
    assert abs(ter["vgv"]["receita_financeira"] - 0.20 * 2844668.32) <= 0.10
    assert abs(inc["vgv"]["receita_financeira"] - 0.80 * 2844668.32) <= 0.10
    # Recebimento mês 30: terrenista = 20% de 189.077,81.
    m30 = next(l for l in ter["fluxo"] if l["mes"] == 30)
    assert abs(m30["entradas"] - 0.20 * 189077.81) <= 0.01


# ----- 3. permuta_lotes -----
def test_split_permuta_lotes(client, fonte_financeira):
    aid = _criar_analise(client)
    p = _caso_a(aquisicao={"modo": "permuta_lotes", "n": 20})
    body = _post(client, aid, p).json()
    ter = body["participantes"]["terrenista"]
    assert ter["modo"] == "permuta_lotes"
    assert ter["vgv"]["nominal"] == 2000000  # 20 lotes × 100.000
    # Terrenista recebe a venda dos 20 lotes pela mesma curva (à vista) → 200.000/mês 1–10.
    m1 = next(l for l in ter["fluxo"] if l["mes"] == 1)
    assert m1["entradas"] == 200000
    # VGV exibido equivale a ~20% do total (vendaveis 80 + 20).
    assert abs(ter["pct"] - 0.20) < 0.001


# ----- 4. compra → terrenista null -----
def test_compra_terrenista_null(client, fonte_financeira):
    aid = _criar_analise(client)
    p = _caso_a(aquisicao={"modo": "compra", "valor": 1500000, "condicao": "avista", "inicio_mes": 0})
    body = _post(client, aid, p).json()
    assert body["participantes"]["terrenista"] is None
    # Pagamento do terreno aparece nas saídas (bloco aquisicao).
    assert any(b["bloco"] == "aquisicao" for b in body["blocos"])


# ----- 5. Preço por m² -----
def test_preco_por_m2(client, fonte_financeira):
    aid = _criar_analise(client)
    p = _caso_a()
    del p["preco_lote"]
    p["preco_m2"] = 350
    p["area_lote_m2"] = 263.21
    body = _post(client, aid, p).json()
    # 350 × 263,21 = 92.123,50 por lote → VGV bruto = 100 × 92.123,50.
    assert body["vgv"]["bruto"] == round(100 * 92123.50, 2)


# ----- 6. leituras[] determinísticas + anti-"viável" -----
def test_leituras_favoravel_e_slots_fase5(client, fonte_financeira):
    aid = _criar_analise(client)
    body = _post(client, aid, _caso_a()).json()
    leituras = {l["chave"]: l for l in body["leituras"]}
    assert leituras["resultado_nominal"]["status"] == "favoravel"
    # Margem 42,19% ≥ referência 20% → favoravel.
    assert leituras["margem"]["status"] == "favoravel"
    for chave in ("vpl", "tir", "payback"):
        assert leituras[chave]["status"] == "pendente"
    # Capital não informado → leitura de exposição omitida.
    assert "exposicao_vs_capital" not in leituras


def test_leitura_margem_atencao_e_capital(client, fonte_financeira):
    aid = _criar_analise(client)
    p = _caso_a(margem_referencia_pct=0.60, capital_disponivel=100000)  # exposição 390k > 100k
    body = _post(client, aid, p).json()
    leituras = {l["chave"]: l for l in body["leituras"]}
    assert leituras["margem"]["status"] == "atencao"
    assert leituras["exposicao_vs_capital"]["status"] == "atencao"
    assert "funding" in leituras["exposicao_vs_capital"]["texto"]


def test_resultado_desfavoravel(client, fonte_financeira):
    aid = _criar_analise(client)
    # Compra cara → resultado negativo → desfavoravel (nunca "inviável").
    p = _caso_a(aquisicao={"modo": "compra", "valor": 20000000, "condicao": "avista", "inicio_mes": 0})
    body = _post(client, aid, p).json()
    leituras = {l["chave"]: l for l in body["leituras"]}
    assert leituras["resultado_nominal"]["status"] == "desfavoravel"


def test_nenhuma_palavra_viavel_na_resposta(client, fonte_financeira):
    """Critério 6 (§1-A): o backend NUNCA emite 'viável'/'inviável' como veredito."""
    aid = _criar_analise(client)
    for premissas in (_caso_a(), _caso_b(), _caso_a(aquisicao={"modo": "compra", "valor": 20000000})):
        texto = str(_post(client, aid, premissas).json()).lower()
        assert not re.search(r"\binvi[aá]vel\b", texto)
        assert not re.search(r"\bvi[aá]vel\b", texto)


# ----- 8. Contrato preservado: um único POST, sem VPL/TIR calculado -----
def test_sem_vpl_tir_calculado(client, fonte_financeira):
    aid = _criar_analise(client)
    body = _post(client, aid, _caso_a()).json()
    # Os slots existem como "pendente", mas não há indicador econômico calculado.
    assert "vpl" not in body["indicadores"]
    assert all(l["status"] == "pendente" for l in body["leituras"] if l["chave"] in ("vpl", "tir", "payback"))


# ----- 10. Determinismo -----
def test_determinismo_participantes(client, fonte_financeira):
    aid = _criar_analise(client)
    a = _post(client, aid, _caso_b()).json()
    b = _post(client, aid, _caso_b()).json()
    assert a == b
