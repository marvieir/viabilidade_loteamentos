"""Grampo legal final — NADA sobre a restrição declarada (achado de campo, dump 022).

A suavização da escada do raster (30 m) cortava cantos p/ DENTRO da mata → via (842 m²) e lotes
(21) com lascas sobre restrição DECLARADA. Valores-ouro:
- nenhum LOTE intersecta a restrição crua (nem 1 m²);
- nenhuma VIA sobre a mata pura (mata−declividade); via sobre ≥30% segue permitida (nota);
- lote que perde área abaixo do piso legal SAI (resto vira verde/sobra — aviso rotula).
"""

import math

from shapely.geometry import LineString, box
from shapely.ops import unary_union

from app.core import urbanismo_geom as geom
from app.core.urbanismo_estilo import carregar_estilo
from app.core.urbanismo_programa import programa_do_preset


def _cenario_raster():
    """Gleba com MATA em ESCADINHA de raster (quadrados de 30 m) na borda leste — o cenário real:
    a suavização corta os cantos da escada e, sem o grampo, lote/via pisam na mata crua."""
    gleba = box(0.0, 0.0, 900.0, 420.0)
    quadrados = [box(870.0 - (i % 2) * 30.0, i * 30.0, 900.0, (i + 1) * 30.0) for i in range(14)]
    mata = unary_union(quadrados)
    aprov = gleba.difference(mata)
    curvas = []
    for i in range(8):
        y0 = 30.0 + i * 52.0
        pts = [(x, y0 + 18.0 * math.sin(x / 900.0 * math.pi * 1.4)) for x in range(-10, 911, 30)]
        curvas.append(LineString(pts))
    return aprov, mata, curvas


def _gerar(gramatica="paisagem"):
    aprov, mata, curvas = _cenario_raster()
    prog = programa_do_preset("alta", {"pct_lazer": 0.12})
    estilo, _ = carregar_estilo("alta")
    estilo["gramatica"] = gramatica
    lay = geom.gerar_layout(
        aprov, prog, orientacao_rad=0.0, restricao_externa=mata,
        contornos=curvas, estilo=estilo,
    )
    return lay, mata


def test_nenhum_lote_sobre_restricao_declarada():
    lay, mata = _gerar()
    assert lay.lotes
    for l in lay.lotes:
        assert l.intersection(mata).area < 0.5, "lote sobre a mata CRUA declarada"


def test_nenhuma_via_sobre_mata_pura():
    lay, mata = _gerar()
    assert lay.arruamento is not None and not lay.arruamento.is_empty
    inv = lay.arruamento.intersection(mata).area
    assert inv < 1.0, f"via sobre mata pura: {inv:.0f} m² (mata bloqueia via; só ≥30% pode)"


def test_grampo_vale_tambem_na_faixas():
    lay, mata = _gerar("faixas_fluidas")
    for l in lay.lotes:
        assert l.intersection(mata).area < 0.5
    assert lay.arruamento.intersection(mata).area < 1.0