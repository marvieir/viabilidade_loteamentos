"""Fase U5 — MEMÓRIA do motor de urbanismo (aprendizado auditável, sem caixa-preta).

O operador AVALIA cada estudo de massa (1–5 estrelas + comentário). As avaliações ficam
num JSONL append-only; na próxima geração, os PROGRAMAS mais bem avaliados da mesma
região/perfil entram como REFERÊNCIA (few-shot) no prompt do gerador — a IA calibra a
estratégia com o que o operador aprovou, e o Python continua medindo tudo (§2: nenhum
número vem da memória; ela orienta a proposta, não o cálculo).

Determinístico e auditável: mesmo arquivo de memória → mesmos exemplos, na mesma ordem.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional, Protocol, runtime_checkable

_DIR_DEFAULT = Path(__file__).resolve().parent.parent / "perfis" / "memoria-urbanismo"

# Só entra na memória de referência o que o operador APROVOU de verdade.
RATING_MIN_REFERENCIA = 4
N_REFERENCIAS = 3


@runtime_checkable
class FonteMemoriaUrbanismo(Protocol):
    def avaliar(self, registro: dict) -> None: ...
    def avaliacoes(self, analise_id: str) -> list[dict]: ...
    def melhores(self, municipio: Optional[str], publico_alvo: str,
                 n: int = N_REFERENCIAS) -> list[dict]: ...


class FonteMemoriaArquivo:
    """JSONL append-only em ``{diretorio}/memoria.jsonl``. Degrada honesto: arquivo
    ausente/linha corrompida → ignora (nunca derruba a geração)."""

    def __init__(self, diretorio: str | os.PathLike):
        self.diretorio = Path(diretorio)

    def _caminho(self) -> Path:
        return self.diretorio / "memoria.jsonl"

    def _ler(self) -> list[dict]:
        caminho = self._caminho()
        if not caminho.exists():
            return []
        registros: list[dict] = []
        try:
            for linha in caminho.read_text(encoding="utf-8").splitlines():
                linha = linha.strip()
                if not linha:
                    continue
                try:
                    registros.append(json.loads(linha))
                except ValueError:
                    continue  # linha corrompida → ignora (não derruba)
        except OSError:
            return []
        return registros

    def avaliar(self, registro: dict) -> None:
        self.diretorio.mkdir(parents=True, exist_ok=True)
        with open(self._caminho(), "a", encoding="utf-8") as f:
            f.write(json.dumps(registro, ensure_ascii=False) + "\n")

    def avaliacoes(self, analise_id: str) -> list[dict]:
        return [r for r in self._ler() if r.get("analise_id") == analise_id]

    def melhores(self, municipio: Optional[str], publico_alvo: str,
                 n: int = N_REFERENCIAS) -> list[dict]:
        """Programas com rating ≥4 do MESMO público-alvo; prioriza o mesmo município (senão
        qualquer região). Última avaliação de cada proposta vale (re-avaliação corrige).
        Ordena por rating desc e recência; devolve só o RESUMO do programa (few-shot)."""
        regs = [r for r in self._ler() if r.get("publico_alvo") == publico_alvo
                and r.get("programa_resumo")]
        # a ÚLTIMA avaliação de cada proposta prevalece (permite corrigir uma nota)
        por_proposta: dict[str, dict] = {}
        for r in regs:
            chave = str(r.get("proposta_id") or f"{r.get('analise_id')}#{r.get('versao')}")
            por_proposta[chave] = r
        aprovados = [r for r in por_proposta.values()
                     if int(r.get("rating") or 0) >= RATING_MIN_REFERENCIA]
        locais = [r for r in aprovados if municipio and r.get("municipio") == municipio]
        base = locais or aprovados
        # recente primeiro dentro do mesmo rating (2 passadas estáveis — determinístico)
        base.sort(key=lambda r: (str(r.get("data") or ""), str(r.get("proposta_id") or "")),
                  reverse=True)
        base.sort(key=lambda r: -int(r.get("rating") or 0))
        saida = []
        for r in base[:n]:
            saida.append({**r["programa_resumo"], "rating": int(r.get("rating") or 0)})
        return saida


def get_fonte_memoria_urbanismo() -> FonteMemoriaUrbanismo:
    diretorio = os.getenv("MEMORIA_URBANISMO_DIR", str(_DIR_DEFAULT))
    return FonteMemoriaArquivo(diretorio)
