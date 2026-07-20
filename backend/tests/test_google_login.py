"""Login com Google — endpoint /api/auth/google com verificador-stub (sem rede).

Contrato coberto: conta nova nasce pelo Google (sem senha), conta existente com o mesmo
e-mail é VINCULADA (mesmo usuário, análises preservadas), token recusado → 401, recurso
desligado (sem GOOGLE_CLIENT_ID) → 503, e o login por senha numa conta nascida pelo
Google devolve mensagem acionável.
"""

import pytest

from app.core.google_login import ErroGoogleLogin, get_verificador_google
from app.main import app


class StubVerificador:
    """Aceita qualquer credential e devolve o payload configurado; ou recusa sempre."""

    def __init__(self, email="google@exemplo.com", nome="Conta Google", recusa=False):
        self._payload = {"email": email, "nome": nome}
        self._recusa = recusa

    def verificar(self, credential):
        if self._recusa:
            raise ErroGoogleLogin("Login do Google inválido ou expirado. Tente de novo.")
        return dict(self._payload)


@pytest.fixture
def verificador_google():
    """Injeta um verificador-stub. Uso: ``verificador_google(email=...)`` no teste."""

    def _set(**kw):
        app.dependency_overrides[get_verificador_google] = lambda: StubVerificador(**kw)

    _set()
    yield _set
    app.dependency_overrides.pop(get_verificador_google, None)


def _google(client, credential="id-token-de-teste"):
    return client.post("/api/auth/google", json={"credential": credential})


def test_google_cria_conta_nova_sem_senha(client_anon, verificador_google):
    r = _google(client_anon)
    assert r.status_code == 200, r.text
    access = r.json()["access_token"]
    assert "refresh_token" in r.cookies  # sessão normal: refresh em cookie httpOnly

    me = client_anon.get("/api/auth/me", headers={"Authorization": f"Bearer {access}"})
    assert me.status_code == 200
    dados = me.json()
    assert dados["email"] == "google@exemplo.com"
    assert dados["nome"] == "Conta Google"
    assert dados["papel"] == "cliente"

    # Login por SENHA nesta conta orienta o caminho certo (Google ou criar senha).
    senha = client_anon.post(
        "/api/auth/login", json={"email": "google@exemplo.com", "senha": "qualquer-senha-1"}
    )
    assert senha.status_code == 401
    assert "Google" in senha.json()["detail"]


def test_google_vincula_conta_existente_pelo_email(client_anon, verificador_google):
    r = client_anon.post(
        "/api/auth/registrar",
        json={"email": "misto@exemplo.com", "senha": "senha-forte-1"},
    )
    assert r.status_code == 201
    id_original = client_anon.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {r.json()['access_token']}"}
    ).json()["id"]

    verificador_google(email="misto@exemplo.com")
    g = _google(client_anon)
    assert g.status_code == 200, g.text
    id_google = client_anon.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {g.json()['access_token']}"}
    ).json()["id"]
    # MESMO usuário — as análises salvas continuam dele.
    assert id_google == id_original

    # A senha original continua valendo (vincular não apaga a senha).
    ok = client_anon.post(
        "/api/auth/login", json={"email": "misto@exemplo.com", "senha": "senha-forte-1"}
    )
    assert ok.status_code == 200


def test_google_email_case_insensitive_no_vinculo(client_anon, verificador_google):
    client_anon.post(
        "/api/auth/registrar", json={"email": "Caixa@Exemplo.com", "senha": "senha-forte-1"}
    )
    verificador_google(email="caixa@exemplo.com")
    r = _google(client_anon)
    assert r.status_code == 200, r.text
    me = client_anon.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {r.json()['access_token']}"}
    )
    assert me.json()["email"] == "caixa@exemplo.com"


def test_google_token_recusado_401(client_anon, verificador_google):
    verificador_google(recusa=True)
    r = _google(client_anon)
    assert r.status_code == 401


def test_google_desligado_503(client_anon):
    # Sem override e sem GOOGLE_CLIENT_ID no ambiente → recurso desligado com instrução.
    r = _google(client_anon)
    assert r.status_code == 503
    assert "GOOGLE_CLIENT_ID" in r.json()["detail"]


def test_conta_google_define_primeira_senha_sem_senha_atual(client_anon, verificador_google):
    access = _google(client_anon).json()["access_token"]
    r = client_anon.post(
        "/api/auth/trocar-senha",
        json={"senha_nova": "primeira-senha-forte-1"},
        headers={"Authorization": f"Bearer {access}"},
    )
    assert r.status_code == 200, r.text
    # Agora o login por senha funciona (conta ganhou senha própria).
    ok = client_anon.post(
        "/api/auth/login",
        json={"email": "google@exemplo.com", "senha": "primeira-senha-forte-1"},
    )
    assert ok.status_code == 200
