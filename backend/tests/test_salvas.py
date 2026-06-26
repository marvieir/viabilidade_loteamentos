"""Fase 12.2 — análises salvas (área do cliente): CRUD escopado ao dono + carregar.

Cobre o isolamento multi-tenant (um cliente não vê/edita a análise de outro), o ciclo
salvar→listar→obter→editar→excluir e a reidratação (carregar devolve o shape do upload).
"""

from tests.conftest import RET_RETANGULO, _fechar


def _token(client, email="dono@exemplo.com", senha="senha-forte-1"):
    r = client.post("/api/auth/registrar", json={"email": email, "senha": senha})
    assert r.status_code == 201, r.text
    return r.json()["access_token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _geojson_ret():
    anel = _fechar(RET_RETANGULO)
    return {"type": "Polygon", "coordinates": [[[lon, lat] for lon, lat in anel]]}


def _payload(titulo="Gleba Teste"):
    return {
        "titulo": titulo,
        "kmz_nome": "gleba.kmz",
        "gleba_geojson": _geojson_ret(),
        "cidade": "São Roque",
        "uf": "SP",
        "area_ha": 12.34,
        "resultados": {"aproveitamento": {"pct": 37.4}},
    }


def test_salvar_exige_login(client_anon):
    assert client_anon.post("/api/salvas", json=_payload()).status_code in (401, 403)


def test_ciclo_salvar_listar_obter(client):
    tok = _token(client)
    criada = client.post("/api/salvas", json=_payload(), headers=_auth(tok))
    assert criada.status_code == 201, criada.text
    aid = criada.json()["id"]

    lista = client.get("/api/salvas", headers=_auth(tok)).json()
    assert len(lista) == 1
    assert lista[0]["titulo"] == "Gleba Teste"
    assert lista[0]["cidade"] == "São Roque" and lista[0]["uf"] == "SP"

    det = client.get(f"/api/salvas/{aid}", headers=_auth(tok)).json()
    assert det["resultados"]["aproveitamento"]["pct"] == 37.4
    assert det["gleba_geojson"]["type"] == "Polygon"


def test_editar_atualiza_resultados(client):
    tok = _token(client)
    aid = client.post("/api/salvas", json=_payload(), headers=_auth(tok)).json()["id"]
    novo = _payload(titulo="Gleba Editada")
    novo["resultados"] = {"aproveitamento": {"pct": 41.9}}
    r = client.put(f"/api/salvas/{aid}", json=novo, headers=_auth(tok))
    assert r.status_code == 200, r.text
    assert r.json()["titulo"] == "Gleba Editada"
    assert r.json()["resultados"]["aproveitamento"]["pct"] == 41.9


def test_excluir(client):
    tok = _token(client)
    aid = client.post("/api/salvas", json=_payload(), headers=_auth(tok)).json()["id"]
    assert client.delete(f"/api/salvas/{aid}", headers=_auth(tok)).status_code == 204
    assert client.get("/api/salvas", headers=_auth(tok)).json() == []


def test_isolamento_entre_clientes(client):
    dono = _token(client, email="a@exemplo.com")
    intruso = _token(client, email="b@exemplo.com")
    aid = client.post("/api/salvas", json=_payload(), headers=_auth(dono)).json()["id"]

    # o intruso não vê na lista...
    assert client.get("/api/salvas", headers=_auth(intruso)).json() == []
    # ...nem acessa por id (404, não 403, p/ não vazar existência)...
    assert client.get(f"/api/salvas/{aid}", headers=_auth(intruso)).status_code == 404
    # ...nem edita ou exclui.
    assert client.put(
        f"/api/salvas/{aid}", json=_payload(), headers=_auth(intruso)
    ).status_code == 404
    assert client.delete(f"/api/salvas/{aid}", headers=_auth(intruso)).status_code == 404


def test_carregar_reidrata_gleba(client):
    tok = _token(client)
    aid = client.post("/api/salvas", json=_payload(), headers=_auth(tok)).json()["id"]
    r = client.post(f"/api/salvas/{aid}/carregar", headers=_auth(tok))
    assert r.status_code == 200, r.text
    corpo = r.json()
    assert corpo["analise_id"]
    assert corpo["geometria"]["geojson"]["type"] == "Polygon"
    assert corpo["geometria"]["area_ha"] > 0
    # a análise reidratada responde às dimensões (pipeline normal): pede aproveitamento.
    ap = client.post(
        f"/api/analises/{corpo['analise_id']}/aproveitamento",
        json={"regime": "URBANO", "lote_min_m2": 250},
        headers=_auth(tok),  # Fase 13 — a análise reidratada é do dono (tok); acesso exige o dono
    )
    assert ap.status_code == 200, ap.text
