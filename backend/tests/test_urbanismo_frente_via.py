"""Fase 9.12 — Urbanismo: TODO LOTE COM FRENTE PARA VIA (corrige lotes encravados) + parser dos
eixos da IA. Bug confirmado por diagnóstico: o motor contava como "lote" (e somava no vendável)
polígonos sem frente para via (16/50 em São Roque, ~69% na caixa por faces profundas). Causa-raiz
(provada com log real): a malha gerava faces de 4-6 fileiras e as do MEIO não tocavam via nenhuma.

A 9.12 conserta em DUAS frentes: (A) GERAÇÃO — cross-streets suficientes (face ≤ ~2 fileiras
costas-com-costas) + cap em 2 fileiras + testada por faixa: TODO lote nasce com frente para via;
o passo `garantir_frente_via` vira rede de segurança (funde lateral o que sobrar, ou vira verde).
(B) PARSER — `_eixos` aceita o esqueleto ACHATADO `[[x,y],…]` (o que a IA manda) e o aninhado.

Critério-âncora: São Roque REAL (fixture congelado, offline determinista). Tudo no Python (§2).
"""

import json
from pathlib import Path

from shapely import wkb
from shapely.geometry import box

from app.core import urbanismo_geom as geom
from app.core import urbanismo_medida as medida
from app.core.urbanismo_diretrizes import resolver_diretrizes
from app.core.urbanismo_programa import programa_do_preset
from tests.test_urbanismo_grade_adaptativa import _layout_sao_roque, _perfil_mue

FIXTURES = Path(__file__).parent / "fixtures"
TESTADA_MIN = 5.0  # Lei 6.766 art. 4º II


def _frente(lote, ruas):
    return 0.0 if ruas is None else lote.exterior.intersection(ruas.buffer(0.5)).length


# ====================== nº1: TODO lote com frente para via (São Roque real) ======================
def test_todo_lote_com_frente_via_sao_roque():
    """Critério 1: nenhum lote CONTADO é encravado — cada um toca o arruamento com testada ≥5 m.
    A invariante vem do diagnóstico (`todos_lotes_com_frente_via`) e é confirmada geometricamente."""
    layout, _ = _layout_sao_roque()
    assert layout.viario_diagnostico["todos_lotes_com_frente_via"] is True
    for lote in layout.lotes:
        assert _frente(lote, layout.arruamento) >= TESTADA_MIN - 1e-6


# ====================== nº2: GERAÇÃO, não filtragem (caixa: verde≈0) ======================
def test_caixa_limpa_via_pela_geracao_nao_filtragem():
    """Critério 2: na caixa limpa, a GERAÇÃO dá frente para via a todo lote — `lotes_viraram_verde
    == 0` (nada é filtrado para verde por falta de acesso). É a prova de que a correção é de
    geração (cross-streets), não de filtragem em massa."""
    dd = resolver_diretrizes(_perfil_mue(), "MUE", None, "alta")
    layout = geom.gerar_layout(box(0, 0, 343, 172), programa_do_preset("alta", {"pct_lazer": 0.2}), diretrizes=dd)
    v = layout.viario_diagnostico
    assert v["lotes_viraram_verde"] == 0
    assert v["todos_lotes_com_frente_via"] is True
    assert medida.medir(layout).indicadores["n_lotes"] >= 50


# ====================== nº3: nenhuma face com fileira do meio encravada ======================
def test_nenhuma_face_profunda_com_fileira_encravada():
    """Critério 3: a malha não gera mais face de 4-6 fileiras (causa-raiz). Cada face é loteada em
    ≤2 fileiras costas-com-costas (ambas lindeiras a uma via). Mede a profundidade das faces."""
    dd = resolver_diretrizes(_perfil_mue(), "MUE", None, "alta")
    prof = float(dd.get("prof_alvo_m", 31.0))
    orig, depths = geom._lotear_face, []

    def _spy(face, ta, p, *a, **k):
        for c in geom._componentes(face):
            depths.append((c.bounds[3] - c.bounds[1]) / p)  # profundidade em nº de fileiras
        return orig(face, ta, p, *a, **k)

    geom._lotear_face = _spy
    try:
        geom.gerar_layout(box(0, 0, 343, 172), programa_do_preset("alta", {"pct_lazer": 0.2}), diretrizes=dd)
    finally:
        geom._lotear_face = orig
    assert depths and max(depths) <= 3.0  # nunca 4-6 fileiras (a do meio ficaria encravada)


# ====================== nº4: clamp legal preservado (fora_da_faixa==0), inclusive gleba grande ===
def test_clamp_preservado_gleba_grande():
    """Critério 4: o clamp legal (9.4) segue intacto — nenhum lote fora de [piso, teto]. Inclui a
    gleba GRANDE (onde o arredondamento da 2-fileira tentava estourar o teto): `fora_da_faixa==0`."""
    dd = resolver_diretrizes(_perfil_mue(), "MUE", None, "alta")
    lay = geom.gerar_layout(box(0, 0, 1200, 800), programa_do_preset("alta", {"pct_lazer": 0.2}), diretrizes=dd)
    med = medida.medir(lay)
    d = medida.distribuicao_tamanhos(med, lay)
    assert d["fora_da_faixa"] == 0
    assert lay.viario_diagnostico["todos_lotes_com_frente_via"] is True


# ====================== nº5: gleba grande ESCALA (sem O(n²)) ======================
def test_gleba_grande_escala_sem_travar():
    """Critério: o passo frente-via usa índice espacial (STRtree) — uma gleba de centenas de
    hectares (milhares de lotes) roda em segundos, não trava. Todo lote com via."""
    import time

    dd = resolver_diretrizes(None, None, None, "alta")
    t0 = time.time()
    lay = geom.gerar_layout(box(0, 0, 2000, 1100), programa_do_preset("alta", {"pct_lazer": 0.2}), diretrizes=dd)
    assert time.time() - t0 < 30.0
    assert medida.medir(lay).indicadores["n_lotes"] > 500
    assert lay.viario_diagnostico["todos_lotes_com_frente_via"] is True


# ====================== nº6: fusão LATERAL (não frente-fundo) — unidade ======================
def test_fusao_lateral_nao_frente_fundo():
    """Critério 3 da spec: o encravado é fundido a vizinho LATERAL com via (soma testada, mantém
    profundidade); um vizinho frente-FUNDO (divisa horizontal) NUNCA absorve (geraria lote
    comprido-estreito). Testa a regra geométrica direta de `garantir_frente_via`."""
    via = box(-1.0, -1.0, 41.0, 0.0)  # rua ao SUL (y≈0), ao longo de x
    # fileira da frente (toca a via): 2 lotes lado a lado [0..20]×[0..30] e [20..40]×[0..30]
    com_via_a = box(0, 0, 20, 30)
    com_via_b = box(20, 0, 40, 30)
    # encravado LATERAL ao com_via_b (divisa vertical x=40) — sem via
    enc_lateral = box(40, 0, 55, 30)
    # encravado FRENTE-FUNDO sobre com_via_a (divisa horizontal y=30) — sem via
    enc_fundo = box(0, 30, 20, 55)
    lotes = [com_via_a, com_via_b, enc_lateral, enc_fundo]
    tags = ["Q1"] * 4
    # teto folgado p/ a união lateral caber (600+450=1050); o frente-fundo é barrado pela GEOMETRIA
    ok, _, verde, stats = geom.garantir_frente_via(lotes, tags, via, piso=300.0, teto=1200.0, testada_min=5.0)
    # o lateral foi FUNDIDO (soma testada → vizinho com via vira mais largo); o frente-fundo NÃO
    assert stats["lotes_fundidos_lateral"] == 1
    assert stats["lotes_viraram_verde"] == 1          # o frente-fundo virou verde (não fundiu)
    assert all(_frente(l, via) >= 5.0 for l in ok)    # todo lote resultante tem frente para via
    # nenhum lote fundido comprido-estreito (razão lado maior/menor contida)
    for l in ok:
        fr, pr = geom._lados_mrr(l)
        assert max(fr, pr) / min(fr, pr) <= 3.0


# ====================== nº7: PARSER aceita achatado E aninhado (Algoritmo B) ======================
def test_parser_eixos_aceita_achatado_e_aninhado():
    """Critério 7: `_eixos` desaninha — o esqueleto ACHATADO `[[x,y],…]` (o que a Opus 4.8 manda,
    antes 100% descartado como 'coordenadas inválidas') e o aninhado `[[[x,y],…],…]` viram AMBOS
    1 eixo válido. Ponta a ponta: `esqueleto_origem=='llm'`, `eixos_ia_descartados==0`."""
    achatado = [[0.05, 0.5], [0.3, 0.8], [0.6, 0.3], [0.95, 0.6]]
    aninhado = [[[0.05, 0.5], [0.3, 0.8], [0.6, 0.3], [0.95, 0.6]]]
    dd = resolver_diretrizes(None, None, None, "alta")
    for esq in (achatado, aninhado):
        lay = geom.gerar_layout(box(0, 0, 343, 172), programa_do_preset("alta", {"esqueleto": esq, "pct_lazer": 0.2}), diretrizes=dd)
        v = lay.viario_diagnostico
        assert v["esqueleto_origem"] == "llm"
        assert v["eixos_ia_aceitos"] >= 1 and v["eixos_ia_descartados"] == 0
    # unidade do desaninhador
    assert len(geom._desaninhar_esqueleto(achatado)) == 1   # achatado → 1 polilinha
    assert len(geom._desaninhar_esqueleto(aninhado)) == 1   # aninhado → 1 polilinha


# ====================== nº8: nº de lotes/vendável CORRIGIDOS (reconciliação) ======================
def test_numero_corrigido_e_testada_exposta():
    """Critério 2/10: o nº de lotes e o vendável refletem só lotes COM via (corrigidos para o real),
    e a `testada_media_m` é exposta p/ comparar com a faixa do perfil (alto ~15 m+)."""
    layout, med = _layout_sao_roque()
    v = layout.viario_diagnostico
    assert med.indicadores["n_lotes"] == len([l for l in layout.lotes if l is not None and not l.is_empty])
    assert v["testada_media_m"] >= 12.0   # tende à faixa do perfil (alto)
    assert "lotes_sem_via_tratados" in v and "lotes_fundidos_lateral" in v
