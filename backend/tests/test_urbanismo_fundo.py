"""Fase 9.13 — Urbanismo: fecha os últimos encravados (FUNDO ÓRFÃO) + declividade harmônica no
mapa (apresentação). Dois ajustes curtos sobre a 9.12:

(A) O lote de FUNDO de quadra órfão (atrás de um lote com via, sem lateral com via) que a fusão
    LATERAL da 9.12 não resolve — a 9.12 o mandava p/ verde — agora funde com a FRENTE (mesma
    coluna), somando profundidade ATÉ o teto; o excedente vira verde (clamp 9.4 preservado).
    Hierarquia: (1) lateral é a regra; (2) fundo órfão → frente (exceção); (3) nem frente → verde.
(B) A restrição ≥30% ganha `estilo_sugerido="hachura_discreta"` p/ o front mostrá-la DISCRETA
    (não bloco sólido). O dado/geometria NÃO muda.

Critério-âncora: São Roque REAL (fixture congelado, offline determinista). Tudo no Python (§2).
"""

import re

from shapely.geometry import box

from app.core import urbanismo_geom as geom
from app.core import urbanismo_medida as medida
from app.core.urbanismo_diretrizes import resolver_diretrizes
from app.core.urbanismo_programa import programa_do_preset
from tests.test_urbanismo_grade_adaptativa import _layout_sao_roque, _perfil_mue

TESTADA_MIN = 5.0


def _frente(lote, ruas):
    return 0.0 if ruas is None else lote.exterior.intersection(ruas.buffer(0.5)).length


# ====================== nº1: ZERO encravados (inclui fundo de quadra) ======================
def test_zero_encravados_inclui_fundo_sao_roque():
    """Critério 1: nenhum lote CONTADO sem frente para via — incluindo os de fundo de quadra que a
    9.12 deixava virar verde. `lotes_sem_via_final == 0` e cada lote toca o arruamento (≥5 m)."""
    layout, _ = _layout_sao_roque()
    v = layout.viario_diagnostico
    assert v["lotes_sem_via_final"] == 0
    assert v["todos_lotes_com_frente_via"] is True
    for lote in layout.lotes:
        assert _frente(lote, layout.arruamento) >= TESTADA_MIN - 1e-6


# ====================== nº2: fusão de fundo correta (respeita [piso, teto]) ======================
def test_fusao_de_fundo_recupera_orfao_respeitando_teto():
    """Critério 2: o fundo órfão de São Roque (que a 9.12 jogava p/ verde) agora FUNDE com a frente
    — `lotes_fundidos_fundo ≥ 1`, `lotes_viraram_verde` cai, e nenhum lote sai de [piso, teto]
    (`fora_da_faixa == 0`). Recuperação real (a frente fica mais profunda), não lote fantasma."""
    layout, med = _layout_sao_roque()
    v = layout.viario_diagnostico
    d = medida.distribuicao_tamanhos(med, layout)
    assert v["lotes_fundidos_fundo"] >= 1   # o órfão foi RECUPERADO (não descartado p/ verde)
    assert v["lotes_viraram_verde"] == 0     # nada sobrou sem destino
    assert d["fora_da_faixa"] == 0           # clamp 9.4 intacto


# ====================== nº3: excedente além do teto vira VERDE ======================
def test_excedente_de_profundidade_vira_verde():
    """Critério 3: quando a fusão frente-fundo passaria do teto, o excedente de profundidade vira
    verde/não-aproveitável — nunca um lote gigante. Frente 450 + fundo 450 = 900 > teto 640 → o
    lote final ≤ 640 e o resto (~260 m²) volta como verde. Unidade direta de `garantir_frente_via`."""
    via = box(-1.0, -1.0, 16.0, 0.0)
    frente = box(0, 0, 15, 30)   # 450 m², com via ao sul
    fundo = box(0, 30, 15, 60)   # 450 m² atrás, sem via
    ok, _, verde, stats = geom.garantir_frente_via([frente, fundo], ["Q1", "Q1"], via,
                                                   piso=300.0, teto=640.0, testada_min=TESTADA_MIN)
    assert stats["lotes_fundidos_fundo"] == 1
    assert len(ok) == 1 and ok[0].area <= 640.0 + 1e-6   # nunca acima do teto
    assert ok[0].area >= 450.0 - 1e-6                     # absorveu profundidade (cresceu)
    assert sum(p.area for p in verde) > 200.0            # excedente virou verde


# ====================== nº4: lateral é a REGRA, fundo é a EXCEÇÃO (hierarquia) ===========
def test_lateral_e_regra_fundo_e_excecao():
    """Critério 4: a hierarquia é respeitada — quando existe vizinho LATERAL com via, o encravado
    funde LATERAL (não frente-fundo); o frente-fundo só roda p/ o órfão SEM lateral. Caso
    construído com os DOIS tipos: cada um vai pelo seu ramo (lateral 1, fundo 1).

    Obs (registrado): no integrado, a 9.12 já faz TODO lote nascer com via, então quase não sobra
    encravado lateral — o resíduo é justamente o fundo órfão. Por isso a garantia de que o frente-
    fundo é EXCEÇÃO (e não regra) é provada aqui, na unidade, pela ORDEM dos ramos."""
    via = box(-1.0, -1.0, 41.0, 0.0)
    com_via_a = box(0, 0, 20, 30)
    com_via_b = box(20, 0, 40, 30)
    enc_lateral = box(40, 0, 55, 30)   # divisa vertical c/ com_via_b → LATERAL
    enc_fundo = box(0, 30, 20, 55)     # divisa horizontal c/ com_via_a, sem lateral → FUNDO órfão
    ok, _, _, stats = geom.garantir_frente_via([com_via_a, com_via_b, enc_lateral, enc_fundo],
                                               ["Q1"] * 4, via, piso=300.0, teto=1200.0, testada_min=TESTADA_MIN)
    assert stats["lotes_fundidos_lateral"] == 1   # o que TEM lateral com via vai pela regra
    assert stats["lotes_fundidos_fundo"] == 1     # o órfão (sem lateral) vai pela exceção
    assert stats["lotes_sem_via_final"] == 0


def test_fundo_e_fracao_pequena_do_total():
    """Critério 4 (integrado): a fusão de fundo é EXCEÇÃO — uma fração pequena do total de lotes
    (a maioria nasce com via pela geração 9.12). Não vira a estratégia dominante de loteamento."""
    dd = resolver_diretrizes(_perfil_mue(), "MUE", None, "alta")
    layout = geom.gerar_layout(box(0, 0, 1200, 800), programa_do_preset("alta", {"pct_lazer": 0.2}), diretrizes=dd)
    med = medida.medir(layout)
    fundo = layout.viario_diagnostico["lotes_fundidos_fundo"]
    assert fundo < 0.1 * med.indicadores["n_lotes"]   # exceção, não regra (<10% dos lotes)


# ====================== nº5: declividade discreta (apresentação) ======================
def test_restricao_estilo_discreto():
    """Critério 5: a restrição recortada (≥30%) carrega `estilo_sugerido="hachura_discreta"` p/ o
    front mostrá-la DISCRETA (não bloco sólido); rótulo e origem permanecem. O dado NÃO muda."""
    lay = medida.Layout()
    lay.restricao_recortada = box(40, 40, 60, 60)
    lay.restricao_origem = ["declividade>=30%"]
    gj = medida._restricao_gj(lay, lambda x, y: (x, y))
    assert gj is not None
    assert gj["estilo_sugerido"] == "hachura_discreta"
    assert gj["origem"] == ["declividade>=30%"]   # origem preservada (dado explícito)
    assert "não-edificável" in gj["rotulo"].lower()


def test_sem_restricao_nao_inventa_estilo():
    """O estilo é dica de apresentação da restrição REAL — sem restrição, não há GeoJSON (não
    inventa mancha nem estilo)."""
    lay = medida.Layout()
    assert medida._restricao_gj(lay, lambda x, y: (x, y)) is None


# ====================== nº6: §2 determinístico + §1-A selo esquemático ======================
def test_determinismo_e_selo_esquematico():
    """Critério 6: a exceção de fusão é DETERMINÍSTICA (mesma entrada → mesma contagem de fundo,
    §2) e o estudo segue rotulado ESQUEMÁTICO, sem palavra de aprovação (§1-A)."""
    a, _ = _layout_sao_roque()
    b, _ = _layout_sao_roque()
    assert a.viario_diagnostico["lotes_fundidos_fundo"] == b.viario_diagnostico["lotes_fundidos_fundo"]
    obs = a.viario_diagnostico["obs"].lower()
    assert not re.search(r"\b(aprovad|viáve|viave|regular)\w*", obs)


# ====================== nº7: não-regressão (números/viário 9.7-9.12 preservados) ======================
def test_nao_regride_geracao_9_12():
    """Critério 7: a 9.13 só muda o DESTINO dos poucos fundos órfãos (verde → lote) e a cor da
    restrição. A geração 9.7-9.12 fica intacta — São Roque segue ~50 lotes, viário na banda
    adaptativa [0,12 ; 0,26], todo lote com via."""
    layout, med = _layout_sao_roque()
    assert med.indicadores["n_lotes"] >= 45
    assert 0.12 <= med.quadro["arruamento"]["pct_apo"] <= 0.26
    assert layout.viario_diagnostico["todos_lotes_com_frente_via"] is True
