"""Login com Google — verificação do ID token (Google Identity Services).

O front recebe do botão do Google um ID token (JWT assinado pelo Google) e o manda para
``POST /api/auth/google``. AQUI ele é verificado contra o endpoint ``tokeninfo`` do próprio
Google (que valida assinatura e expiração do lado deles) + checagens locais:

- ``aud`` == ``GOOGLE_CLIENT_ID`` (o token foi emitido para o NOSSO app, não outro);
- ``email_verified`` == true (nunca criar conta por e-mail não verificado).

Escolha deliberada: ``tokeninfo`` em vez de validar a assinatura localmente (JWKS +
``cryptography``) — uma chamada HTTPS por login, zero dependência nova, e o botão do Google
já exige rede até o Google de qualquer forma. Se o volume de logins crescer, trocar por
``jwt.PyJWKClient`` com cache é o upgrade natural (mesma interface).

Gate por env: sem ``GOOGLE_CLIENT_ID`` o recurso fica DESLIGADO (endpoint responde 503
com instrução). Testes injetam um verificador-stub via ``get_verificador_google``.
"""

from __future__ import annotations

import os

import httpx

_TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"


class ErroGoogleLogin(Exception):
    """Token recusado — a mensagem é segura para mostrar ao usuário."""


class VerificadorGoogle:
    def __init__(self, client_id: str):
        self._client_id = client_id

    def verificar(self, credential: str) -> dict:
        """Valida o ID token e devolve ``{"email", "nome"}``. Levanta ErroGoogleLogin."""
        try:
            resp = httpx.get(_TOKENINFO_URL, params={"id_token": credential}, timeout=10)
        except httpx.HTTPError:
            raise ErroGoogleLogin(
                "Não foi possível confirmar o login com o Google agora. "
                "Tente novamente em instantes."
            )
        if resp.status_code != 200:
            raise ErroGoogleLogin("Login do Google inválido ou expirado. Tente de novo.")
        dados = resp.json()
        if dados.get("aud") != self._client_id:
            # Token emitido para OUTRO aplicativo — nunca aceitar.
            raise ErroGoogleLogin("Login do Google inválido para este aplicativo.")
        if dados.get("email_verified") not in (True, "true"):
            raise ErroGoogleLogin(
                "Seu e-mail do Google ainda não está verificado. "
                "Verifique-o no Google e tente de novo."
            )
        email = (dados.get("email") or "").strip().lower()
        if not email:
            raise ErroGoogleLogin("O Google não informou um e-mail para esta conta.")
        return {"email": email, "nome": dados.get("name") or None}


def get_verificador_google() -> VerificadorGoogle | None:
    """Dependência FastAPI: verificador real quando GOOGLE_CLIENT_ID existe; senão None."""
    client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    return VerificadorGoogle(client_id) if client_id else None
