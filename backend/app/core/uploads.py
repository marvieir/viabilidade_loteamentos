"""Leitura de upload com TETO de tamanho (Fase 13 — anti-DoS de memória).

Os endpoints liam o upload inteiro em memória (``await up.read()``), sem limite — um arquivo
gigante derruba o worker. Aqui lemos em blocos e abortamos com 413 ao passar do teto.
"""

from __future__ import annotations

import os

from fastapi import HTTPException, UploadFile

MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "25"))
_MAX = MAX_UPLOAD_MB * 1024 * 1024


async def ler_upload_limitado(up: UploadFile, max_bytes: int = _MAX) -> bytes:
    """Lê o upload em blocos de 1 MB, abortando com 413 se ultrapassar ``max_bytes``."""
    pedacos: list[bytes] = []
    total = 0
    while True:
        chunk = await up.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(
                413, f"Arquivo grande demais (limite {max_bytes // (1024 * 1024)} MB)."
            )
        pedacos.append(chunk)
    return b"".join(pedacos)
