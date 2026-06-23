"""Fase 12 — camada de banco (multi-tenant). SQLAlchemy 2.x.

``DATABASE_URL`` (env) escolhe o banco: Postgres em produção
(``postgresql+psycopg://user:senha@db:5432/viabilidade``), SQLite no dev/teste
(``sqlite:///./dev.db`` — default). O código é agnóstico ao banco; só a URL muda.
"""

from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./dev.db")

# SQLite precisa de check_same_thread=False sob o servidor; Postgres usa pool com pre-ping.
_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=_connect_args, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


def get_db():
    """Dependência FastAPI: uma sessão por request, sempre fechada."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def criar_tabelas() -> None:
    """Cria as tabelas se não existem (Fase 12 — MVP). Migração versionada (Alembic) entra
    quando o schema estabilizar; por ora ``create_all`` é idempotente e suficiente."""
    from app.models import db_models  # noqa: F401 — registra os modelos no metadata

    Base.metadata.create_all(bind=engine)
