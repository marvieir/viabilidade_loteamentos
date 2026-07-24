"""Aplicação FastAPI — Pré-Viabilidade de Loteamento.

Cada dimensão de viabilidade é um router isolado (CLAUDE.md). Na Fase 1, só a
dimensão Casca + Aproveitamento (routers/analises.py).
"""

import os
from pathlib import Path

from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

# Carrega backend/.env (ANTHROPIC_API_KEY etc.) já na importação — robusto mesmo se o
# uvicorn for iniciado sem `--env-file`. Não sobrescreve vars já presentes no ambiente
# (ex.: as do docker-compose), então container e dev convivem.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.core.config import EH_PRODUCAO, validar_seguranca_producao
from app.core.db import criar_tabelas
from app.core.ratelimit import limiter
from app.routers import (
    admin,
    ambiental,
    analises,
    areas_umidas,
    auth,
    conformidade,
    custo_infra,
    declividade,
    economica,
    financeira,
    juridico,
    laudo,
    localizacao,
    perfil,
    salvas,
    trilha,
    urbanismo,
    vegetacao,
)

@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Fase 13 — em produção, ABORTA o boot se a config de segurança estiver insegura (segredos
    # default, CORS '*', cookie sem Secure). Em dev/teste é no-op.
    validar_seguranca_producao()
    # Fase 12 — garante o schema (usuarios/analises) no boot. Idempotente; Alembic entra
    # quando o schema estabilizar. Em produção com Postgres, roda no start do container.
    criar_tabelas()
    yield


app = FastAPI(
    title="Pré-Viabilidade de Loteamento — API",
    version="0.1.0",
    lifespan=lifespan,
)

# Fase 13 — rate limiting (anti brute-force) nos endpoints de auth (decorados em routers/auth).
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# NUNCA 500 mudo: exceção não tratada → traceback completo no LOG e mensagem AMIGÁVEL na
# tela (achado do operador, 24/07: o texto técnico não diz nada ao usuário final). O código
# curto entre colchetes liga a tela ao log sem expor stack. IMPORTANTE: o catch mora no
# middleware INTERNO (dentro do CORS) — o handler global do Starlette responde por FORA do
# CORS, o navegador bloqueia a resposta e o front só vê "falha de rede".
import logging as _logging

_log_app = _logging.getLogger("app.erros")

MSG_ERRO_INTERNO = (
    "Algo deu errado do nosso lado ao processar este pedido — sua análise não foi "
    "perdida. Tente de novo em alguns instantes; se continuar, fale com o suporte "
    "citando o código entre colchetes."
)


def _resposta_erro_interno(request, exc):
    from fastapi.responses import JSONResponse

    _log_app.exception("Erro não tratado em %s", request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "detail": f"{MSG_ERRO_INTERNO} [{type(exc).__name__} · {request.url.path}]"
        },
    )


@app.exception_handler(Exception)
async def _erro_nao_tratado(request, exc):
    # Backstop (erros fora do middleware, ex.: no próprio CORS) — mesma mensagem amigável.
    return _resposta_erro_interno(request, exc)


# Fase 13 — security headers (defesa contra clickjacking / MIME sniffing; HSTS só em HTTPS/prod).
class _SecurityHeaders(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        try:
            resp = await call_next(request)
        except Exception as exc:  # noqa: BLE001 — vira 500 amigável DENTRO do CORS
            resp = _resposta_erro_interno(request, exc)
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "no-referrer")
        if EH_PRODUCAO:
            resp.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
        return resp


app.add_middleware(_SecurityHeaders)

# Fase 13 — TrustedHost: em produção, aceita só os hosts esperados (Host header spoofing). Em dev
# aceita tudo. Configurável por ALLOWED_HOSTS (vírgula). Combina com o reverse proxy do Lightsail.
_hosts = [h.strip() for h in os.getenv("ALLOWED_HOSTS", "*").split(",") if h.strip()]
if _hosts and _hosts != ["*"]:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=_hosts)

# Frontend roda em porta > 3700 (convenção do projeto). Em produção o boot exige CORS_ORIGINS
# explícito (ver config); em dev cai em '*' p/ facilitar o desenvolvimento local.
_origens = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origens,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(salvas.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(analises.router, prefix="/api")
app.include_router(ambiental.router, prefix="/api")
app.include_router(vegetacao.router, prefix="/api")
app.include_router(areas_umidas.router, prefix="/api")
app.include_router(declividade.router, prefix="/api")
app.include_router(perfil.router, prefix="/api")
app.include_router(juridico.router, prefix="/api")
app.include_router(conformidade.router, prefix="/api")
app.include_router(financeira.router, prefix="/api")
app.include_router(economica.router, prefix="/api")
app.include_router(localizacao.router, prefix="/api")
app.include_router(laudo.router, prefix="/api")
app.include_router(urbanismo.router, prefix="/api")
app.include_router(custo_infra.router, prefix="/api")
app.include_router(trilha.router, prefix="/api")  # Fase UX-1 — Trilha da Análise


@app.get("/health")
def health():
    return {"status": "ok"}
