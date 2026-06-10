"""Fase 4 — Financeira: Caso Fechado A (valores-ouro) + variações. Aritmética pura, offline.

Caso Fechado A: 100 lotes × R$ 100.000; permuta_vgv 20%; vendas 10/mês meses 1–10 à vista;
comissão 5% s/ bruto; tributo 5,93% s/ receita própria; urbanização R$ 30.000/lote linear
meses 1–6; projetos 280.000 + topografia 100.000 no mês 0; administração 10.000/mês (0–10);
marketing 2% do VGV próprio linear meses 1–4.
"""

from tests.conftest import RET_RETANGULO, make_kmz


def _criar_analise(client):
    r = client.post(
        "/api/analises",
        files={"kmz": ("g.kmz", make_kmz([RET_RETANGULO]), "application/vnd.google-earth.kmz")},
    )
    assert r.status_code == 200
    return r.json()["analise_id"]


def _premissas_caso_a(**over):
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


def _post(client, aid, premissas):
    return client.post(f"/api/analises/{aid}/financeira", json=premissas)


def _linha(body, mes):
    return next(l for l in body["fluxo"] if l["mes"] == mes)


# ----- 1 + 3: VGV e fluxo-ouro -----
def test_caso_a_vgv(client, fonte_financeira):
    aid = _criar_analise(client)
    body = _post(client, aid, _premissas_caso_a()).json()
    assert body["vgv"]["bruto"] == 10000000
    assert body["vgv"]["proprio"] == 8000000
    assert body["vgv"]["permuta"]["valor"] == 2000000
    assert body["vgv"]["bruto_fmt"] == "R$ 10.000.000,00"


def test_caso_a_fluxo_ouro_mes_a_mes(client, fonte_financeira):
    aid = _criar_analise(client)
    body = _post(client, aid, _premissas_caso_a()).json()
    assert _linha(body, 0)["liquido"] == -390000
    for m in (1, 2, 3, 4):
        assert _linha(body, m)["liquido"] == 152560
    for m in (5, 6):
        assert _linha(body, m)["liquido"] == 192560
    for m in (7, 8, 9, 10):
        assert _linha(body, m)["liquido"] == 692560
    # Formatação no backend.
    assert _linha(body, 0)["liquido_fmt"] == "-R$ 390.000,00"
    assert _linha(body, 1)["saidas"] == 647440


def test_caso_a_indicadores(client, fonte_financeira):
    aid = _criar_analise(client)
    body = _post(client, aid, _premissas_caso_a()).json()
    ind = body["indicadores"]
    assert ind["resultado_nominal"] == 3375600
    assert ind["resultado_nominal_fmt"] == "R$ 3.375.600,00"
    assert abs(ind["margem_sobre_vgv_proprio"] - 0.421950) < 0.0001
    assert ind["exposicao_maxima"]["valor"] == -390000
    assert ind["exposicao_maxima"]["mes"] == 0
    assert ind["horizonte_meses"] == 10
    # Consistência interna: Σ liquido == acumulado final == VGV próprio − Σ saídas.
    soma = round(sum(l["liquido"] for l in body["fluxo"]), 2)
    assert soma == 3375600
    saidas = round(sum(b["total"] for b in body["blocos"]), 2)
    assert round(8000000 - saidas, 2) == 3375600


# ----- 4: origem dos lotes (§3.1) -----
def test_origem_diretriz_sem_aviso(client, fonte_financeira):
    aid = _criar_analise(client)
    p = _premissas_caso_a(lotes={"origem": "auto", "n_diretriz": 100, "n_teto": 163})
    body = _post(client, aid, p).json()
    assert body["caso_base"]["origem_lotes"] == "diretriz"
    assert body["caso_base"]["aviso_lotes"] is None
    assert body["indicadores"]["resultado_nominal"] == 3375600


def test_origem_teto_com_aviso(client, fonte_financeira):
    aid = _criar_analise(client)
    p = _premissas_caso_a(lotes={"origem": "auto", "n_teto": 100})
    body = _post(client, aid, p).json()
    assert body["caso_base"]["origem_lotes"] == "teto_fisico"
    assert "SUPERESTIMAR" in body["caso_base"]["aviso_lotes"]


def test_origem_declarado_sobrepoe(client, fonte_financeira):
    aid = _criar_analise(client)
    p = _premissas_caso_a(lotes={"origem": "declarado", "n": 100, "n_diretriz": 999})
    body = _post(client, aid, p).json()
    assert body["caso_base"]["origem_lotes"] == "declarado"
    assert body["caso_base"]["lotes"] == 100


# ----- 5: tributação = parâmetro -----
def test_tributo_zero_muda_so_o_bloco(client, fonte_financeira):
    aid = _criar_analise(client)
    p = _premissas_caso_a()
    p["tributos"] = {"aliquota_pct": 0.0}
    body = _post(client, aid, p).json()
    assert body["indicadores"]["resultado_nominal"] == 3850000
    assert all(b["bloco"] != "tributos" for b in body["blocos"])


def test_tributo_default_rotulado_sem_ret(client, fonte_financeira):
    aid = _criar_analise(client)
    # Sem informar tributos → usa o default 5,93% ROTULADO.
    p = _premissas_caso_a()
    del p["tributos"]
    body = _post(client, aid, p).json()
    trib = next(b for b in body["blocos"] if b["bloco"] == "tributos")
    assert "CONFIRME COM CONTADOR" in trib["proveniencia"].upper()
    assert "não é ret" in trib["proveniencia"].lower()


# ----- 6: parcelado desloca caixa -----
def test_parcelado_piora_exposicao(client, fonte_financeira):
    aid = _criar_analise(client)
    avista = _post(client, aid, _premissas_caso_a()).json()
    p = _premissas_caso_a()
    p["vendas"] = {
        "inicio_mes": 1, "duracao_meses": 10, "curva": "linear",
        "modo": "parcelado", "entrada_pct": 0.2, "n_parcelas": 4,
    }
    parc = _post(client, aid, p).json()
    # Mesma receita total própria (à vista e parcelado), caixa deslocado → exposição pior.
    assert parc["vgv"]["proprio"] == avista["vgv"]["proprio"]
    assert parc["indicadores"]["exposicao_maxima"]["valor"] < avista["indicadores"]["exposicao_maxima"]["valor"]


# ----- 7: permuta por lotes -----
def test_permuta_por_lotes(client, fonte_financeira):
    aid = _criar_analise(client)
    p = _premissas_caso_a(
        lotes={"origem": "declarado", "n": 100},
        aquisicao={"modo": "permuta_lotes", "n": 20},
    )
    body = _post(client, aid, p).json()
    assert body["caso_base"]["lotes_vendaveis"] == 80
    assert body["vgv"]["proprio"] == 8000000
    assert abs(body["vgv"]["permuta"]["pct"] - 0.20) < 0.001


# ----- 8: eficiência de projeto -----
def test_eficiencia_projeto(client, fonte_financeira):
    aid = _criar_analise(client)
    p = _premissas_caso_a(eficiencia_projeto_pct=0.9)
    body = _post(client, aid, p).json()
    assert body["caso_base"]["lotes_vendaveis"] == 90


# ----- 9: degradação honesta -----
def test_sem_preco_422(client, fonte_financeira):
    aid = _criar_analise(client)
    p = _premissas_caso_a()
    del p["preco_lote"]
    r = _post(client, aid, p)
    assert r.status_code == 422
    assert "preco_lote" in r.json()["detail"]


def test_curva_custom_nao_soma_1(client, fonte_financeira):
    aid = _criar_analise(client)
    p = _premissas_caso_a()
    p["vendas"] = {
        "inicio_mes": 1, "duracao_meses": 3, "curva": "custom",
        "curva_custom": [0.5, 0.3, 0.1], "modo": "avista",
    }
    r = _post(client, aid, p)
    assert r.status_code == 422
    assert "somar" in r.json()["detail"].lower()


def test_sem_lotes_422(client, fonte_financeira):
    aid = _criar_analise(client)
    p = _premissas_caso_a(lotes={"origem": "auto"})
    r = _post(client, aid, p)
    assert r.status_code == 422


# ----- 10: determinismo + persistência + sem VPL/TIR + não-regressão -----
def test_determinismo_e_persistencia(client, fonte_financeira):
    aid = _criar_analise(client)
    a = _post(client, aid, _premissas_caso_a()).json()
    b = _post(client, aid, _premissas_caso_a()).json()
    assert a == b
    g = client.get(f"/api/analises/{aid}/financeira")
    assert g.status_code == 200
    assert g.json()["indicadores"]["resultado_nominal"] == 3375600


def test_sem_vpl_tir_nos_indicadores(client, fonte_financeira):
    # A fronteira 4×5: nenhum indicador descontado na resposta (só fluxo nominal).
    # (Os avisos PODEM citar "VPL/TIR é a Fase 5" — isso é prosa, não um campo.)
    aid = _criar_analise(client)
    body = _post(client, aid, _premissas_caso_a()).json()
    chaves = set(body["indicadores"].keys())
    for proibido in ("vpl", "tir", "payback", "tma", "desconto"):
        assert not any(proibido in k.lower() for k in chaves)
    assert set(chaves) == {
        "resultado_nominal", "resultado_nominal_fmt", "margem_sobre_vgv_proprio",
        "exposicao_maxima", "horizonte_meses",
    }


def test_get_sem_execucao_404(client, fonte_financeira):
    aid = _criar_analise(client)
    assert client.get(f"/api/analises/{aid}/financeira").status_code == 404


def test_nao_altera_aproveitamento(client, fonte_financeira):
    aid = _criar_analise(client)
    payload = {"regime": "URBANO", "lote_min_m2": 200}
    antes = client.post(f"/api/analises/{aid}/aproveitamento", json=payload).json()
    _post(client, aid, _premissas_caso_a())
    depois = client.post(f"/api/analises/{aid}/aproveitamento", json=payload).json()
    assert antes["area_aproveitavel_m2"] == depois["area_aproveitavel_m2"]
    assert antes["n_lotes_teto"] == depois["n_lotes_teto"]
