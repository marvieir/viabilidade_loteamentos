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

from app.core.extrator_luos import MODELO_PADRAO, cadeia_de_modelos, _opcoes_tls

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
    # Fase 10 (Parte 3) — PONTO de travessia entre porções partidas (normalizado 0..1 do bbox da
    # área aproveitável). A IA propõe POR ONDE conectar (julgamento espacial); o Python mede o
    # greide real sobre o DEM e materializa a via. ``[]`` = motor escolhe o vão mais favorável.
    travessia: list = field(default_factory=list)
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
    "alta": {"testada": 15.0, "prof": 31.0, "faixa": (450.0, 1000.0)},  # premium: teto de MERCADO
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
    # CAP de largura (engine é dono da medida, §2): condomínio de lotes tem vias PRIVADAS — a
    # coletora-tronco de pista única vive bem com ≤11 m. Largura maior (a IA às vezes propõe 14 m de
    # "boulevard") só infla o viário (gargalo do aproveitamento) sem ganho. Caímos road e medição
    # juntos, então o contrato "tronco = largura_via_m" segue intacto.
    largura_via = min(float(ov.get("largura_via_m", base["largura_via_m"])), 11.0)
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
        travessia=list(ov.get("travessia", [])),
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
    "sinuoso/misto.\n"
    "4. PROGRAMA DE TRAÇADO — HIERARQUIA (Fase 9.14): organize as vias em (a) UMA via-TRONCO "
    "coletora que costura a gleba da entrada às porções (é o que impede o loteamento partido), "
    "(b) vias LOCAIS que servem as quadras, (c) CUL-DE-SACS (ramos sem saída) nos fundos de "
    "exclusividade — fundo de mata, cota alta, frente para verde — onde cabe lote premium em "
    "leque. Indique no esqueleto a via-tronco PRIMEIRO e os ramos curtos depois; sinalize na "
    "justificativa ONDE fazer cul-de-sac e a INTENÇÃO de CONTORNAR a restrição (nunca cruzá-la). "
    "O motor materializa o contorno, a conectividade, os bulbos e a recuperação — você dá a "
    "ESTRATÉGIA do traçado, NUNCA o número, a largura, o raio ou a medida (§2).\n"
    "5. CONSISTÊNCIA E QUALIDADE (CRÍTICO): a MESMA gleba deve receber SEMPRE o MESMO programa — "
    "não varie a cada chamada. Use os VALORES-PADRÃO do perfil, não invente: lazer = alta ~20%, "
    "média ~12%, baixa ~5% (NÃO proponha 22%, 18% etc. — fique no padrão); lote-alvo e mix do "
    "perfil. O ESQUELETO deve ser UM traçado LIMPO e SUAVE acompanhando o eixo maior loteável e "
    "contornando a restrição — sem ziguezague, sem ramos soltos, 4–6 vértices bem distribuídos. "
    "Prefira o traçado que GERA BONS LOTES (quadra cheia, todo lote com frente para via) ao desenho "
    "rebuscado: na pré-análise, ESTABILIDADE e aproveitamento valem mais que criatividade."
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
            "travessia": {
                "type": "array",
                "description": (
                    "Fase 10 — SE a área aproveitável vier PARTIDA em porções (uma declividade/mata "
                    "separa dois lados), proponha o PONTO [x,y] (coords NORMALIZADAS 0..1 do bbox) por "
                    "onde a via-tronco deve CRUZAR p/ ligar as porções: o vão mais estreito / a sela "
                    "mais suave, evitando a encosta íngreme. Só o PONTO (julgamento espacial) — o "
                    "motor mede o greide real sobre o relevo e materializa a via. Omitir se não há "
                    "porções separadas."
                ),
                "items": {"type": "number"},
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


def _prompt_usuario(contexto: dict, tipo_loteamento: str, publico_alvo: str) -> str:
    """Prompt do usuário (idêntico p/ todos os provedores — a proposta deve ser estável).

    Fase U5 — se o contexto traz ``programas_bem_avaliados`` (memória do operador), eles
    entram como REFERÊNCIA destacada: calibram lote-alvo/arquétipo/amenidades que a região
    aprovou, sem virar cópia (e sem nenhum número de medida — §2)."""
    referencia = contexto.get("programas_bem_avaliados") or []
    instrucoes = (contexto.get("instrucoes_do_operador") or "").strip()
    ctx = {k: v for k, v in contexto.items()
           if k not in ("programas_bem_avaliados", "instrucoes_do_operador")}
    prompt = (
        f"Gleba: público-alvo '{publico_alvo}', tipo '{tipo_loteamento}'. "
        f"Contexto medido pelo motor (NÃO recalcule): {ctx}. "
        "Proponha o programa. Lembre: nada de nº de lotes nem áreas vendáveis."
    )
    if instrucoes:
        prompt += (
            " DIRETRIZES DO OPERADOR (Movimento 1 — prioridade sobre os defaults do perfil, "
            f"dentro dos limites legais): \"{instrucoes}\". Traduza-as no programa (amenidades/"
            "arquétipo/heurísticas) — números e geometria continuam sendo do motor."
        )
    if referencia:
        prompt += (
            " REFERÊNCIA (memória do operador — programas anteriores BEM AVALIADOS na mesma "
            f"região/perfil): {referencia}. Use como calibração do lote-alvo, arquétipo e "
            "amenidades que agradaram; adapte à gleba atual, não copie cegamente."
        )
    return prompt


# Chaves que o LLM PODE propor e o preset funde (mesma lista p/ Claude e Gemini — contrato §2).
_CHAVES_LLM = (
    "lote_alvo_m2", "pct_lazer", "largura_via_m", "amenidades",
    "pct_institucional", "esqueleto", "estrategia_mix", "heuristicas",
)


def _montar_programa(bruto: dict, publico_alvo: str, overrides: Optional[dict] = None) -> Programa:
    """Funde a proposta CRUA do LLM (dict de tool-use/JSON) com o preset (defaults) e os
    ``overrides`` do usuário (que vencem). Caps de consistência (§4) + §2 aplicados aqui —
    UM só lugar, para Claude e Gemini produzirem o MESMO Programa a partir do mesmo bruto."""
    merged = dict(overrides or {})
    for k in _CHAVES_LLM:
        if k in bruto and k not in merged:
            merged[k] = bruto[k]
    # CAP de lazer da IA (consistência §4 + §2): a IA pode REDUZIR o lazer (mais lote), mas NÃO
    # exceder o padrão do perfil — 22% (vs 20%) reserva verde demais e derruba o nº de lotes entre
    # regenerações. NÃO toca override EXPLÍCITO do usuário (esse vale como pedido).
    if "pct_lazer" in merged and "pct_lazer" not in (overrides or {}):
        base_lazer = float(PRESETS.get(publico_alvo, PRESETS["media"])["pct_lazer"])
        try:
            merged["pct_lazer"] = min(float(merged["pct_lazer"]), base_lazer)
        except (TypeError, ValueError):
            merged.pop("pct_lazer", None)  # valor capenga do LLM → usa o do preset
    prog = programa_do_preset(publico_alvo, merged)
    prog.densidade = bruto.get("densidade", prog.densidade)
    prog.arquetipo_viario = bruto.get("arquetipo_viario", prog.arquetipo_viario)
    prog.origem = "proposto_llm"
    prog.esqueleto_origem = "llm" if prog.esqueleto else "vazio"  # 9.9 — origem do esqueleto
    prog.justificativa = bruto.get("justificativa", prog.justificativa)
    return prog


class GeradorProgramaClaude:
    """Provedor Claude (tool use forçado). Import de ``anthropic`` é TARDIO. Expõe ``propor_bruto``
    (dict cru) — a fusão/preset fica no compositor. Cadeia de modelos via ``cadeia_de_modelos``;
    erro de serviço (ex.: 529) propaga p/ o compositor tentar o próximo provedor (Gemini)."""

    nome = "Claude"

    def __init__(self, api_key: Optional[str] = None, modelo: str = MODELO_PADRAO):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        # Cadeia de modelos: env URBANISMO_MODELO fixa um modelo; senão Fable 5 → Opus 4.8.
        self.modelos = cadeia_de_modelos(os.getenv("URBANISMO_MODELO"))
        self.modelo_usado: Optional[str] = None

    def propor_bruto(self, contexto, tipo_loteamento, publico_alvo) -> Optional[dict]:
        try:
            import anthropic
        except ImportError as exc:
            raise GeradorIndisponivel("Pacote 'anthropic' ausente.") from exc

        # Poucas retentativas do SDK (degradar RÁPIDO): há fallback (Gemini → preset), então não
        # vale travar o request num 529 prolongado — o compositor passa pro próximo provedor.
        # (sem ``timeout=`` aqui: é mutuamente exclusivo com o http_client da TLS corporativa.)
        client = anthropic.Anthropic(api_key=self.api_key, max_retries=1, **_opcoes_tls())
        prompt = _prompt_usuario(contexto, tipo_loteamento, publico_alvo)
        resp, ultimo_erro = None, None
        for modelo in self.modelos:
            try:
                resp = client.messages.create(
                    model=modelo,
                    max_tokens=4000,
                    # NÃO passar `temperature`: alguns modelos novos (Opus 4.8/Fable 5) a depreciaram
                    # e devolvem 400. A CONSISTÊNCIA (§4) vem do CAP de lazer/largura + da regra 5.
                    system=_INSTRUCAO,
                    tools=[_FERRAMENTA],
                    tool_choice={"type": "tool", "name": _FERRAMENTA["name"]},
                    messages=[{"role": "user", "content": prompt}],
                )
                self.modelo_usado = modelo  # proveniência: qual modelo de fato serviu
                break
            except Exception as exc:  # noqa: BLE001 — tenta o próximo modelo da cadeia
                ultimo_erro = exc
                _log.warning("Claude: modelo %s falhou — tentando próximo: %r", modelo, exc)
        if resp is None:
            if ultimo_erro is not None:
                raise ultimo_erro  # compositor decide: próximo provedor ou preset
            return None
        # Mede o custo real desta chamada (tokens de verdade), atribuído à análise.
        from app.core import uso_llm

        uso_llm.registrar(self.modelo_usado, getattr(resp, "usage", None))
        bruto = next(
            (b.input for b in resp.content if getattr(b, "type", None) == "tool_use"), None
        )
        return bruto if isinstance(bruto, dict) else None


# Sufixo de formato p/ o Gemini (JSON mode): mesma estratégia, sem tool-use (formato difere).
_SUFIXO_JSON_GEMINI = (
    "\n\nResponda APENAS com um objeto JSON (sem markdown, sem comentários) com as chaves: "
    "lote_alvo_m2 (number), densidade ('alta'|'media'|'baixa'), pct_lazer (fração, ex.: 0.20), "
    "amenidades (array de string), arquetipo_viario (string), largura_via_m (number), "
    "pct_institucional (fração; 0 se não souber), esqueleto (array de polilinhas [[x,y],...] "
    "normalizadas 0..1 do bbox; [] em grelha_eficiente), travessia (array [x,y] ou []), "
    "estrategia_mix (array de objetos), heuristicas (objeto), justificativa (string)."
)


def _extrair_json(txt: str) -> Optional[dict]:
    """Extrai o 1º objeto JSON de um texto (tolera cerca ```json ... ``` ou ruído ao redor)."""
    import json

    s = txt.strip()
    if s.startswith("```"):
        s = s.strip("`")
        s = s[4:] if s[:4].lower() == "json" else s
    ini, fim = s.find("{"), s.rfind("}")
    if ini == -1 or fim <= ini:
        return None
    try:
        data = json.loads(s[ini:fim + 1])
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None


def _gemini_thinking(types) -> dict:
    """Config de thinking do Gemini, nível MÉDIO por padrão (pedido do operador). Configurável por
    ``URBANISMO_GEMINI_THINKING`` (``low``/``medium``/``high`` ou um nº de tokens). Robusto à versão
    do SDK: tenta a API por NÍVEL (Gemini 3.x: ``thinking_level``) e cai p/ ORÇAMENTO de tokens
    (Gemini 2.x: ``thinking_budget``); se nenhuma existir, degrada SEM thinking (não quebra)."""
    bruto = os.getenv("URBANISMO_GEMINI_THINKING", "medium").strip().lower()
    if bruto.isdigit():
        try:
            return {"thinking_config": types.ThinkingConfig(thinking_budget=int(bruto))}
        except Exception:  # noqa: BLE001
            return {}
    try:
        return {"thinking_config": types.ThinkingConfig(thinking_level=bruto)}
    except Exception:  # noqa: BLE001 — SDK por tokens: mapeia o nível p/ um orçamento equivalente
        pass
    budget = {"low": 2048, "medium": 8192, "high": 16384}.get(bruto, 8192)
    try:
        return {"thinking_config": types.ThinkingConfig(thinking_budget=budget)}
    except Exception:  # noqa: BLE001
        return {}


class GeradorProgramaGemini:
    """Provedor de FALLBACK Gemini (Google). Import de ``google-genai`` é TARDIO. Usa JSON mode
    (o formato de tool difere do Claude) + thinking nível médio. Modelo configurável por
    ``URBANISMO_GEMINI_MODELO`` (default ``gemini-3.5-flash``) — corrige o ID sem mexer no código."""

    nome = "Gemini"

    def __init__(self, api_key: Optional[str] = None, modelo: Optional[str] = None):
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        self.modelo = modelo or os.getenv("URBANISMO_GEMINI_MODELO", "gemini-3.5-flash")
        self.modelo_usado = self.modelo

    def propor_bruto(self, contexto, tipo_loteamento, publico_alvo) -> Optional[dict]:
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise GeradorIndisponivel("Pacote 'google-genai' ausente.") from exc

        client = genai.Client(api_key=self.api_key)
        prompt = _prompt_usuario(contexto, tipo_loteamento, publico_alvo) + _SUFIXO_JSON_GEMINI
        config = types.GenerateContentConfig(
            system_instruction=_INSTRUCAO,
            response_mime_type="application/json",
            **_gemini_thinking(types),
        )
        resp = client.models.generate_content(model=self.modelo, contents=prompt, config=config)
        txt = (getattr(resp, "text", None) or "").strip()
        if not txt:
            return None
        import json

        try:
            data = json.loads(txt)
        except json.JSONDecodeError:
            data = _extrair_json(txt)  # tolera cerca/ruído
        return data if isinstance(data, dict) else None


class GeradorProgramaEmCadeia:
    """Compositor: tenta os provedores em ORDEM (Claude → Gemini); o 1º que devolver um bruto
    válido vence (fundido pelo preset). TODOS falharem → preset determinístico (degradação
    honesta, nunca quebra o estudo). Nunca propaga exceção p/ o router — sempre devolve Programa."""

    def __init__(self, provedores: list):
        self.provedores = provedores
        self.modelo_usado: Optional[str] = None

    def propor(self, contexto, tipo_loteamento, publico_alvo, overrides=None) -> Programa:
        erros: list[str] = []
        for prov in self.provedores:
            try:
                bruto = prov.propor_bruto(contexto, tipo_loteamento, publico_alvo)
            except Exception as exc:  # noqa: BLE001 — provedor falhou → tenta o próximo
                erros.append(f"{prov.nome}: {type(exc).__name__}: {exc}")
                _log.warning("Programa via %s falhou — tentando próximo provedor: %r",
                             prov.nome, exc, exc_info=True)
                continue
            if isinstance(bruto, dict):
                self.modelo_usado = getattr(prov, "modelo_usado", None) or prov.nome
                return _montar_programa(bruto, publico_alvo, overrides)
            erros.append(f"{prov.nome}: resposta sem JSON/tool_use")
        # Todos os provedores falharam → preset honesto, com o motivo na proveniência.
        detalhe = " | ".join(erros)[:200] if erros else "sem provedor configurado"
        _log.warning("Programa via IA falhou em todos os provedores — caindo no preset: %s", detalhe)
        prog = programa_do_preset(publico_alvo, overrides)
        prog.justificativa = (
            f"Serviço de IA indisponível ({detalhe}) — programa do preset. " + prog.justificativa
        )
        return prog


def get_gerador_programa() -> Optional[GeradorPrograma]:
    """Dependência FastAPI. Monta a CADEIA de provedores conforme as credenciais presentes:
    Claude (``ANTHROPIC_API_KEY``) → Gemini (``GOOGLE_API_KEY``/``GEMINI_API_KEY``). Sem nenhuma
    credencial (ou ``URBANISMO_GERADOR_DESLIGADO``) → ``None`` → router responde 503 honesto.
    Nos testes é sobrescrito por um stub offline (ou ``None`` para exercer o 503)."""
    if os.getenv("URBANISMO_GERADOR_DESLIGADO"):
        return None
    provedores: list = []
    if os.getenv("ANTHROPIC_API_KEY"):
        provedores.append(GeradorProgramaClaude())
    if os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"):
        provedores.append(GeradorProgramaGemini())
    if not provedores:
        return None
    return GeradorProgramaEmCadeia(provedores)
