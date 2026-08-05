"""Gate do AI Portfolio Insights — estado por USUÁRIO (prévia de 30 dias / liberação).

Mesmo padrão injetável dos demais stores (perfil_custos): produção grava JSON por
usuário num volume (``PORTFOLIO_DIR``); testes injetam diretório temporário. Guarda
apenas o mínimo do gate: ``primeiro_acesso`` (ISO UTC — o prazo conta do primeiro
ACESSO ao painel, decisão do operador 05/08) e ``liberado`` (destrava manual do admin
enquanto não existe billing).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional, Protocol, runtime_checkable

_DIR_DEFAULT = Path(__file__).resolve().parent.parent / "perfis" / "portfolio"


@runtime_checkable
class FontePortfolio(Protocol):
    def carregar(self, usuario_id: str) -> Optional[dict]: ...
    def salvar(self, usuario_id: str, dados: dict) -> None: ...


class FontePortfolioArquivo:
    """``{diretorio}/{usuario_id}.json``. Degrada honesto: ausente/corrompido → None."""

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

    def salvar(self, usuario_id: str, dados: dict) -> None:
        self.diretorio.mkdir(parents=True, exist_ok=True)
        self._caminho(usuario_id).write_text(
            json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8"
        )


def get_fonte_portfolio() -> FontePortfolio:
    return FontePortfolioArquivo(os.getenv("PORTFOLIO_DIR", str(_DIR_DEFAULT)))
