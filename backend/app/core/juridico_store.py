"""Persistência das fichas jurídicas CONFIRMADAS por análise (Fase 3) — fonte injetável.

Cada análise pode ter várias fichas (1 matrícula + N certidões). Só ficha ``confirmado``
(gate humano) é gravada e alimenta a síntese. Mesmo padrão da 1.8 (perfil municipal):
interface injetável; produção lê/grava JSON num volume; testes injetam memória.

Nada aqui calcula — só carrega/grava o contrato Pydantic ``FichaJuridica``.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional, Protocol, runtime_checkable

from app.models.schemas import FichaJuridica

_DIR_DEFAULT = Path(__file__).resolve().parent.parent / "perfis" / "juridico"


@runtime_checkable
class FonteJuridica(Protocol):
    """Carrega/grava as fichas jurídicas confirmadas por ``analise_id``."""

    def carregar(self, analise_id: str) -> list[FichaJuridica]:
        """Lista de fichas confirmadas da análise (vazia se não houver)."""

    def salvar(self, analise_id: str, ficha: FichaJuridica) -> None:
        """Acrescenta/substitui a ficha (por tipo+fonte). Router só chama com confirmado."""


def _mesclar(fichas: list[FichaJuridica], nova: FichaJuridica) -> list[FichaJuridica]:
    """Substitui a ficha de mesmo (tipo, fonte_documento); senão acrescenta. Determinístico."""
    chave = (nova.tipo, nova.fonte_documento)
    out = [f for f in fichas if (f.tipo, f.fonte_documento) != chave]
    out.append(nova)
    return out


class FonteJuridicaArquivo:
    """Fichas em ``{diretorio}/{analise_id}.json`` (lista). Degrada honesto: arquivo
    ausente/corrompido → lista vazia (não inventa ficha)."""

    def __init__(self, diretorio: str | os.PathLike):
        self.diretorio = Path(diretorio)

    def carregar(self, analise_id: str) -> list[FichaJuridica]:
        caminho = self.diretorio / f"{analise_id}.json"
        if not caminho.exists():
            return []
        try:
            dados = json.loads(caminho.read_text(encoding="utf-8"))
            return [FichaJuridica.model_validate(d) for d in dados]
        except (OSError, ValueError):
            return []

    def salvar(self, analise_id: str, ficha: FichaJuridica) -> None:
        self.diretorio.mkdir(parents=True, exist_ok=True)
        atuais = self.carregar(analise_id)
        novas = _mesclar(atuais, ficha)
        caminho = self.diretorio / f"{analise_id}.json"
        caminho.write_text(
            json.dumps(
                [f.model_dump(exclude_none=False) for f in novas],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )


def get_fonte_juridica() -> FonteJuridica:
    """Dependência FastAPI. PRODUÇÃO: ``JURIDICO_DIR`` (ou ``perfis/juridico``).
    TESTES: sobrescrito por uma fonte em memória."""
    diretorio = os.getenv("JURIDICO_DIR", str(_DIR_DEFAULT))
    return FonteJuridicaArquivo(diretorio)
