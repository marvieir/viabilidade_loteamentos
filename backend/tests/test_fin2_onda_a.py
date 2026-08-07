"""FIN-2 Onda A — curva rampa, cenários de venda, cronograma da obra e indicadores novos."""

import pytest

from app.core import economica as eco
from app.core import financeira as fin
from app.core.financeira import ContextoFinanceira
from app.models import schemas


CTX = ContextoFinanceira(lotes_base=100, origem_lotes="declarado", aviso_lotes=None)


def _premissas(**kw):
    base = dict(
        preco_lote=100_000.0,
        vendas=schemas.VendasIn(inicio_mes=1, duracao_meses=10, modo="avista"),
        custos=schemas.CustosIn(
            urbanizacao=schemas.CustoUrbanizacaoIn(base="por_lote", valor=30_000, inicio_mes=1, duracao_meses=10),
            projetos_aprovacao=schemas.CustoPontualIn(valor=0, mes=0),
            topografia=schemas.CustoPontualIn(valor=0, mes=0),
        ),
        tributos=schemas.TributosIn(aliquota_pct=0.0),
    )
    base.update(kw)
    return schemas.PremissasFinanceiraIn(**base)


def test_curva_rampa_deterministica_e_soma_1():
    fr = fin._fracoes(1, 4, "rampa", None)
    # pesos ∝ (dur − i): 4,3,2,1 / 10 — começo forte, cauda longa.
    assert [round(fr[m], 4) for m in (1, 2, 3, 4)] == [0.4, 0.3, 0.2, 0.1]
    assert abs(sum(fr.values()) - 1.0) < 1e-9
    # frente_carregada (obra) é a MESMA régua declarada.
    assert fin._fracoes(0, 4, "frente_carregada", None) == {0: 0.4, 1: 0.3, 2: 0.2, 3: 0.1}


def test_sem_cenarios_compat_total():
    out, fluxos = fin.montar_com_cenarios(_premissas(), CTX)
    assert fluxos == {} and out.cenarios == []
    assert out.vgv.bruto == 10_000_000.0  # 100 lotes × 100 mil


def test_cenarios_resumo_e_ativo():
    p = _premissas(
        cenarios=[
            schemas.CenarioVendaIn(nome="Conservador", duracao_meses=20, curva="linear"),
            schemas.CenarioVendaIn(nome="Base", duracao_meses=10, curva="rampa"),
            schemas.CenarioVendaIn(nome="Otimista", duracao_meses=5, curva="rampa"),
        ],
        cenario_ativo="Base",
    )
    out, fluxos = fin.montar_com_cenarios(p, CTX)
    assert [c.nome for c in out.cenarios] == ["Conservador", "Base", "Otimista"]
    ativo = {c.nome: c.ativo for c in out.cenarios}
    assert ativo == {"Conservador": False, "Base": True, "Otimista": False}
    # Mesmo VGV; vender mais devagar NUNCA melhora a exposição máxima.
    exp = {c.nome: abs(c.exposicao_maxima.valor) for c in out.cenarios}
    assert exp["Conservador"] >= exp["Base"] >= exp["Otimista"]
    # O out principal é o do cenário ATIVO (duração 10 → última venda no mês 10).
    assert out.fluxo_vendas[-1].mes == 10
    # Fluxos persistíveis para a Econômica: 3 cenários, com o ativo marcado.
    assert set(fluxos) == {"Conservador", "Base", "Otimista"}
    assert fluxos["Base"]["ativo"] is True and len(fluxos["Base"]["fluxo"]) > 0


def test_cenario_ativo_invalido_e_nomes_repetidos():
    p = _premissas(cenarios=[schemas.CenarioVendaIn(nome="A", duracao_meses=5)], cenario_ativo="X")
    with pytest.raises(fin.CurvaInvalida):
        fin.montar_com_cenarios(p, CTX)
    p2 = _premissas(cenarios=[
        schemas.CenarioVendaIn(nome="A", duracao_meses=5),
        schemas.CenarioVendaIn(nome="A", duracao_meses=6),
    ])
    with pytest.raises(fin.CurvaInvalida):
        fin.montar_com_cenarios(p2, CTX)


def test_cronograma_disciplinas_prevalece_e_pico():
    p = _premissas(
        custos=schemas.CustosIn(
            urbanizacao=schemas.CustoUrbanizacaoIn(
                valor=999,  # ignorado: disciplinas prevalecem
                disciplinas=[
                    schemas.DisciplinaObraIn(nome="Terraplenagem", valor=400_000, inicio_mes=1, duracao_meses=4, curva="frente_carregada"),
                    schemas.DisciplinaObraIn(nome="Pavimentação", valor=600_000, inicio_mes=5, duracao_meses=3, curva="linear"),
                ],
            ),
            projetos_aprovacao=schemas.CustoPontualIn(valor=0, mes=0),
            topografia=schemas.CustoPontualIn(valor=0, mes=0),
        ),
        tributos=schemas.TributosIn(aliquota_pct=0.0),
    )
    out = fin.montar_fluxo(p, CTX)
    urb = next(b for b in out.blocos if b.bloco == "urbanizacao")
    assert urb.total == 1_000_000.0  # soma das disciplinas, não o valor=999
    assert "cronograma por disciplina (2" in urb.proveniencia
    # Pico: pavimentação linear = 200 mil/mês (meses 5-7) > terraplenagem m1 = 160 mil.
    assert out.obra_pico is not None
    assert out.obra_pico.mes == 5 and out.obra_pico.valor == 200_000.0


def test_estatico_fecha_com_o_fluxo():
    out = fin.montar_fluxo(_premissas(), CTX)
    est = out.estatico
    assert est is not None
    assert est.vgv == out.vgv.bruto
    assert est.custos_total == round(sum(b.total for b in out.blocos), 2)
    assert est.resultado == out.indicadores.resultado_nominal
    assert est.custo_por_lote == round(est.custos_total / 100, 2)
    assert abs(sum(est.composicao.values()) - est.custos_pct_vgv) < 1e-6


def test_economica_mtir_roe_exposicao_media():
    # Fluxo sintético: -1000 no mês 0; +300 nos meses 1..5 (convencional).
    fluxo = [(0, -1000.0)] + [(m, 300.0) for m in range(1, 6)]
    ac, acc = [], 0.0
    for m, v in fluxo:
        acc += v
        ac.append((m, acc))
    p = schemas.PremissasEconomicaIn(tma_aa_real=0.12)
    out = eco.avaliar(fluxo, ac, p, proveniencia="teste")
    assert out.mtir_aa is not None and 0 < out.mtir_aa < 5
    assert out.roe_nominal == round(500.0 / 1000.0, 4)
    assert out.roe_aa is not None and out.roe_aa > out.roe_nominal  # horizonte < 12 meses
    assert out.exposicao_media is not None
    # Acumulados negativos: -1000, -700, -400, -100 → média -550, 4 meses no vermelho.
    assert out.exposicao_media.valor == -550.0 and out.exposicao_media.meses == 4


def test_economica_avaliar_cenarios():
    cen = {
        "Base": {"ativo": True, "fluxo": [(0, -1000.0), (1, 600.0), (2, 600.0)],
                 "acumulado": [(0, -1000.0), (1, -400.0), (2, 200.0)]},
        "Lento": {"ativo": False, "fluxo": [(0, -1000.0), (3, 600.0), (6, 600.0)],
                  "acumulado": [(0, -1000.0), (3, -400.0), (6, 200.0)]},
    }
    p = schemas.PremissasEconomicaIn(tma_aa_real=0.12)
    saida = eco.avaliar_cenarios(cen, p)
    por_nome = {c.nome: c for c in saida}
    assert por_nome["Base"].ativo is True and por_nome["Lento"].ativo is False
    assert por_nome["Base"].vpl > por_nome["Lento"].vpl  # mesmo nominal, mais cedo = mais valor
    assert por_nome["Base"].payback_simples_mes == 2
    assert por_nome["Lento"].payback_simples_mes == 6
