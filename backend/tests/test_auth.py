"""Fase 12 — fluxo de autenticação (registrar/login/refresh/me/logout) via TestClient + SQLite.

Cobre o contrato de produção: senha nunca em texto (bcrypt), access token no corpo,
refresh em cookie httpOnly, guarda 401 sem token, e-mail duplicado/credencial errada.
"""


def _registrar(client_anon, email="cliente@exemplo.com", senha="senha-forte-1", nome="Cliente"):
    return client_anon.post(
        "/api/auth/registrar", json={"email": email, "senha": senha, "nome": nome}
    )


def test_registrar_devolve_access_token_e_cookie_refresh(client_anon):
    r = _registrar(client_anon)
    assert r.status_code == 201, r.text
    corpo = r.json()
    assert corpo["token_type"] == "bearer"
    assert corpo["access_token"]
    # refresh viaja em cookie httpOnly (não no corpo).
    assert "refresh_token" in r.cookies
    assert "access_token" not in r.cookies


def test_email_duplicado_conflita(client_anon):
    assert _registrar(client_anon).status_code == 201
    r2 = _registrar(client_anon)  # mesmo e-mail
    assert r2.status_code == 409


def test_senha_curta_recusada(client_anon):
    r = client_anon.post("/api/auth/registrar", json={"email": "x@y.com", "senha": "curta"})
    assert r.status_code == 422


def test_login_ok_e_senha_errada(client_anon):
    _registrar(client_anon, email="ana@exemplo.com", senha="minha-senha-99")
    ok = client_anon.post(
        "/api/auth/login", json={"email": "ana@exemplo.com", "senha": "minha-senha-99"}
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["access_token"]

    ruim = client_anon.post(
        "/api/auth/login", json={"email": "ana@exemplo.com", "senha": "errada"}
    )
    assert ruim.status_code == 401


def test_login_email_case_insensitive(client_anon):
    _registrar(client_anon, email="Joao@Exemplo.com", senha="senha-forte-1")
    r = client_anon.post(
        "/api/auth/login", json={"email": "JOAO@exemplo.COM", "senha": "senha-forte-1"}
    )
    assert r.status_code == 200, r.text


def test_me_exige_token_e_devolve_usuario(client_anon):
    token = _registrar(client_anon, email="bia@exemplo.com").json()["access_token"]
    # sem token → 401
    assert client_anon.get("/api/auth/me").status_code == 401
    # com token → dados do usuário
    r = client_anon.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    dados = r.json()
    assert dados["email"] == "bia@exemplo.com"
    assert dados["papel"] == "cliente"
    assert "senha" not in dados and "senha_hash" not in dados


def test_token_invalido_recusado(client_anon):
    r = client_anon.get("/api/auth/me", headers={"Authorization": "Bearer lixo.invalido"})
    assert r.status_code == 401


def test_refresh_emite_novo_access(client_anon):
    r = _registrar(client_anon, email="cau@exemplo.com")
    # o TestClient mantém o cookie de refresh entre chamadas.
    nova = client_anon.post("/api/auth/refresh")
    assert nova.status_code == 200, nova.text
    assert nova.json()["access_token"]


def test_refresh_sem_cookie_falha(client_anon):
    r = client_anon.post("/api/auth/refresh")  # nenhum registro/login antes
    assert r.status_code == 401


def test_logout_limpa_cookie(client_anon):
    _registrar(client_anon, email="leo@exemplo.com")
    out = client_anon.post("/api/auth/logout")
    assert out.status_code == 204
