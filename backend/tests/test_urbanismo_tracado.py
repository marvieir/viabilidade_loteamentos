"""Fase 9.14 — TRAÇADO INTELIGENTE: contorno da restrição (A), conectividade (B), cul-de-sac de
bulbo (C), recuperação de sobra-verde (D). A IA propõe o programa de traçado; o Python materializa
e mede toda a geometria (§2). Âncoras: São Roque REAL (não-regressão + contorno/conectividade/bulbo
visíveis) e uma gleba-fixture DONUT (restrição central contornável → a regra D recupera lote).

Crit 5 RECALIBRADO (decisão do operador): a regra D recupera lote ONDE há sobra acessível (fixture,
recuperados≥1); em São Roque, já maximizada por 9.11–9.13 e com porções só uníveis por PONTE (fora
de escopo §10), n_lotes/vendável NÃO REGRIDEM e verde_sobra não cresce — ganho ~0 é honesto (§1-A:
recuperar é dar acesso geométrico, não forçar número)."""

import re

from shapely.geometry import Point, box

from app.core import urbanismo_geom as geom
from app.core import urbanismo_medida as medida
from app.core import urbanismo_tracado as trac
from app.core.urbanismo_diretrizes import resolver_diretrizes
from app.core.urbanismo_programa import programa_do_preset
from tests.test_urbanismo_grade_adaptativa import _layout_sao_roque, _perfil_mue

FRENTE_MIN = 5.0
SR_9_13_LOTES = 50  # baseline de não-regressão (Fase 9.13)


def _dd():
    return resolver_diretrizes(_perfil_mue(), "MUE", None, "alta")


def _prog():
    return programa_do_preset("alta", {"pct_lazer": 0.2})


def _layout_donut():
    """Gleba-fixture: retângulo com restrição CENTRAL grande (buraco) — contornável, com faces que
    o contorno torna acessíveis. É onde a regra D DEMONSTRA recuperação de lote (sobra → lote)."""
    gleba = box(0, 0, 420, 300).difference(box(150, 110, 290, 200))  # buraco ≥30% central
    lay = geom.gerar_layout(gleba, _prog(), diretrizes=_dd())
    return lay, medida.medir(lay), gleba


def _layout_caixa():
    lay = geom.gerar_layout(box(0, 0, 343, 172), _prog(), diretrizes=_dd())
    return lay, medida.medir(lay)


# ====================== nº1: SEM vias mortas (São Roque + fixture) ======================
def test_sem_vias_mortas():
    """Critério 1: `vias_mortas == 0` — nenhuma via termina em ponta solta; toda via reconecta
    (contorno) ou fecha em bulbo. Vale na gleba real e na fixture com restrição."""
    for lay in (_layout_sao_roque()[0], _layout_donut()[0]):
        assert lay.viario_diagnostico["vias_mortas"] == 0


# ====================== nº2: contorno da restrição (via NÃO cruza) ======================
def test_contorno_da_restricao_sem_cruzar():
    """Critério 2: `trechos_contornando_restricao >= 1` (a via acompanha a borda vedada) e NENHUMA
    via cruza a restrição. Na fixture donut, o arruamento não entra no buraco (área vedada)."""
    lay_sr = _layout_sao_roque()[0]
    assert lay_sr.viario_diagnostico["trechos_contornando_restricao"] >= 1
    lay_d, _, gleba = _layout_donut()
    assert lay_d.viario_diagnostico["trechos_contornando_restricao"] >= 1
    buraco = box(150, 110, 290, 200)  # a restrição (área vedada)
    if lay_d.arruamento is not None:
        invade = lay_d.arruamento.intersection(buraco).area
        assert invade < 1.0, f"via invadiu a restrição: {invade:.1f} m²"


# ====================== nº3: conectividade — porções ligam à entrada ======================
def test_porcoes_conectadas_a_entrada():
    """Critério 3: `porcoes_conectadas == porcoes_loteaveis` (ou as isoladas viraram verde, contagem
    coerente). São Roque: as 2 porções (separadas pela ≥30%) ligam à entrada pela borda livre."""
    v = _layout_sao_roque()[0].viario_diagnostico
    assert v["porcoes_loteaveis"] >= 2
    assert v["porcoes_conectadas"] + v["porcoes_isoladas_viraram_verde"] == v["porcoes_loteaveis"]
    assert v["porcoes_conectadas"] == v["porcoes_loteaveis"]  # ambas têm borda livre (acesso próprio)
    assert isinstance(v["indice_conectividade"], float)


# ====================== nº4: cul-de-sac de bulbo + lotes em leque ======================
def test_culdesac_bulbo_com_leque():
    """Critério 4: onde há ramo terminal, `culdesacs_bulbo >= 1`; o bulbo tem raio ≥ RAIO_BULBO e os
    lotes ao redor têm frente para via (o arco do bulbo). A fixture exercita o bulbo."""
    lay, med, _ = _layout_donut()
    v = lay.viario_diagnostico
    assert v["culdesacs_bulbo"] >= 1
    assert v["todos_lotes_com_frente_via"] is True  # lotes do leque também têm frente (arco)
    # unidade: o bulbo é um disco de raio ≥ RAIO_BULBO (giro de veículo de serviço)
    bulbo = trac.fechar_culdesac_bulbo(Point(0, 0), trac.RAIO_BULBO_M)
    assert bulbo.area >= 3.14 * trac.RAIO_BULBO_M ** 2 * 0.98


# ====================== nº5 (RECALIBRADO): recupera na fixture; não regride em São Roque ========
def test_recuperacao_na_fixture_e_nao_regride_em_sao_roque():
    """Critério 5 (recalibrado): a regra D RECUPERA lote onde há sobra-verde acessível — na fixture
    donut, `lotes_recuperados_de_sobra >= 1`. Em São Roque (já maximizada; porções só uníveis por
    ponte, fora de escopo) n_lotes NÃO REGRIDE vs 9.13 (≥ baseline) — ganho ~0 honesto (§1-A)."""
    lay_d, med_d, _ = _layout_donut()
    assert lay_d.viario_diagnostico["lotes_recuperados_de_sobra"] >= 1  # regra D provada
    _, med_sr = _layout_sao_roque()
    assert med_sr.indicadores["n_lotes"] >= SR_9_13_LOTES  # NÃO regride (não forçado)


# ====================== nº6: reserva × sobra honesta (não loteia a mata) ======================
def test_reserva_permanece_verde():
    """Critério 6: `verde_reserva_m2` (mata/lazer do programa) permanece verde — não é loteada (§1-A);
    só a sobra ACESSÍVEL vira lote. A reserva existe e não some para inflar o vendável."""
    lay = _layout_sao_roque()[0]
    v = lay.viario_diagnostico
    assert v["verde_reserva_m2"] > 0.0
    # a reserva (verde reservado do programa) não vira lote: lotes não cobrem a reserva
    if lay.areas_verdes_reservada is not None and lay.lotes:
        from shapely.ops import unary_union
        sobre = unary_union(lay.lotes).intersection(lay.areas_verdes_reservada).area
        assert sobre < lay.areas_verdes_reservada.area * 0.05  # quase nada de sobreposição


# ====================== nº7: clamp + frente-via preservados ======================
def test_clamp_e_frente_via_preservados():
    """Critério 7: `fora_da_faixa == 0` e `todos_lotes_com_frente_via == true` — inclui os lotes
    recuperados (regra D) e os do leque do bulbo. Nenhum lote novo fura a faixa legal nem fica sem
    frente."""
    for lay, med in (_layout_sao_roque(), (_layout_donut()[0], _layout_donut()[1])):
        d = medida.distribuicao_tamanhos(med, lay)
        assert d["fora_da_faixa"] == 0
        assert lay.viario_diagnostico["todos_lotes_com_frente_via"] is True


# ====================== nº8: §2 determinístico + §1-A selo ======================
def test_determinismo_e_selo_esquematico():
    """Critério 8: regras A–D determinísticas (mesma entrada → mesma saída, §2) e estudo rotulado
    ESQUEMÁTICO, sem palavra de aprovação (§1-A)."""
    a = _layout_donut()[0].viario_diagnostico
    b = _layout_donut()[0].viario_diagnostico
    for k in ("trechos_contornando_restricao", "culdesacs_bulbo", "lotes_recuperados_de_sobra",
              "porcoes_conectadas", "vias_mortas"):
        assert a[k] == b[k]  # determinístico
    obs = _layout_sao_roque()[0].viario_diagnostico["obs"].lower()
    assert not re.search(r"\b(aprovad|viáve|viave|regular)\w*", obs)


# ====================== nº9: não-regressão (geração 9.7-9.13 preservada) ======================
def test_nao_regressao_geracao():
    """Critério 9: subdivisão/frente-via/clamp preservados — São Roque segue ≥ baseline de lotes,
    todo lote com via, sem lote fora da faixa."""
    lay, med = _layout_sao_roque()
    assert med.indicadores["n_lotes"] >= SR_9_13_LOTES
    assert lay.viario_diagnostico["todos_lotes_com_frente_via"] is True
    assert lay.viario_diagnostico["lotes_sem_via_final"] == 0


# ====================== nº10: caixa limpa SÃ (sem bulbo/contorno espúrio) ======================
def test_caixa_limpa_sa():
    """Critério 10: numa gleba retangular SEM restrição, o traçado segue são — `contorno == 0`,
    `bulbos == 0`, `recuperados == 0`, conectividade alta, lotes intactos. A 9.14 não degrada o
    caso fácil."""
    lay, med = _layout_caixa()
    v = lay.viario_diagnostico
    assert v["trechos_contornando_restricao"] == 0
    assert v["culdesacs_bulbo"] == 0
    assert v["lotes_recuperados_de_sobra"] == 0
    assert v["vias_mortas"] == 0
    assert med.indicadores["n_lotes"] >= 50  # caixa intacta (não degrada)
