"""Consolidação de restrições (Fase 2.2) — união sem dupla contagem, em CRS métrico."""

from shapely.geometry import Polygon

from app.core.aproveitavel import consolidar

# Gleba ~ retângulo de teste (mesma do conftest), centro ~ (-47.130, -23.525).
GLEBA = Polygon(
    [(-47.140, -23.530), (-47.120, -23.530), (-47.120, -23.520), (-47.140, -23.520)]
)
METADE_ESQ = Polygon(
    [(-47.140, -23.530), (-47.130, -23.530), (-47.130, -23.520), (-47.140, -23.520)]
)
METADE_BAIXO = Polygon(
    [(-47.140, -23.530), (-47.120, -23.530), (-47.120, -23.525), (-47.140, -23.525)]
)


def test_uniao_sem_dupla_contagem():
    # Verde = metade esquerda; APP = metade de baixo. Sobrepõem no quadrante inferior-esq.
    r = consolidar(GLEBA, {"verde": METADE_ESQ, "app": METADE_BAIXO})
    soma_itens = sum(i.area_m2 for i in r.itens)
    # União < soma das partes (há sobreposição) e sobreposicao = soma − união.
    assert r.area_restritiva_m2 < soma_itens
    assert abs(r.sobreposicao_m2 - (soma_itens - r.area_restritiva_m2)) < 1.0
    # União de duas metades que se cruzam = 3/4 da gleba (quadrante comum contado 1x).
    total_aprox = consolidar(GLEBA, {"tudo": GLEBA}).area_restritiva_m2
    assert abs(r.area_restritiva_m2 - 0.75 * total_aprox) / total_aprox < 0.02


def test_ignora_none_e_vazio():
    r = consolidar(GLEBA, {"verde": METADE_ESQ, "app": None})
    assert [i.tipo for i in r.itens] == ["verde"]
    assert r.sobreposicao_m2 == 0.0


def test_sem_restricoes():
    r = consolidar(GLEBA, {})
    assert r.area_restritiva_m2 == 0.0
    assert r.itens == []
