"""Aplicação FastAPI — Pré-Viabilidade de Loteamento.

Cada dimensão de viabilidade é um router isolado (CLAUDE.md). Na Fase 1, só a
dimensão Casca + Aproveitamento (routers/analises.py).
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Carrega backend/.env (ANTHROPIC_API_KEY etc.) já na importação — robusto mesmo se o
# uvicorn for iniciado sem `--env-file`. Não sobrescreve vars já presentes no ambiente
# (ex.: as do docker-compose), então container e dev convivem.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from app.routers import (
    ambiental,
    analises,
    conformidade,
    declividade,
    economica,
    financeira,
    juridico,
    perfil,
    vegetacao,
)

app = FastAPI(
    title="Pré-Viabilidade de Loteamento — API",
    version="0.1.0",
)

# Frontend roda em porta > 3700 (convenção do projeto). CORS liberado p/ dev;
# restringir via env em produção.
_origens = os.getenv("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origens,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analises.router, prefix="/api")
app.include_router(ambiental.router, prefix="/api")
app.include_router(vegetacao.router, prefix="/api")
app.include_router(declividade.router, prefix="/api")
app.include_router(perfil.router, prefix="/api")
app.include_router(juridico.router, prefix="/api")
app.include_router(conformidade.router, prefix="/api")
app.include_router(financeira.router, prefix="/api")
app.include_router(economica.router, prefix="/api")


@app.get("/health")
def health():
    return {"status": "ok"}
