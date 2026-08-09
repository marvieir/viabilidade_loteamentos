"""AMB-EXC — persistência da reconciliação (padrão da casa: JSON por análise, versionado).

Cada aplicação de laudo APPENDA um snapshot em ``{AMBEXC_DIR}/{analise_id}.json`` — a leitura
de satélite original nunca é sobrescrita (histórico auditável; o vigente é o último).
Degrada honesto em erro de disco (lista vazia / ``None``), como urbanismo_store.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional, Protocol, runtime_checkable

_DIR_DEFAULT = "/data/perfis/ambexc"


@runtime_checkable
class FonteReconciliacao(Protocol):
    def carregar(self, analise_id: str) -> list[dict]: ...
    def salvar(self, analise_id: str, snapshot: dict) -> int: ...


class FonteReconciliacaoArquivo:
    def __init__(self, diretorio: str):
        self.dir = Path(diretorio)

    def _caminho(self, analise_id: str) -> Path:
        seguro = "".join(c for c in analise_id if c.isalnum() or c in "-_")[:64]
        return self.dir / f"{seguro}.json"

    def carregar(self, analise_id: str) -> list[dict]:
        try:
            bruto = self._caminho(analise_id).read_text()
            dados = json.loads(bruto)
            return dados if isinstance(dados, list) else []
        except (OSError, ValueError):
            return []

    def salvar(self, analise_id: str, snapshot: dict) -> int:
        """Appenda e devolve o nº da versão (1-based)."""
        versoes = self.carregar(analise_id)
        versoes.append(snapshot)
        try:
            self.dir.mkdir(parents=True, exist_ok=True)
            self._caminho(analise_id).write_text(json.dumps(versoes, ensure_ascii=False))
        except OSError:
            pass  # degrada honesto — o chamador reporta pelo retorno da leitura seguinte
        return len(versoes)


def vigente(fonte: Optional[FonteReconciliacao], analise_id: str) -> Optional[dict]:
    """Último snapshot aplicado (o vigente) ou ``None``."""
    if fonte is None:
        return None
    versoes = fonte.carregar(analise_id)
    return versoes[-1] if versoes else None


def get_fonte_reconciliacao() -> FonteReconciliacao:
    return FonteReconciliacaoArquivo(os.getenv("AMBEXC_DIR", _DIR_DEFAULT))
