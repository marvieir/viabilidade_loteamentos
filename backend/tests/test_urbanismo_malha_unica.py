"""Fase 10.4 — MALHA VIÁRIA ÚNICA (sem buraco entre porções).

Diagnóstico: numa gleba partida pela faixa ≥30%, o motor gerava a via-tronco de conexão, mas ela
NÃO alcançava a malha da outra porção (ficava a >60 m, ou só TOCAVA num ponto — sem largura, carro
não passa). A malha saía em pedaços desconexos e o `loteamento_conexo` era falso-positivo (o check
só via se *alguma* peça tocava cada porção). Resultado na tela: vias que não fluem + vazio no meio.

`_conectar_malha` GARANTE uma malha única: solda toques pontuais (disco da caixa de via) e liga vãos
reais (conector reto), mas só é chamado quando há ponte SANCIONADA (greide viável) — sem travessia
ou greide inviável, NÃO força conexão (degradação honesta).
"""

from shapely.geometry import box

from app.core import urbanismo_geom as geom


def _ncomp(g):
    return len(geom._componentes(g))


def test_solda_toque_pontual():
    """Duas malhas que se TOCAM num ponto (canto) contam como 2 componentes (sem largura → carro não
    passa). `_conectar_malha` solda num disco da caixa → UMA peça."""
    a = box(0, 0, 30, 30)
    b = box(30, 30, 60, 60)          # toca `a` só no ponto (30, 30)
    malha = a.union(b)
    assert _ncomp(malha) == 2
    unida = geom._conectar_malha(malha, caixa=12.0)
    assert _ncomp(unida) == 1


def test_liga_vao_real():
    """Duas malhas com VÃO entre elas → conector reto (caixa de via) liga as duas numa peça só."""
    a = box(0, 0, 30, 30)
    b = box(50, 0, 80, 30)           # vão de 20 m
    malha = a.union(b)
    assert _ncomp(malha) == 2
    unida = geom._conectar_malha(malha, caixa=12.0)
    assert _ncomp(unida) == 1


def test_ja_conexo_inalterado():
    """Malha já conexa (1 peça) volta inalterada — não inventa conector."""
    a = box(0, 0, 60, 30)
    unida = geom._conectar_malha(a, caixa=12.0)
    assert _ncomp(unida) == 1
    assert unida.equals(a)


def test_ignora_sliver():
    """Sliver minúsculo (ruído de buffer, < min_area) NÃO é soldado — não cria conector espúrio
    atravessando a gleba até um caquinho de 1 m²."""
    grande = box(0, 0, 60, 40)
    sliver = box(200, 200, 201, 201)  # 1 m², longe
    malha = grande.union(sliver)
    unida = geom._conectar_malha(malha, caixa=12.0, min_area=80.0)
    # o sliver fica de fora (segue 2 peças), mas NENHUM conector gigante foi criado
    assert geom._maior_parte(unida).area < grande.area + 5.0  # main intacto (sem braço até o sliver)
