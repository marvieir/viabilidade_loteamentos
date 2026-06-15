"""Urbanismo (Fase 9) — GERAÇÃO determinística do layout esquemático. NÚCLEO Python puro
(shapely): recebe a área aproveitável (CRS métrico) + o PROGRAMA proposto pela IA e
materializa viário/quadras/LOTES, **recortando tudo contra a área aproveitável** (nada
loteado sobre restrição). A IA não fornece coordenada de lote nem número — só o programa.

Invariantes da fronteira (§3 da spec):
  • A área aproveitável é a TELA: lotes ⊂ aproveitável (recorte geométrico, não aviso).
  • O esqueleto do LLM é SUGESTÃO: validado/regularizado; trecho inviável é IGNORADO e
    registrado — geometria crua do LLM nunca vira verdade.
  • v1 deliberadamente esquemática (grelha axial). Qualidade do traçado evolui por iteração.

Determinístico: mesmo (aproveitável, programa) → mesmo layout.
"""

from __future__ import annotations

from typing import Optional, Sequence

from shapely.geometry import LineString, Polygon, box
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from app.core.urbanismo_medida import Layout
from app.core.urbanismo_programa import Programa


def _maior_poligono(geom: BaseGeometry) -> Optional[Polygon]:
    """Maior componente poligonal (o recorte pode fragmentar a tela)."""
    if geom is None or geom.is_empty:
        return None
    if geom.geom_type == "Polygon":
        return geom
    if geom.geom_type in ("MultiPolygon", "GeometryCollection"):
        polis = [g for g in geom.geoms if g.geom_type == "Polygon" and not g.is_empty]
        return max(polis, key=lambda g: g.area) if polis else None
    return None


def _validar_esqueleto(
    esqueleto: Sequence[Sequence[Sequence[float]]], canvas: Polygon
) -> tuple[list[LineString], list[str]]:
    """Cada polilinha do LLM: vira ``LineString`` e só sobrevive se válida, simples e
    intersecta a tela. Inválida → IGNORADA + motivo (nunca propaga geometria crua)."""
    validas: list[LineString] = []
    ignorados: list[str] = []
    for i, coords in enumerate(esqueleto or []):
        try:
            ls = LineString([(float(x), float(y)) for x, y in coords])
        except Exception:  # noqa: BLE001 — coords malformadas do LLM
            ignorados.append(f"esqueleto[{i}] descartado: coordenadas inválidas")
            continue
        if len(ls.coords) < 2 or not ls.is_valid or not ls.is_simple:
            ignorados.append(f"esqueleto[{i}] descartado: polilinha auto-intersectada/degenerada")
            continue
        rec = ls.intersection(canvas)
        if rec.is_empty or rec.length == 0:
            ignorados.append(f"esqueleto[{i}] descartado: fora da área aproveitável")
            continue
        validas.append(ls)
    return validas, ignorados


def gerar_layout(
    aproveitavel: BaseGeometry,
    programa: Programa,
    restricoes: Optional[BaseGeometry] = None,
) -> Layout:
    """Gera o layout esquemático dentro de ``aproveitavel`` (CRS métrico).

    ``restricoes`` (opcional) é subtraído da tela ANTES de lotear — garante que nenhum lote
    caia sobre APP/≥30%/verde-dura/faixa/servidão (critério 3). ``aproveitavel`` já costuma
    vir sem restrição (o router calcula total − união); ``restricoes`` é a cinta de segurança
    do teste.
    """
    avisos: list[str] = []
    canvas = aproveitavel
    if restricoes is not None and not restricoes.is_empty:
        canvas = canvas.difference(restricoes)
    canvas = _maior_poligono(canvas)
    if canvas is None or canvas.area <= 0:
        return Layout(avisos=["Sem área aproveitável suficiente para um estudo de massa."])

    # Esqueleto do LLM: validado e REGISTRADO (v1 usa grelha axial; o esqueleto é hint).
    centerlines, ignorados = _validar_esqueleto(programa.esqueleto, canvas)

    via = max(programa.largura_via_m, 6.0)
    testada = max(programa.testada_m, 5.0)
    prof = max(programa.profundidade_m, 10.0)

    minx, miny, maxx, maxy = canvas.bounds
    largura = maxx - minx
    altura = maxy - miny

    # 1) Reserva de verde/lazer: faixa no topo, dimensionada por pct_lazer (área-alvo).
    verde = None
    pct_lazer = max(0.0, min(programa.pct_lazer, 0.6))
    if pct_lazer > 0 and altura > prof:
        alvo = canvas.area * pct_lazer
        faixa_h = min(max(alvo / largura, 0.0), altura - prof)
        if faixa_h > 0:
            verde = canvas.intersection(box(minx, maxy - faixa_h, maxx, maxy))
            if verde.is_empty:
                verde = None

    # 2) Institucional (doação): faixa pequena na base (default 0 — só se o programa pedir).
    inst = None
    pct_inst = max(0.0, min(programa.pct_institucional, 0.3))
    if pct_inst > 0 and altura > prof:
        alvo = canvas.area * pct_inst
        faixa_h = min(max(alvo / largura, 0.0), altura - prof)
        if faixa_h > 0:
            inst = canvas.intersection(box(minx, miny, maxx, miny + faixa_h))
            if inst.is_empty:
                inst = None

    reservado = unary_input([g for g in (verde, inst) if g is not None])
    miolo = canvas.difference(reservado) if reservado is not None else canvas

    # 3) Grelha de lotes: fileiras (profundidade) separadas por via; colunas (testada).
    passo_linha = 2 * prof + via  # duas fileiras costas-com-costas + uma via entre blocos
    lotes: list[Polygon] = []
    y = miny
    linha_idx = 0
    while y + prof <= maxy + 1e-6:
        # duas fileiras de lotes por "passo" (frente para vias opostas)
        for desloc in (0.0, prof):
            yb = y + desloc
            if yb + prof > maxy + 1e-6:
                continue
            x = minx
            while x + testada <= maxx + 1e-6:
                cel = box(x, yb, x + testada, yb + prof)
                lote = cel.intersection(miolo)
                # mantém só lote "cheio" (≥ 60% do alvo) e poligonal
                if lote.geom_type == "Polygon" and lote.area >= 0.6 * testada * prof:
                    lotes.append(lote)
                x += testada
        y += passo_linha
        linha_idx += 1
        if linha_idx > 5000:  # guarda determinística contra laço patológico
            break

    miolo_lotes = unary_union(lotes) if lotes else None
    # 4) Arruamento = o que sobra da tela depois de lotes + reservas.
    sobra = canvas
    for g in (miolo_lotes, verde, inst):
        if g is not None and not g.is_empty:
            sobra = sobra.difference(g)
    arruamento = sobra if (sobra is not None and not sobra.is_empty) else None

    if not lotes:
        avisos.append(
            "A grelha esquemática não acomodou lotes na área aproveitável "
            "(gleba pequena/irregular para o lote-alvo)."
        )

    return Layout(
        lotes=lotes,
        arruamento=arruamento,
        areas_verdes=verde,
        sistema_lazer=None,
        institucional=inst,
        centerlines=[c.intersection(canvas) for c in centerlines],
        via_largura_m=via,
        ignorados=ignorados,
        avisos=avisos,
    )


def unary_input(geoms: list[BaseGeometry]) -> Optional[BaseGeometry]:
    """União ou None (evita ``unary_union([])`` devolver GEOMETRYCOLLECTION vazio)."""
    geoms = [g for g in geoms if g is not None and not g.is_empty]
    if not geoms:
        return None
    return unary_union(geoms)
