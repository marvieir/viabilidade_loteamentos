"""Fase 10 (Parte 3) — LOTEAMENTO ÚNICO: reavalia a separação entre porções contra o RELEVO REAL
(não o recorte binário ≥30%), e materializa a via-tronco de CONEXÃO que a IA propôs. Refinamento
do §2: a IA propõe POR ONDE cruzar (julgamento espacial); o Python MEDE o greide real sobre o DEM
e materializa a geometria — nenhum número vem da IA.

Âncoras (catálogo §2.3): rampa de via ≤~10%; **>15% = escadaria, não via** (⇒ não materializa).
Greide = desnível / extensão horizontal. O DEM público (30 m) não resolve vão de 22 m → a conexão
é diretriz de triagem; greide definitivo exige topografia de campo (§1-A, alerta honesto)."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import gcd, hypot
from typing import Callable, Optional

from shapely.geometry import LineString, Point
from shapely.geometry.base import BaseGeometry
from shapely.ops import nearest_points
from shapely.prepared import prep

# Limiares (catálogo §2.3) — geometria/engenharia, não vêm do LLM.
GREIDE_VIA_NORMAL_PCT = 12.0   # ≤ isto = via pavimentada normal
GREIDE_ALERTA_PCT = 15.0       # 12–15% = via com greide acentuado (alerta); > isto = escadaria
DECLIV_SEPARA_PCT = 30.0       # contato genuinamente ≥ isto por toda a frente = separadas de fato
CAIXA_TRONCO_M = 11.0          # coletora-tronco pista única, condomínio privado (catálogo §2.2)
LARG_PESCOCO_M = 26.0          # estreitamento ≤ isto (1 peça) separa duas concentrações → 2 porções
MIN_PORCAO_M2 = 4000.0         # uma porção/loba precisa ser substancial (não sliver)


def _polys(g) -> list:
    if g is None or g.is_empty:
        return []
    if g.geom_type == "Polygon":
        return [g]
    if g.geom_type in ("MultiPolygon", "GeometryCollection"):
        return [x for x in g.geoms if x.geom_type == "Polygon" and not x.is_empty]
    return []


@dataclass
class Travessia:
    """Travessia entre duas porções: eixo (LineString no frame métrico), greide medido e veredicto."""

    eixo: LineString
    ponto: tuple[float, float]
    greide_pct: float
    extensao_m: float
    desnivel_m: float
    veredicto: str                 # "via_normal" | "alerta_greide" | "inviavel"
    proposta_por: str = "llm"      # "llm" (IA propôs) | "auto" (reto) | "diagonal" (pathfinder 10.3)
    cruza_restricao: bool = False  # 10.3 — a via cruza a faixa ≥30%/mata (veda LOTE, não via) → laudo
    terreno_max_pct: Optional[float] = None  # 10.3 — declividade MÁX do terreno sob a via (diagnóstico)


@dataclass
class Conexao:
    """Resultado da reavaliação + materialização da conexão (vai para o `viario_diagnostico`)."""

    loteamento_conexo: bool
    porcoes_detectadas: int
    porcoes_conectadas: int
    barreira_reavaliada_contra_relevo: bool = False
    travessia: Optional[Travessia] = None
    alerta_topografia: bool = True
    avisos: list[str] = field(default_factory=list)


def detectar_porcoes(aprov, larg_pescoco: float = LARG_PESCOCO_M,
                     min_area: float = MIN_PORCAO_M2) -> list:
    """Fase 10.1 — porções a CONECTAR, por MORFOLOGIA, não por topologia binária. (a) Se o
    aproveitável já vem em ≥2 peças (vão real) → essas peças. (b) Se vem em 1 peça mas tem um
    ESTREITAMENTO (pescoço) mais fino que ``larg_pescoco`` separando duas concentrações de área, a
    erosão (`buffer(-larg/2)`) parte o miolo em ≥2 núcleos → trata como 2 porções (o mesmo fluxo da
    travessia). Devolve os NÚCLEOS (não se sobrepõem) — base p/ o eixo de travessia e p/ o alcance.
    1 núcleo (sem pescoço, ex. caixa limpa) → 1 porção (não inventa conexão)."""
    comps = [c for c in _polys(aprov) if c.area >= min_area]
    if len(comps) >= 2:
        return sorted(comps, key=lambda p: -p.area)
    if not comps:
        return _polys(aprov)
    nucleo = comps[0].buffer(-larg_pescoco / 2.0)
    nucs = [c for c in _polys(nucleo) if c.area >= min_area]
    return sorted(nucs, key=lambda p: -p.area) if len(nucs) >= 2 else comps


def lobos_alcancados(porcoes: list, ruas, tol: float = LARG_PESCOCO_M) -> bool:
    """Fase 10.1 — CONEXÃO POR ALCANCE DE RUAS (não por contagem de polígono): há UM componente de
    via que toca TODAS as porções? (transita-se de um lado ao outro pela via). ``tol`` folga p/ a
    rua alcançar o núcleo erodido. 0/1 porção → trivialmente alcançado. SEM via → não alcança."""
    if len(porcoes) <= 1:
        return True
    if ruas is None or ruas.is_empty:
        return False
    comps = _polys(ruas)
    return any(all(comp.intersects(p.buffer(tol)) for p in porcoes) for comp in comps)


def classificar_greide(greide_pct: float) -> str:
    """Catálogo §2.3: ≤12% via normal; 12–15% alerta de greide acentuado; >15% inviável (escadaria,
    não via) — o Python NÃO materializa como via nesse caso."""
    if greide_pct <= GREIDE_VIA_NORMAL_PCT:
        return "via_normal"
    if greide_pct <= GREIDE_ALERTA_PCT:
        return "alerta_greide"
    return "inviavel"


def greide_travessia(pa: Point, pb: Point, amostrar_cota: Callable[[float, float], float]) -> tuple[float, float, float]:
    """Mede o greide REAL da travessia pa→pb: ``amostrar_cota(x,y)`` devolve a cota (m) do DEM.
    Greide = |Δcota| / distância horizontal × 100. Devolve ``(greide_pct, extensao_m, desnivel_m)``."""
    ext = pa.distance(pb)
    if ext <= 1e-6:
        return 0.0, 0.0, 0.0
    dz = abs(amostrar_cota(pb.x, pb.y) - amostrar_cota(pa.x, pa.y))
    return round(100.0 * dz / ext, 1), round(ext, 1), round(dz, 1)


def construir_eixo_travessia(porcao_a: BaseGeometry, porcao_b: BaseGeometry,
                             ponto: Optional[tuple[float, float]] = None) -> tuple[LineString, Point, Point]:
    """Eixo da via de conexão entre A e B. Se a IA propôs um ``ponto`` (julgamento espacial), o eixo
    passa por ele: do ponto mais próximo em A, pelo ponto, ao mais próximo em B. Sem ponto, liga os
    dois pontos mais próximos (vão mais estreito). Devolve ``(eixo, pa, pb)`` no frame métrico."""
    if ponto is not None:
        p = Point(ponto)
        pa = nearest_points(p, porcao_a)[1]
        pb = nearest_points(p, porcao_b)[1]
        eixo = LineString([(pa.x, pa.y), (p.x, p.y), (pb.x, pb.y)])
    else:
        pa, pb = nearest_points(porcao_a, porcao_b)
        eixo = LineString([(pa.x, pa.y), (pb.x, pb.y)])
    return eixo, pa, pb


MAX_TRAVESSIA_M = 80.0  # travessia não pode ser arbitrariamente longa (catálogo: via, não viaduto)


def travessia_otima(porcao_a: BaseGeometry, porcao_b: BaseGeometry,
                    amostrar_cota: Callable[[float, float], float], n: int = 36) -> "Travessia":
    """Fase 10.1 — sem ponto da IA, busca a SELA MAIS SUAVE: varre pares (ponto em A × ponto em B)
    na frente de contato (até ``MAX_TRAVESSIA_M``) e escolhe o de MENOR greide medido sobre o DEM —
    NÃO o vão mais estreito (que costuma ser o mais íngreme). Um cruzamento um pouco mais longo, mas
    plano, é via normal; o estreito e íngreme é escadaria. Entre greides ~iguais, prefere o mais
    curto. Determinístico: a IA não entra; o Python mede e escolhe (§2)."""
    La, Lb = porcao_a.exterior.length, porcao_b.exterior.length
    pts_a = [porcao_a.exterior.interpolate(i / n * La) for i in range(n)]
    pts_b = [porcao_b.exterior.interpolate(j / n * Lb) for j in range(n)]
    cands: list = []
    for pa in pts_a:
        if pa.distance(porcao_b) > MAX_TRAVESSIA_M:
            continue
        for pb in pts_b:
            d = pa.distance(pb)
            if d < 1.0 or d > MAX_TRAVESSIA_M:
                continue
            g, ext, dz = greide_travessia(pa, pb, amostrar_cota)
            cands.append((round(g, 1), d, pa, pb, ext, dz))
    if not cands:
        eixo, pa, pb = construir_eixo_travessia(porcao_a, porcao_b, None)
        g, ext, dz = greide_travessia(pa, pb, amostrar_cota)
        return Travessia(eixo, (round((pa.x + pb.x) / 2, 1), round((pa.y + pb.y) / 2, 1)),
                         g, ext, dz, classificar_greide(g), "auto")
    cands.sort(key=lambda c: (c[0], c[1]))  # menor greide; empate → mais curto
    g, _d, pa, pb, ext, dz = cands[0]
    return Travessia(LineString([(pa.x, pa.y), (pb.x, pb.y)]),
                     (round((pa.x + pb.x) / 2, 1), round((pa.y + pb.y) / 2, 1)),
                     g, ext, dz, classificar_greide(g), "auto")


def avaliar_travessia(porcao_a: BaseGeometry, porcao_b: BaseGeometry,
                      amostrar_cota: Callable[[float, float], float],
                      ponto: Optional[tuple[float, float]] = None,
                      proposta_por: str = "llm") -> Travessia:
    """Materializa o eixo (IA propõe o ponto) e MEDE o greide real sobre o DEM (Python). O veredicto
    decide se vira via (≤15%) ou não (escadaria). Determinístico (§2): nenhum número vem da IA."""
    eixo, pa, pb = construir_eixo_travessia(porcao_a, porcao_b, ponto)
    greide, ext, dz = greide_travessia(pa, pb, amostrar_cota)
    pmid = ((pa.x + pb.x) / 2.0, (pa.y + pb.y) / 2.0) if ponto is None else ponto
    return Travessia(
        eixo=eixo, ponto=(round(pmid[0], 1), round(pmid[1], 1)),
        greide_pct=greide, extensao_m=ext, desnivel_m=dz,
        veredicto=classificar_greide(greide), proposta_por=proposta_por,
    )


# ============================ Fase 10.3 — TRAVESSIA DIAGONAL ============================
# Correção conceitual: a faixa ≥30% veda LOTE (Lei 6.766 art. 3º, parág. único, III), NÃO via. Uma
# via cruza terreno ≥30% na DIAGONAL com greide controlado (corte/aterro): greide_via = s·sen θ — a
# 25° do contorno, 30% de terreno vira ~13% de via. Logo a conexão não se decide por "a faixa é
# ≥30%", e sim pelo GREIDE DA VIA no melhor traçado diagonal. Aqui o Python acha esse traçado por
# busca minimax sobre o DEM (caminho de menor greide-MÁXIMO) e mede — nenhum número vem da IA (§1/§2).
PASSO_GRADE_M = 6.0          # resolução da grade de busca (m); adaptada p/ limitar nº de nós
ALVO_MAX_NOS = 5000          # teto de nós (determinístico) — passo cresce em gleba grande
# vizinhança 16-direções (offsets coprimos até 2 células) → diagonais rasas (~26°) p/ greide baixo
_OFFSETS = [(a, b) for a in (-2, -1, 0, 1, 2) for b in (-2, -1, 0, 1, 2)
            if (a, b) != (0, 0) and gcd(abs(a), abs(b)) == 1]


def travessia_diagonal(porcao_a: BaseGeometry, porcao_b: BaseGeometry,
                       amostrar_cota: Callable[[float, float], float],
                       dominio: BaseGeometry,
                       restricao: Optional[BaseGeometry] = None,
                       passo: Optional[float] = None) -> Travessia:
    """Fase 10.3 — VIA de conexão por traçado DIAGONAL: busca, sobre o ``dominio`` (a gleba, onde a
    via pode passar — inclusive sobre ≥30%), o caminho A→B de MENOR greide-MÁXIMO (minimax) e MEDE o
    greide da VIA ao longo dele. A via PODE cruzar a faixa ≥30%/mata (veda lote, não via) → se cruzar,
    marca ``cruza_restricao`` p/ o rótulo geotécnico. Determinístico: a IA não entra; o Python acha o
    corredor ótimo e mede (§1/§2). Degrada p/ ``travessia_otima`` (reto) se a grade não resolver."""
    minx, miny, maxx, maxy = dominio.bounds
    if passo is None:
        passo = max(PASSO_GRADE_M, (dominio.area / ALVO_MAX_NOS) ** 0.5)
    pdom, pa_, pb_ = prep(dominio), prep(porcao_a), prep(porcao_b)
    xs = [minx + passo / 2 + j * passo for j in range(int((maxx - minx) / passo) + 1)]
    ys = [maxy - passo / 2 - i * passo for i in range(int((maxy - miny) / passo) + 1)]
    idx: dict[tuple[int, int], int] = {}
    pts: list[tuple[float, float]] = []
    cota: list[float] = []
    tag: list[int] = []   # 1 = porção A, 2 = porção B, 0 = terreno intermediário (faixa)
    for i, Y in enumerate(ys):
        for j, X in enumerate(xs):
            p = Point(X, Y)
            if pdom.contains(p):
                idx[(i, j)] = len(pts)
                pts.append((X, Y))
                cota.append(amostrar_cota(X, Y))
                tag.append(1 if pa_.contains(p) else 2 if pb_.contains(p) else 0)
    if 1 not in tag or 2 not in tag:   # grade não pegou as duas porções → reto (degrada honesto)
        return travessia_otima(porcao_a, porcao_b, amostrar_cota)

    edges: list[tuple[float, int, int]] = []
    for (i, j), n in idx.items():
        X, Y = pts[n]
        for da, db in _OFFSETS:
            m = idx.get((i + da, j + db))
            if m is None or m <= n:
                continue
            d = passo * hypot(da, db)
            # 2 células de salto: confere que o MEIO segue no domínio (não pula concavidade/saída)
            if max(abs(da), abs(db)) == 2 and not pdom.contains(
                    Point((X + pts[m][0]) / 2, (Y + pts[m][1]) / 2)):
                continue
            edges.append((100.0 * abs(cota[m] - cota[n]) / d, n, m))
    edges.sort(key=lambda e: e[0])

    par = list(range(len(pts)))
    hasA = [t == 1 for t in tag]
    hasB = [t == 2 for t in tag]

    def find(x: int) -> int:
        while par[x] != x:
            par[x] = par[par[x]]
            x = par[x]
        return x

    gargalo: Optional[float] = None
    for g, a, b in edges:
        ra, rb = find(a), find(b)
        if ra != rb:
            par[ra] = rb
            hasA[rb] = hasA[rb] or hasA[ra]
            hasB[rb] = hasB[rb] or hasB[ra]
        r = find(a)
        if hasA[r] and hasB[r]:
            gargalo = g
            break
    if gargalo is None:   # desconexo na grade (não deveria, gleba é conexa) → reto
        return travessia_otima(porcao_a, porcao_b, amostrar_cota)

    # reconstrói UM caminho usando só arestas ≤ gargalo (BFS de A até B)
    from collections import deque, defaultdict
    adj: dict[int, list[int]] = defaultdict(list)
    for g, a, b in edges:
        if g <= gargalo + 1e-9:
            adj[a].append(b)
            adj[b].append(a)
    src = [n for n, t in enumerate(tag) if t == 1]
    dst = {n for n, t in enumerate(tag) if t == 2}
    prev: dict[int, Optional[int]] = {s: None for s in src}
    dq = deque(src)
    end: Optional[int] = None
    while dq:
        u = dq.popleft()
        if u in dst:
            end = u
            break
        for v in adj[u]:
            if v not in prev:
                prev[v] = u
                dq.append(v)
    caminho: list[int] = []
    u = end
    while u is not None:
        caminho.append(u)
        u = prev[u]
    caminho.reverse()

    coords = [pts[n] for n in caminho]
    eixo = LineString(coords).simplify(passo / 2.0, preserve_topology=False)
    if eixo.is_empty or eixo.length <= 0:
        return travessia_otima(porcao_a, porcao_b, amostrar_cota)
    ext = round(eixo.length, 1)
    dz = round(abs(cota[caminho[-1]] - cota[caminho[0]]), 1)
    cruza = bool(restricao is not None and not restricao.is_empty and eixo.intersects(restricao))
    pmid = eixo.interpolate(0.5, normalized=True)
    return Travessia(
        eixo=eixo, ponto=(round(pmid.x, 1), round(pmid.y, 1)),
        greide_pct=round(gargalo, 1), extensao_m=ext, desnivel_m=dz,
        veredicto=classificar_greide(gargalo), proposta_por="diagonal",
        cruza_restricao=cruza,
    )
