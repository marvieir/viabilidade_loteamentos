"""Fase 10 (Parte 4) — ALTO PADRÃO (catálogo §8): UMA portaria/pórtico na entrada única do
loteamento conectado, institucional na entrada, tags premium (sem violar §1-A)."""

import json
from pathlib import Path

from shapely import wkb
from shapely.geometry import box

from app.core import conexao as cx
from app.core import urbanismo_geom as geom
from app.core.urbanismo_diretrizes import resolver_diretrizes
from app.core.urbanismo_programa import programa_do_preset
from tests.test_urbanismo_grade_adaptativa import _layout_sao_roque, _perfil_mue


def test_uma_portaria_no_loteamento_conectado():
    """Critério P4.1: UMA portaria/pórtico (não duas) — o loteamento é único. `porticos == 1` e há
    um ponto de entrada definido."""
    d = json.loads(Path("tests/fixtures/sao_roque_aproveitavel_decliv.json").read_text())
    aprov = wkb.loads(d["aproveitavel_wkb_hex"], hex=True)
    comps = sorted((c for c in geom._componentes(aprov)), key=lambda p: -p.area)
    dd = resolver_diretrizes(_perfil_mue(), "MUE", None, "alta")
    prog = programa_do_preset("alta", {"pct_lazer": 0.2})
    tv = cx.avaliar_travessia(comps[0], comps[1], lambda x, y: 1000.0, ponto=(-36.0, -23.0))
    lay = geom.gerar_layout(aprov, prog, orientacao_rad=float(d["orientacao_rad"]), diretrizes=dd,
                            travessia_eixo=tv.eixo, travessia_diag={"veredicto": tv.veredicto})
    ap = lay.viario_diagnostico["alto_padrao"]
    assert ap["porticos"] == 1               # UMA entrada (loteamento conectado)
    assert ap["portico_ponto"] is not None


def test_portico_nao_invade_mata_preservada():
    """Fase 11.4: a portaria fica numa BOCA de acesso que serve as quadras — nunca encravada no meio
    da mata preservada/não-edificável. O disco do pórtico NÃO intersecta o verde reservado, e o ponto
    fica muito mais perto dos lotes do que da reserva (entrada do loteamento, não gate no bosque)."""
    from shapely.geometry import Point
    from shapely.ops import unary_union

    d = json.loads(Path("tests/fixtures/sao_roque_aproveitavel_decliv.json").read_text())
    aprov = wkb.loads(d["aproveitavel_wkb_hex"], hex=True)
    comps = sorted((c for c in geom._componentes(aprov)), key=lambda p: -p.area)
    dd = resolver_diretrizes(_perfil_mue(), "MUE", None, "alta")
    prog = programa_do_preset("alta", {"pct_lazer": 0.2})
    tv = cx.avaliar_travessia(comps[0], comps[1], lambda x, y: 1000.0, ponto=(-36.0, -23.0))
    lay = geom.gerar_layout(aprov, prog, orientacao_rad=float(d["orientacao_rad"]), diretrizes=dd,
                            travessia_eixo=tv.eixo, travessia_diag={"veredicto": tv.veredicto})
    pt = Point(lay.viario_diagnostico["alto_padrao"]["portico_ponto"])
    reserva = lay.areas_verdes_reservada
    lotes = unary_union(lay.lotes)
    assert lay.portico is not None
    assert not lay.portico.intersects(reserva)     # o disco da portaria não invade a mata preservada
    assert reserva.distance(pt) >= geom.RAIO_PORTICO_M  # boca afastada da reserva ao menos o raio do disco
    assert lotes.distance(pt) < reserva.distance(pt)    # entrada serve as quadras (perto de lote, longe da mata)


def test_portico_evita_mata_externa_descontada():
    """Fase 11.4: a mata/APP/≥30% é DESCONTADA da gleba pelo chamador → vira um BURACO na
    aproveitável que a via de contorno acompanha. Sem informar essa restrição ao motor, a portaria
    cai justamente na frente da mata (o maior contato via-borda). Passando ``restricao_externa``, o
    veto afasta o pórtico da mata. Repro sintética determinística (não depende de fixture)."""
    from shapely.geometry import Point, Polygon, box

    dd = resolver_diretrizes(_perfil_mue(), "MUE", None, "alta")
    prog = programa_do_preset("alta", {"pct_lazer": 0.2})
    gleba = box(0, 0, 360, 220)
    mata = Polygon([(140, 30), (360, 30), (360, 190), (140, 190), (220, 110)])  # língua que entra pelo leste
    aprov = gleba.difference(mata)

    bug = geom.gerar_layout(aprov, prog, diretrizes=dd, restricao_externa=None)
    fix = geom.gerar_layout(aprov, prog, diretrizes=dd, restricao_externa=mata)
    pt_bug = Point(bug.viario_diagnostico["alto_padrao"]["portico_ponto"])
    pt_fix = Point(fix.viario_diagnostico["alto_padrao"]["portico_ponto"])

    assert bug.portico.intersects(mata)            # sem o veto, a portaria invade a mata (regressão)
    assert not fix.portico.intersects(mata)        # com o veto, o disco fica fora da mata preservada
    assert mata.distance(pt_fix) >= geom.RAIO_PORTICO_M
    assert mata.distance(pt_fix) > mata.distance(pt_bug)


def test_institucional_na_entrada_e_tags():
    """Critério P4.2/3: a flag `institucional_na_entrada` existe (setorização da entrada) e a
    arborização viária é exposta como TAG (não muda área de lote — §1-A)."""
    lay, _ = _layout_sao_roque()
    ap = lay.viario_diagnostico["alto_padrao"]
    assert isinstance(ap["institucional_na_entrada"], bool)
    assert ap["arborizacao_viaria"] is True  # tag premium (faixa de serviço ≥0,70 m)
    assert ap["porticos"] in (0, 1)


def test_caixa_limpa_uma_entrada():
    """Não-regressão: numa caixa limpa (1 porção) há UMA entrada — porticos == 1, sem inventar duas."""
    dd = resolver_diretrizes(_perfil_mue(), "MUE", None, "alta")
    lay = geom.gerar_layout(box(0, 0, 343, 172), programa_do_preset("alta", {"pct_lazer": 0.2}), diretrizes=dd)
    assert lay.viario_diagnostico["alto_padrao"]["porticos"] == 1


def test_portico_gleba_real_sao_roque_fica_no_norte_perto_dos_lotes():
    """Regressão com a GLEBA REAL (Urbanisi/São Roque, 3 matrículas, 18,71 ha): o pórtico não pode
    voltar pro exit remoto no sul (de frente p/ a mata externa). Deve cair na metade NORTE (lado da
    estrada de acesso) e PERTO dos lotes — a entrada serve o miolo loteado, não uma ponta isolada."""
    from shapely import wkb
    from shapely.geometry import Point
    from shapely.ops import unary_union

    d = json.loads(Path("tests/fixtures/sao_roque_gleba_real.json").read_text())
    gleba_m = wkb.loads(d["gleba_metrica_wkb_hex"], hex=True)
    dd = resolver_diretrizes(_perfil_mue(), "MUE", None, "alta")
    lay = geom.gerar_layout(gleba_m, programa_do_preset("alta", {"pct_lazer": 0.2}), diretrizes=dd)
    pt = Point(lay.viario_diagnostico["alto_padrao"]["portico_ponto"])
    gminx, gminy, gmaxx, gmaxy = gleba_m.bounds
    y_rel = (pt.y - gminy) / (gmaxy - gminy)
    lotes = unary_union(lay.lotes)
    assert y_rel > 0.5, f"pórtico caiu no sul (y_rel={y_rel:.2f}) — regressão da entrada na mata"
    assert lotes.distance(pt) <= 15.0  # entrada junto às quadras (não numa ponta isolada)
