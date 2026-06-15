"""Urbanismo (Fase 9) — a BORDA: o LLM PROPÕE o PROGRAMA, nunca a geometria nem o número.

O artefato que cruza a fronteira do §2 é um ``Programa`` estruturado (intenção + esqueleto
grosseiro). O LLM escolhe a ESTRATÉGIA (lote-alvo, hierarquia viária, % de lazer, arquétipo,
densidade); o ``urbanismo_geom`` materializa a geometria e o ``urbanismo_medida`` mede. O
LLM **jamais** devolve polígono de lote nem nº de lotes (o nº EMERGE da geração).

Os PERFIS de público-alvo são PRESETS EMBARCADOS (conhecimento estável de mercado —
"dado estável é pipeline, não agente"), editáveis e rotulados. O LLM contextualiza
qualitativamente; os guard-rails numéricos são determinísticos.

Fonte INJETÁVEL (``GeradorPrograma``): testes usam stub offline (sem rede/chave); a impl
real (``GeradorProgramaClaude``) fica atrás da interface e DESLIGADA por padrão — só liga
com ``ANTHROPIC_API_KEY`` (reusa TLS/erros da 1.8; sem credencial nova).
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass, field
from typing import Optional, Protocol, runtime_checkable

from app.core.extrator_luos import MODELO_PADRAO, _opcoes_tls

TIPOS = ("aberto", "fechado", "condominio_lotes", "desmembramento", "loteamento_rural")
PUBLICOS = ("baixa", "media", "alta")


class GeradorIndisponivel(RuntimeError):
    """Gerador de programa não configurado (sem credencial de LLM). Router → 503 honesto."""


@dataclass
class Programa:
    """O que o LLM PROPÕE (intenção). Os campos numéricos são ESTRATÉGIA, não medida —
    a geometria e o nº de lotes saem do núcleo Python a partir daqui."""

    lote_alvo_m2: float
    densidade: str
    pct_lazer: float
    amenidades: list[str]
    arquetipo_viario: str
    largura_via_m: float
    testada_m: float
    profundidade_m: float
    pct_institucional: float = 0.0
    # esqueleto grosseiro de vias principais (polilinhas, CRS métrico da tela) — SUGESTÃO.
    esqueleto: list[list[list[float]]] = field(default_factory=list)
    origem: str = "preset"
    justificativa: str = ""


# ----------------------------- PRESETS EMBARCADOS (§5) -----------------------------
# Monotônico em lote_alvo e pct_lazer (baixa ≤ média ≤ alta) — guard-rail testável.
PRESETS: dict[str, dict] = {
    "baixa": {
        "lote_alvo_m2": 200.0,
        "densidade": "alta",
        "pct_lazer": 0.05,
        "amenidades": ["institucional básico"],
        "arquetipo_viario": "grelha_eficiente",
        "largura_via_m": 10.0,
    },
    "media": {
        "lote_alvo_m2": 350.0,
        "densidade": "media",
        "pct_lazer": 0.12,
        "amenidades": ["playground", "quadra", "salão de festas"],
        "arquetipo_viario": "misto",
        "largura_via_m": 12.0,
    },
    "alta": {
        "lote_alvo_m2": 800.0,
        "densidade": "baixa",
        "pct_lazer": 0.20,
        "amenidades": ["clube", "lago", "tênis", "mirante", "paisagismo"],
        "arquetipo_viario": "sinuoso_fundo_verde",
        "largura_via_m": 14.0,
    },
}

# Razão testada:profundidade típica de lote (frente menor que a profundidade).
_RAZAO_TESTADA = 0.72


def _dims_lote(area: float) -> tuple[float, float]:
    """(testada, profundidade) de um retângulo de ``area`` com razão fixa — determinístico."""
    testada = math.sqrt(area * _RAZAO_TESTADA)
    profundidade = area / testada
    return round(testada, 2), round(profundidade, 2)


def programa_do_preset(publico_alvo: str, overrides: Optional[dict] = None) -> Programa:
    """Programa determinístico a partir do preset (sem LLM) — base do stub e do fallback.
    ``overrides`` (do usuário) sobrepõem campos do preset, com proveniência ``preset+override``."""
    base = PRESETS.get(publico_alvo, PRESETS["media"])
    ov = overrides or {}
    lote_alvo = float(ov.get("lote_alvo_m2", base["lote_alvo_m2"]))
    pct_lazer = float(ov.get("pct_lazer", base["pct_lazer"]))
    largura_via = float(ov.get("largura_via_m", base["largura_via_m"]))
    amenidades = list(ov.get("amenidades", base["amenidades"]))
    testada, profundidade = _dims_lote(lote_alvo)
    if "testada_m" in ov:
        testada = float(ov["testada_m"])
        profundidade = round(lote_alvo / testada, 2) if testada else profundidade
    return Programa(
        lote_alvo_m2=lote_alvo,
        densidade=base["densidade"],
        pct_lazer=pct_lazer,
        amenidades=amenidades,
        arquetipo_viario=base["arquetipo_viario"],
        largura_via_m=largura_via,
        testada_m=testada,
        profundidade_m=profundidade,
        pct_institucional=float(ov.get("pct_institucional", 0.0)),
        esqueleto=list(ov.get("esqueleto", [])),
        origem="preset+override" if ov else "preset",
        justificativa=(
            f"Preset de público-alvo '{publico_alvo}' (perfil de referência de mercado — "
            "calibre com seu urbanista/corretor)."
        ),
    )


# ----------------------------- interface injetável -----------------------------
@runtime_checkable
class GeradorPrograma(Protocol):
    def propor(self, contexto: dict, tipo_loteamento: str, publico_alvo: str,
               overrides: Optional[dict] = None) -> Programa: ...


_INSTRUCAO = (
    "Você é urbanista de PRÉ-ANÁLISE. Propõe um PROGRAMA de estudo de massa (não o projeto "
    "executivo) para uma gleba, dado o público-alvo. Regras INEGOCIÁVEIS:\n"
    "1. Você propõe ESTRATÉGIA (lote-alvo em m², hierarquia viária, % de lazer, arquétipo, "
    "densidade, esqueleto grosseiro de vias principais). NUNCA devolva nº de lotes, área "
    "vendável ou polígono de lote — isso é MEDIDO pelo motor depois, não por você.\n"
    "2. Coerência com o público-alvo: alta renda → lotes maiores, mais lazer, viário "
    "sinuoso; baixa renda → lotes menores, grelha eficiente, lazer mínimo.\n"
    "3. O esqueleto é OPCIONAL e apenas uma SUGESTÃO de eixos de via (polilinhas em metros, "
    "relativas à tela informada) — o motor valida/regulariza e pode ignorar trecho inviável."
)

_FERRAMENTA = {
    "name": "registrar_programa_urbanistico",
    "description": (
        "Registra o PROGRAMA de estudo de massa (estratégia + esqueleto). Sem nº de lotes, "
        "sem áreas medidas, sem polígono de lote."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "lote_alvo_m2": {"type": "number"},
            "densidade": {"type": "string", "enum": ["alta", "media", "baixa"]},
            "pct_lazer": {"type": "number", "description": "fração (0.20 = 20%)"},
            "amenidades": {"type": "array", "items": {"type": "string"}},
            "arquetipo_viario": {"type": "string"},
            "largura_via_m": {"type": "number"},
            "pct_institucional": {"type": "number", "description": "fração; 0 se não souber"},
            "esqueleto": {
                "type": "array",
                "description": "polilinhas [[x,y],...] em metros relativos à tela (opcional)",
                "items": {"type": "array", "items": {"type": "array", "items": {"type": "number"}}},
            },
            "justificativa": {"type": "string"},
        },
        "required": ["lote_alvo_m2", "densidade", "pct_lazer", "arquetipo_viario"],
    },
}


class GeradorProgramaClaude:
    """Proposta real via Claude API (tool use forçado). Import de ``anthropic`` é TARDIO.
    Falha de serviço → cai no preset (degradação honesta), nunca quebra o estudo."""

    def __init__(self, api_key: Optional[str] = None, modelo: str = MODELO_PADRAO):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.modelo = os.getenv("URBANISMO_MODELO", modelo)

    def propor(self, contexto, tipo_loteamento, publico_alvo, overrides=None) -> Programa:
        try:
            import anthropic
        except ImportError as exc:
            raise GeradorIndisponivel("Pacote 'anthropic' ausente.") from exc

        client = anthropic.Anthropic(api_key=self.api_key, **_opcoes_tls())
        prompt = (
            f"Gleba: público-alvo '{publico_alvo}', tipo '{tipo_loteamento}'. "
            f"Contexto medido pelo motor (NÃO recalcule): {contexto}. "
            "Proponha o programa. Lembre: nada de nº de lotes nem áreas vendáveis."
        )
        try:
            resp = client.messages.create(
                model=self.modelo,
                max_tokens=4000,
                system=_INSTRUCAO,
                tools=[_FERRAMENTA],
                tool_choice={"type": "tool", "name": _FERRAMENTA["name"]},
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception:  # noqa: BLE001 — serviço fora → preset (não inventa, degrada)
            prog = programa_do_preset(publico_alvo, overrides)
            prog.justificativa = "Serviço de IA indisponível — programa do preset. " + prog.justificativa
            return prog

        bruto = next(
            (b.input for b in resp.content if getattr(b, "type", None) == "tool_use"), None
        )
        if not isinstance(bruto, dict):
            return programa_do_preset(publico_alvo, overrides)

        # Funde a proposta do LLM com o preset (defaults) e aplica overrides do usuário por cima.
        merged = dict(overrides or {})
        for k in ("lote_alvo_m2", "pct_lazer", "largura_via_m", "amenidades",
                  "pct_institucional", "esqueleto"):
            if k in bruto and k not in merged:
                merged[k] = bruto[k]
        prog = programa_do_preset(publico_alvo, merged)
        prog.densidade = bruto.get("densidade", prog.densidade)
        prog.arquetipo_viario = bruto.get("arquetipo_viario", prog.arquetipo_viario)
        prog.origem = "proposto_llm"
        prog.justificativa = bruto.get("justificativa", prog.justificativa)
        return prog


def get_gerador_programa() -> Optional[GeradorPrograma]:
    """Dependência FastAPI. Liga o Claude só com ``ANTHROPIC_API_KEY`` e sem
    ``URBANISMO_GERADOR_DESLIGADO``; senão ``None`` → router responde 503 honesto.
    Nos testes é sobrescrito por um stub offline (ou ``None`` para exercer o 503)."""
    if os.getenv("URBANISMO_GERADOR_DESLIGADO"):
        return None
    if os.getenv("ANTHROPIC_API_KEY"):
        return GeradorProgramaClaude()
    return None
