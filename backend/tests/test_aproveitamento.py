"""Critério de aceite #2 e #3 — valores-ouro do motor de aproveitamento (Aula 09)."""

import pytest

from app.core import aproveitamento as m

# Aula 09: área 50.000 m², vias 11.500 m², doação 20%, lote 200 m².
AREA = 50_000.0
VIAS = 11_500.0
DOACAO = 0.20
LOTE = 200.0


def test_base_total():
    r = m.aproveitamento_loteamento(AREA, VIAS, DOACAO, "total", 0.35, LOTE)
    assert r["area_aproveitavel_m2"] == 28_500.0
    assert r["pct_aproveitamento"] == 0.57
    assert r["n_lotes"] == 142
    assert r["base_doacao"] == "total"


def test_base_liquida():
    r = m.aproveitamento_loteamento(AREA, VIAS, DOACAO, "liquida", 0.35, LOTE)
    assert r["area_aproveitavel_m2"] == 30_800.0
    assert r["pct_aproveitamento"] == 0.616
    assert r["n_lotes"] == 154


def test_base_combinada():
    r = m.aproveitamento_loteamento(AREA, VIAS, DOACAO, "combinada", 0.35, LOTE)
    assert r["area_aproveitavel_m2"] == 32_500.0
    assert r["pct_aproveitamento"] == 0.65
    assert r["n_lotes"] == 162


def test_base_invalida():
    with pytest.raises(ValueError):
        m.aproveitamento_loteamento(AREA, VIAS, DOACAO, "xpto", 0.35, LOTE)


def test_desmembramento_default():
    r = m.aproveitamento_desmembramento(AREA, 0.74, LOTE)
    assert r["pct_aproveitamento"] == 0.74
    assert r["area_aproveitavel_m2"] == 37_000.0
    assert r["n_lotes"] == 185
    assert "não é exigência legal" in r["proveniencia"]


def test_proveniencia_loteamento():
    r = m.aproveitamento_loteamento(AREA, VIAS, DOACAO, "total", 0.35, LOTE)
    assert "9.785" in r["proveniencia"]
