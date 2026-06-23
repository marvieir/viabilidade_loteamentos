"""Fase 12 — modelos ORM (SQLAlchemy 2.x). Multi-tenant: cada análise tem dono.

UUID como PK (string em SQLite, nativo em Postgres via tipo agnóstico). JSON guarda
a geometria da gleba e o snapshot dos resultados — o suficiente para recarregar a tela
sem reupload nem re-rodar o motor.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.core.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _agora() -> datetime:
    return datetime.now(timezone.utc)


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    senha_hash: Mapped[str] = mapped_column(Text, nullable=False)
    nome: Mapped[str | None] = mapped_column(String(200), nullable=True)
    papel: Mapped[str] = mapped_column(String(20), default="cliente", nullable=False)  # cliente|admin
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_agora, nullable=False)

    analises: Mapped[list["Analise"]] = relationship(
        back_populates="usuario", cascade="all, delete-orphan"
    )


class Analise(Base):
    __tablename__ = "analises"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    usuario_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("usuarios.id", ondelete="CASCADE"), index=True, nullable=False
    )
    titulo: Mapped[str] = mapped_column(String(300), nullable=False)
    kmz_nome: Mapped[str | None] = mapped_column(String(300), nullable=True)
    gleba_geojson: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    cidade: Mapped[str | None] = mapped_column(String(200), nullable=True)
    uf: Mapped[str | None] = mapped_column(String(2), nullable=True)
    area_ha: Mapped[float | None] = mapped_column(Float, nullable=True)
    resultados: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    criada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_agora, nullable=False)
    atualizada_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_agora, onupdate=_agora, nullable=False
    )

    usuario: Mapped["Usuario"] = relationship(back_populates="analises")
