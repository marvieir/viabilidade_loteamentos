"""Alerta de declividade ≥30% ciente do REGIME (achado do operador, 22/07/2026).

A vedação de 30% é do parcelamento URBANO (Lei 6.766, art. 3º, § único, II). No regime
RURAL (INCRA/Lei 5.868) ela não veda a divisão — restringe construção/uso, e a APP de
encosta só nasce acima de 45° (Lei 12.651, art. 4º, V). Um projeto de chácaras não pode
carimbar "risco alto" por uma régua que não o rege.
"""

from app.core.alertas_geo import alerta_declividade


def test_urbano_continua_vedacao_critica():
    a = alerta_declividade(77.85, rural=False)
    assert a.nivel == "vedado"
    assert "vedação" in a.descricao and "6.766" in a.descricao
    assert "77.85 ha" in a.descricao
    # E aponta a saída para quem é rural (o alerta educa, não só acusa).
    assert "Loteamento rural" in a.descricao


def test_rural_vira_atencao_com_base_legal_correta():
    a = alerta_declividade(77.85, rural=True)
    assert a.nivel == "atencao"  # sai dos críticos → risco alto não dispara por isto
    assert "não veda a divisão" in a.descricao
    assert "6.766" in a.descricao  # nomeia de onde vem a régua urbana…
    assert "45°" in a.descricao and "12.651" in a.descricao  # …e a régua rural real (APP)
