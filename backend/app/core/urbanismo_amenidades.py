"""Fase U2 — BIBLIOTECA de amenidades + programa interno do hub de lazer.

A IA propõe ``amenidades`` como STRINGS (estratégia); este módulo as MATERIALIZA (§2):
mapeia cada string para uma amenidade PARAMÉTRICA da biblioteca e fatia o clube/hub em
sub-parcelas rotuladas, por prioridade do perfil. Nenhum número vem do LLM — as dimensões
são da biblioteca (típicas de mercado, verificar com urbanista) e as áreas finais são
MEDIDAS da geometria fatiada. Python puro, determinístico, sem rede.

O que não cabe no hub é reportado em ``nao_coube`` (degradação honesta); o que a biblioteca
não materializa nesta fase (lago → U3; trilhas → perímetro) vai para ``fora_do_hub``.
"""

from __future__ import annotations

import math
import unicodedata
from dataclasses import dataclass
from typing import Optional, Sequence

from shapely.affinity import rotate
from shapely.geometry import box
from shapely.geometry.base import BaseGeometry

# Fração mínima do hub que fica LIVRE (jardins/circulação/estar) — o hub não vira só laje.
HUB_FRACAO_LIVRE_MIN = 0.25


@dataclass(frozen=True)
class Amenidade:
    chave: str
    rotulo: str
    area_m2: float  # área-alvo da sub-parcela (dimensão típica de mercado + entorno)
    prioridade: int  # menor = entra primeiro no hub
    perfis: tuple[str, ...]  # em que públicos entra por DEFAULT (sem proposta da IA)
    sinonimos: tuple[str, ...]


# Dimensões típicas de mercado (quadra poliesportiva 28×15 m + entorno; tênis 36,6×18,3 m;
# piscina adulto+infantil com deck…). São PARÂMETROS de triagem, não projeto — o projeto
# de arquitetura dimensiona de verdade (§1-A).
BIBLIOTECA: tuple[Amenidade, ...] = (
    Amenidade("playground", "Playground", 250.0, 1, ("baixa", "media", "alta"),
              ("playground", "brinquedo", "infantil", "kids")),
    Amenidade("salao_festas", "Salão de festas / gourmet", 400.0, 2, ("baixa", "media", "alta"),
              ("salao", "festas", "gourmet", "churrasqueira", "eventos")),
    Amenidade("quadra_poliesportiva", "Quadra poliesportiva", 700.0, 3, ("baixa", "media", "alta"),
              ("quadra", "poliesportiva", "esporte", "futebol", "society", "basquete", "volei")),
    Amenidade("piscina", "Piscina (adulto + infantil)", 600.0, 4, ("media", "alta"),
              ("piscina", "aquatico", "aquático")),
    Amenidade("academia", "Academia / fitness", 300.0, 5, ("media", "alta"),
              ("academia", "fitness", "gym", "crossfit")),
    Amenidade("sede_clube", "Sede social do clube", 500.0, 6, ("alta",),
              ("clube", "sede", "social", "lounge", "coworking")),
    Amenidade("tenis", "Quadra de tênis / beach", 700.0, 7, ("alta",),
              ("quadra de tenis", "tenis", "tênis", "beach tennis", "padel")),
    Amenidade("pet_place", "Pet place", 200.0, 8, ("media", "alta"),
              ("pet",)),
    # Movimento 1 — amenidades "de bolso" (padrão dos master plans de referência: lazer
    # ESPALHADO em pequenas estações, não só no clube).
    Amenidade("quiosque", "Quiosque / apoio", 150.0, 9, ("baixa", "media", "alta"),
              ("quiosque", "apoio")),
    Amenidade("redario", "Redário / estar zen", 120.0, 10, ("media", "alta"),
              ("redario", "redário", "estar zen", "zen", "descanso", "rede")),
    Amenidade("horta_pomar", "Horta / pomar comunitário", 300.0, 11, ("media", "alta"),
              ("horta", "pomar", "agrihood", "comunitaria", "comunitária")),
    Amenidade("play_aventura", "Play aventura", 250.0, 12, ("alta",),
              ("play aventura", "aventura", "arvorismo")),
    Amenidade("mirante_estar", "Mirante / estar contemplativo", 200.0, 13, ("alta",),
              ("mirante", "contemplativo", "deck", "vista")),
)

# Movimento 1 — programa SUGERIDO (esquemático) para as praças de bolso, ciclado por
# perfil. Rotula o lazer espalhado no mapa; a posição fina é do projeto executivo (§1-A).
SUGESTOES_PRACA: dict[str, tuple[str, ...]] = {
    "baixa": ("playground", "campo / estar"),
    "media": ("playground", "quiosque", "estar / redário"),
    "alta": ("playground", "quiosque + redário", "estar zen", "horta / pomar",
             "play aventura", "mirante / estar"),
}

# Amenidades que a IA costuma propor mas NÃO viram sub-parcela do hub nesta fase — rotuladas
# com o destino honesto (nunca somem em silêncio).
FORA_DO_HUB: dict[str, str] = {
    "lago": "lago/espelho d'água — Fase U3 (síntese no ponto baixo do DEM)",
    "lagoa": "lago/espelho d'água — Fase U3 (síntese no ponto baixo do DEM)",
    "espelho": "lago/espelho d'água — Fase U3 (síntese no ponto baixo do DEM)",
    "trilha": "trilha/pista de caminhada — linear (perímetro do verde), não sub-parcela do hub",
    "caminhada": "trilha/pista de caminhada — linear (perímetro do verde), não sub-parcela do hub",
    "ciclovia": "ciclovia — linear (faixa viária), não sub-parcela do hub",
    "golfe": "golfe — âncora de grande porte fora do escopo do estudo de massa",
    "equestre": "centro equestre — âncora de grande porte fora do escopo do estudo de massa",
    "paisagismo": "paisagismo — difuso (área livre do hub e canteiros), não sub-parcela",
    "arborizacao": "arborização — difusa (faixa de serviço viária), não sub-parcela",
    "praca": "praças — materializadas como praças de BOLSO distribuídas (não no hub)",
    "praça": "praças — materializadas como praças de BOLSO distribuídas (não no hub)",
}


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def mapear_amenidades(
    propostas: Sequence[str], publico_alvo: str
) -> tuple[list[Amenidade], list[str], list[str]]:
    """Strings da IA → amenidades da biblioteca. Devolve ``(selecionadas, fora_do_hub,
    sem_correspondencia)``. Sem proposta aproveitável → defaults do perfil (nunca hub vazio).
    Determinístico: dedup por chave, ordem por prioridade."""
    selecionadas: dict[str, Amenidade] = {}
    fora: list[str] = []
    sem: list[str] = []
    for prop in propostas or []:
        p = _norm(str(prop))
        if not p.strip():
            continue
        # O sinônimo MAIS LONGO vence ("quadra de tênis" → tênis, não "quadra" poliesportiva).
        hit = None
        hit_len = 0
        for a in BIBLIOTECA:
            for s in a.sinonimos:
                ns = _norm(s)
                if ns in p and len(ns) > hit_len:
                    hit, hit_len = a, len(ns)
        if hit is not None:
            selecionadas.setdefault(hit.chave, hit)
            continue
        destino = next((rot for chave, rot in FORA_DO_HUB.items() if _norm(chave) in p), None)
        if destino is not None:
            fora.append(f"“{prop}” → {destino}")
        else:
            sem.append(str(prop))
    if not selecionadas:
        for a in BIBLIOTECA:
            if publico_alvo in a.perfis:
                selecionadas[a.chave] = a
    ordem = sorted(selecionadas.values(), key=lambda a: a.prioridade)
    return ordem, fora, sem


def _frame_axial(hub: BaseGeometry):
    """Gira o hub para o frame AXIAL do seu retângulo mínimo (fatias verticais viram fatias
    reais da figura). Devolve ``(hub_axial, ang_deg, origem)`` p/ desfazer com ``rotate``."""
    try:
        mrr = hub.minimum_rotated_rectangle
        pts = list(mrr.exterior.coords)[:-1]
        e1 = (pts[1][0] - pts[0][0], pts[1][1] - pts[0][1])
        e2 = (pts[2][0] - pts[1][0], pts[2][1] - pts[1][1])
        dx, dy = e1 if math.hypot(*e1) >= math.hypot(*e2) else e2
        ang = math.degrees(math.atan2(dy, dx))
    except Exception:  # noqa: BLE001 — geometria degenerada → sem rotação
        return hub, 0.0, hub.centroid
    origem = hub.centroid
    return rotate(hub, -ang, origin=origem), ang, origem


def programa_hub(
    hub: Optional[BaseGeometry], publico_alvo: str, propostas: Sequence[str],
    fracao_livre: Optional[float] = None,
) -> tuple[list[dict], dict]:
    """Fatia o hub em SUB-PARCELAS rotuladas (uma por amenidade selecionada), varrendo o eixo
    longo do hub por prioridade e preservando ≥``HUB_FRACAO_LIVRE_MIN`` de área livre.
    Devolve ``(features, diag)``: features = [{chave, rotulo, area_m2, geom}] (frame de
    entrada); diag = programa medido + nao_coube/fora_do_hub/sem_correspondencia."""
    if hub is None or hub.is_empty or hub.area <= 1.0:
        return [], {}
    ordem, fora, sem = mapear_amenidades(propostas, publico_alvo)
    axial, ang, origem = _frame_axial(hub)
    minx, miny, maxx, maxy = axial.bounds
    altura = max(maxy - miny, 1e-6)
    # Mov.2 — a fração livre pode vir do perfil de estilo (default embarcado).
    livre_min = HUB_FRACAO_LIVRE_MIN if fracao_livre is None else max(0.0, min(fracao_livre, 0.9))
    orcamento = hub.area * (1.0 - livre_min)

    features: list[dict] = []
    nao_coube: list[str] = []
    cursor = minx
    usado = 0.0
    for a in ordem:
        if usado + a.area_m2 > orcamento + 1e-6:
            nao_coube.append(a.rotulo)
            continue
        largura = a.area_m2 / altura
        fatia = axial.intersection(box(cursor, miny, cursor + largura, maxy))
        # fatia irregular (borda do hub) rende menos que o alvo → alarga até ~1,6× p/ compensar,
        # sem varrer além do hub. Se ainda ficou <60% do alvo, a amenidade não coube ALI.
        tent = 1
        while fatia.area < a.area_m2 * 0.95 and tent < 4 and cursor + largura < maxx:
            largura *= 1.2
            fatia = axial.intersection(box(cursor, miny, cursor + largura, maxy))
            tent += 1
        if fatia.is_empty or fatia.area < a.area_m2 * 0.6:
            nao_coube.append(a.rotulo)
            continue
        cursor += largura
        usado += fatia.area
        geom = rotate(fatia, ang, origin=origem) if ang else fatia
        features.append({
            "chave": a.chave, "rotulo": a.rotulo, "tipo": "hub",
            "area_m2": round(fatia.area, 2), "geom": geom,
        })

    livre = max(hub.area - usado, 0.0)
    from app.core.urbanismo_medida import _fmt  # pt-BR — o front não reformata (§2)

    diag = {
        "programa_hub": [
            {"rotulo": f["rotulo"], "area_m2": f["area_m2"], "area_fmt": _fmt(f["area_m2"], 0)}
            for f in features
        ],
        "hub_area_m2": round(hub.area, 2),
        "hub_area_livre_m2": round(livre, 2),
        "nao_coube": nao_coube,
        "amenidades_fora_do_hub": fora,
        "amenidades_sem_correspondencia": sem,
        "proveniencia_programa": (
            "Sub-parcelas fatiadas pelo motor com dimensões típicas de mercado (biblioteca "
            "paramétrica U2); a IA propôs a LISTA, não os números. Programa esquemático — "
            "o projeto de arquitetura dimensiona de verdade (§1-A)."
        ),
    }
    return features, diag
