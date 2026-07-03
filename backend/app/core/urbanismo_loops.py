"""Fase U6a — traçador de COMPOSIÇÃO PAISAGÍSTICA (spec ``fase-U6-pods.md``).

Gera os EIXOS viários no lugar da grade axial quando o arquétipo do estilo é
``loops_paisagem``: a paisagem estrutura, os lotes preenchem. Dois modos, escolhidos
pela FORMA da ilha (determinístico):

- **anéis** (gleba compacta): fitas concêntricas em volta da ARMADURA (lago/verde
  central) + radiais de costura — padrão Lagoon/Lake Side/Verano;
- **folha** (gleba alongada, elongação ≥ ``ELONGACAO_FOLHA``): espinha no eixo longo +
  nervuras diagonais arqueadas morrendo em cul-de-sac — padrão Ribeira/SMA.

Devolve eixos ``(LineString, largura)`` prontos para o ``construir_malha`` existente:
faces, poda, bulbos, subdivisão, praças, hub e score REUSAM o pipeline testado. Python
puro, sem rede, sem LLM; mesma entrada → mesmos eixos (§ determinismo).
"""

from __future__ import annotations

import math
from typing import Optional, Sequence

from shapely.geometry import LineString, Point
from shapely.geometry.base import BaseGeometry
from shapely.ops import nearest_points, unary_union

# Elongação (lado maior / lado menor do MRR) a partir da qual a ilha é "alongada" → folha.
ELONGACAO_FOLHA = 2.2
# Ângulo das nervuras em relação à espinha (padrão folha das referências: diagonais ~65°).
ANGULO_NERVURA_GRAUS = 65.0


def _mrr_eixos(reg: BaseGeometry):
    """(centro, dir_longo, dir_curto, comp_longo, comp_curto) do retângulo mínimo rotado."""
    mrr = reg.minimum_rotated_rectangle
    pts = list(mrr.exterior.coords)[:-1]
    e1 = (pts[1][0] - pts[0][0], pts[1][1] - pts[0][1])
    e2 = (pts[2][0] - pts[1][0], pts[2][1] - pts[1][1])
    l1, l2 = math.hypot(*e1), math.hypot(*e2)
    if l1 >= l2:
        longo, comp_l, curto, comp_c = e1, l1, e2, l2
    else:
        longo, comp_l, curto, comp_c = e2, l2, e1, l1
    ul = (longo[0] / comp_l, longo[1] / comp_l)
    uc = (curto[0] / comp_c, curto[1] / comp_c)
    c = mrr.centroid
    return (c.x, c.y), ul, uc, comp_l, comp_c


def _linhas_de(geom) -> list[LineString]:
    """Extrai LineStrings de uma interseção (LineString/MultiLineString/coleção)."""
    if geom is None or geom.is_empty:
        return []
    if isinstance(geom, LineString):
        return [geom]
    partes = getattr(geom, "geoms", None)
    if partes is None:
        return []
    out: list[LineString] = []
    for g in partes:
        if isinstance(g, LineString) and not g.is_empty:
            out.append(g)
        else:
            out.extend(_linhas_de(g))
    return out


def _aneis(reg, nucleo, passo_anel: float, via_local: float, via_tronco: float,
           entrada: Optional[Point]) -> list[tuple[LineString, float]]:
    """Fitas concêntricas em volta do ``nucleo`` + 2 radiais de costura (conectividade)."""
    eixos: list[tuple[LineString, float]] = []
    interior = reg.buffer(-via_local / 2.0)
    if interior.is_empty:
        return eixos
    diag = math.hypot(*(reg.bounds[2] - reg.bounds[0], reg.bounds[3] - reg.bounds[1]))
    d = max(via_tronco, passo_anel * 0.5)
    while d < diag:
        anel = nucleo.buffer(d, quad_segs=8)
        if anel.contains(reg):
            break
        borda = anel.exterior if hasattr(anel, "exterior") else anel.boundary
        for linha in _linhas_de(borda.intersection(interior)):
            if linha.length >= passo_anel * 1.5:  # pedaço curto demais não vira via
                eixos.append((linha, via_local))
        d += passo_anel
    # RADIAIS de costura: do núcleo para fora, na direção da entrada e na oposta —
    # sem elas os anéis ficam concêntricos e DESCONEXOS (a poda derrubaria tudo).
    cen = nucleo.centroid
    if entrada is not None and not entrada.is_empty:
        alvo = entrada if isinstance(entrada, Point) else entrada.representative_point()
    else:
        alvo = Point(cen.x, reg.bounds[1])  # base da ilha (mesmo fallback do pórtico)
    ang = math.atan2(alvo.y - cen.y, alvo.x - cen.x)
    for a in (ang, ang + math.pi):
        raio = LineString([
            (cen.x, cen.y),
            (cen.x + diag * math.cos(a), cen.y + diag * math.sin(a)),
        ])
        for linha in _linhas_de(raio.intersection(interior)):
            if linha.length >= passo_anel * 0.75:
                eixos.append((linha, via_tronco))
    return eixos


def _folha(reg, passo_anel: float, via_local: float, via_tronco: float
           ) -> list[tuple[LineString, float]]:
    """Espinha no eixo longo + nervuras diagonais ARQUEADAS (3 pontos) dos dois lados."""
    (cx, cy), ul, uc, comp_l, _comp_c = _mrr_eixos(reg)
    interior = reg.buffer(-via_local / 2.0)
    if interior.is_empty:
        return []
    eixos: list[tuple[LineString, float]] = []
    meia = comp_l / 2.0
    espinha_full = LineString([
        (cx - ul[0] * meia, cy - ul[1] * meia),
        (cx + ul[0] * meia, cy + ul[1] * meia),
    ])
    espinha_partes = _linhas_de(espinha_full.intersection(interior))
    for linha in espinha_partes:
        eixos.append((linha, via_tronco))
    espinha = max(espinha_partes, key=lambda g: g.length, default=None)
    if espinha is None:
        return eixos
    # nervuras: a cada passo ao longo da espinha, uma diagonal arqueada para CADA lado
    # (ângulo ~65°, arco leve — padrão "folha" das referências), morrendo dentro da ilha
    # (a ponta vira cul-de-sac de bulbo na Fase 9.14).
    ang_esp = math.atan2(ul[1], ul[0])
    rad = math.radians(ANGULO_NERVURA_GRAUS)
    diag = math.hypot(*(reg.bounds[2] - reg.bounds[0], reg.bounds[3] - reg.bounds[1]))
    n = max(int(espinha.length // passo_anel), 1)
    for i in range(1, n + 1):
        base = espinha.interpolate(min(i * passo_anel, espinha.length - 1.0))
        for lado in (1.0, -1.0):
            a = ang_esp + lado * rad
            fim = (base.x + diag * math.cos(a), base.y + diag * math.sin(a))
            # arco leve: ponto médio deslocado na direção da espinha (curva "de folha")
            meio = (
                (base.x + fim[0]) / 2.0 + ul[0] * passo_anel * 0.35,
                (base.y + fim[1]) / 2.0 + ul[1] * passo_anel * 0.35,
            )
            nervura = LineString([(base.x, base.y), meio, fim])
            for linha in _linhas_de(nervura.intersection(interior)):
                if linha.length >= passo_anel:
                    eixos.append((linha, via_local))
    return eixos


def eixos_paisagem(
    reg: BaseGeometry,
    armadura: Optional[BaseGeometry],
    entrada: Optional[Point],
    passo_anel: float,
    via_local: float,
    via_tronco: float,
) -> tuple[list[tuple[LineString, float]], str]:
    """Eixos do arquétipo ``loops_paisagem`` para UMA ilha. ``passo_anel`` = profundidade
    da fita dupla (2×prof do lote + via). Devolve ``(eixos, modo)``; eixos vazios → o
    chamador degrada para a grade axial (nunca quebra a geração)."""
    _c, _ul, _uc, comp_l, comp_c = _mrr_eixos(reg)
    elong = comp_l / max(comp_c, 1.0)
    if elong >= ELONGACAO_FOLHA:
        eixos = _folha(reg, passo_anel, via_local, via_tronco)
        return eixos, "folha"
    # núcleo dos anéis = maior célula da ARMADURA dentro da ilha; sem armadura → disco
    # central (o "coração" verde que os anéis abraçam — Verano).
    nucleo = None
    if armadura is not None and not armadura.is_empty:
        inter = armadura.intersection(reg)
        if not inter.is_empty:
            celulas = list(getattr(inter, "geoms", [inter]))
            poligonos = [g for g in celulas if g.area > passo_anel ** 2]
            if poligonos:
                nucleo = max(poligonos, key=lambda g: g.area)
    if nucleo is None:
        nucleo = reg.centroid.buffer(passo_anel * 0.8, quad_segs=8)
    eixos = _aneis(reg, nucleo, passo_anel, via_local, via_tronco, entrada)
    return eixos, "aneis"


def cinturao_perimetral(aprov: BaseGeometry, largura: float):
    """Fase U6a P1 — cinturão VERDE na divisa: devolve ``(canvas_util, cinturao)``. O
    cinturão emoldura o empreendimento (nenhum lote na borda — todas as referências);
    entra na doação como verde reservado. Gleba pequena demais → sem cinturão (honesto)."""
    if largura <= 0:
        return aprov, None
    canvas = aprov.buffer(-largura)
    if canvas.is_empty or canvas.area < aprov.area * 0.35:
        return aprov, None  # cinturão comeria a gleba → degrada (sem moldura)
    cinturao = aprov.difference(canvas)
    if cinturao.is_empty:
        return aprov, None
    return canvas, cinturao


def armadura_de(restricao: Optional[BaseGeometry], agua: Optional[BaseGeometry],
                minimo_m2: float = 2000.0) -> Optional[BaseGeometry]:
    """Células de ARMADURA (verde preservado + lago) que os anéis abraçam — SR-SP mostra
    múltiplas células. Só células relevantes (≥ ``minimo_m2``)."""
    partes = []
    for g in (restricao, agua):
        if g is None or g.is_empty:
            continue
        for c in getattr(g, "geoms", [g]):
            if c.area >= minimo_m2:
                partes.append(c)
    return unary_union(partes) if partes else None
