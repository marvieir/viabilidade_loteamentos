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


def test_mata_que_tambem_e_encosta_bloqueia_via():
    """Dump 027 (achado do operador): mata∩encosta CONTINUA mata — via jamais. Sem a camada de
    vegetação separada, o motor tratava tudo que é ≥30% como 'via ok' e cortava por cima da
    floresta íngreme. Aqui a mata É TAMBÉM declividade (pior caso): com `restricao_via_bloqueio`
    a via não pisa nela nem 1 m²."""
    aprov, mata, curvas = _cenario_raster()
    prog = programa_do_preset("alta", {"pct_lazer": 0.12})
    estilo, _ = carregar_estilo("alta")
    estilo["gramatica"] = "paisagem"
    lay = geom.gerar_layout(
        aprov, prog, orientacao_rad=0.0,
        restricao_externa=mata,
        declividade_acentuada=mata,      # a mata TODA é também ≥30% (pior caso do dump 027)
        restricao_via_bloqueio=mata,     # camada de vegetação separada: bloqueia via SEMPRE
        contornos=curvas, estilo=estilo,
    )
    assert lay.arruamento is not None and not lay.arruamento.is_empty
    inv = lay.arruamento.intersection(mata).area
    assert inv < 1.0, f"via sobre mata∩encosta: {inv:.0f} m² (mata bloqueia via mesmo sendo ≥30%)"


# ------------------- roteador da via de acesso (desvia da restrição — dump 026) -------------------
def test_rota_acesso_desvia_do_bloqueio():
    """A via de acesso NÃO corta reto por cima do bloqueado quando há corredor livre do lado:
    o A* contorna (achado do operador — a descida do pórtico cortava a encosta sem necessidade)."""
    from shapely.geometry import Point

    origem, destino = Point(150.0, 290.0), Point(150.0, 10.0)
    bloqueio = box(60.0, 120.0, 240.0, 180.0)   # muro no meio; corredor livre nas laterais
    rota = geom._rota_acesso_desviando(origem, destino, bloqueio, None)
    assert rota is not None
    assert not rota.intersects(bloqueio.buffer(-1.0)), "rota atravessou o bloqueado"
    assert rota.length < 600.0  # desvio razoável, não passeio


def test_rota_acesso_prefere_barato_ao_caro():
    """Com corredor LIVRE disponível, a rota evita a zona cara (≥30%); cruza só sem alternativa."""
    from shapely.geometry import Point

    origem, destino = Point(150.0, 290.0), Point(150.0, 10.0)
    caro = box(60.0, 120.0, 240.0, 180.0)       # zona cara no meio; livre nas laterais
    rota = geom._rota_acesso_desviando(origem, destino, None, caro)
    assert rota is not None
    dentro = rota.intersection(caro).length
    assert dentro < rota.length * 0.15, f"rota passou {dentro:.0f} m pelo caro tendo corredor livre"
    # bloqueio TOTAL (sem corredor) → None (o chamador cai no traço reto + grampo)
    parede = box(-50.0, 120.0, 350.0, 180.0)
    assert geom._rota_acesso_desviando(origem, destino, parede, None) is None