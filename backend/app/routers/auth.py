"""Fase 12 — router de autenticação (``/api/auth``).

Fluxo: ``registrar``/``login`` devolvem o access token no corpo e setam o refresh em
cookie httpOnly; ``refresh`` troca o cookie por um novo access token; ``logout`` limpa o
cookie; ``me`` devolve o usuário logado. Cadastro é ABERTO (qualquer um vira ``cliente``);
o papel ``admin`` só nasce por seed (scripts/criar_admin.py), nunca pela UI.
"""

from __future__ import annotations

import os

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.auth import (
    hash_senha,
    sub_do_refresh,
    token_acesso,
    token_refresh,
    usuario_atual,
    verifica_senha,
    REFRESH_TTL_DIAS,
)
from app.core.db import get_db
from app.models.db_models import Usuario
from app.models.schemas import LoginIn, RegistrarIn, TokenOut, UsuarioOut

router = APIRouter(prefix="/auth", tags=["auth"])

_COOKIE = "refresh_token"
# Em produção (HTTPS) o cookie precisa de Secure; em dev/HTTP, não (senão o browser o
# descarta). Gate por env COOKIE_SECURE (Compose liga em produção).
_COOKIE_SECURE = os.getenv("COOKIE_SECURE", "0") == "1"


def _usuario_out(u: Usuario) -> UsuarioOut:
    return UsuarioOut(
        id=u.id, email=u.email, nome=u.nome, papel=u.papel, criado_em=u.criado_em.isoformat()
    )


def _set_refresh(resp: Response, usuario: Usuario) -> None:
    resp.set_cookie(
        _COOKIE,
        token_refresh(usuario),
        max_age=REFRESH_TTL_DIAS * 24 * 3600,
        httponly=True,
        secure=_COOKIE_SECURE,
        samesite="lax",
        path="/api/auth",
    )


@router.post("/registrar", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
def registrar(body: RegistrarIn, resp: Response, db: Session = Depends(get_db)) -> TokenOut:
    email = body.email.strip().lower()
    if not email or "@" not in email:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "E-mail inválido.")
    existe = db.query(Usuario).filter(func.lower(Usuario.email) == email).first()
    if existe is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Já existe uma conta com este e-mail.")
    usuario = Usuario(
        email=email, senha_hash=hash_senha(body.senha), nome=(body.nome or None), papel="cliente"
    )
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    _set_refresh(resp, usuario)
    return TokenOut(access_token=token_acesso(usuario))


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, resp: Response, db: Session = Depends(get_db)) -> TokenOut:
    email = body.email.strip().lower()
    usuario = db.query(Usuario).filter(func.lower(Usuario.email) == email).first()
    if usuario is None or not verifica_senha(body.senha, usuario.senha_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "E-mail ou senha incorretos.")
    if not usuario.ativo:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Conta desativada.")
    _set_refresh(resp, usuario)
    return TokenOut(access_token=token_acesso(usuario))


@router.post("/refresh", response_model=TokenOut)
def refresh(
    resp: Response,
    refresh_token: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> TokenOut:
    if not refresh_token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sem refresh token.")
    uid = sub_do_refresh(refresh_token)
    usuario = db.get(Usuario, uid)
    if usuario is None or not usuario.ativo:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sessão inválida.")
    _set_refresh(resp, usuario)  # rotação do refresh no uso
    return TokenOut(access_token=token_acesso(usuario))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(resp: Response) -> Response:
    resp.delete_cookie(_COOKIE, path="/api/auth")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UsuarioOut)
def me(usuario: Usuario = Depends(usuario_atual)) -> UsuarioOut:
    return _usuario_out(usuario)
