"""Persistência da última avaliação econômica por análise (Fase 5) — fonte injetável.

Guarda ``{premissas, resultado}`` por ``analise_id`` (TMA declarada + avaliação). Mesmo
padrão da financeira_store: produção grava JSON em volume; testes em memória.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional, Protocol, runtime_checkable

_DIR_DEFAULT = Path(__file__).resolve().parent.parent / "perfis" / "economica"


@runtime_checkable
class FonteEconomica(Protocol):
    def carregar(self, analise_id: str) -> Optional[dict]: ...
    def salvar(self, analise_id: str, dados: dict) -> None: ...


class FonteEconomicaArquivo:
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


def get_fonte_economica() -> FonteEconomica:
    diretorio = os.getenv("ECONOMICA_DIR", str(_DIR_DEFAULT))
    return FonteEconomicaArquivo(diretorio)
