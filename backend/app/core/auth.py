"""Fase 12 — autenticação (produção). Senha com bcrypt; sessão com JWT.

- **Senha:** bcrypt via passlib (nunca em texto).
- **Access token:** JWT curto (30 min), assinado com ``JWT_SECRET`` (env), enviado no
  header ``Authorization: Bearer``. Guardado em memória no front (resistente a XSS).
- **Refresh token:** JWT longo (7 dias), assinado com ``JWT_REFRESH_SECRET``, viaja em
  cookie httpOnly+SameSite (não acessível por JS).
- **Guardas:** ``usuario_atual`` (decodifica o access token) e ``requer_admin``.

Os segredos vêm do ambiente; há um default APENAS para dev/teste (com aviso). Em produção
defina ``JWT_SECRET``/``JWT_REFRESH_SECRET`` por env (Compose), nunca no código.
"""

from __future__ import annotations

import hashlib
import os
from datetime import datetime, timedelta, timezone
from typing import Literal

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.db_models import Usuario

# Default só para dev/teste — em produção SOBRESCREVA por env. Diferenciar os dois segredos
# impede que um refresh seja aceito como access (e vice-versa).
JWT_SECRET = os.getenv("JWT_SECRET", "dev-inseguro-troque-em-producao")
JWT_REFRESH_SECRET = os.getenv("JWT_REFRESH_SECRET", "dev-inseguro-refresh-troque")
JWT_ALG = "HS256"
ACCESS_TTL_MIN = int(os.getenv("JWT_ACCESS_TTL_MIN", "30"))
REFRESH_TTL_DIAS = int(os.getenv("JWT_REFRESH_TTL_DIAS", "7"))


# bcrypt opera sobre no máx. 72 bytes; truncamos o excedente (limite do algoritmo).
def _bytes(senha: str) -> bytes:
    return senha.encode("utf-8")[:72]


def hash_senha(senha: str) -> str:
    return bcrypt.hashpw(_bytes(senha), bcrypt.gensalt()).decode("utf-8")


def verifica_senha(senha: str, senha_hash: str) -> bool:
    try:
        return bcrypt.checkpw(_bytes(senha), senha_hash.encode("utf-8"))
    except ValueError:
        return False


def hash_sessao(senha_hash: str) -> str:
    """Impressão digital da senha atual, embutida no refresh token (claim ``sh``).

    Trocar a senha muda a impressão → TODO refresh emitido antes deixa de valer no
    próximo uso (quem roubou a sessão é derrubado), sem precisar de estado no banco.
    O access token curto (30 min) expira sozinho.
    """
    return hashlib.sha256(senha_hash.encode("utf-8")).hexdigest()[:16]


def _emitir(sub: str, papel: str, tipo: Literal["access", "refresh"], extras: dict | None = None) -> str:
    agora = datetime.now(timezone.utc)
    ttl = timedelta(minutes=ACCESS_TTL_MIN) if tipo == "access" else timedelta(days=REFRESH_TTL_DIAS)
    segredo = JWT_SECRET if tipo == "access" else JWT_REFRESH_SECRET
    payload = {"sub": sub, "papel": papel, "tipo": tipo, "iat": agora, "exp": agora + ttl}
    if extras:
        payload.update(extras)
    return jwt.encode(payload, segredo, algorithm=JWT_ALG)


def token_acesso(usuario: Usuario) -> str:
    return _emitir(usuario.id, usuario.papel, "access")


def token_refresh(usuario: Usuario) -> str:
    return _emitir(usuario.id, usuario.papel, "refresh", {"sh": hash_sessao(usuario.senha_hash)})


def _decodificar(token: str, tipo: Literal["access", "refresh"]) -> dict:
    segredo = JWT_SECRET if tipo == "access" else JWT_REFRESH_SECRET
    try:
        payload = jwt.decode(token, segredo, algorithms=[JWT_ALG])
    except jwt.ExpiredSignatureError:
        # Mensagem CLARA e acionável p/ o usuário (não o jargão "token expirado").
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Sua sessão expirou por inatividade. Faça login novamente para continuar.",
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Sessão inválida. Faça login novamente.",
        )
    if payload.get("tipo") != tipo:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Tipo de token inválido.")
    return payload


def payload_do_refresh(token: str) -> dict:
    """Valida um refresh token (cookie) e devolve o payload (``sub`` + ``sh``)."""
    return _decodificar(token, "refresh")


_bearer = HTTPBearer(auto_error=False)


def usuario_atual(
    cred: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> Usuario:
    """Guarda: exige um access token válido e devolve o usuário ativo."""
    if cred is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Autenticação necessária.")
    payload = _decodificar(cred.credentials, "access")
    usuario = db.get(Usuario, payload["sub"])
    if usuario is None or not usuario.ativo:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuário inexistente ou inativo.")
    return usuario


def requer_admin(usuario: Usuario = Depends(usuario_atual)) -> Usuario:
    """Guarda: além de logado, exige papel admin."""
    if usuario.papel != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Acesso restrito ao administrador.")
    return usuario
