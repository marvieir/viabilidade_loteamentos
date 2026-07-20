"""Recuperação de senha (esqueci/redefinir) + troca logada — fluxo completo via TestClient.

Contrato coberto:
- /esqueci responde 200 com a MESMA mensagem exista ou não a conta (anti-enumeração);
- o e-mail sai em background com um link cujo token é de USO ÚNICO e expira;
- /redefinir troca a senha (login antigo falha, novo funciona) e DERRUBA os refresh
  antigos (claim ``sh``);
- /trocar-senha logado exige a senha atual e mantém a própria sessão viva.

O envio real de SMTP nunca acontece aqui: ``_enviar_email_reset`` é capturado por
monkeypatch (o token em claro só existe no link).
"""

from datetime import datetime, timedelta, timezone

import pytest

import app.routers.auth as auth_router
from app.models.db_models import ResetSenhaToken


@pytest.fixture
def links(monkeypatch):
    """Captura os links de redefinição que sairiam por e-mail (destino, link)."""
    capturados: list[tuple[str, str]] = []
    monkeypatch.setattr(
        auth_router, "_enviar_email_reset", lambda destino, link: capturados.append((destino, link))
    )
    return capturados


def _registrar(client_anon, email="reset@exemplo.com", senha="senha-original-1"):
    r = client_anon.post("/api/auth/registrar", json={"email": email, "senha": senha})
    assert r.status_code == 201, r.text
    return r


def _token_do_link(link: str) -> str:
    assert "/redefinir?token=" in link
    return link.split("token=", 1)[1]


def test_esqueci_mesma_resposta_com_e_sem_conta(client_anon, links):
    _registrar(client_anon)
    com_conta = client_anon.post("/api/auth/esqueci", json={"email": "reset@exemplo.com"})
    sem_conta = client_anon.post("/api/auth/esqueci", json={"email": "ninguem@exemplo.com"})
    assert com_conta.status_code == 200 and sem_conta.status_code == 200
    # Mensagem idêntica — a resposta não denuncia se o e-mail existe.
    assert com_conta.json() == sem_conta.json()
    # Mas o e-mail só saiu para a conta real.
    assert [d for d, _ in links] == ["reset@exemplo.com"]


def test_fluxo_completo_redefinir(client_anon, links):
    _registrar(client_anon)
    client_anon.post("/api/auth/esqueci", json={"email": "reset@exemplo.com"})
    token = _token_do_link(links[0][1])

    r = client_anon.post(
        "/api/auth/redefinir", json={"token": token, "senha": "senha-nova-forte-2"}
    )
    assert r.status_code == 200, r.text

    # Senha antiga morreu; a nova entra.
    antiga = client_anon.post(
        "/api/auth/login", json={"email": "reset@exemplo.com", "senha": "senha-original-1"}
    )
    assert antiga.status_code == 401
    nova = client_anon.post(
        "/api/auth/login", json={"email": "reset@exemplo.com", "senha": "senha-nova-forte-2"}
    )
    assert nova.status_code == 200, nova.text


def test_token_e_uso_unico(client_anon, links):
    _registrar(client_anon)
    client_anon.post("/api/auth/esqueci", json={"email": "reset@exemplo.com"})
    token = _token_do_link(links[0][1])
    assert (
        client_anon.post(
            "/api/auth/redefinir", json={"token": token, "senha": "senha-nova-forte-2"}
        ).status_code
        == 200
    )
    repetido = client_anon.post(
        "/api/auth/redefinir", json={"token": token, "senha": "outra-senha-forte-3"}
    )
    assert repetido.status_code == 400
    assert "Esqueci minha senha" in repetido.json()["detail"]


def test_token_invalido_e_expirado(client_anon, links):
    r = client_anon.post(
        "/api/auth/redefinir", json={"token": "lixo-inexistente", "senha": "senha-forte-1"}
    )
    assert r.status_code == 400

    _registrar(client_anon)
    client_anon.post("/api/auth/esqueci", json={"email": "reset@exemplo.com"})
    token = _token_do_link(links[0][1])
    # Envelhece o registro direto no banco (o TTL real é 60 min).
    from app.core.db import SessionLocal

    with SessionLocal() as db:
        registro = db.query(ResetSenhaToken).one()
        registro.expira_em = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.commit()
    r = client_anon.post(
        "/api/auth/redefinir", json={"token": token, "senha": "senha-nova-forte-2"}
    )
    assert r.status_code == 400


def test_pedido_novo_invalida_link_anterior(client_anon, links):
    _registrar(client_anon)
    client_anon.post("/api/auth/esqueci", json={"email": "reset@exemplo.com"})
    client_anon.post("/api/auth/esqueci", json={"email": "reset@exemplo.com"})
    token_velho = _token_do_link(links[0][1])
    token_novo = _token_do_link(links[1][1])
    assert (
        client_anon.post(
            "/api/auth/redefinir", json={"token": token_velho, "senha": "senha-forte-2x"}
        ).status_code
        == 400
    )
    assert (
        client_anon.post(
            "/api/auth/redefinir", json={"token": token_novo, "senha": "senha-forte-2x"}
        ).status_code
        == 200
    )


def test_redefinir_derruba_refresh_antigo(client_anon, links):
    _registrar(client_anon)  # o TestClient guarda o cookie de refresh desta sessão
    client_anon.post("/api/auth/esqueci", json={"email": "reset@exemplo.com"})
    token = _token_do_link(links[0][1])
    client_anon.post("/api/auth/redefinir", json={"token": token, "senha": "senha-nova-forte-2"})
    # O refresh emitido ANTES da troca não vale mais (claim sh divergiu).
    r = client_anon.post("/api/auth/refresh")
    assert r.status_code == 401
    assert "senha" in r.json()["detail"].lower()


def test_trocar_senha_logado(client_anon):
    access = _registrar(client_anon, email="troca@exemplo.com").json()["access_token"]
    h = {"Authorization": f"Bearer {access}"}

    errada = client_anon.post(
        "/api/auth/trocar-senha",
        json={"senha_atual": "nao-e-esta", "senha_nova": "senha-nova-forte-2"},
        headers=h,
    )
    assert errada.status_code == 401

    ok = client_anon.post(
        "/api/auth/trocar-senha",
        json={"senha_atual": "senha-original-1", "senha_nova": "senha-nova-forte-2"},
        headers=h,
    )
    assert ok.status_code == 200, ok.text
    # A PRÓPRIA sessão segue viva: o endpoint rotacionou o cookie de refresh.
    assert client_anon.post("/api/auth/refresh").status_code == 200
    # E o login passa a exigir a senha nova.
    assert (
        client_anon.post(
            "/api/auth/login", json={"email": "troca@exemplo.com", "senha": "senha-nova-forte-2"}
        ).status_code
        == 200
    )


def test_trocar_senha_exige_login(client_anon):
    r = client_anon.post(
        "/api/auth/trocar-senha", json={"senha_atual": "x", "senha_nova": "senha-forte-1"}
    )
    assert r.status_code == 401


def test_senha_nova_curta_recusada(client_anon, links):
    _registrar(client_anon)
    client_anon.post("/api/auth/esqueci", json={"email": "reset@exemplo.com"})
    token = _token_do_link(links[0][1])
    r = client_anon.post("/api/auth/redefinir", json={"token": token, "senha": "curta"})
    assert r.status_code == 422
