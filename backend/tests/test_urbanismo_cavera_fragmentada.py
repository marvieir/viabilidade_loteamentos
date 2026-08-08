"""MOTOR-3 — valores-ouro da gleba REAL da Caverá (Alegrete/RS): estreita e FRAGMENTADA.

Caso de 07/08/2026 (teste do operador): o KMZ carregava certo (fix do alfinete, ca29a47),
mas o urbanismo saía degenerado — viário 50,1%, sobra 21,0%, vendável 21,1%, 18 lotes. O dump
do /propor mostrou a anatomia: ``aproveitavel`` é MULTIPOLYGON de 17 bolsões (a mata
rasterizada pica a faixa de ~90 m de largura), e duas causas no motor:

1. A grade adaptativa (9.11) afinava o quarteirão ao piso 0,45 numa ILHA-FAIXA — onde o nº de
   fileiras é travado pela LARGURA, afinar só multiplica transversais (grade teórica > 45% de
   via). Fixes: FREIO DE VIA (``TETO_VIA_GRADE``: a escala nunca desce do ponto em que a grade
   teórica passa de 30% de via) e ILHA-FAIXA (< ``FAIXA_FILEIRAS_MAX`` fileiras → teto do
   perfil, sem afinar).
2. Coletora de 21 m numa gleba de 2,1 ha consumia ~10% do aproveitável sozinha. Fix:
   ``COLETORA_MIN_APROV_M2`` — hierarquia proporcional ao porte.

MOTOR-3b (2ª rodada, 08/08 — feedback do operador: "recortes, não lotes" no norte): com o
viário domado, sobraram lotes em ESCADINHA (20-34 vértices, compacidade 0,31-0,68) e a ilha
norte virava teia de via. Três réguas novas, as duas primeiras só no REGIME FRAGMENTADO
(≥ ``GLEBA_FRAG_MIN_BOLSOES`` bolsões sub-lote — Alegrete/São Roque ficam fora por calibração):

3. Borda limpa no canvas mesmo sem ``tracado`` no estilo (o econômico entrava cru).
4. Grampo do LOTE contra a restrição FECHADA (closing = superset da crua, mais conservador
   que a lei) — a escadinha vira borda reta, os dentes viram verde.
5. ILHA ESTREITA DEMAIS (global): largura média (2A/P) < rua + 1 fileira de lote → a porção
   NÃO é urbanizável por construção; vai inteira para verde remanescente ROTULADO (o norte
   da Caverá: 22-25 m de largura média vs 28-29 m necessários).

Resultado do replay (este dump): 21 lotes REAIS / viário 26,7% (era 18 lotes falsos + teia /
viário 51,5%); norte = verde rotulado. A gleba segue estruturalmente ruim — e agora o motor
DIZ isso em avisos, em vez de entregar um labirinto mudo. Motor determinístico (regra 4).
"""

import dataclasses
import json
import math

from shapely import wkt as W

from app.core import urbanismo_geom as geom
from app.core.urbanismo_medida import medir
from app.core.urbanismo_programa import Programa

DUMP = "tests/fixtures/dump_cavera_fragmentada.json"


def _carregar():
    d = json.load(open(DUMP))
    wk = d["wkt"]
    g = lambda k: (W.loads(wk[k]) if wk.get(k) else None)  # noqa: E731
    return d, g


def _replay():
    d, g = _carregar()
    campos = {f.name for f in dataclasses.fields(Programa)}
    prog = Programa(**{k: v for k, v in d["programa"].items() if k in campos})
    lay = geom.gerar_layout(
        g("aproveitavel"), prog, restricoes=g("restricoes_lote"),
        orientacao_rad=float(d["orientacao_rad"]), diretrizes=d["diretrizes"],
        travessia_eixo=g("travessia_eixo"), travessia_diag=d.get("travessia_diag"),
        declividade_acentuada=g("declividade_acentuada"),
        restricao_externa=g("restricao_externa"), acesso_externo=g("acesso_externo"),
        variante=d.get("variante"), lago=d.get("lago"), estilo=d.get("estilo"),
        contornos=[W.loads(s) for s in d.get("contornos_b") or []],
        restricao_via_bloqueio=g("restricao_via_bloqueio"),
    )
    return d, lay


def test_cavera_nao_degenera():
    """O quadro que o operador viu (18 lotes-teia, viário 50,1%) não volta. Bandas largas de
    não-regressão — o que manda é a PROPORÇÃO (viário domado + lote de verdade), não a
    contagem: lote em escadinha não é lote."""
    d, lay = _replay()
    med = medir(lay, d.get("publico_alvo") or "baixa")
    aprov = W.loads(d["wkt"]["aproveitavel"])

    n = med.indicadores["n_lotes"]
    vendavel = sum(lote.area for lote in lay.lotes) / aprov.area
    viario = (lay.arruamento.area if lay.arruamento is not None else 0.0) / aprov.area

    assert n >= 18, f"degenerou: {n} lotes (v2: 21 reais; bug: 18 em teia)"
    assert vendavel >= 0.22, f"vendável {vendavel:.1%} (v2: 25,7%)"
    assert viario <= 0.33, f"viário {viario:.1%} explodiu (v2: 26,7%; bug: 51,5%)"
    # Invariante duro: nenhum lote ilhado, nenhum lote abaixo do piso legal.
    assert lay.viario_diagnostico["todos_lotes_com_frente_via"] is True
    piso = float(d["diretrizes"]["piso_lote_efetivo_m2"])
    assert all(lote.area >= piso - 1.0 for lote in lay.lotes)


def test_cavera_ilha_faixa_usa_teto_e_norte_vira_verde():
    """A ilha grande (~15 mil m², MRR curto ~90 m) é FAIXA (< 1,95 fileiras): NÃO afina a
    quadra ('teto do perfil'). A ilha NORTE (~5,5 mil m², largura média ~22 m) é estreita
    demais: vira verde rotulada, sem malha (o 'emaranhado' da 2ª rodada não volta)."""
    d, lay = _replay()
    detalhe = lay.viario_diagnostico["ilhas_detalhe"]
    grande = max(detalhe, key=lambda x: x["area_m2"])
    assert grande["area_m2"] > 10_000
    assert "teto do perfil" in grande["motivo"]
    estreitas = [x for x in detalhe if "estreita demais" in x["motivo"]]
    assert estreitas, "a ilha norte deveria ser rotulada estreita demais"
    assert any(x["area_m2"] > 4_000 for x in estreitas)
    for det in detalhe:
        if "estreita demais" in det["motivo"]:
            assert det["lado_quadra_m"] is None and det["faces"] == 0  # sem malha forçada
        elif "sub-lote" in det["motivo"]:
            assert det["lado_quadra_m"] is None  # caquinho não ganha quarteirão


def test_cavera_avisos_rotulam_as_causas():
    """Honestidade: o quadro ruim vem ROTULADO — fragmentação (bolsões sub-lote) e porção
    estreita descartada aparecem em avisos para o operador ler a CAUSA, não só o número."""
    _, lay = _replay()
    avisos = " | ".join(lay.avisos)
    assert "GLEBA FRAGMENTADA" in avisos
    assert "estreita" in avisos and "verde remanescente" in avisos


def test_freio_de_via_na_escala():
    """Unidade: com o freio ligado (via_m), a grade teórica do quarteirão devolvido nunca
    passa de TETO_VIA_GRADE; sem via_m, comportamento 9.11 original (compat)."""
    teto_w, teto_h, via = 54.0, 40.0, 8.0
    # ilha pequena SEM freio → piso 0,45 (comportamento antigo preservado p/ compat)
    bw0, bh0 = geom.lado_quadra_adaptativo(5_000.0, teto_w, teto_h, 18.0, 20.0)
    assert math.isclose(bw0, teto_w * 0.45, abs_tol=0.1)
    # COM freio → o share teórico do resultado fica no teto (30%), não em 45%+
    bw, bh = geom.lado_quadra_adaptativo(5_000.0, teto_w, teto_h, 18.0, 20.0, via_m=via)
    share = 1.0 - (bw * bh) / ((bw + via) * (bh + via))
    assert share <= geom.TETO_VIA_GRADE + 1e-6
    # ilha grande → teto cheio, com ou sem freio (caixa limpa intacta)
    assert geom.lado_quadra_adaptativo(80_000.0, teto_w, teto_h, 18.0, 20.0, via_m=via) == (teto_w, teto_h)
