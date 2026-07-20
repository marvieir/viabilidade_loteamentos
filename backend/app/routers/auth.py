"""Fase 12 — router de autenticação (``/api/auth``).

Fluxo: ``registrar``/``login`` devolvem o access token no corpo e setam o refresh em
cookie httpOnly; ``refresh`` troca o cookie por um novo access token; ``logout`` limpa o
cookie; ``me`` devolve o usuário logado. Cadastro é ABERTO (qualquer um vira ``cliente``);
o papel ``admin`` só nasce por seed (scripts/criar_admin.py), nunca pela UI.

Recuperação de senha (auto-serviço): ``esqueci`` manda por e-mail um link com token de uso
único (só o SHA-256 fica no banco, expira em 1 h) e responde 200 SEMPRE — existir ou não a
conta (anti-enumeração de e-mails); ``redefinir`` troca a senha e derruba as sessões
refresh antigas (claim ``sh``). ``trocar-senha`` é a variante logada. ``google`` fecha o
ciclo: login/cadastro com o ID token do botão do Google (conta nasce sem senha).
"""

import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Cookie,
    Depends,
    HTTPException,
    Request,
    Response,
    status,
)
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.ratelimit import LIMITE_AUTH, limiter

from app.core.auth import (
    hash_senha,
    hash_sessao,
    payload_do_refresh,
    token_acesso,
    token_refresh,
    usuario_atual,
    verifica_senha,
    REFRESH_TTL_DIAS,
)
from app.core.db import get_db
from app.core.email_saida import enviar_email
from app.core.google_login import ErroGoogleLogin, VerificadorGoogle, get_verificador_google
from app.models.db_models import ResetSenhaToken, Usuario
from app.models.schemas import (
    EsqueciSenhaIn,
    GoogleLoginIn,
    LoginIn,
    MensagemOut,
    RedefinirSenhaIn,
    RegistrarIn,
    TokenOut,
    TrocarSenhaIn,
    UsuarioOut,
)

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
@limiter.limit(LIMITE_AUTH)
def registrar(request: Request, resp: Response, body: RegistrarIn, db: Session = Depends(get_db)) -> TokenOut:
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
@limiter.limit(LIMITE_AUTH)
def login(request: Request, resp: Response, body: LoginIn, db: Session = Depends(get_db)) -> TokenOut:
    email = body.email.strip().lower()
    usuario = db.query(Usuario).filter(func.lower(Usuario.email) == email).first()
    if usuario is not None and usuario.senha_hash == "":
        # Conta nascida pelo Google — não tem senha para conferir. Mensagem acionável.
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Esta conta entra com o Google. Use o botão 'Entrar com o Google' ou crie uma "
            "senha em 'Esqueci minha senha'.",
        )
    if usuario is None or not verifica_senha(body.senha, usuario.senha_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "E-mail ou senha incorretos.")
    if not usuario.ativo:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Conta desativada.")
    _set_refresh(resp, usuario)
    return TokenOut(access_token=token_acesso(usuario))


@router.post("/refresh", response_model=TokenOut)
@limiter.limit(LIMITE_AUTH)
def refresh(
    request: Request,
    resp: Response,
    refresh_token: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> TokenOut:
    if not refresh_token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sem refresh token.")
    payload = payload_do_refresh(refresh_token)
    usuario = db.get(Usuario, payload["sub"])
    if usuario is None or not usuario.ativo:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sessão inválida.")
    # Claim ``sh`` = impressão da senha na emissão. Divergiu → a senha foi trocada depois
    # que este refresh nasceu (reset/troca) → sessão antiga morre. Tokens pré-upgrade (sem
    # o claim) também caem: um re-login único após o deploy.
    if payload.get("sh") != hash_sessao(usuario.senha_hash):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Sua senha foi alterada. Faça login novamente com a senha nova.",
        )
    _set_refresh(resp, usuario)  # rotação do refresh no uso
    return TokenOut(access_token=token_acesso(usuario))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(resp: Response) -> Response:
    resp.delete_cookie(_COOKIE, path="/api/auth")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UsuarioOut)
def me(usuario: Usuario = Depends(usuario_atual)) -> UsuarioOut:
    return _usuario_out(usuario)


# ----- Recuperação de senha (esqueci/redefinir) + troca logada -----

# Validade do link de redefinição (minutos) e base do LINK que vai no e-mail (o frontend).
_RESET_TTL_MIN = int(os.getenv("RESET_SENHA_TTL_MIN", "60"))
_APP_URL_BASE = os.getenv("APP_URL_BASE", "http://localhost:3700").rstrip("/")

_MSG_ESQUECI = (
    "Se existir uma conta com este e-mail, enviamos um link para redefinir a senha. "
    "Confira a caixa de entrada e o spam."
)


def _sha256(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def _aware(dt: datetime) -> datetime:
    """SQLite devolve datetime NAIVE mesmo em coluna timezone=True; normaliza para UTC."""
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def _enviar_email_reset(destino: str, link: str) -> None:
    texto = (
        "Você pediu para redefinir a senha da sua conta na Viabilidade homeeye.\n\n"
        f"Abra este link para criar a senha nova (vale por {_RESET_TTL_MIN} minutos e "
        "só funciona uma vez):\n\n"
        f"{link}\n\n"
        "Se não foi você, ignore este e-mail — sua senha continua a mesma."
    )
    html = (
        "<p>Você pediu para redefinir a senha da sua conta na "
        "<strong>Viabilidade homeeye</strong>.</p>"
        f'<p><a href="{link}">Clique aqui para criar a senha nova</a> '
        f"(vale por {_RESET_TTL_MIN} minutos e só funciona uma vez).</p>"
        f'<p>Se o botão não abrir, copie e cole este endereço no navegador:<br>{link}</p>'
        "<p>Se não foi você, ignore este e-mail — sua senha continua a mesma.</p>"
    )
    enviar_email(destino, "Redefinir sua senha — Viabilidade homeeye", texto, html)


@router.post("/esqueci", response_model=MensagemOut)
@limiter.limit(LIMITE_AUTH)
def esqueci_senha(
    request: Request,
    body: EsqueciSenhaIn,
    tarefas: BackgroundTasks,
    db: Session = Depends(get_db),
) -> MensagemOut:
    """Responde 200 com a MESMA mensagem exista ou não a conta (anti-enumeração). O envio
    do e-mail vai para background — o tempo de resposta também não denuncia a existência."""
    email = body.email.strip().lower()
    usuario = db.query(Usuario).filter(func.lower(Usuario.email) == email).first()
    if usuario is not None and usuario.ativo:
        # Um pedido novo invalida os links pendentes (só o link mais recente vale).
        agora = datetime.now(timezone.utc)
        db.query(ResetSenhaToken).filter(
            ResetSenhaToken.usuario_id == usuario.id,
            ResetSenhaToken.usado_em.is_(None),
        ).update({ResetSenhaToken.usado_em: agora})
        token = secrets.token_urlsafe(32)  # em claro SÓ no link; no banco fica o SHA-256
        db.add(
            ResetSenhaToken(
                usuario_id=usuario.id,
                token_sha256=_sha256(token),
                expira_em=agora + timedelta(minutes=_RESET_TTL_MIN),
            )
        )
        db.commit()
        link = f"{_APP_URL_BASE}/redefinir?token={token}"
        tarefas.add_task(_enviar_email_reset, usuario.email, link)
    return MensagemOut(mensagem=_MSG_ESQUECI)


@router.post("/redefinir", response_model=MensagemOut)
@limiter.limit(LIMITE_AUTH)
def redefinir_senha(
    request: Request, body: RedefinirSenhaIn, db: Session = Depends(get_db)
) -> MensagemOut:
    registro = (
        db.query(ResetSenhaToken)
        .filter(ResetSenhaToken.token_sha256 == _sha256(body.token))
        .first()
    )
    valido = (
        registro is not None
        and registro.usado_em is None
        and _aware(registro.expira_em) > datetime.now(timezone.utc)
    )
    if not valido:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Este link de redefinição é inválido, já foi usado ou expirou. "
            "Peça um link novo em 'Esqueci minha senha'.",
        )
    usuario = db.get(Usuario, registro.usuario_id)
    if usuario is None or not usuario.ativo:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Conta indisponível.")
    usuario.senha_hash = hash_senha(body.senha)  # muda o ``sh`` → derruba refreshs antigos
    registro.usado_em = datetime.now(timezone.utc)
    db.commit()
    return MensagemOut(mensagem="Senha redefinida. Entre com a senha nova.")


@router.post("/trocar-senha", response_model=MensagemOut)
@limiter.limit(LIMITE_AUTH)
def trocar_senha(
    request: Request,
    resp: Response,
    body: TrocarSenhaIn,
    usuario: Usuario = Depends(usuario_atual),
    db: Session = Depends(get_db),
) -> MensagemOut:
    if usuario.senha_hash:  # conta com senha exige a atual; conta Google define a primeira
        if not body.senha_atual or not verifica_senha(body.senha_atual, usuario.senha_hash):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Senha atual incorreta.")
    usuario.senha_hash = hash_senha(body.senha_nova)
    db.commit()
    # As OUTRAS sessões refresh morrem (claim ``sh``); esta ganha um cookie novo e segue.
    _set_refresh(resp, usuario)
    return MensagemOut(mensagem="Senha alterada.")


# ----- Login com Google (Google Identity Services) -----

@router.post("/google", response_model=TokenOut)
@limiter.limit(LIMITE_AUTH)
def login_google(
    request: Request,
    resp: Response,
    body: GoogleLoginIn,
    db: Session = Depends(get_db),
    verificador: VerificadorGoogle | None = Depends(get_verificador_google),
) -> TokenOut:
    if verificador is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Login com Google não está habilitado neste servidor "
            "(defina GOOGLE_CLIENT_ID no backend).",
        )
    try:
        dados = verificador.verificar(body.credential)
    except ErroGoogleLogin as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc))
    usuario = (
        db.query(Usuario).filter(func.lower(Usuario.email) == dados["email"]).first()
    )
    if usuario is None:
        # Conta nasce SEM senha (senha_hash vazio) — o login por senha orienta usar o
        # Google ou criar senha via 'Esqueci minha senha'.
        usuario = Usuario(
            email=dados["email"], senha_hash="", nome=dados["nome"], papel="cliente"
        )
        db.add(usuario)
        db.commit()
        db.refresh(usuario)
    elif not usuario.ativo:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Conta desativada.")
    _set_refresh(resp, usuario)
    return TokenOut(access_token=token_acesso(usuario))
