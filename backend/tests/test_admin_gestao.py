"""ADMIN-1 — gestão de contas: desativar corta o acesso NA HORA; excluir é definitivo."""

from tests.test_admin import _auth, _criar_admin, _login, _payload, _registrar


def _uid_por_email(client, adm, email):
    clientes = client.get("/api/admin/clientes", headers=_auth(adm)).json()
    return next(c["id"] for c in clientes if c["email"] == email)


def test_gestao_exige_admin(client_anon):
    tok = _registrar(client_anon, "g-cliente@exemplo.com")
    assert (
        client_anon.put(
            "/api/admin/clientes/x/ativo", json={"ativo": False}, headers=_auth(tok)
        ).status_code
        == 403
    )
    assert (
        client_anon.delete("/api/admin/clientes/x?email=x@x.com", headers=_auth(tok)).status_code
        == 403
    )


def test_desativar_corta_acesso_e_reativar_devolve(client_anon):
    tok = _registrar(client_anon, "g-alvo@exemplo.com")
    _criar_admin("g-adm@exemplo.com")
    adm = _login(client_anon, "g-adm@exemplo.com", "senha-admin-1")
    uid = _uid_por_email(client_anon, adm, "g-alvo@exemplo.com")

    # Antes: o alvo acessa normalmente.
    assert client_anon.get("/api/salvas", headers=_auth(tok)).status_code == 200

    r = client_anon.put(
        f"/api/admin/clientes/{uid}/ativo", json={"ativo": False}, headers=_auth(adm)
    )
    assert r.status_code == 200 and r.json()["ativo"] is False
    # Corte IMEDIATO: o token existente morre e o login recusa.
    assert client_anon.get("/api/salvas", headers=_auth(tok)).status_code == 401
    login = client_anon.post(
        "/api/auth/login", json={"email": "g-alvo@exemplo.com", "senha": "senha-forte-1"}
    )
    assert login.status_code in (401, 403)

    # Reativar devolve o acesso (a conta e as análises nunca sumiram).
    client_anon.put(f"/api/admin/clientes/{uid}/ativo", json={"ativo": True}, headers=_auth(adm))
    tok2 = _login(client_anon, "g-alvo@exemplo.com", "senha-forte-1")
    assert client_anon.get("/api/salvas", headers=_auth(tok2)).status_code == 200


def test_guardas_do_gestao(client_anon):
    _criar_admin("g-adm2@exemplo.com")
    _criar_admin("g-adm3@exemplo.com")
    adm = _login(client_anon, "g-adm2@exemplo.com", "senha-admin-1")
    uid_adm2 = _uid_por_email(client_anon, adm, "g-adm2@exemplo.com")
    uid_adm3 = _uid_por_email(client_anon, adm, "g-adm3@exemplo.com")

    # Auto-alteração: 400; outra conta admin: 403; inexistente: 404.
    assert (
        client_anon.put(
            f"/api/admin/clientes/{uid_adm2}/ativo", json={"ativo": False}, headers=_auth(adm)
        ).status_code
        == 400
    )
    assert (
        client_anon.put(
            f"/api/admin/clientes/{uid_adm3}/ativo", json={"ativo": False}, headers=_auth(adm)
        ).status_code
        == 403
    )
    assert (
        client_anon.put(
            "/api/admin/clientes/nao-existe/ativo", json={"ativo": False}, headers=_auth(adm)
        ).status_code
        == 404
    )


def test_excluir_definitivo_com_confirmacao(client_anon):
    tok = _registrar(client_anon, "g-excluir@exemplo.com")
    client_anon.post("/api/salvas", json=_payload("A", "São Roque", "SP"), headers=_auth(tok))
    _criar_admin("g-adm4@exemplo.com")
    adm = _login(client_anon, "g-adm4@exemplo.com", "senha-admin-1")
    uid = _uid_por_email(client_anon, adm, "g-excluir@exemplo.com")

    # E-mail de confirmação errado → 422 e NADA é apagado.
    assert (
        client_anon.delete(
            f"/api/admin/clientes/{uid}?email=errado@exemplo.com", headers=_auth(adm)
        ).status_code
        == 422
    )
    assert client_anon.get("/api/salvas", headers=_auth(tok)).status_code == 200

    # Confirmação certa → 204; conta some (login recusa), análises somem da lista admin.
    assert (
        client_anon.delete(
            f"/api/admin/clientes/{uid}?email=g-excluir@exemplo.com", headers=_auth(adm)
        ).status_code
        == 204
    )
    login = client_anon.post(
        "/api/auth/login", json={"email": "g-excluir@exemplo.com", "senha": "senha-forte-1"}
    )
    assert login.status_code in (401, 403)
    clientes = client_anon.get("/api/admin/clientes", headers=_auth(adm)).json()
    assert all(c["email"] != "g-excluir@exemplo.com" for c in clientes)
    # Idempotência honesta: excluir de novo → 404.
    assert (
        client_anon.delete(
            f"/api/admin/clientes/{uid}?email=g-excluir@exemplo.com", headers=_auth(adm)
        ).status_code
        == 404
    )
