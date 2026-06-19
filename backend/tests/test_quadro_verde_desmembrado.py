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
