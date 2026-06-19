"""Fase 9.14 — TRAÇADO INTELIGENTE: contorno da restrição, conectividade, cul-de-sacs de bulbo,
recuperação de faces órfãs. A IA propõe o **programa** de traçado (hierarquia, onde fazer
cul-de-sac, intenção de contornar); AQUI o **Python materializa e mede** toda a geometria — nenhum
número vem do LLM (§2). As quatro regras são algoritmos DETERMINÍSTICOS, no frame ROTACIONADO
(eixos axiais), antes do `_back` da `gerar_layout`.

Fontes (§0 da spec): SIURB/IP-03 (>15% = escadaria, não via → a via CONTORNA a ≥30%, regra A);
VTPI connectivity index (regra B); cul-de-sac standards PA/Scribd (raio ~9–12 m, ≤~300 m, regra C);
ACCESS Magazine "loops-and-lollipops" (tronco coletora costura tudo)."""

from __future__ import annotations

from collections import Counter
from typing import Optional, Sequence

from shapely.geometry import LineString, Point, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

# ---- parâmetros de traçado (NORMA/PESQUISA §0; geometria determinística, não vêm do LLM) ----
AFAST_VIA_M = 7.0        # SIURB/IP-03 — afastamento da via à área vedada (≥30%)
DETECT_GAP_M = 35.0      # borda externa a ≤ isto de outra porção = face p/ a restrição (o "gap")
RAIO_BULBO_M = 10.0      # turnaround do bulbo (giro de veículo de serviço) — cul-de-sac standards
CULDESAC_MAX_M = 300.0   # comprimento máx do ramo sem saída (~1000 ft)
MIN_CONTORNO_M = 8.0     # trecho de contorno curto demais não vira via
MIN_MANCHA_RING_M2 = 2500.0  # mancha ≥30% interna PEQUENA (mata) fica verde-ilha, SEM anel viário —
                             # só restrição grande (que bloqueia acesso) ganha via de contorno
SNAP_M = 0.75            # tolerância p/ casar pontas no grafo de vias


def _linhas(geom: Optional[BaseGeometry]) -> list[LineString]:
    if geom is None or geom.is_empty:
        return []
    if geom.geom_type == "LineString":
        return [geom]
    if geom.geom_type in ("MultiLineString", "GeometryCollection"):
        return [g for g in geom.geoms if g.geom_type == "LineString" and not g.is_empty]
    return []


def _borda_para_restricao(ilha, outras: Optional[BaseGeometry]) -> Optional[BaseGeometry]:
    """Linhas da borda da ilha que FACEIAM a restrição: (a) anéis interiores (manchas ≥30% internas
    = buracos) e (b) trechos da borda externa próximos de OUTRA porção (o gap que as separa). É o
    que a via de contorno deve acompanhar — nunca a borda livre da gleba (essa é a entrada).

    Só restrição GRANDE (mancha interna ≥ ``MIN_MANCHA_RING_M2`` ou o gap entre porções) ganha via
    de contorno: mancha de mata pequena fica como verde-ilha (os lotes ao redor já têm acesso pela
    malha normal) — anelar cada patch minúsculo só inflaria o viário sem recuperar lote."""
    linhas: list[LineString] = [
        LineString(r.coords) for r in ilha.interiors if Polygon(r).area >= MIN_MANCHA_RING_M2
    ]
    if outras is not None and not outras.is_empty:
        linhas += _linhas(ilha.exterior.intersection(outras.buffer(DETECT_GAP_M)))
    u = unary_union(linhas) if linhas else None
    return u if (u is not None and not u.is_empty) else None


def rotear_contornando_restricao(ilha, outras: Optional[BaseGeometry],
                                 afast: float = AFAST_VIA_M, via_w: float = 10.0) -> list[LineString]:
    """REGRA A — eixos da via-tronco de CONTORNO da restrição. Em vez de CORTAR o trecho que cruzaria
    a área vedada (o "caco podado" de hoje), a via CONTORNA: corre por DENTRO da ilha, a ``afast`` da
    borda vedada (anéis ≥30% + borda do gap). NUNCA invade a área vedada (a ilha já a exclui) e dá
    frente para via às faces antes órfãs ao longo dela. Devolve LineStrings (centerlines)."""
    borda = _borda_para_restricao(ilha, outras)
    if borda is None:
        return []
    recuo = ilha.buffer(-(afast + via_w / 2.0))  # a via fica a ``afast`` da borda vedada
    if recuo.is_empty:
        return []
    perto = borda.buffer(afast + via_w + 6.0)
    return [p for p in _linhas(recuo.boundary.intersection(perto)) if p.length >= MIN_CONTORNO_M]


def _no(pt, q: float = SNAP_M) -> tuple[float, float]:
    return (round(pt[0] / q) * q, round(pt[1] / q) * q)


def grafo_de_vias(centerlines: Sequence[LineString]) -> tuple[Counter, int, int]:
    """Grafo de vias (nós = pontas; arestas = trechos): devolve ``(grau_por_no, n_intersecoes,
    n_links)``. Interseção = nó de grau ≥3 (cruzamento/T); ponta = grau 1 (fim de via)."""
    grau: Counter = Counter()
    for ls in centerlines:
        cs = list(ls.coords)
        if len(cs) < 2:
            continue
        grau[_no(cs[0])] += 1
        grau[_no(cs[-1])] += 1
    n_inter = sum(1 for g in grau.values() if g >= 3)
    return grau, n_inter, len(list(centerlines))


def pontas_mortas(centerlines: Sequence[LineString], borda_entrada: Optional[BaseGeometry],
                  contorno: Optional[BaseGeometry] = None) -> list[Point]:
    """REGRA B/C — pontas de grau 1 (dead-ends) que NÃO terminam na entrada (borda da gleba) nem no
    contorno (já reconectadas) NEM numa junção em T (a ponta cai no MEIO de outra via → conecta, não
    é via morta). São as candidatas a cul-de-sac de bulbo (regra C). Determinístico."""
    grau, _, _ = grafo_de_vias(centerlines)
    borda_buf = borda_entrada.buffer(SNAP_M * 2) if borda_entrada is not None else None
    cont_buf = contorno.buffer(SNAP_M * 2) if (contorno is not None and not contorno.is_empty) else None
    linhas = list(centerlines)
    pontas: list[Point] = []
    for no, g in grau.items():
        if g != 1:
            continue
        p = Point(no)
        if borda_buf is not None and borda_buf.contains(p):
            continue  # termina na ENTRADA da gleba = via legítima (não é via morta)
        if cont_buf is not None and cont_buf.contains(p):
            continue  # já reconectada pelo contorno
        disco = p.buffer(SNAP_M * 1.5)
        if sum(1 for ls in linhas if ls.intersects(disco)) > 1:
            continue  # junção em T: a ponta cai no meio de OUTRA via → conecta (não é morta)
        pontas.append(p)
    return pontas


def fechar_culdesac_bulbo(ponta: Point, raio: float = RAIO_BULBO_M):
    """REGRA C — fecha o ramo terminal num BULBO de retorno: disco de raio ``raio`` (giro de veículo
    de serviço) que vira pavimento. NENHUMA via fica como ponta solta (vias_mortas→0). Os lotes em
    LEQUE emergem da subdivisão da face ao redor (frente = arco do bulbo), pelo clamp/frente-via."""
    return ponta.buffer(raio)


def indice_conectividade(centerlines: Sequence[LineString], n_culdesacs: int) -> float:
    """REGRA B — índice de conectividade (VTPI): links ÷ (interseções + culs-de-sac). ≥1,4 = malha
    caminhável. Diagnóstico de triagem (não é trava). Determinístico a partir do grafo de vias."""
    _, n_inter, n_links = grafo_de_vias(centerlines)
    den = n_inter + max(n_culdesacs, 0)
    return round(n_links / den, 2) if den else float(n_links)
