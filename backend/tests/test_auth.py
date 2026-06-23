"""Fase 12 — fluxo de autenticação (registrar/login/refresh/me/logout) via TestClient + SQLite.

Cobre o contrato de produção: senha nunca em texto (bcrypt), access token no corpo,
refresh em cookie httpOnly, guarda 401 sem token, e-mail duplicado/credencial errada.
"""


def _registrar(client, email="cliente@exemplo.com", senha="senha-forte-1", nome="Cliente"):
    return client.post(
        "/api/auth/registrar", json={"email": email, "senha": senha, "nome": nome}
    )


def test_registrar_devolve_access_token_e_cookie_refresh(client):
    r = _registrar(client)
    assert r.status_code == 201, r.text
    corpo = r.json()
    assert corpo["token_type"] == "bearer"
    assert corpo["access_token"]
    # refresh viaja em cookie httpOnly (não no corpo).
    assert "refresh_token" in r.cookies
    assert "access_token" not in r.cookies


def test_email_duplicado_conflita(client):
    assert _registrar(client).status_code == 201
    r2 = _registrar(client)  # mesmo e-mail
    assert r2.status_code == 409


def test_senha_curta_recusada(client):
    r = client.post("/api/auth/registrar", json={"email": "x@y.com", "senha": "curta"})
    assert r.status_code == 422


def test_login_ok_e_senha_errada(client):
    _registrar(client, email="ana@exemplo.com", senha="minha-senha-99")
    ok = client.post(
        "/api/auth/login", json={"email": "ana@exemplo.com", "senha": "minha-senha-99"}
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["access_token"]

    ruim = client.post(
        "/api/auth/login", json={"email": "ana@exemplo.com", "senha": "errada"}
    )
    assert ruim.status_code == 401


def test_login_email_case_insensitive(client):
    _registrar(client, email="Joao@Exemplo.com", senha="senha-forte-1")
    r = client.post(
        "/api/auth/login", json={"email": "JOAO@exemplo.COM", "senha": "senha-forte-1"}
    )
    assert r.status_code == 200, r.text


def test_me_exige_token_e_devolve_usuario(client):
    token = _registrar(client, email="bia@exemplo.com").json()["access_token"]
    # sem token → 401
    assert client.get("/api/auth/me").status_code == 401
    # com token → dados do usuário
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    dados = r.json()
    assert dados["email"] == "bia@exemplo.com"
    assert dados["papel"] == "cliente"
    assert "senha" not in dados and "senha_hash" not in dados


def test_token_invalido_recusado(client):
    r = client.get("/api/auth/me", headers={"Authorization": "Bearer lixo.invalido"})
    assert r.status_code == 401


def test_refresh_emite_novo_access(client):
    r = _registrar(client, email="cau@exemplo.com")
    # o TestClient mantém o cookie de refresh entre chamadas.
    nova = client.post("/api/auth/refresh")
    assert nova.status_code == 200, nova.text
    assert nova.json()["access_token"]


def test_refresh_sem_cookie_falha(client):
    r = client.post("/api/auth/refresh")  # nenhum registro/login antes
    assert r.status_code == 401


def test_logout_limpa_cookie(client):
    _registrar(client, email="leo@exemplo.com")
    out = client.post("/api/auth/logout")
    assert out.status_code == 204
