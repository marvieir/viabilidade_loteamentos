"""Persistência do perfil municipal da LUOS (Fase 1.8) — fonte injetável.

O perfil CONFIRMADO (extração da LUOS validada por humano) é persistido por ``cod_ibge``
e recarregado em análises futuras **sem re-extrair** (critério 9). Mesmo padrão das demais
fontes (jurisdição/FMP/camadas): interface injetável; produção lê/grava JSON num volume;
testes injetam uma fonte em memória via ``dependency_overrides``.

Nada aqui calcula número — só carrega/grava o contrato Pydantic ``PerfilMunicipal``
(``models/schemas.py``). O gate humano (proposto → confirmado) e o cálculo determinístico
ficam no router/``core.aproveitamento`` (ARCHITECTURE §2).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Protocol, runtime_checkable

from app.models.schemas import PerfilMunicipal

# Volume padrão (não vai no git; igual ao raster da 2.2 / malha da 1.7).
_DIR_DEFAULT = Path(__file__).resolve().parent.parent / "perfis" / "municipais"


@runtime_checkable
class FontePerfilMunicipal(Protocol):
    """Carrega/grava o perfil municipal por ``cod_ibge``."""

    def carregar(self, cod_ibge: str) -> Optional[PerfilMunicipal]:
        """Perfil persistido (confirmado) do município, ou ``None`` se não houver."""

    def salvar(self, perfil: PerfilMunicipal) -> None:
        """Persiste o perfil (o router só chama isto com ``status='confirmado'``)."""


class FontePerfilMunicipalArquivo:
    """Perfil em arquivos JSON: ``{diretorio}/{cod_ibge}.json``. Degrada honesto: JSON
    ausente/corrompido → ``None`` (não inventa perfil)."""

    def __init__(self, diretorio: str | os.PathLike):
        self.diretorio = Path(diretorio)

    def carregar(self, cod_ibge: str) -> Optional[PerfilMunicipal]:
        caminho = self.diretorio / f"{cod_ibge}.json"
        if not caminho.exists():
            return None
        try:
            return PerfilMunicipal.model_validate_json(caminho.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def salvar(self, perfil: PerfilMunicipal) -> None:
        self.diretorio.mkdir(parents=True, exist_ok=True)
        caminho = self.diretorio / f"{perfil.cod_ibge}.json"
        caminho.write_text(
            perfil.model_dump_json(indent=2, exclude_none=False), encoding="utf-8"
        )


def get_fonte_perfil() -> FontePerfilMunicipal:
    """Dependência FastAPI da fonte de perfil municipal.

    PRODUÇÃO: grava/lê em ``PERFIL_MUNICIPAL_DIR`` (ou ``perfis/municipais`` por padrão);
    o diretório é criado no primeiro ``salvar``. TESTES: sobrescrito via
    ``dependency_overrides`` por uma fonte em memória.
    """
    diretorio = os.getenv("PERFIL_MUNICIPAL_DIR", str(_DIR_DEFAULT))
    return FontePerfilMunicipalArquivo(diretorio)
