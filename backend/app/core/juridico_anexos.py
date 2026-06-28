"""Anexos do checklist jurídico (Fase C manual) — o cliente baixa o documento do órgão e o
ANEXA ao item do roteiro. Fonte injetável (mesmo padrão das fichas): produção grava arquivo +
metadados num volume; testes injetam memória.

Guarda o ARQUIVO em disco (``{dir}/anexos/{analise_id}/{id}__{nome}``) e os metadados num JSON
(``{dir}/anexos/{analise_id}.json``). Determinístico: o id vem de (chave, nome) — re-anexar o
mesmo arquivo no mesmo item SUBSTITUI; nomes diferentes no mesmo item coexistem (ex.: certidões
de vários titulares). Nada aqui analisa — só persiste.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Optional, Protocol, runtime_checkable

from app.models.schemas import AnexoOut

_DIR_DEFAULT = Path(__file__).resolve().parent.parent / "perfis" / "juridico"


def _anexo_id(chave: str, nome: str) -> str:
    return hashlib.sha1(f"{chave}|{nome}".encode("utf-8")).hexdigest()[:12]


def _nome_seguro(nome: str) -> str:
    """Só o basename, sem separadores de caminho (anti path-traversal)."""
    base = (nome or "documento").replace("\\", "/").rsplit("/", 1)[-1]
    return base[:180] or "documento"


@runtime_checkable
class FonteAnexos(Protocol):
    def listar(self, analise_id: str) -> list[AnexoOut]: ...
    def salvar(self, analise_id: str, chave: str, nome: str, conteudo: bytes, hoje: str) -> AnexoOut: ...
    def remover(self, analise_id: str, anexo_id: str) -> bool: ...
    def ler(self, analise_id: str, anexo_id: str) -> Optional[tuple[str, bytes]]: ...


class FonteAnexosArquivo:
    """Anexos em ``{dir}/anexos/``. Degrada honesto: metadados ausentes/corrompidos → lista vazia."""

    def __init__(self, diretorio: str | os.PathLike):
        self.base = Path(diretorio) / "anexos"

    def _meta_path(self, analise_id: str) -> Path:
        return self.base / f"{analise_id}.json"

    def _dir_arquivos(self, analise_id: str) -> Path:
        return self.base / analise_id

    def _ler_meta(self, analise_id: str) -> list[dict]:
        p = self._meta_path(analise_id)
        if not p.exists():
            return []
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []

    def _gravar_meta(self, analise_id: str, registros: list[dict]) -> None:
        self.base.mkdir(parents=True, exist_ok=True)
        self._meta_path(analise_id).write_text(
            json.dumps(registros, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def listar(self, analise_id: str) -> list[AnexoOut]:
        return [AnexoOut(**{k: v for k, v in r.items() if k != "arquivo"}) for r in self._ler_meta(analise_id)]

    def salvar(self, analise_id: str, chave: str, nome: str, conteudo: bytes, hoje: str) -> AnexoOut:
        nome = _nome_seguro(nome)
        anexo_id = _anexo_id(chave, nome)
        dir_arq = self._dir_arquivos(analise_id)
        dir_arq.mkdir(parents=True, exist_ok=True)
        nome_disco = f"{anexo_id}__{nome}"
        (dir_arq / nome_disco).write_bytes(conteudo)
        registros = [r for r in self._ler_meta(analise_id) if r.get("id") != anexo_id]
        rec = {
            "id": anexo_id,
            "chave": chave,
            "fonte_documento": nome,
            "data_referencia": hoje,
            "tamanho_bytes": len(conteudo),
            "arquivo": nome_disco,  # só no metadado em disco; não vai pro AnexoOut
        }
        registros.append(rec)
        self._gravar_meta(analise_id, registros)
        return AnexoOut(**{k: v for k, v in rec.items() if k != "arquivo"})

    def remover(self, analise_id: str, anexo_id: str) -> bool:
        registros = self._ler_meta(analise_id)
        alvo = next((r for r in registros if r.get("id") == anexo_id), None)
        if alvo is None:
            return False
        try:
            (self._dir_arquivos(analise_id) / alvo.get("arquivo", "")).unlink(missing_ok=True)
        except OSError:
            pass
        self._gravar_meta(analise_id, [r for r in registros if r.get("id") != anexo_id])
        return True

    def ler(self, analise_id: str, anexo_id: str) -> Optional[tuple[str, bytes]]:
        alvo = next((r for r in self._ler_meta(analise_id) if r.get("id") == anexo_id), None)
        if alvo is None:
            return None
        caminho = self._dir_arquivos(analise_id) / alvo.get("arquivo", "")
        if not caminho.exists():
            return None
        return (alvo.get("fonte_documento", "documento"), caminho.read_bytes())


def get_fonte_anexos() -> FonteAnexos:
    """Dependência FastAPI. PRODUÇÃO: ``JURIDICO_DIR`` (ou ``perfis/juridico``).
    TESTES: sobrescrito por uma fonte em memória."""
    diretorio = os.getenv("JURIDICO_DIR", str(_DIR_DEFAULT))
    return FonteAnexosArquivo(diretorio)
