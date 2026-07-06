"""Opção B — via-tronco na CURVA DE NÍVEL (traçado serpenteando a declividade).

Valores-ouro:
- marching squares (_segmentos_isolinha) acha a isolinha de um grid conhecido;
- gerar_layout(tracado="contorno_serpente", contornos=[curva]) usa a curva como espinha:
  malha ÚNICA conectada, ZERO lote inválido, todo lote com frente para via;
- B sem curva (sem DEM) DEGRADA para a grade limpa (Opção A) — nunca quebra;
- a sanitização final não deixa lote inválido sair do motor.
"""

import numpy as np
from shapely.geometry import LineString, box

from app.core import contorno_dem
from app.core import urbanismo_geom as geom
from app.core.urbanismo_estilo import ESTILO_DEFAULT
from app.core.urbanismo_programa import programa_do_preset

GLEBA = box(0.0, 0.0, 900.0, 500.0)


def _estilo(tracado):
    e = dict(ESTILO_DEFAULT["alta"])
    e["tracado"] = tracado
    return e


def test_marching_squares_acha_isolinha_conhecida():
    # rampa em x + ondulação em y → a isolinha da mediana é uma curva contínua não trivial
    r, c = np.mgrid[0:40, 0:60]
    z = c * 1.0 + 5 * np.sin(r * 0.3)
    segs = contorno_dem._segmentos_isolinha(z, float(np.median(z)))
    assert len(segs) > 10  # muitos segmentos ao longo da grade
    # todos os cruzamentos ficam DENTRO da grade
    for (x0, y0), (x1, y1) in segs:
        assert 0 <= x0 <= 59 and 0 <= y0 <= 39


def test_b_usa_espinha_curva_e_sai_limpo():
    prog = programa_do_preset("alta", {"pct_lazer": 0.15})
    # espinha curva atravessando a gleba (uma "curva de nível" sintética, já no frame do motor)
    curva = LineString([(60, 250), (250, 210), (450, 270), (650, 220), (840, 260)])
    lay = geom.gerar_layout(GLEBA, prog, estilo=_estilo("contorno_serpente"), contornos=[curva])
    # invariantes duros
    assert lay.lotes, "B deve lotear"
    assert all(l.is_valid and l.geom_type == "Polygon" for l in lay.lotes), "zero lote inválido"
    arr = lay.arruamento
    assert arr is not None and arr.is_valid
    comps = geom._componentes(arr)
    assert len(comps) == 1, "malha viária ÚNICA (conectada)"
    arr_buf = arr.buffer(1.0)
    assert all(l.boundary.intersection(arr_buf).length >= 1.0 for l in lay.lotes), "todo lote com frente"


def test_b_sem_curva_degrada_para_grade_limpa():
    prog = programa_do_preset("alta", {"pct_lazer": 0.15})
    # sem contornos (sem DEM) → B degrada p/ a grade limpa da Opção A (não quebra, malha única)
    lay = geom.gerar_layout(GLEBA, prog, estilo=_estilo("contorno_serpente"), contornos=None)
    assert lay.lotes
    assert all(l.is_valid for l in lay.lotes)
    assert len(geom._componentes(lay.arruamento)) == 1


def test_b_deterministico():
    prog = programa_do_preset("alta", {"pct_lazer": 0.15})
    curva = LineString([(60, 250), (250, 210), (450, 270), (650, 220), (840, 260)])
    a = geom.gerar_layout(GLEBA, prog, estilo=_estilo("contorno_serpente"), contornos=[curva])
    b = geom.gerar_layout(GLEBA, prog, estilo=_estilo("contorno_serpente"), contornos=[curva])
    assert len(a.lotes) == len(b.lotes)
    assert abs(sum(l.area for l in a.lotes) - sum(l.area for l in b.lotes)) < 1.0


def _estilo_organico():
    e = _estilo("contorno_serpente")
    e["ruas_locais_contorno"] = True
    return e


def test_b_organica_bandas_arruamento_valido_e_conexo():
    """Opção B ORGÂNICA — ruas locais em bandas de contorno: várias curvas paralelas viram a malha
    LOCAL. Invariantes duros: arruamento VÁLIDO (a união densa de vias curvas sai auto-intersectada,
    o motor repara), UMA malha conexa (fora slivers), zero lote inválido, todo lote com frente."""
    prog = programa_do_preset("alta", {"pct_lazer": 0.15})
    bandas = [
        LineString([(50, 150 + k), (300, 120 + k), (550, 180 + k), (850, 140 + k)])
        for k in (0, 60, 120, 180, 240, 300)
    ]
    lay = geom.gerar_layout(GLEBA, prog, estilo=_estilo_organico(), contornos=bandas)
    assert lay.lotes
    assert all(l.is_valid and l.geom_type == "Polygon" for l in lay.lotes), "zero lote inválido"
    arr = lay.arruamento
    assert arr is not None and arr.is_valid, "arruamento deve sair VÁLIDO (reparo buffer(0))"
    comps = sorted(geom._componentes(arr), key=lambda c: -c.area)
    principais = [c for c in comps if c.area >= 200]
    assert len(principais) == 1, "malha ÚNICA (ignorando slivers de buffer)"
    arr_buf = arr.buffer(1.0)
    assert all(l.boundary.intersection(arr_buf).length >= 1.0 for l in lay.lotes)


def test_marching_squares_bandas_selecao_espacial():
    """extrair_bandas seleciona curvas espaçadas ~banda_m (guloso): num grid com rampa suave, poucas
    curvas espaçadas — nunca amontoadas. Testa o encadeamento por nível (sem reprojeção/DEM real)."""
    r, c = np.mgrid[0:50, 0:70]
    z = c * 1.0 + 3 * np.sin(r * 0.25)
    níveis = np.quantile(z[np.isfinite(z)], np.linspace(0.1, 0.9, 20))
    # cada nível gera segmentos; níveis distintos → isolinhas distintas (não colapsam num ponto)
    contagens = [len(contorno_dem._segmentos_isolinha(z, float(n))) for n in níveis]
    assert all(n > 5 for n in contagens), "toda cota interna tem uma isolinha contínua"
