"""Motor de aproveitamento (TRIAGEM, Fase 2.2): teto de lotes urbano + parcelas rurais.

Vias e doação saíram do cálculo (dependem do projeto urbanístico e da diretriz municipal).
O nº de lotes urbano é um TETO = área aproveitável ÷ lote mínimo.
"""

import pytest

from app.core import aproveitamento as m


def test_lotes_teto():
    # 30.000 m² aproveitáveis / lote 200 m² = 150 lotes (teto).
    assert m.lotes_teto(30_000.0, 200.0) == 150


def test_lotes_teto_arredonda_para_baixo():
    assert m.lotes_teto(30_150.0, 200.0) == 150  # floor, nunca vende lote a mais


def test_lotes_teto_lote_invalido():
    with pytest.raises(ValueError):
        m.lotes_teto(30_000.0, 0.0)


def test_rural_parcelas_por_fmp():
    # PARCELA-CHEIA (RURAL-6): o módulo incide sobre a área TOTAL do imóvel — a chácara
    # pode conter mata/APP (Lei 12.651 restringe uso/edificação, não a composição).
    r = m.aproveitamento_rural(area_total=100_000.0, fmp_m2=20_000.0)
    assert r["n_parcelas"] == 5
    assert r["area_m2"] == 100_000.0
    assert "FMP" in r["proveniencia"]
    assert "parcela-cheia" in r["proveniencia"].lower()
    assert "Urbanismo" in r["leitura"]  # aponta o estudo de massa como nº realista


def test_rural_fmp_invalida():
    with pytest.raises(ValueError):
        m.aproveitamento_rural(area_total=100_000.0, fmp_m2=0.0)
