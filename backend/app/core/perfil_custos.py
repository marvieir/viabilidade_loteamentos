"""Persistência do perfil de custos do operador (Tier 3) — fonte injetável.

A tabela de custos unitários é GLOBAL por operador (preenche uma vez; vale para todas as
análises) — diferente da Financeira, que é por análise. Persistida por ``usuario_id`` para
não vazar entre contas. Mesmo padrão das demais fontes: interface injetável; produção grava
JSON num volume; testes injetam em memória via ``dependency_overrides``.

Degrada honesto: arquivo ausente/corrompido → ``None`` (o motor trata como "sem perfil" e
rotula cobertura INDISPONIVEL — não inventa custo).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional, Protocol, runtime_checkable

_DIR_DEFAULT = Path(__file__).resolve().parent.parent / "perfis" / "custos"


@runtime_checkable
class FontePerfilCustos(Protocol):
    def carregar(self, usuario_id: str) -> Optional[dict]: ...
    def salvar(self, usuario_id: str, perfil: dict) -> None: ...


class FontePerfilCustosArquivo:
    """``{diretorio}/{usuario_id}.json`` = perfil de custos do operador."""

    def __init__(self, diretorio: str | os.PathLike):
        self.diretorio = Path(diretorio)

    def _caminho(self, usuario_id: str) -> Path:
        return self.diretorio / f"{usuario_id}.json"

    def carregar(self, usuario_id: str) -> Optional[dict]:
        caminho = self._caminho(usuario_id)
        if not caminho.exists():
            return None
        try:
            return json.loads(caminho.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def salvar(self, usuario_id: str, perfil: dict) -> None:
        self.diretorio.mkdir(parents=True, exist_ok=True)
        self._caminho(usuario_id).write_text(
            json.dumps(perfil, ensure_ascii=False, indent=2), encoding="utf-8"
        )


def get_fonte_perfil_custos() -> FontePerfilCustos:
    diretorio = os.getenv("PERFIL_CUSTOS_DIR", str(_DIR_DEFAULT))
    return FontePerfilCustosArquivo(diretorio)
