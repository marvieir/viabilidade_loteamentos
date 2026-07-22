"""Regime RURAL no urbanismo (achado do operador, 21/07/2026; decisão B).

O tipo "loteamento_rural" tratava chácara com régua urbana: piso federal de 125 m² e lotes
de 300 m² — abaixo da Fração Mínima de Parcelamento (FMP/módulo rural, Lei 5.868/72 art. 8º).
Contrato corrigido: piso do lote = FMP do município (tabela INCRA; sem tabela → default 2 ha
ROTULADO "confirmar no CCIR"); doação/verde/institucional permanecem no quadro como
referência rotulada no aviso. O regime urbano segue intacto.
"""

from tests.conftest import RET_RETANGULO, make_kmz


def _upload(client):
    r = client.post(
        "/api/analises",
        files={"kmz": ("g.kmz", make_kmz([RET_RETANGULO]), "application/vnd.google-earth.kmz")},
    )
    assert r.status_code == 200, r.text
    return r.json()["analise_id"]


def _propor_rural(client, aid, **extra):
    return client.post(
        f"/api/analises/{aid}/urbanismo/propor",
        json={"tipo_loteamento": "loteamento_rural", "publico_alvo": "media", **extra},
    )


def test_rural_usa_fmp_da_tabela(client, gerador_urbanismo, fonte_urbanismo, fmp):
    fmp({"3550605": 20000.0})  # São Roque na tabela INCRA de teste
    aid = _upload(client)
    r = _propor_rural(client, aid)
    assert r.status_code == 200, r.text
    d = r.json()["diretrizes"]
    assert d["regime"] == "rural"
    assert d["piso_lote_efetivo_m2"] == 20000.0
    assert d["fmp_m2"] == 20000.0 and d["fmp_origem"] == "tabela INCRA"
    assert "RURAL" in d["aviso"] and "FMP" in d["aviso"] and "20.000" in d["aviso"]
    assert "referência" in d["aviso"]  # decisão B: quadro urbano rotulado, não removido
    # Nenhuma chácara abaixo do módulo: a distribuição respeita a faixa legal rural.
    dist = r.json()["distribuicao_tamanhos"]
    assert dist["fora_da_faixa"] == 0
    assert r.json()["indicadores"]["n_lotes"] >= 1


def test_rural_sem_tabela_usa_default_rotulado(client, gerador_urbanismo, fonte_urbanismo, fmp):
    fmp({})  # município fora da tabela → default 2 ha com proveniência explícita
    aid = _upload(client)
    r = _propor_rural(client, aid)
    assert r.status_code == 200, r.text
    d = r.json()["diretrizes"]
    assert d["piso_lote_efetivo_m2"] == 20000.0
    assert d["fmp_origem"] == "default 2 ha (confirmar no CCIR)"


def test_rural_teto_respeita_lote_max_do_operador(
    client, gerador_urbanismo, fonte_urbanismo, fmp
):
    fmp({"3550605": 20000.0})
    aid = _upload(client)
    r = _propor_rural(client, aid, lote_max_m2=50000.0)
    assert r.status_code == 200, r.text
    d = r.json()["diretrizes"]
    assert d["teto_lote_m2"] == 50000.0
    # lote_max abaixo da FMP não fura o piso legal
    r2 = _propor_rural(client, aid, lote_max_m2=500.0)
    assert r2.status_code == 200, r2.text
    assert r2.json()["diretrizes"]["teto_lote_m2"] == 20000.0


def test_urbano_continua_intacto(client, gerador_urbanismo, fonte_urbanismo, fmp):
    fmp({"3550605": 20000.0})  # a tabela FMP existir NÃO pode contaminar o regime urbano
    aid = _upload(client)
    r = client.post(
        f"/api/analises/{aid}/urbanismo/propor",
        json={"tipo_loteamento": "aberto", "publico_alvo": "media"},
    )
    assert r.status_code == 200, r.text
    d = r.json()["diretrizes"]
    assert d["regime"] is None and d["fmp_m2"] is None
    assert d["piso_lote_efetivo_m2"] < 1000  # régua urbana (federal/mercado), não FMP
