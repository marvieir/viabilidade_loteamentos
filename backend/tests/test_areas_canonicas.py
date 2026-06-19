"""Fase 10 (Parte 1) — fonte CANÔNICA de área: a "área líquida aproveitável" tem UM valor só, lido
por todas as abas (catálogo §10). Testa a definição única e a coerência inter-abas."""

from shapely.geometry import box

from app.core import areas_canonicas as ac


def _gleba():
    # gleba 100×100 = 10.000 m² (em graus pequeno → AEQD local mede em m²)
    return box(-47.0, -23.0, -46.999, -22.999)


def test_liquida_e_gleba_menos_uniao_das_restricoes():
    """A líquida canônica = gleba − UNIÃO(vegetação ∪ declividade ∪ APP), SEM dupla contagem onde
    elas se sobrepõem (a soma das partes pode exceder a união; a líquida usa a união)."""
    g = _gleba()
    # duas restrições que SE SOBREPÕEM (metade comum) — a união < soma
    veg = box(-47.0, -23.0, -46.9996, -22.999)      # ~40% da gleba
    dec = box(-46.9996, -23.0, -46.999, -22.999)    # ~60% (encosta a veg, sem sobrepor)
    r = ac.computar_areas_canonicas(g, vegetacao=veg, declividade=dec, app=None)
    assert r.gleba_bruta_m2 > 0
    # líquida = gleba − união; união ≈ veg+dec (não se sobrepõem aqui)
    assert abs(r.area_liquida_aproveitavel_m2 - (r.gleba_bruta_m2 - r.restricoes_fisicas_m2)) < 1.0
    assert r.vegetacao_m2 > 0 and r.declividade_30_m2 > 0 and r.app_m2 == 0.0


def test_sobreposicao_nao_conta_duas_vezes():
    """Restrições sobrepostas: a líquida desconta a área comum UMA vez (união), não duas."""
    g = _gleba()
    a = box(-47.0, -23.0, -46.9994, -22.999)
    b = box(-46.9996, -23.0, -46.999, -22.999)  # sobrepõe ``a`` numa faixa
    r = ac.computar_areas_canonicas(g, vegetacao=a, declividade=b)
    assert r.sobreposicao_m2 > 0  # houve área comum
    soma = r.vegetacao_m2 + r.declividade_30_m2 + r.app_m2
    assert r.restricoes_fisicas_m2 < soma  # união < soma (não contou a sobreposição 2x)
    assert r.area_liquida_aproveitavel_m2 == round(r.gleba_bruta_m2 - r.restricoes_fisicas_m2, 2)


def test_sem_restricoes_degrada_honesto():
    """Sem fontes (None) → líquida = gleba bruta (não inventa restrição)."""
    g = _gleba()
    r = ac.computar_areas_canonicas(g)
    assert r.area_liquida_aproveitavel_m2 == r.gleba_bruta_m2
    assert r.restricoes_fisicas_m2 == 0.0


def test_coerencia_inter_abas_mesma_fonte():
    """Critério P1: o número da líquida é IDÊNTICO para qualquer aba — porque todas chamam a MESMA
    função determinística com a MESMA gleba e restrições. Simula as 3 abas lendo a fonte única."""
    g = _gleba()
    veg = box(-47.0, -23.0, -46.9996, -22.999)
    dec = box(-46.9997, -23.0, -46.999, -22.999)
    ambiental = ac.computar_areas_canonicas(g, veg, dec)
    aproveitamento = ac.computar_areas_canonicas(g, veg, dec)
    urbanismo = ac.computar_areas_canonicas(g, veg, dec)
    liqs = {ambiental.area_liquida_aproveitavel_m2,
            aproveitamento.area_liquida_aproveitavel_m2,
            urbanismo.area_liquida_aproveitavel_m2}
    assert len(liqs) == 1  # mesmo número nas 3 abas (zero divergência)
