"""Fase 10 (Parte 3) — LOTEAMENTO ÚNICO: reavalia a separação entre porções contra o RELEVO REAL
(não o recorte binário ≥30%), e materializa a via-tronco de CONEXÃO que a IA propôs. Refinamento
do §2: a IA propõe POR ONDE cruzar (julgamento espacial); o Python MEDE o greide real sobre o DEM
e materializa a geometria — nenhum número vem da IA.

Âncoras (catálogo §2.3): rampa de via ≤~10%; **>15% = escadaria, não via** (⇒ não materializa).
Greide = desnível / extensão horizontal. O DEM público (30 m) não resolve vão de 22 m → a conexão
é diretriz de triagem; greide definitivo exige topografia de campo (§1-A, alerta honesto)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

from shapely.geometry import LineString, Point
from shapely.geometry.base import BaseGeometry
from shapely.ops import nearest_points

# Limiares (catálogo §2.3) — geometria/engenharia, não vêm do LLM.
GREIDE_VIA_NORMAL_PCT = 12.0   # ≤ isto = via pavimentada normal
GREIDE_ALERTA_PCT = 15.0       # 12–15% = via com greide acentuado (alerta); > isto = escadaria
DECLIV_SEPARA_PCT = 30.0       # contato genuinamente ≥ isto por toda a frente = separadas de fato
CAIXA_TRONCO_M = 14.0          # coletora-tronco pista única (catálogo §2.2)
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
    proposta_por: str = "llm"      # "llm" (IA propôs o ponto) | "auto" (ponto mais favorável)


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
