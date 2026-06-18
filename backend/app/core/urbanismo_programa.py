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

import logging
import math
import os
from dataclasses import dataclass, field
from typing import Optional, Protocol, runtime_checkable

from app.core.extrator_luos import MODELO_PADRAO, _opcoes_tls

_log = logging.getLogger(__name__)

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
    # esqueleto de vias principais (polilinhas/curvas, coords normalizadas 0..1). Fase 9.9: a IA
    # propõe a via-tronco SINUOSA + ramos (≥4 vértices p/ curvar); o Python suaviza e materializa.
    esqueleto: list = field(default_factory=list)
    esqueleto_origem: str = "vazio"  # "llm" quando veio do modelo; senão fallback/grade (geom)
    # Fase 9.3 — CALIBRAÇÃO por perfil (o lote emerge da subdivisão da quadra, mirando estes).
    publico_alvo: str = "media"
    testada_alvo_m: float = 12.0
    faixa_lote_m2: tuple[float, float] = (300.0, 450.0)
    lote_alvo_origem: str = ""
    # Fase 9.2 (HISTÓRICO — não governa mais o tamanho; mantido só p/ proveniência da proposta).
    estrategia_mix: list[dict] = field(default_factory=list)
    heuristicas: dict = field(default_factory=dict)
    origem: str = "preset"
    justificativa: str = ""


# ----------------------------- CALIBRAÇÃO de lote por perfil (Fase 9.3, §4) -----------------------------
# O tamanho NÃO é imposto — emerge da quadra; estes são a MIRA (testada/prof) e a FAIXA do perfil.
# testada × prof ≈ piso da faixa (lote grande é exceção; massa no piso). Referência de mercado.
PERFIL_LOTE: dict[str, dict] = {
    "baixa": {"testada": 9.0, "prof": 20.0, "faixa": (125.0, 250.0)},   # ~180 m²
    "media": {"testada": 12.0, "prof": 28.0, "faixa": (300.0, 450.0)},  # ~336 m²
    "alta": {"testada": 15.0, "prof": 31.0, "faixa": (450.0, 640.0)},   # ~465 m²
}


def dims_perfil(publico_alvo: str, lote_alvo_m2: float) -> dict:
    """Mira de subdivisão (testada/prof) + faixa do perfil. O ``lote_alvo`` da IA é REFERÊNCIA:
    se cair fora da faixa, registra o rebaixamento — nunca força uma área única (§3)."""
    p = PERFIL_LOTE.get(publico_alvo, PERFIL_LOTE["media"])
    lo, hi = p["faixa"]
    if lote_alvo_m2 > hi:
        origem = (
            f"rebaixado para a faixa: IA propôs {lote_alvo_m2:.0f} m²; perfil '{publico_alvo}' "
            f"= {lo:.0f}–{hi:.0f} m² — o tamanho emerge da quadra, mirando o piso."
        )
    elif lote_alvo_m2 < lo:
        origem = (
            f"elevado para a faixa: IA propôs {lote_alvo_m2:.0f} m²; perfil '{publico_alvo}' "
            f"= {lo:.0f}–{hi:.0f} m²."
        )
    else:
        origem = f"referência da IA ({lote_alvo_m2:.0f} m²) dentro da faixa do perfil."
    return {"testada": p["testada"], "prof": p["prof"], "faixa": (lo, hi), "lote_alvo_origem": origem}


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

# Fase 9.2 — POLÍTICA de mix de tamanhos (faixas de área + proporção-alvo) por perfil. Defaults
# calibrados por referência de mercado (urbIA); EDITÁVEIS — NUNCA são meta, só ponto de partida.
MIX_PRESETS: dict[str, list[dict]] = {
    "baixa": [
        {"faixa": "premium", "min_m2": 250.0, "max_m2": 350.0, "prop_alvo": 0.15},
        {"faixa": "padrao", "min_m2": 180.0, "max_m2": 250.0, "prop_alvo": 0.55},
        {"faixa": "compacto", "min_m2": 125.0, "max_m2": 180.0, "prop_alvo": 0.30},
    ],
    "media": [
        {"faixa": "premium", "min_m2": 450.0, "max_m2": 600.0, "prop_alvo": 0.20},
        {"faixa": "padrao", "min_m2": 300.0, "max_m2": 420.0, "prop_alvo": 0.55},
        {"faixa": "compacto", "min_m2": 220.0, "max_m2": 300.0, "prop_alvo": 0.25},
    ],
    "alta": [
        {"faixa": "premium", "min_m2": 700.0, "max_m2": 900.0, "prop_alvo": 0.25},
        {"faixa": "padrao", "min_m2": 450.0, "max_m2": 600.0, "prop_alvo": 0.55},
        {"faixa": "compacto", "min_m2": 350.0, "max_m2": 450.0, "prop_alvo": 0.20},
    ],
}
# Heurísticas de valorização (conhecimento estável de urbanismo) — ONDE pôr o premium.
HEURISTICAS_DEFAULT = {
    "premium_em": ["fundo_mata", "frente_lazer", "cota_alta"],
    "penalizar": ["via_principal", "entrada"],
    "origem": "preset",
    "justificativa": (
        "Táticas de valorização: lote grande na cota alta, fundo para mata, frente para "
        "lazer; penaliza ruído da via principal/entrada. Referência de mercado — calibre."
    ),
}


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
    # Fase 9.3 — mira de subdivisão por perfil (o tamanho emerge da quadra, não do lote_alvo).
    cal = dims_perfil(publico_alvo, lote_alvo)
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
        publico_alvo=publico_alvo,
        testada_alvo_m=float(ov.get("testada_alvo_m", cal["testada"])),
        faixa_lote_m2=cal["faixa"],
        lote_alvo_origem=cal["lote_alvo_origem"],
        estrategia_mix=list(ov.get("estrategia_mix", [])),
        heuristicas=dict(ov.get("heuristicas", HEURISTICAS_DEFAULT)),
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
    "densidade, esqueleto, MIX de tamanhos por faixa + proporção, e heurísticas de "
    "valorização — onde pôr lotes premium: cota alta, fundo de mata, frente para lazer). "
    "NUNCA devolva nº de lotes, área vendável, tamanho ou polígono de lote — isso é MEDIDO "
    "pelo motor depois, não por você. O mix é POLÍTICA, não otimização: você não busca a "
    "distribuição 'ótima', só propõe a estratégia; o heatmap mede a consequência.\n"
    "2. Coerência com o público-alvo: alta renda → lotes maiores, mais lazer, viário "
    "sinuoso; baixa renda → lotes menores, grelha eficiente, lazer mínimo.\n"
    "3. ESQUELETO VIÁRIO — OBRIGATÓRIO quando o arquétipo NÃO é 'grelha_eficiente' (Fase 9.9): "
    "proponha a via-tronco como uma POLILINHA SINUOSA com PELO MENOS 4 vértices (para o motor "
    "curvar), acompanhando o eixo maior da parte loteável, MAIS 1–3 ramos curtos. Coordenadas "
    "NORMALIZADAS 0..1 do bounding box da gleba (x=0 oeste→1 leste; y=0 sul→1 norte). As curvas "
    "devem CONTORNAR a área íngreme/não-edificável (o motor já a recortou) e acompanhar o "
    "relevo. Formato: lista de polilinhas [[x,y],[x,y],...]; a via-tronco vem primeiro. O motor "
    "mapeia para a gleba real, SUAVIZA (Bézier/Catmull-Rom), valida e recorta — você dá a forma "
    "da curva, NÃO coordenadas finais nem larguras. Para 'grelha_eficiente' o esqueleto pode "
    "ser omitido (o motor usa grelha ortogonal). NUNCA devolva o esqueleto vazio num arquétipo "
    "sinuoso/misto."
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
                "description": (
                    "OBRIGATÓRIO p/ arquétipo sinuoso/misto (Fase 9.9): lista de polilinhas "
                    "[[x,y],...] em coords NORMALIZADAS 0..1 do bbox (x oeste→leste, y sul→norte). "
                    "A 1ª é a VIA-TRONCO SINUOSA com ≥4 vértices (curva acompanhando o eixo maior "
                    "loteável, contornando o íngreme); as demais são ramos curtos. Só a forma da "
                    "curva — o motor suaviza/mede. Omitir apenas em 'grelha_eficiente'."
                ),
                "items": {"type": "array", "items": {"type": "array", "items": {"type": "number"}}},
            },
            "estrategia_mix": {
                "type": "array",
                "description": (
                    "faixas de tamanho de lote + proporção-alvo (mix heterogêneo); ex.: "
                    '[{"faixa":"premium","min_m2":700,"max_m2":900,"prop_alvo":0.25}, …]. '
                    "POLÍTICA — o motor dimensiona e mede; não é meta."
                ),
                "items": {"type": "object"},
            },
            "heuristicas": {
                "type": "object",
                "description": (
                    'onde aplicar valorização: {"premium_em":["cota_alta","fundo_mata",'
                    '"frente_lazer"],"penalizar":["via_principal","entrada"]}'
                ),
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

        # Esta chamada TEM fallback (preset) — então poucas retentativas do SDK p/ degradar
        # RÁPIDO se a API estiver sobrecarregada (evita o request travar e o front cair).
        # (sem ``timeout=`` aqui: é mutuamente exclusivo com o http_client da TLS corporativa.)
        client = anthropic.Anthropic(api_key=self.api_key, max_retries=1, **_opcoes_tls())
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
        except Exception as exc:  # noqa: BLE001 — serviço fora → preset (não inventa, degrada)
            # NÃO engolir o motivo: loga o erro real (traceback no log do container) e expõe o
            # TIPO + mensagem curta na justificativa, p/ o operador diagnosticar SEM adivinhar
            # (key inválida? rede/TLS bloqueada p/ api.anthropic.com? sobrecarga?). O tipo/str da
            # exceção da SDK não vaza a chave (ex.: "AuthenticationError: invalid x-api-key").
            _log.warning("Programa via IA falhou no /propor — caindo no preset: %r", exc, exc_info=True)
            detalhe = f"{type(exc).__name__}: {exc}"[:160]
            prog = programa_do_preset(publico_alvo, overrides)
            prog.justificativa = (
                f"Serviço de IA indisponível ({detalhe}) — programa do preset. " + prog.justificativa
            )
            return prog

        bruto = next(
            (b.input for b in resp.content if getattr(b, "type", None) == "tool_use"), None
        )
        if not isinstance(bruto, dict):
            return programa_do_preset(publico_alvo, overrides)

        # Funde a proposta do LLM com o preset (defaults) e aplica overrides do usuário por cima.
        merged = dict(overrides or {})
        for k in ("lote_alvo_m2", "pct_lazer", "largura_via_m", "amenidades",
                  "pct_institucional", "esqueleto", "estrategia_mix", "heuristicas"):
            if k in bruto and k not in merged:
                merged[k] = bruto[k]
        prog = programa_do_preset(publico_alvo, merged)
        prog.densidade = bruto.get("densidade", prog.densidade)
        prog.arquetipo_viario = bruto.get("arquetipo_viario", prog.arquetipo_viario)
        prog.origem = "proposto_llm"
        # Fase 9.9 — marca a origem do esqueleto: "llm" se o modelo de fato propôs a(s) curva(s).
        prog.esqueleto_origem = "llm" if prog.esqueleto else "vazio"
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
