"""RURAL-6 (achado do operador, 22/07/2026) — conformidade urbanística × projeto RURAL.

A conformidade (índices da LUOS/Lei 6.766) não se aplica ao chacreamento: a régua é o
módulo rural do INCRA (FMP — Lei 5.868/72). A intenção RURAL fica registrada na última
proposta de urbanismo; a conformidade lê a MESMA fonte da trilha (core/regime.py) e
degrada honesta (avaliada=false + motivo do regime certo), sem pedir LUOS.
"""

from tests.conftest import RET_RETANGULO, make_kmz


def _upload(c):
    r = c.post(
        "/api/analises",
        files={"kmz": ("g.kmz", make_kmz([RET_RETANGULO]), "application/vnd.google-earth.kmz")},
    )
    assert r.status_code == 200, r.text
    return r.json()["analise_id"]


def test_conformidade_sem_proposta_segue_pedindo_luos(client, fonte_urbanismo):
    """Sem proposta de urbanismo → régua urbana conservadora (pede perfil municipal)."""
    aid = _upload(client)
    r = client.get(f"/api/analises/{aid}/conformidade")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["avaliada"] is False
    assert "perfil municipal" in body["motivo"]


def test_conformidade_projeto_rural_nao_cobra_luos(client, gerador_urbanismo, fonte_urbanismo, fmp):
    """Proposta RURAL registrada → a conformidade explica o regime INCRA em vez de pedir LUOS."""
    fmp({"3550605": 20000.0})
    aid = _upload(client)
    r = client.post(
        f"/api/analises/{aid}/urbanismo/propor",
        json={"tipo_loteamento": "loteamento_rural", "publico_alvo": "media"},
    )
    assert r.status_code == 200, r.text

    c = client.get(f"/api/analises/{aid}/conformidade")
    assert c.status_code == 200, c.text
    body = c.json()
    assert body["avaliada"] is False
    assert "RURAL" in body["motivo"]
    assert "FMP" in body["motivo"] and "INCRA" in body["motivo"]
    # E NÃO manda confirmar a LUOS na Fase 1.8 (mensagem urbana antiga).
    assert "Fase 1.8" not in body["motivo"]
