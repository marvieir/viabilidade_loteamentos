"""FIN2-5 — comparador tributário: valores-ouro (spec fase-fin2-5-tributario.md §3).

Caso-ouro POPULAR: 67 lotes × R$ 120.000 (VGV 8.040.000); carga atual 6,73%;
terreno R$ 1.000.000 + ITBI/laudêmio R$ 48.000 + contrapartidas R$ 350.000 (correção 0);
alíquota padrão de referência 28% → efetiva 14%.

Conta fechada à mão:
  redutor de ajuste = 1.398.000 → 20.865,67/lote; base 120.000 → 99.134,33 → 69.134,33
  IBS/CBS = 0,14 × (67×90.000 − 1.398.000) = 0,14 × 4.632.000 = 648.480
  IRPJ+CSLL = (6,73% − 3,65%) × 8.040.000 = 247.632
  A = 6,73% × 8.040.000 = 541.092 ; B = 896.112 → transição economiza 355.020
  breakeven = 0,14 × (20.865,67 + 30.000) / (0,14 − 0,0365) = 68.803,79
"""

import pytest

from app.core import tributario
from app.models import schemas

GATE_OK = schemas.PortfolioGateOut(status="liberado", motivo="teste")


def _popular(**over):
    kw = dict(
        gate=GATE_OK,
        n_lotes=67,
        preco_lote=120_000.0,
        vgv=8_040_000.0,
        carga_atual=0.0673,
        carga_atual_declarada=True,
        valor_terreno=1_000_000.0,
        origem_terreno="compra declarada na Parceria",
        itbi_laudemio=48_000.0,
        origem_itbi="declarado",
        contrapartidas=350_000.0,
        correcao=0.0,
        aliquota_padrao=0.28,
        lotes_residenciais=None,
    )
    kw.update(over)
    return tributario.comparar_regimes(**kw)


def _regime(comp, codigo):
    return next(r for r in comp.regimes if r.codigo == codigo)


# ----- 1. Caso-ouro popular: cargas fechadas e transição vencendo -----
def test_popular_cargas_ouro():
    comp = _popular()
    a, b = _regime(comp, "atual_transicao"), _regime(comp, "ibs_cbs")
    assert a.carga_total == pytest.approx(541_092.0, abs=0.5)
    assert b.carga_total == pytest.approx(896_112.0, abs=0.5)
    assert comp.melhor == "atual_transicao"
    assert comp.economia == pytest.approx(355_020.0, abs=1.0)
    # decomposição do A: IRPJ+CSLL 3,08% + CBS 3,65%
    assert a.componentes[0].valor == pytest.approx(247_632.0, abs=0.5)
    assert a.componentes[1].valor == pytest.approx(293_460.0, abs=0.5)
    # IBS/CBS do B sobre base reduzida
    ibs = next(c for c in b.componentes if c.rotulo.startswith("IBS/CBS"))
    assert ibs.valor == pytest.approx(648_480.0, abs=0.5)
    # por lote e % efetivo
    assert a.carga_por_lote == pytest.approx(541_092.0 / 67, abs=0.5)
    assert b.pct_efetivo_vgv == pytest.approx(896_112.0 / 8_040_000.0, abs=1e-4)
    # proveniência POR LINHA (regra da casa)
    for r in comp.regimes:
        for c in r.componentes:
            assert c.base_legal


def test_popular_breakeven_ouro():
    comp = _popular()
    assert comp.breakeven.preco_lote == pytest.approx(68_803.79, abs=1.0)
    # Abaixo do breakeven o regime novo vence: mesmo estudo com lote de R$ 60 mil.
    barato = _popular(preco_lote=60_000.0, vgv=67 * 60_000.0)
    assert barato.melhor == "ibs_cbs"


# ----- 2. Alto padrão: efeito relativo dos redutores despenca -----
def test_alto_padrao_transicao_vence_com_folga():
    alto = _popular(preco_lote=400_000.0, vgv=67 * 400_000.0)
    b = _regime(alto, "ibs_cbs")
    ibs = next(c for c in b.componentes if c.rotulo.startswith("IBS/CBS"))
    assert ibs.valor == pytest.approx(0.14 * (67 * 370_000 - 1_398_000), abs=1.0)
    popular = _popular()
    # diferença em p.p. do VGV é MAIOR no alto padrão (redutores fixos pesam menos)
    assert alto.diferenca_pp > popular.diferenca_pp > 0


# ----- 3. Base nunca negativa (art. 259) -----
def test_base_nunca_negativa():
    comp = _popular(
        preco_lote=30_000.0, vgv=67 * 30_000.0, valor_terreno=5_000_000.0,
    )
    b = _regime(comp, "ibs_cbs")
    ibs = next(c for c in b.componentes if c.rotulo.startswith("IBS/CBS"))
    assert ibs.valor == 0.0  # redutores > preço → base 0, nunca negativa
    # sobra só IRPJ/CSLL no cenário B → regime novo vence
    assert b.carga_total == pytest.approx(0.0308 * 67 * 30_000.0, abs=0.5)
    assert comp.melhor == "ibs_cbs"


# ----- 4. Redutor social só nos lotes residenciais declarados -----
def test_redutor_social_parcial():
    todos = _popular()
    metade = _popular(lotes_residenciais=33)
    ibs_todos = next(c for c in _regime(todos, "ibs_cbs").componentes if c.rotulo.startswith("IBS/CBS"))
    ibs_metade = next(c for c in _regime(metade, "ibs_cbs").componentes if c.rotulo.startswith("IBS/CBS"))
    # 34 lotes perdem o redutor de 30k × 14% = 4.200 cada
    assert ibs_metade.valor - ibs_todos.valor == pytest.approx(34 * 30_000 * 0.14, abs=1.0)


# ----- 5. Correção declarada infla o redutor de ajuste (premissa, não índice vivo) -----
def test_correcao_declarada():
    com = _popular(correcao=0.10)
    ra = _regime(com, "ibs_cbs").componentes[0]
    assert ra.valor == pytest.approx(1_398_000 * 1.10 / 67, abs=0.5)


# ----- 6. Breakeven inexistente quando a efetiva ≤ 3,65% -----
def test_breakeven_none_quando_efetiva_baixa():
    comp = _popular(aliquota_padrao=0.07)  # efetiva 3,5% < 3,65%
    assert comp.breakeven.preco_lote is None
    assert comp.melhor == "ibs_cbs"


# ----- 7. Degradação honesta sem lotes/VGV -----
def test_sem_lotes_sem_numeros():
    comp = _popular(n_lotes=0, vgv=0.0)
    assert comp.regimes == []
    assert any("indisponível" in a for a in comp.avisos)


# ----- 8. Router: comparativo no FinanceiraOut + gate bloqueado + 402 -----
from tests.conftest import RET_RETANGULO, make_kmz  # noqa: E402


def _criar_analise(client):
    r = client.post(
        "/api/analises",
        files={"kmz": ("g.kmz", make_kmz([RET_RETANGULO]), "application/vnd.google-earth.kmz")},
    )
    assert r.status_code == 200
    return r.json()["analise_id"]


def _premissas(**over):
    p = {
        "lotes": {"origem": "declarado", "n": 67},
        "preco_lote": 120000,
        "vendas": {"inicio_mes": 1, "duracao_meses": 10, "curva": "linear", "modo": "avista"},
        "aquisicao": {"modo": "compra", "valor": 1000000, "condicao": "avista", "inicio_mes": 0},
        "tributos": {
            "regime": "presumido", "aliquota_pct": 0.0673,
            "itbi_laudemio": 48000, "contrapartidas": 350000,
        },
    }
    p.update(over)
    return p


def test_router_comparativo_no_resultado(client, fonte_financeira):
    aid = _criar_analise(client)
    body = client.post(f"/api/analises/{aid}/financeira", json=_premissas()).json()
    comp = body["comparativo_tributario"]
    assert comp["gate"]["status"] in ("previa", "liberado")
    assert {r["codigo"] for r in comp["regimes"]} == {"atual_transicao", "ibs_cbs"}
    a = next(r for r in comp["regimes"] if r["codigo"] == "atual_transicao")
    assert a["carga_total"] == pytest.approx(541_092.0, abs=0.5)
    assert comp["breakeven"]["preco_lote"] == pytest.approx(68_803.79, abs=1.0)
    assert comp["alerta_janela"]
    assert any("parecer tributário" in av for av in comp["avisos"])
    # a linha de tributos do FLUXO segue o comportamento atual (compat)
    trib = next(b for b in body["blocos"] if b["bloco"] == "tributos")
    assert trib["total"] == pytest.approx(0.0673 * 8_040_000, abs=1.0)


def test_router_cenario_fluxo_ibs_cbs_alimenta_fluxo(client, fonte_financeira):
    aid = _criar_analise(client)
    p = _premissas()
    p["tributos"]["cenario_fluxo"] = "ibs_cbs"
    body = client.post(f"/api/analises/{aid}/financeira", json=p).json()
    trib = next(b for b in body["blocos"] if b["bloco"] == "tributos")
    # carga efetiva do B (896.112 / 8.040.000 = 11,1457%) sobre a receita própria
    assert trib["total"] == pytest.approx(896_112.0, rel=1e-3)
    comp = body["comparativo_tributario"]
    assert any("CENÁRIO B" in av for av in comp["avisos"])


def test_router_gate_bloqueado_so_gate_e_402(client, fonte_financeira):
    import os
    from datetime import datetime, timedelta, timezone

    from app.core.portfolio_store import FontePortfolioArquivo

    me = client.get("/api/auth/me").json()
    velho = (datetime.now(timezone.utc) - timedelta(days=40)).isoformat()
    FontePortfolioArquivo(os.environ["FIN25_GATE_DIR"]).salvar(
        me["id"], {"primeiro_acesso": velho}
    )
    aid = _criar_analise(client)
    body = client.post(f"/api/analises/{aid}/financeira", json=_premissas()).json()
    comp = body["comparativo_tributario"]
    assert comp["gate"]["status"] == "bloqueado"
    assert comp["regimes"] == []  # bloqueio REAL no servidor: sem números
    # e o resto da Financeira segue aberto
    assert body["vgv"]["bruto"] == 8_040_000
    # cenário pago no fluxo com gate bloqueado → 402
    p = _premissas()
    p["tributos"]["cenario_fluxo"] = "ibs_cbs"
    r = client.post(f"/api/analises/{aid}/financeira", json=p)
    assert r.status_code == 402
