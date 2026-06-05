"""Fase 2.3 — severidade do verde (restrição dura × a verificar). Puro, offline."""

from shapely.geometry import Polygon

from app.core.severidade_verde import classificar_severidade_verde

# Gleba retangular (~mesma do conftest).
GLEBA = Polygon(
    [(-47.140, -23.530), (-47.120, -23.530), (-47.120, -23.520), (-47.140, -23.520)]
)
# Verde = metade esquerda da gleba.
VERDE = Polygon(
    [(-47.140, -23.530), (-47.130, -23.530), (-47.130, -23.520), (-47.140, -23.520)]
)
# APP = faixa de baixo (cobre o quarto inferior-esquerdo do verde).
APP = Polygon(
    [(-47.140, -23.530), (-47.120, -23.530), (-47.120, -23.525), (-47.140, -23.525)]
)


def test_conservacao_de_area():
    # dura + a_verificar == verde_total (tolerância pequena).
    s = classificar_severidade_verde(GLEBA, VERDE, {"app": APP})
    soma = s.restricao_dura.area_m2 + s.a_verificar.area_m2
    assert abs(soma - s.verde_total_m2) / s.verde_total_m2 < 0.005


def test_dura_eh_verde_em_app():
    s = classificar_severidade_verde(GLEBA, VERDE, {"app": APP})
    assert s.restricao_dura.area_m2 > 0
    assert "app" in s.fontes_dura
    # verde = metade esquerda; APP = metade de baixo → verde∩APP = metade do verde
    assert 0.45 <= s.restricao_dura.pct_do_verde <= 0.55


def test_uniao_app_e_uc_sem_dupla_contagem():
    # APP e UC sobrepostas: a dura conta a área uma vez só.
    s = classificar_severidade_verde(GLEBA, VERDE, {"app": APP, "uc": APP})
    soma = s.restricao_dura.area_m2 + s.a_verificar.area_m2
    assert abs(soma - s.verde_total_m2) / s.verde_total_m2 < 0.005
    assert set(s.fontes_dura) == {"app", "uc"}


def test_sem_protecao_tudo_a_verificar():
    s = classificar_severidade_verde(GLEBA, VERDE, {})
    assert s.restricao_dura.area_m2 == 0.0
    assert abs(s.a_verificar.area_m2 - s.verde_total_m2) < 0.5
    assert s.fontes_dura == []


def test_potencial_desconta_faixa_nao_edificavel():
    # Toda a metade superior (a_verificar, fora da APP) está sob faixa não-edificável.
    faixa = Polygon(
        [(-47.140, -23.525), (-47.120, -23.525), (-47.120, -23.520), (-47.140, -23.520)]
    )
    s = classificar_severidade_verde(GLEBA, VERDE, {"app": APP, "faixa_nao_edificavel": faixa})
    # a_verificar existe, mas o potencial desbloqueável cai (parte sob a faixa).
    assert s.potencial_desbloqueavel_m2 < s.a_verificar.area_m2
    assert s.potencial_desbloqueavel_m2 >= 0
