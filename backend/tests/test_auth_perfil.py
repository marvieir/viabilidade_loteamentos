"""Contato obrigatório no 1º login (pedido do operador, 23/07/2026).

O front bloqueia com um modal até nome+celular existirem; o backend expõe
``PATCH /api/auth/perfil`` (logado) e devolve os campos no ``/me`` para o front decidir.
Celular normalizado para dígitos (aceita máscara e +55); validação BR: DDD + 10/11 dígitos.
"""


def _registrar(client, email="perfil@exemplo.com"):
    r = client.post(
        "/api/auth/registrar", json={"email": email, "senha": "senha-forte-1"}
    )
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_me_expoe_celular_vazio(client_anon):
    h = _registrar(client_anon)
    me = client_anon.get("/api/auth/me", headers=h).json()
    assert me["celular"] is None  # front usa isto para abrir o modal


def test_atualizar_perfil_normaliza_celular(client_anon):
    h = _registrar(client_anon, "perfil2@exemplo.com")
    r = client_anon.patch(
        "/api/auth/perfil",
        json={"nome": "  Marco  Vieira ", "celular": "+55 (24) 99999-8888"},
        headers=h,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["nome"] == "Marco Vieira"  # espaços colapsados
    assert body["celular"] == "24999998888"  # dígitos, sem +55
    # E o /me passa a refletir (o modal não reabre).
    me = client_anon.get("/api/auth/me", headers=h).json()
    assert me["celular"] == "24999998888"


def test_celular_invalido_422(client_anon):
    h = _registrar(client_anon, "perfil3@exemplo.com")
    r = client_anon.patch(
        "/api/auth/perfil", json={"nome": "Fulano", "celular": "9999"}, headers=h
    )
    assert r.status_code == 422
    assert "DDD" in r.json()["detail"]


def test_nome_vazio_422(client_anon):
    h = _registrar(client_anon, "perfil4@exemplo.com")
    r = client_anon.patch(
        "/api/auth/perfil", json={"nome": " ", "celular": "24 99999-8888"}, headers=h
    )
    assert r.status_code == 422


def test_perfil_exige_login(client_anon):
    r = client_anon.patch(
        "/api/auth/perfil", json={"nome": "X Y", "celular": "24999998888"}
    )
    assert r.status_code in (401, 403)
