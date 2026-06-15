"""Urbanismo (Fase 9.1) — GERAÇÃO determinística com FIDELIDADE ao programa. NÚCLEO Python
puro (shapely): a IA propõe **programa + esqueleto** (intenção); o Python materializa toda a
geometria e mede. Sobe a fidelidade da v1 em três frentes, SEM mover a fronteira do §2:

  (a) MATERIALIZA o programa de áreas — reserva lazer (clube central + verde) e institucional
      ANTES de lotear, com a área medida CONVERGINDO para o programa (área reservada exata por
      busca binária de raio) ou DEGRADANDO rotulado quando a gleba não comporta.
  (b) VIÁRIO por arquétipo — consome o esqueleto da IA (coords normalizadas 0..1 → bbox da
      gleba; snap/clip/valida) como eixos-base; trecho inviável é descartado e contado.
  (c) TOPOGRAFIA — orienta a grelha de quarteirões por um ângulo derivado da declividade
      (DEM 2.5), calculado pelo chamador. Orientação geométrica (acompanhar curva de nível),
      NÃO terraplenagem.

A régua do §3 da spec: snap/buffer/offset/recorte/rotação/reservar/medir = OK; inventar
traçado, otimizar, dimensionar greide = projeto (do urbanista), fora. Determinístico.
"""

from __future__ import annotations

import math
from typing import Optional, Sequence

from shapely.affinity import rotate
from shapely.geometry import LineString, Point, Polygon, box
from shapely.geometry.base import BaseGeometry
from shapely.ops import nearest_points, unary_union

from app.core.urbanismo_medida import Layout
from app.core.urbanismo_programa import Programa

# Convergência: |medido − alvo| ≤ tol → "atendido" (spec §4.1).
TOL_CONVERGENCIA_PP = 0.03
# Degradação: reserva lazer só até sobrar área para ~este nº de lotes (preserva o parcelamento).
MIN_LOTES_RESERVA = 8
# Fração da reserva de lazer destinada ao clube central (resto = áreas verdes ao redor).
LAZER_CLUBE_FRAC = 0.40
ARQUETIPO_GRELHA = "grelha_eficiente"


# ============================ componentes / grelha ============================
def _componentes(geom: BaseGeometry) -> list[Polygon]:
    """TODOS os polígonos buildáveis (a restrição pode partir a tela em várias ilhas)."""
    if geom is None or geom.is_empty:
        return []
    if geom.geom_type == "Polygon":
        return [geom]
    if geom.geom_type in ("MultiPolygon", "GeometryCollection"):
        return [g for g in geom.geoms if g.geom_type == "Polygon" and not g.is_empty]
    return []


def _grelha_axial(comp: Polygon, via: float, testada: float, prof: float) -> list[Polygon]:
    """Grelha ortogonal de lotes dentro de UMA ilha (CRS já alinhado ao eixo)."""
    minx, miny, maxx, maxy = comp.bounds
    if (maxx - minx) <= 0 or (maxy - miny) < prof:
        return []
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
                lote = box(x, yb, x + testada, yb + prof).intersection(comp)
                if lote.geom_type == "Polygon" and lote.area >= 0.6 * testada * prof:
                    lotes.append(lote)
                x += testada
        y += passo_linha
        guarda += 1
        if guarda > 5000:
            break
    return lotes


def _lotear(
    miolo: BaseGeometry, via: float, testada: float, prof: float, ang_rad: float
) -> list[Polygon]:
    """Loteia o miolo (todas as ilhas) com a grelha ORIENTADA por ``ang_rad`` (topografia).
    Gera no frame rotacionado e volta — vias acompanham a curva de nível quando ``ang_rad≠0``."""
    if miolo is None or miolo.is_empty:
        return []
    ang_deg = math.degrees(ang_rad)
    cen = miolo.centroid
    reg = rotate(miolo, -ang_deg, origin=cen) if ang_deg else miolo
    lotes_rot: list[Polygon] = []
    for comp in _componentes(reg):
        lotes_rot.extend(_grelha_axial(comp, via, testada, prof))
    if not ang_deg:
        return lotes_rot
    return [rotate(l, ang_deg, origin=cen) for l in lotes_rot]


# ============================ reserva de áreas (área EXATA) ============================
def _raio_max(poly: BaseGeometry, seed: Point) -> float:
    minx, miny, maxx, maxy = poly.bounds
    cantos = [(minx, miny), (minx, maxy), (maxx, miny), (maxx, maxy)]
    return max(seed.distance(Point(c)) for c in cantos) or 1.0


def _crescer_para_area(poly: BaseGeometry, seed: Point, target: float) -> Optional[BaseGeometry]:
    """Região de ``poly`` em torno de ``seed`` com área ≈ ``target`` (busca binária de raio).
    Convergência garantida (área é monótona no raio). ``None`` se target ≤ 0."""
    if target <= 0 or poly.is_empty:
        return None
    if target >= poly.area:
        return poly
    lo, hi = 0.0, _raio_max(poly, seed)
    reg: Optional[BaseGeometry] = None
    for _ in range(34):
        r = (lo + hi) / 2
        reg = poly.intersection(seed.buffer(r, quad_segs=24))
        if reg.area < target:
            lo = r
        else:
            hi = r
    return poly.intersection(seed.buffer((lo + hi) / 2, quad_segs=24))


def _maior(geom: Optional[BaseGeometry]) -> Optional[Polygon]:
    polis = _componentes(geom) if geom is not None else []
    return max(polis, key=lambda g: g.area) if polis else None


def _reservar_lazer(aprov: BaseGeometry, target: float, evitar: Optional[BaseGeometry]):
    """Clube central + áreas verdes ao redor, com área TOTAL ≈ ``target`` (central na gleba)."""
    if target <= 0:
        return None, None
    base = aprov.difference(evitar) if (evitar is not None and not evitar.is_empty) else aprov
    base = _maior(base) or aprov
    seed = base.representative_point()
    regiao = _crescer_para_area(base, seed, target)
    if regiao is None or regiao.is_empty:
        return None, None
    clube = _crescer_para_area(regiao, seed, regiao.area * LAZER_CLUBE_FRAC)
    verde = regiao.difference(clube) if (clube is not None and not clube.is_empty) else regiao
    return (
        clube if (clube is not None and not clube.is_empty) else None,
        verde if (verde is not None and not verde.is_empty) else None,
    )


def _reservar_institucional(aprov: BaseGeometry, target: float) -> Optional[BaseGeometry]:
    """Doação institucional (área ≈ ``target``) encostada numa borda (canto inferior)."""
    if target <= 0:
        return None
    minx, miny, _, _ = aprov.bounds
    canto = nearest_points(aprov, Point(minx, miny))[0]
    reg = _crescer_para_area(aprov, canto, target)
    return reg if (reg is not None and not reg.is_empty) else None


# ============================ esqueleto da IA (intenção → eixos) ============================
def _eixos(esqueleto: Sequence, canvas: Polygon) -> tuple[list[BaseGeometry], list[str]]:
    """Denormaliza o esqueleto da IA (coords 0..1 do bbox da gleba) → eixos métricos, snapados
    à tela. Trecho inválido (auto-interseção, fora) é DESCARTADO e registrado (nunca cru)."""
    minx, miny, maxx, maxy = canvas.bounds
    w, h = (maxx - minx), (maxy - miny)
    validos: list[BaseGeometry] = []
    descartes: list[str] = []
    for i, coords in enumerate(esqueleto or []):
        try:
            pts = [(minx + float(x) * w, miny + float(y) * h) for x, y in coords]
            ls = LineString(pts)
        except Exception:  # noqa: BLE001 — coords malformadas do LLM
            descartes.append(f"esqueleto[{i}] descartado: coordenadas inválidas")
            continue
        if len(ls.coords) < 2 or not ls.is_valid or not ls.is_simple:
            descartes.append(f"esqueleto[{i}] descartado: polilinha auto-intersectada/degenerada")
            continue
        rec = ls.intersection(canvas)
        if rec.is_empty or rec.length == 0:
            descartes.append(f"esqueleto[{i}] descartado: fora da área aproveitável")
            continue
        validos.append(rec)
    return validos, descartes


# ============================ orquestração ============================
def _dims(programa: Programa) -> tuple[float, float, float]:
    return (
        max(programa.largura_via_m, 6.0),
        max(programa.testada_m, 5.0),
        max(programa.profundidade_m, 10.0),
    )


def gerar_layout(
    aproveitavel: BaseGeometry,
    programa: Programa,
    restricoes: Optional[BaseGeometry] = None,
    orientacao_rad: float = 0.0,
) -> Layout:
    """Materializa o estudo de massa dentro de ``aproveitavel`` (CRS métrico), com fidelidade
    ao programa. ``restricoes`` (cinta de segurança do teste) é recortado antes; ``orientacao_rad``
    gira a grelha para acompanhar a curva de nível (0 = sem topografia)."""
    canvas = aproveitavel
    if restricoes is not None and not restricoes.is_empty:
        canvas = canvas.difference(restricoes)
    comps = _componentes(canvas)
    if not comps:
        return Layout(avisos=["Sem área aproveitável suficiente para um estudo de massa."])
    aprov = unary_union(comps)
    aprov_area = aprov.area

    via, testada, prof = _dims(programa)
    pct_lazer0 = max(0.0, min(programa.pct_lazer, 0.6))
    pct_inst = max(0.0, min(programa.pct_institucional, 0.3))

    # (b) esqueleto da IA → eixos; usado quando o arquétipo NÃO é grelha pura e há eixo válido.
    centerlines, descartes = _eixos(programa.esqueleto, aprov)
    usar_esqueleto = programa.arquetipo_viario != ARQUETIPO_GRELHA and bool(centerlines)
    road_skel = None
    if usar_esqueleto:
        road_skel = unary_union(centerlines).buffer(via / 2.0).intersection(aprov)
        if road_skel.is_empty:
            road_skel = None

    # (a) materializar: CAP analítico — reserva lazer só até sobrar área p/ ~MIN_LOTES_RESERVA
    # lotes (preserva o parcelamento). Acima disso, DEGRADA rotulado (nunca infla nem ignora).
    lote_area = max(testada * prof, 1.0)
    inst_area = pct_inst * aprov_area
    disp_lazer = max(aprov_area - inst_area - MIN_LOTES_RESERVA * lote_area, 0.0)
    alvo_lazer_area = pct_lazer0 * aprov_area
    lazer_area = min(alvo_lazer_area, disp_lazer)
    degradado = lazer_area < alvo_lazer_area - 1e-6
    pct_usado = lazer_area / aprov_area if aprov_area else 0.0

    inst = _reservar_institucional(aprov, inst_area)
    clube, verde = _reservar_lazer(aprov, lazer_area, evitar=inst)
    reservas = [g for g in (clube, verde, inst, road_skel) if g is not None and not g.is_empty]
    miolo = aprov.difference(unary_union(reservas)) if reservas else aprov
    lotes = _lotear(miolo, via, testada, prof, orientacao_rad)

    # Arruamento = aproveitável − lotes − reservas (o road_skel cai aqui, como via).
    consumido = [g for g in (unary_union(lotes) if lotes else None, clube, verde, inst)
                 if g is not None and not g.is_empty]
    sobra = aprov.difference(unary_union(consumido)) if consumido else aprov
    arruamento = sobra if (sobra is not None and not sobra.is_empty) else None

    avisos: list[str] = []
    if not lotes:
        avisos.append(
            "A grelha esquemática não acomodou lotes na área aproveitável "
            "(gleba pequena/irregular para o lote-alvo)."
        )

    meta = {
        "lazer_alvo_pct": round(pct_lazer0, 4),
        "lazer_usado_pct": round(pct_usado, 4),
        "lazer_degradado": degradado,
        "inst_alvo_pct": round(pct_inst, 4),
        "arquetipo": programa.arquetipo_viario,
        "esqueleto_usado": usar_esqueleto,
        "trechos_descartados": len(descartes),
        "orientacao_rad": round(orientacao_rad, 6),
        "topo_aplicada": abs(orientacao_rad) > 1e-9,
    }

    return Layout(
        lotes=lotes,
        arruamento=arruamento,
        areas_verdes=verde,
        sistema_lazer=clube,
        institucional=inst,
        centerlines=centerlines if usar_esqueleto else [],
        via_largura_m=via,
        ignorados=descartes,
        avisos=avisos,
        meta=meta,
    )


# ============================ topografia (DEM 2.5 → orientação) ============================
def orientacao_contorno(dem) -> Optional[float]:
    """Ângulo (rad) da CURVA DE NÍVEL média do recorte de DEM (2.5) — perpendicular ao
    gradiente. Orienta a grelha de quarteirões (acompanhar o relevo). ``None`` se não há DEM
    ou o terreno é praticamente plano. Orientação de triagem, NÃO terraplenagem."""
    if dem is None or getattr(dem, "elevacao", None) is None:
        return None
    try:
        import numpy as np

        z = np.asarray(dem.elevacao, dtype="float64")
        if z.ndim != 2 or z.size < 4:
            return None
        px = getattr(dem, "px_m", 0.0) or 1.0
        gr, gc = np.gradient(z, px)  # gr = dz/drow (linha cresce p/ SUL), gc = dz/dcol (LESTE)
        gx = float(np.nanmean(gc))
        gy = -float(np.nanmean(gr))  # y métrico cresce p/ NORTE → inverte a linha
    except Exception:  # noqa: BLE001 — sem numpy/grid inválido → sem orientação
        return None
    if abs(gx) < 1e-12 and abs(gy) < 1e-12:
        return None  # plano → grelha axial
    return math.atan2(gy, gx) + math.pi / 2.0  # curva de nível ⟂ gradiente
