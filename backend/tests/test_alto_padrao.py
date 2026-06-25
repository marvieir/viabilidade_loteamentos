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
