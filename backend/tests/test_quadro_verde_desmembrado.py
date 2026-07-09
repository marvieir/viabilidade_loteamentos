"""Fase 10 (Parte 2) — VERDE DESMEMBRADO: o quadro expõe verde-reserva e sobra-geométrica em
linhas SEPARADAS; a sobra nunca é "área verde" (catálogo §5/§10)."""

from tests.test_urbanismo_grade_adaptativa import _layout_sao_roque


def test_quadro_separa_reserva_de_sobra():
    """Critério P2: o quadro tem `area_verde_reserva` e `sobra_geometrica` em chaves separadas; a
    reserva é verde legítimo, a sobra é sobra (não entra como "área verde")."""
    _, med = _layout_sao_roque()
    q = med.quadro
    assert "area_verde_reserva" in q and "sobra_geometrica" in q
    assert q["area_verde_reserva"]["m2"] >= 0.0
    assert q["sobra_geometrica"]["m2"] >= 0.0
    # a "área verde" legítima (reserva) NÃO inclui a sobra
    assert q["area_verde_reserva"]["m2"] <= q["areas_verdes"]["m2"] + 1.0


def test_reserva_mais_sobra_fecha_o_total_verde():
    """A soma reserva + sobra ≈ o total histórico `areas_verdes` (são as duas partes do verde)."""
    _, med = _layout_sao_roque()
    q = med.quadro
    soma = q["area_verde_reserva"]["m2"] + q["sobra_geometrica"]["m2"]
    assert abs(soma - q["areas_verdes"]["m2"]) <= max(q["areas_verdes"]["m2"] * 0.02, 5.0)


def test_sobra_e_fracao_e_nao_some_no_verde():
    """Em São Roque a sobra geométrica é material (faces sem aproveitamento) — exposta, não escondida
    dentro de "área verde". Prova de que o usuário VÊ a decomposição."""
    _, med = _layout_sao_roque()
    q = med.quadro
    assert q["sobra_geometrica"]["m2"] > 0.0  # há sobra real a mostrar (não zero forçado)


# ------------------------- U8.1 — VERDE CONSOLIDADO (os dois baldes sobre a gleba bruta) -------------------------
def test_verde_consolidado_soma_preservada_mais_reserva_sobre_a_bruta():
    """U8.1: o quadro é sobre a área LÍQUIDA (sem a mata preservada), então a "reserva" parece baixa.
    `consolidar_verde` soma preservada (não-edif., conta p/ APAC) + reserva na base da GLEBA BRUTA e
    devolve o total — os números que a UI mostra no bloco 'Verde ambiental'."""
    from app.core import urbanismo_medida as medida

    _, med = _layout_sao_roque()
    q = med.quadro
    reserva_m2 = q["area_verde_reserva"]["m2"]
    gleba_bruta = 190000.0
    preservada = 52000.0
    vc = medida.consolidar_verde(q, gleba_bruta, preservada)
    assert vc is not None
    # preservada e reserva batem com as entradas; total = soma; % sobre a BRUTA (não a líquida)
    assert abs(vc["preservada"]["m2"] - preservada) < 1.0
    assert abs(vc["reserva"]["m2"] - reserva_m2) < 1.0
    assert abs(vc["total"]["m2"] - (preservada + reserva_m2)) < 1.0
    assert abs(vc["preservada"]["pct_apo"] - preservada / gleba_bruta) < 1e-3
    assert abs(vc["total"]["pct_apo"] - (preservada + reserva_m2) / gleba_bruta) < 1e-3
    # a preservada domina o verde (é o balde que some do quadro) e o total supera a reserva sozinha
    assert vc["total"]["m2"] > reserva_m2
    assert "APAC" in vc["fonte"] and "bruta" in vc["fonte"].lower()  # proveniência (§3) explica o cálculo


def test_consolidar_verde_aceita_schema_quadroareas():
    """Regressão de CAMPO (500 em toda geração): o router passa `QuadroAreasOut` (Pydantic), não o
    dict cru — e o schema não tem `.get()`, então `consolidar_verde` estourava com AttributeError.
    Reproduz o que o router monta e exige que a função aceite os dois (dict e schema)."""
    from app.core import urbanismo_medida as medida
    from app.models.schemas import QuadroAreasOut

    _, med = _layout_sao_roque()
    schema = QuadroAreasOut(**med.quadro)  # EXATAMENTE o objeto que o router passava
    vc = medida.consolidar_verde(schema, 190000.0, 52000.0)
    assert vc is not None and vc["total"]["m2"] > 0
    # e o dict cru segue funcionando idêntico
    vc_dict = medida.consolidar_verde(med.quadro, 190000.0, 52000.0)
    assert vc_dict["total"]["m2"] == vc["total"]["m2"]


def test_verde_consolidado_degrada_sem_gleba_bruta():
    """Sem gleba bruta canônica → None (não inventa denominador — degrada honesto, §5)."""
    from app.core import urbanismo_medida as medida

    _, med = _layout_sao_roque()
    assert medida.consolidar_verde(med.quadro, None, 52000.0) is None
    assert medida.consolidar_verde(med.quadro, 0.0, 52000.0) is None
