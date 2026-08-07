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

Resultado do replay após o fix: 36 lotes / vendável 42,5% / viário 38,8% (era 18 / 21,7% /
51,5%). A gleba segue estruturalmente ruim — e agora o motor DIZ isso (aviso GLEBA
FRAGMENTADA), em vez de entregar um labirinto mudo. Motor determinístico (regra 4).
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
    """O quadro que o operador viu (18 lotes, viário 50,1%, vendável 21,1%) não volta.
    Bandas largas de não-regressão — o que manda é a PROPORÇÃO, não o número fino."""
    d, lay = _replay()
    med = medir(lay, d.get("publico_alvo") or "baixa")
    aprov = W.loads(d["wkt"]["aproveitavel"])

    n = med.indicadores["n_lotes"]
    vendavel = sum(lote.area for lote in lay.lotes) / aprov.area
    viario = (lay.arruamento.area if lay.arruamento is not None else 0.0) / aprov.area

    assert n >= 30, f"degenerou de novo: {n} lotes (era 36 no fix, 18 no bug)"
    assert vendavel >= 0.35, f"vendável {vendavel:.1%} (fix: 42,5%; bug: 21,7%)"
    assert viario <= 0.45, f"viário {viario:.1%} (fix: 38,8%; bug: 51,5%)"
    # Invariante duro: nenhum lote ilhado, nenhum lote abaixo do piso legal.
    assert lay.viario_diagnostico["todos_lotes_com_frente_via"] is True
    piso = float(d["diretrizes"]["piso_lote_efetivo_m2"])
    assert all(lote.area >= piso - 1.0 for lote in lay.lotes)


def test_cavera_ilha_faixa_usa_teto():
    """A ilha grande (~15 mil m², MRR curto ~90 m) é FAIXA (< 1,95 fileiras de quarteirão):
    NÃO afina a quadra (motivo 'teto do perfil'), e nenhum bolsão sub-lote ganha quarteirão."""
    d, lay = _replay()
    detalhe = lay.viario_diagnostico["ilhas_detalhe"]
    grande = max(detalhe, key=lambda x: x["area_m2"])
    assert grande["area_m2"] > 10_000
    assert "teto do perfil" in grande["motivo"]
    for det in detalhe:
        if "sub-lote" in det["motivo"]:
            assert det["lado_quadra_m"] is None


def test_cavera_aviso_gleba_fragmentada():
    """Honestidade: o quadro ruim vem ROTULADO — o aviso nomeia a fragmentação (17 bolsões,
    15 sub-lote) para o operador ler a causa, não só o número."""
    _, lay = _replay()
    avisos = " | ".join(lay.avisos)
    assert "GLEBA FRAGMENTADA" in avisos
    assert "17 bolsões" in avisos


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
