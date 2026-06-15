"""Persistência das propostas urbanísticas (Fase 9) — snapshots VERSIONADOS por análise.

A proposta do LLM é não-determinística → guarda-se o snapshot (programa + geometria +
medição) imutável e versionado: "mesmo snapshot → mesma medição" (determinismo, §7).
Regenerar cria nova versão, nunca sobrescreve. Mesmo padrão injetável da 4/5: produção
grava JSON em volume; testes em memória.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional, Protocol, runtime_checkable

_DIR_DEFAULT = Path(__file__).resolve().parent.parent / "perfis" / "urbanismo"


@runtime_checkable
class FonteUrbanismo(Protocol):
    def listar(self, analise_id: str) -> list[dict]: ...
    def carregar(self, analise_id: str, proposta_id: str) -> Optional[dict]: ...
    def salvar(self, analise_id: str, proposta: dict) -> None: ...
    def proxima_versao(self, analise_id: str) -> int: ...


class FonteUrbanismoArquivo:
    """``{diretorio}/{analise_id}.json`` = lista de snapshots. Degrada honesto se ausente."""

    def __init__(self, diretorio: str | os.PathLike):
        self.diretorio = Path(diretorio)

    def _caminho(self, analise_id: str) -> Path:
        return self.diretorio / f"{analise_id}.json"

    def listar(self, analise_id: str) -> list[dict]:
        caminho = self._caminho(analise_id)
        if not caminho.exists():
            return []
        try:
            return json.loads(caminho.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []

    def carregar(self, analise_id: str, proposta_id: str) -> Optional[dict]:
        for p in self.listar(analise_id):
            if p.get("proposta_id") == proposta_id:
                return p
        return None

    def salvar(self, analise_id: str, proposta: dict) -> None:
        self.diretorio.mkdir(parents=True, exist_ok=True)
        atuais = self.listar(analise_id)
        atuais.append(proposta)
        self._caminho(analise_id).write_text(
            json.dumps(atuais, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def proxima_versao(self, analise_id: str) -> int:
        return len(self.listar(analise_id)) + 1


def get_fonte_urbanismo() -> FonteUrbanismo:
    diretorio = os.getenv("URBANISMO_DIR", str(_DIR_DEFAULT))
    return FonteUrbanismoArquivo(diretorio)
