"""Aplicação FastAPI — Pré-Viabilidade de Loteamento.

Cada dimensão de viabilidade é um router isolado (CLAUDE.md). Na Fase 1, só a
dimensão Casca + Aproveitamento (routers/analises.py).
"""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import ambiental, analises, perfil, vegetacao

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
app.include_router(perfil.router, prefix="/api")


@app.get("/health")
def health():
    return {"status": "ok"}
