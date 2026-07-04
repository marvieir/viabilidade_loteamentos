"""Movimento 2 — PERFIL DE ESTILO do urbanismo (a "skill" do operador, sem treinar modelo).

Um conjunto de REGRAS por padrão (baixa/media/alta) que o gerador e o motor SEMPRE leem:
- ``prompt_regras``: texto que entra em toda proposta como seção de estilo (orienta o
  PROGRAMA da IA — amenidades, arquétipo, caráter);
- knobs DETERMINÍSTICOS do motor (praças por quadras, fração do lazer para praças,
  prioridade/dimensão do lago, fração livre do hub).

Defaults embarcados (versionados no git — auditáveis) reproduzem o comportamento atual;
o operador pode SOBRESCREVER por arquivo ``{ESTILO_URBANISMO_DIR}/{perfil}.json`` montado
em volume (edita sem rebuild). Arquivo inválido/ausente → default + aviso, nunca derruba.
Nenhum número de MEDIDA vem daqui (§2) — só estratégia e parâmetros de composição.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

# Defaults por perfil — espelham as regras U2/U3/Mov.1 já testadas (mudar aqui é mudar a
# política de composição; os valores-ouro dos testes usam estes defaults).
ESTILO_DEFAULT: dict[str, dict] = {
    "baixa": {
        "prompt_regras": (
            "Estilo do padrão ECONÔMICO: eficiência e essencial bem posicionado — grelha "
            "eficiente, praça/playground/campo acessíveis, comércio local junto à entrada."
        ),
        "pracas_por_quadras": 0,      # praças só por cobertura de 400 m
        "lazer_pracas_frac": 0.35,    # teto do orçamento de lazer que pode virar praça
        "lago_prioritario": False,    # lotes têm prioridade sobre o lago
        "lago_frac_aproveitavel": 0.03,
        "lago_max_m2": 12000.0,
        "hub_fracao_livre": 0.25,
    },
    "media": {
        "prompt_regras": (
            "Estilo do padrão MÉDIO: equilíbrio yield×qualidade — clube compacto (piscina/"
            "quadra/salão), praças de bolso, arborização viária, entrada cuidada."
        ),
        "pracas_por_quadras": 0,
        "lazer_pracas_frac": 0.35,
        "lago_prioritario": False,
        "lago_frac_aproveitavel": 0.03,
        "lago_max_m2": 12000.0,
        "hub_fracao_livre": 0.25,
    },
    "alta": {
        "prompt_regras": (
            "Estilo do padrão ALTO (referência master plans tipo Riviera/Fazenda Boa Vista): "
            "lazer ESPALHADO em estações pequenas (quiosque, redário, mirante, horta, play "
            "aventura) além do clube âncora; lago como elemento estruturador; traçado sinuoso "
            "com vistas terminadas; verde conectando os setores; entrada com parkway."
        ),
        "pracas_por_quadras": 10,     # 1 praça a cada ~10 quadras MESMO com cobertura ok
        "lazer_pracas_frac": 0.35,
        "lago_prioritario": True,     # lago sacrifica lotes (o prêmio do anel paga)
        "lago_frac_aproveitavel": 0.03,
        "lago_max_m2": 12000.0,
        "hub_fracao_livre": 0.25,
        # Fase U6a — o arquétipo paisagístico VOLTOU AO LABORATÓRIO (feedback do operador:
        # desenho pior que o clássico — buracos no miolo, vias angulosas). O ALTO usa o
        # traçado CLÁSSICO sinuoso até o paisagem passar na revisão VISUAL (harness de
        # render); para experimentar: "arquetipo": "loops_paisagem" no alta.json.
        "arquetipo": "",
        # Traçado do alto padrão (aprovado pelo operador). Valores:
        #   "contorno_serpente" (Opção B, DEFAULT): via-tronco seguindo a CURVA DE NÍVEL do DEM
        #     (vias acompanham a declividade) + limpezas da A. Sem DEM → degrada p/ a grade limpa.
        #   "grelha_ortogonal" (Opção A): grade axial pura, sem espinha curva.
        #   "" : sinuoso da IA (traçado clássico antigo).
        # Todas partilham: bordas raster suavizadas, malha SEMPRE conectada, piso de verde.
        "tracado": "contorno_serpente",
        "cinturao_verde_m": 8.0,
        "paisagem_area_min_m2": 80000.0,
        "verde_min_pct": 0.20,  # piso LEGAL de doação verde (o operador pediu ≥20%)
    },
}

_CHAVES_NUM = ("pracas_por_quadras", "lazer_pracas_frac", "lago_frac_aproveitavel",
               "lago_max_m2", "hub_fracao_livre", "cinturao_verde_m",
               "paisagem_area_min_m2", "verde_min_pct")


def carregar_estilo(publico_alvo: str) -> tuple[dict, Optional[str]]:
    """Estilo do perfil: default embarcado + override do operador (se houver). Devolve
    ``(estilo, aviso)`` — aviso ≠ None quando um override foi ignorado por inválido.
    Determinístico: mesmo arquivo → mesmo estilo."""
    base = dict(ESTILO_DEFAULT.get(publico_alvo, ESTILO_DEFAULT["media"]))
    diretorio = os.getenv("ESTILO_URBANISMO_DIR", "").strip()
    if not diretorio:
        return base, None
    caminho = Path(diretorio) / f"{publico_alvo}.json"
    if not caminho.exists():
        return base, None
    try:
        bruto = json.loads(caminho.read_text(encoding="utf-8"))
        if not isinstance(bruto, dict):
            raise ValueError("estilo deve ser um objeto JSON")
    except (OSError, ValueError) as exc:
        return base, (
            f"Perfil de estilo '{caminho.name}' ignorado (inválido: {exc}) — usando o "
            "default embarcado."
        )
    # merge raso, com sanidade nos numéricos (valor não-numérico → default daquele knob)
    for chave, valor in bruto.items():
        if chave in _CHAVES_NUM:
            try:
                base[chave] = float(valor)
            except (TypeError, ValueError):
                continue
        elif chave == "lago_prioritario":
            base[chave] = bool(valor)
        elif chave == "arquetipo" and isinstance(valor, str) and valor.strip():
            base[chave] = valor.strip()  # "loops_paisagem" liga a U6a; outro valor desliga
        elif chave == "tracado" and isinstance(valor, str):
            base[chave] = valor.strip()  # "grelha_ortogonal" liga a Opção A; "" volta ao sinuoso
        elif chave == "prompt_regras" and isinstance(valor, str) and valor.strip():
            base[chave] = valor.strip()[:2000]
    return base, None
