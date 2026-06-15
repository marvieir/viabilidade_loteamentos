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


def _componentes(geom: BaseGeometry) -> list[Polygon]:
    """TODOS os polígonos buildáveis (a restrição pode partir a tela em várias ilhas — cada
    ilha viável é loteada; NÃO descartamos as menores, só o que é sliver/sem área)."""
    if geom is None or geom.is_empty:
        return []
    if geom.geom_type == "Polygon":
        return [geom]
    if geom.geom_type in ("MultiPolygon", "GeometryCollection"):
        return [g for g in geom.geoms if g.geom_type == "Polygon" and not g.is_empty]
    return []


def _lotear_componente(
    comp: Polygon, via: float, testada: float, prof: float, pct_lazer: float, pct_inst: float
):
    """Loteia UMA ilha contígua: reserva verde/institucional + grelha axial. Devolve
    ``(lotes, verde, inst)`` em CRS métrico (o arruamento é a sobra, calculada no chamador)."""
    minx, miny, maxx, maxy = comp.bounds
    largura = maxx - minx
    altura = maxy - miny
    if largura <= 0 or altura < prof:
        return [], None, None  # sliver: nem uma fileira cabe

    # 1) Verde/lazer: faixa no topo, dimensionada por pct_lazer (área-alvo da ilha).
    verde = None
    if pct_lazer > 0 and altura > prof:
        faixa_h = min(max(comp.area * pct_lazer / largura, 0.0), altura - prof)
        if faixa_h > 0:
            v = comp.intersection(box(minx, maxy - faixa_h, maxx, maxy))
            verde = v if not v.is_empty else None

    # 2) Institucional (doação): faixa na base (default 0 — só se o programa pedir).
    inst = None
    if pct_inst > 0 and altura > prof:
        faixa_h = min(max(comp.area * pct_inst / largura, 0.0), altura - prof)
        if faixa_h > 0:
            i = comp.intersection(box(minx, miny, maxx, miny + faixa_h))
            inst = i if not i.is_empty else None

    reservado = unary_input([g for g in (verde, inst) if g is not None])
    miolo = comp.difference(reservado) if reservado is not None else comp

    # 3) Grelha de lotes: fileiras (profundidade) separadas por via; colunas (testada).
    passo_linha = 2 * prof + via
    lotes: list[Polygon] = []
    y = miny
    guarda = 0
    while y + prof <= maxy + 1e-6:
        for desloc in (0.0, prof):
            yb = y + desloc
            if yb + prof > maxy + 1e-6:
                continue
            x = minx
            while x + testada <= maxx + 1e-6:
                lote = box(x, yb, x + testada, yb + prof).intersection(miolo)
                if lote.geom_type == "Polygon" and lote.area >= 0.6 * testada * prof:
                    lotes.append(lote)
                x += testada
        y += passo_linha
        guarda += 1
        if guarda > 5000:  # guarda determinística contra laço patológico
            break
    return lotes, verde, inst


def gerar_layout(
    aproveitavel: BaseGeometry,
    programa: Programa,
    restricoes: Optional[BaseGeometry] = None,
) -> Layout:
    """Gera o layout esquemático dentro de ``aproveitavel`` (CRS métrico).

    ``restricoes`` (opcional) é subtraído da tela ANTES de lotear — garante que nenhum lote
    caia sobre APP/≥30%/verde-dura/faixa/servidão (critério 3). ``aproveitavel`` já costuma
    vir sem restrição (o router calcula total − união); ``restricoes`` é a cinta de segurança
    do teste. **Loteia TODAS as ilhas buildáveis** (a restrição pode partir a gleba em duas;
    versões anteriores perdiam a menor — fix do "metade do terreno vazio").
    """
    avisos: list[str] = []
    canvas = aproveitavel
    if restricoes is not None and not restricoes.is_empty:
        canvas = canvas.difference(restricoes)
    comps = _componentes(canvas)
    if not comps:
        return Layout(avisos=["Sem área aproveitável suficiente para um estudo de massa."])

    # Esqueleto do LLM: validado e REGISTRADO contra a tela inteira (v1 usa grelha axial).
    tela = unary_union(comps)
    centerlines, ignorados = _validar_esqueleto(programa.esqueleto, tela)

    via = max(programa.largura_via_m, 6.0)
    testada = max(programa.testada_m, 5.0)
    prof = max(programa.profundidade_m, 10.0)
    pct_lazer = max(0.0, min(programa.pct_lazer, 0.6))
    pct_inst = max(0.0, min(programa.pct_institucional, 0.3))

    lotes: list[Polygon] = []
    verdes: list[BaseGeometry] = []
    insts: list[BaseGeometry] = []
    usados: list[BaseGeometry] = []  # ilhas que de fato receberam loteamento (p/ arruamento)
    for comp in sorted(comps, key=lambda g: g.area, reverse=True):
        lotes_c, verde_c, inst_c = _lotear_componente(
            comp, via, testada, prof, pct_lazer, pct_inst
        )
        if not lotes_c:
            continue  # ilha pequena demais p/ o lote-alvo → terra não-parcelada (não vira via)
        lotes.extend(lotes_c)
        if verde_c is not None:
            verdes.append(verde_c)
        if inst_c is not None:
            insts.append(inst_c)
        usados.append(comp)

    verde = unary_input(verdes)
    inst = unary_input(insts)

    # Arruamento = (ilhas loteadas) − lotes − reservas. Ilhas não-parceladas NÃO entram.
    arruamento = None
    if usados:
        sobra = unary_union(usados)
        for g in (unary_input(lotes), verde, inst):
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
        centerlines=[c.intersection(tela) for c in centerlines],
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
