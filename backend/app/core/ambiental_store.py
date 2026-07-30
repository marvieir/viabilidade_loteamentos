"""Marcador de EXECUÇÃO da pré-análise ambiental por análise (30/07).

Motivo: o ambiental era a ÚNICA dimensão sem rastro no servidor — vivia só no snapshot da
salva. A trilha (servidor) então mostrava "Disponível" com os alertas na frente do operador,
até ele salvar E reabrir. Aqui gravamos um marcador leve (não o resultado inteiro — os
overlays têm MBs e o snapshot da salva continua sendo a fonte de reidratação): executada em
tal data, com N alertas. A trilha passa a reconhecer a execução na hora.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

_DIR_DEFAULT = Path(__file__).resolve().parent.parent / "perfis" / "_dados" / "ambiental"


def _dir() -> Path:
    d = os.getenv("AMBIENTAL_DIR", "").strip()
    if d:
        return Path(d)
    return Path("/data/perfis/ambiental") if Path("/data/perfis").is_dir() else _DIR_DEFAULT


def marcar(analise_id: str, n_alertas: int) -> None:
    """Best-effort: falha de disco nunca derruba a análise."""
    try:
        d = _dir(); d.mkdir(parents=True, exist_ok=True)
        (d / f"{analise_id}.json").write_text(json.dumps({
            "executada_em": datetime.now(timezone.utc).isoformat(),
            "n_alertas": int(n_alertas),
        }), encoding="utf-8")
    except OSError:
        pass


def consta(analise_id: str) -> Optional[dict]:
    try:
        arq = _dir() / f"{analise_id}.json"
        return json.loads(arq.read_text(encoding="utf-8")) if arq.exists() else None
    except (OSError, ValueError):
        return None
