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


# ---- Fase 9.2: zoneamento por qualidade + dimensionamento por faixa (mix heterogêneo) ----
def _bandas(estrategia_mix: list[dict], prof: float) -> dict:
    """Da política de mix (faixas de ÁREA + proporção) → larguras-alvo por faixa (área÷prof).
    Ordena premium→compacto. ``None`` se sem política (cai p/ lote uniforme no chamador)."""
    if not estrategia_mix:
        return {}
    faixas = {}
    for b in estrategia_mix:
        nome = b["faixa"]
        amid = (float(b["min_m2"]) + float(b["max_m2"])) / 2.0
        faixas[nome] = {
            "w": amid / prof,
            "w_min": float(b["min_m2"]) / prof,
            "w_max": float(b["max_m2"]) / prof,
            "area_min": float(b["min_m2"]),
            "prop": float(b.get("prop_alvo", 0.0)),
        }
    return faixas


def _quality(pt: Point, verde, lazer, elev_fn, premium_em: list[str]):
    """Qualidade geométrica de uma POSIÇÃO (cota/verde/lazer) + motivos — base do zoneamento.
    Só conta os atributos que a heurística da IA pediu E que existem (degrada honesto)."""
    q, mot = 0.0, []
    if verde is not None and "fundo_mata" in premium_em:
        qv = math.exp(-pt.distance(verde) / 40.0)
        q += qv
        if qv > 0.4:
            mot.append("fundo_mata")
    if lazer is not None and "frente_lazer" in premium_em:
        ql = math.exp(-pt.distance(lazer) / 40.0)
        q += ql
        if ql > 0.4:
            mot.append("frente_lazer")
    if elev_fn is not None and "cota_alta" in premium_em:
        e = max(0.0, min(elev_fn(pt), 1.0))
        q += e
        if e > 0.6:
            mot.append("cota_alta")
    return q, mot


def _quantil(vals: list[float], q: float) -> float:
    if not vals:
        return 0.0
    s = sorted(vals)
    i = max(0, min(len(s) - 1, int(round(q * (len(s) - 1)))))
    return s[i]


def _linhas_de_quadra(comp: Polygon, via: float, prof: float):
    """Faixas (strips) horizontais de profundidade ``prof`` que formam as quadras da ilha."""
    minx, miny, maxx, maxy = comp.bounds
    if (maxx - minx) <= 0 or (maxy - miny) < prof:
        return []
    passo = 2 * prof + via
    faixas = []
    y = miny
    guarda = 0
    while y + prof <= maxy + 1e-6:
        for desloc in (0.0, prof):
            yb = y + desloc
            if yb + prof <= maxy + 1e-6:
                faixas.append((yb, yb + prof))
        y += passo
        guarda += 1
        if guarda > 5000:
            break
    return faixas


def _tile_faixa(comp, y0, y1, qfn, q_hi, q_lo, bandas):
    """Tila UMA faixa de quadra com lotes de largura POR FAIXA (premium maior), fechando a
    quadra sem sobra (redistribui o resto). Devolve ``([(geom, faixa, motivos)], retalho_m2)``."""
    strip = comp.intersection(box(comp.bounds[0], y0, comp.bounds[2], y1))
    saida = []
    retalho = 0.0
    for piece in _componentes(strip):
        x0, _, x1, _ = piece.bounds
        ymid = (y0 + y1) / 2.0
        L = x1 - x0

        def _faixa_em(x):
            q, mot = qfn(Point(x + 1.0, ymid))
            f = "premium" if q >= q_hi else ("compacto" if q <= q_lo else "padrao")
            return (f if f in bandas else next(iter(bandas))), mot

        plano = []  # (faixa, w, motivos) — só lotes INTEIROS (sem retalho fino no fim)
        x = x0
        guarda = 0
        while guarda < 5000:
            guarda += 1
            faixa, mot = _faixa_em(x)
            w = bandas[faixa]["w"]
            if x + w > x1 + 1e-6:
                break
            plano.append((faixa, w, mot))
            x += w
        if not plano:
            # Quadra mais curta que um lote: um lote ocupa a faixa toda.
            faixa, mot = _faixa_em((x0 + x1) / 2.0)
            plano = [(faixa, L, mot)]
        else:
            # Fecha a quadra sem retalho: distribui a folga restante entre os lotes inteiros.
            folga = x1 - x
            if folga > 1e-6:
                add = folga / len(plano)
                plano = [(f, w + add, m) for f, w, m in plano]
        usado = 0.0
        xx = x0
        for faixa, w, mot in plano:
            cel = box(xx, y0, xx + w, y1).intersection(piece)
            xx += w
            if cel.geom_type == "Polygon" and cel.area >= 0.5 * bandas[faixa]["area_min"]:
                saida.append((cel, faixa, mot))
                usado += cel.area
        retalho += max(piece.area - usado, 0.0)
    return saida, retalho


def _lotear_heterogeneo(miolo, via, prof, qfn, q_hi, q_lo, bandas, ang_rad):
    """Loteia o miolo com MIX por qualidade, orientado por ``ang_rad`` (topografia). Gera no
    frame rotacionado (verde/lazer já rotacionados no ``qfn``) e volta. Acumula o retalho
    (sobra dentro das quadras) — métrica da Fase 9.2."""
    if miolo is None or miolo.is_empty or not bandas:
        return [], [], [], 0.0
    ang_deg = math.degrees(ang_rad)
    cen = miolo.centroid
    reg = rotate(miolo, -ang_deg, origin=cen) if ang_deg else miolo
    lotes, faixas, motivos, retalho = [], [], [], 0.0
    for comp in _componentes(reg):
        for (y0, y1) in _linhas_de_quadra(comp, via, prof):
            saida, ret = _tile_faixa(comp, y0, y1, qfn, q_hi, q_lo, bandas)
            retalho += ret
            for geom, faixa, mot in saida:
                lotes.append(rotate(geom, ang_deg, origin=cen) if ang_deg else geom)
                faixas.append(faixa)
                motivos.append(mot)
    return lotes, faixas, motivos, retalho


def _prescan_thresholds(miolo, via, prof, qfn, bandas, ang_rad):
    """Pré-varre posições candidatas (largura nominal) e fixa os cortes de quantil para as
    proporções-alvo (premium = topo; compacto = base) → zoneamento estável e auditável."""
    if not bandas:
        return 0.0, 0.0
    ang_deg = math.degrees(ang_rad)
    cen = miolo.centroid
    reg = rotate(miolo, -ang_deg, origin=cen) if ang_deg else miolo
    w_nom = bandas.get("padrao", next(iter(bandas.values())))["w"]
    qs = []
    for comp in _componentes(reg):
        for (y0, y1) in _linhas_de_quadra(comp, via, prof):
            strip = comp.intersection(box(comp.bounds[0], y0, comp.bounds[2], y1))
            for piece in _componentes(strip):
                x0, _, x1, _ = piece.bounds
                ymid = (y0 + y1) / 2.0
                x = x0
                while x < x1 - 1e-6:
                    qs.append(qfn(Point(x + 1.0, ymid))[0])
                    x += w_nom
    # Compensa a largura: lote premium é mais largo (cabe menos por comprimento), então para
    # a PROPORÇÃO de LOTES bater o alvo, dou a ele uma fração maior de POSIÇÕES (∝ largura).
    w_pad = bandas.get("padrao", next(iter(bandas.values())))["w"]
    prem = bandas.get("premium", {})
    comp = bandas.get("compacto", {})
    eff_prem = min(prem.get("prop", 0.0) * (prem.get("w", w_pad) / w_pad), 0.95)
    eff_comp = min(comp.get("prop", 0.0) * (comp.get("w", w_pad) / w_pad), 0.95)
    q_hi = _quantil(qs, 1.0 - eff_prem) if eff_prem > 0 else float("inf")
    q_lo = _quantil(qs, eff_comp) if eff_comp > 0 else float("-inf")
    return q_hi, q_lo


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

    # (9.2) MIX heterogêneo: zoneia por qualidade (verde/lazer/cota) e dimensiona por faixa,
    # fechando a quadra sem sobra. Sem política de mix → uma faixa só (lote uniforme — compat).
    bandas = _bandas(programa.estrategia_mix, prof)
    if not bandas:
        bandas = {"padrao": {"w": testada, "w_min": testada, "w_max": testada,
                             "area_min": testada * prof, "prop": 1.0}}
    cen = miolo.centroid if (miolo is not None and not miolo.is_empty) else aprov.centroid
    ang_deg = math.degrees(orientacao_rad)
    premium_em = (programa.heuristicas or {}).get("premium_em", [])
    verde_r = rotate(verde, -ang_deg, origin=cen) if (verde is not None and ang_deg) else verde
    clube_r = rotate(clube, -ang_deg, origin=cen) if (clube is not None and ang_deg) else clube
    qfn = lambda pt: _quality(pt, verde_r, clube_r, None, premium_em)  # noqa: E731
    q_hi, q_lo = _prescan_thresholds(miolo, via, prof, qfn, bandas, orientacao_rad)
    lotes, lote_faixas, lote_motivos, retalho_m2 = _lotear_heterogeneo(
        miolo, via, prof, qfn, q_hi, q_lo, bandas, orientacao_rad
    )

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
        "sobra_retalho_m2": round(retalho_m2, 2),
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
        lote_faixas=lote_faixas,
        lote_motivos=lote_motivos,
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
