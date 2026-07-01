"""Medição de custo de LLM por análise — instrumentação do `usage` das chamadas Claude.

Objetivo: substituir a ESTIMATIVA de custo por MEDIÇÃO real (disciplina do projeto: não
inventar dado). Cada uma das 3 chamadas de IA (extração LUOS, urbanismo IA, extração jurídica)
registra os tokens reais devolvidos pela API (``response.usage``) num log append-only, atribuídos
à análise em curso via um *contexto* setado pelo router. O painel admin agrega isso em custo real
por análise (§ router admin).

Não invasivo: o extrator só chama ``registrar(modelo, usage)``; o analise_id/dimensão vêm do
contextvar que o router preenche com ``with contexto(...)``. Nunca levanta exceção — logar custo
JAMAIS pode quebrar uma extração (envolvido em try/except silencioso).
"""

from __future__ import annotations

import contextlib
import contextvars
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Preço por 1M de tokens (US$): (input, output). Fonte: tabela oficial Anthropic 2026-06.
# Fable 5 incluído por completude, mas hoje NÃO é usado (indisponível → cai p/ Opus 4.8).
PRECOS: dict[str, tuple[float, float]] = {
    "claude-opus-4-8": (5.0, 25.0),
    "claude-opus-4-7": (5.0, 25.0),
    "claude-opus-4-6": (5.0, 25.0),
    "claude-sonnet-5": (3.0, 15.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-haiku-4-5": (1.0, 5.0),
    "claude-fable-5": (10.0, 50.0),
}

_LOG_DEFAULT = Path(__file__).resolve().parent.parent / "perfis" / "uso_llm" / "uso.jsonl"


def _usd_brl() -> float:
    try:
        return float(os.getenv("USD_BRL", "5.5"))
    except ValueError:
        return 5.5


def _caminho_log() -> Path:
    return Path(os.getenv("USO_LLM_LOG", str(_LOG_DEFAULT)))


# ----- Contexto da análise em curso (setado pelo router antes de chamar o extrator) -----
_CTX: contextvars.ContextVar[Optional[dict]] = contextvars.ContextVar("uso_ctx", default=None)


@contextlib.contextmanager
def contexto(
    dimensao: str,
    analise_id: str = "",
    cod_ibge: str = "",
    usuario_id: str = "",
    meta: Optional[dict] = None,
):
    """Marca a análise/dimensão em curso; o ``registrar`` seguinte atribui o custo a ela.
    ``meta`` grava atributos extras no registro (ex.: tipo_loteamento) para as métricas de uso."""
    token = _CTX.set(
        {
            "dimensao": dimensao,
            "analise_id": analise_id or "",
            "cod_ibge": cod_ibge or "",
            "usuario_id": usuario_id or "",
            "meta": meta or {},
        }
    )
    try:
        yield
    finally:
        _CTX.reset(token)


def custo_usd(modelo: str, input_tok: int, output_tok: int, cache_tok: int = 0) -> Optional[float]:
    """Custo em US$ da chamada. Cache read ≈ 0,1× do input. None se o modelo não está tabelado."""
    p = PRECOS.get(modelo)
    if not p:
        return None
    p_in, p_out = p
    billed_in = max(input_tok - cache_tok, 0)
    return (billed_in * p_in + cache_tok * p_in * 0.1 + output_tok * p_out) / 1_000_000


def registrar(modelo: str, usage, fonte=None) -> None:
    """Registra o custo real de UMA chamada Claude. Lê o contexto (analise/dimensão) e
    persiste um registro no log. Silencioso e à prova de falha — nunca quebra a extração."""
    try:
        if usage is None:
            return
        ctx = _CTX.get()
        if ctx is None:
            return  # sem contexto (ex.: teste/uso solto) → não registra
        in_tok = int(getattr(usage, "input_tokens", 0) or 0)
        out_tok = int(getattr(usage, "output_tokens", 0) or 0)
        cache_tok = int(getattr(usage, "cache_read_input_tokens", 0) or 0)
        c_usd = custo_usd(modelo, in_tok, out_tok, cache_tok)
        registro = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "dimensao": ctx["dimensao"],
            "analise_id": ctx["analise_id"],
            "cod_ibge": ctx["cod_ibge"],
            "usuario_id": ctx["usuario_id"],
            "modelo": modelo,
            "input_tokens": in_tok,
            "output_tokens": out_tok,
            "cache_read_tokens": cache_tok,
            "custo_usd": c_usd,
            "custo_brl": (round(c_usd * _usd_brl(), 4) if c_usd is not None else None),
        }
        # Atributos extras de uso (ex.: tipo_loteamento), sem sobrescrever os campos-núcleo.
        for k, v in (ctx.get("meta") or {}).items():
            if k not in registro:
                registro[k] = v
        (fonte or _gravar)(registro)
    except Exception:  # noqa: BLE001 — logar custo nunca pode derrubar a extração
        pass


def _gravar(registro: dict) -> None:
    caminho = _caminho_log()
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("a", encoding="utf-8") as f:
        f.write(json.dumps(registro, ensure_ascii=False) + "\n")


def ler_registros() -> list[dict]:
    """Lê todos os registros do log (para o painel admin). Degrada honesto: sem log → []."""
    caminho = _caminho_log()
    if not caminho.exists():
        return []
    out: list[dict] = []
    try:
        for linha in caminho.read_text(encoding="utf-8").splitlines():
            linha = linha.strip()
            if not linha:
                continue
            try:
                out.append(json.loads(linha))
            except ValueError:
                continue
    except OSError:
        return []
    return out
