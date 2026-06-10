"""Persistência da última execução financeira por análise (Fase 4) — fonte injetável.

Guarda ``{premissas, resultado}`` por ``analise_id`` (o operador não redigita as premissas).
Mesmo padrão da 1.8/3: interface injetável; produção grava JSON em volume; testes em memória.
Sem gate proposto→confirmado — a origem das premissas já é o humano (proveniência basta).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional, Protocol, runtime_checkable

_DIR_DEFAULT = Path(__file__).resolve().parent.parent / "perfis" / "financeira"


@runtime_checkable
class FonteFinanceira(Protocol):
    def carregar(self, analise_id: str) -> Optional[dict]: ...
    def salvar(self, analise_id: str, dados: dict) -> None: ...


class FonteFinanceiraArquivo:
    """``{diretorio}/{analise_id}.json``. Degrada honesto: ausente/corrompido → None."""

    def __init__(self, diretorio: str | os.PathLike):
        self.diretorio = Path(diretorio)

    def carregar(self, analise_id: str) -> Optional[dict]:
        caminho = self.diretorio / f"{analise_id}.json"
        if not caminho.exists():
            return None
        try:
            return json.loads(caminho.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def salvar(self, analise_id: str, dados: dict) -> None:
        self.diretorio.mkdir(parents=True, exist_ok=True)
        (self.diretorio / f"{analise_id}.json").write_text(
            json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8"
        )


def get_fonte_financeira() -> FonteFinanceira:
    diretorio = os.getenv("FINANCEIRA_DIR", str(_DIR_DEFAULT))
    return FonteFinanceiraArquivo(diretorio)
