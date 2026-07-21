"""Decisão de produto (21/07/2026, operador): gleba com aproveitável abaixo de 1 ha NÃO gera
estudo de parcelamento — recusa 422 EXPLICADA (nessa escala o caminho é desmembramento), em vez
de um quadro distorcido pelas reservas de quadra inteira (o caso da calibração 9.3 em que o
verde/doação inflava acima do programa numa gleba de ~5.000 m²)."""

from tests.conftest import LAT0, LON0, make_kmz

# ~92 m × ~55 m ≈ 5.100 m² — abaixo do mínimo de 10.000 m² (1 ha).
RET_MINUSCULO = [
    (LON0, LAT0),
    (LON0 + 0.0009, LAT0),
    (LON0 + 0.0009, LAT0 + 0.0005),
    (LON0, LAT0 + 0.0005),
]


def test_gleba_minuscula_recusada_com_explicacao(client, gerador_urbanismo, fonte_urbanismo):
    r = client.post(
        "/api/analises",
        files={"kmz": ("g.kmz", make_kmz([RET_MINUSCULO]), "application/vnd.google-earth.kmz")},
    )
    assert r.status_code == 200, r.text
    aid = r.json()["analise_id"]

    resp = client.post(f"/api/analises/{aid}/urbanismo/propor", json={"publico_alvo": "alta"})
    assert resp.status_code == 422, resp.text
    detalhe = resp.json()["detail"]
    # Mensagem ACIONÁVEL: diz o porquê (escala de desmembramento) e o mínimo em ha.
    assert "desmembramento" in detalhe
    assert "1 ha" in detalhe
