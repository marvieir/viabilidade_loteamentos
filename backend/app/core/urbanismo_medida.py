"""Urbanismo (Fase 9) — MEDIÇÃO determinística do layout. NÚCLEO Python puro: recebe
geometria (lotes/vias/verde/lazer/institucional) e devolve quadro de áreas + indicadores +
heatmap. **Nenhum número aqui vem do LLM** (§2): a IA propôs o programa; este módulo MEDE.

Trabalha em CRS métrico planar local (AEQD), igual a ``aproveitavel.consolidar`` e à
declividade/agrupamento — área/distância em METROS, nunca em graus. Sem rede, sem LLM,
determinístico: mesmo layout → mesma medição (critério de aceite 5/10).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional, Sequence

from pyproj import CRS, Transformer
from shapely.geometry import mapping, shape
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform, unary_union

ROTULO_ESQUEMATICO = "ESTUDO DE MASSA ESQUEMÁTICO"

# Avisos §1-A — SEMPRE presentes em toda saída de urbanismo (critério 9).
AVISOS_1A = [
    "ESTUDO DE MASSA ESQUEMÁTICO — pré-análise (§1-A); NÃO é projeto urbanístico nem "
    "traçado executivo; o projeto e as diretrizes da gleba são do urbanista (art. 6º Lei "
    "6.766). Verificar com urbanista.",
    "Nº de lotes e quadro de áreas MEDIDOS pelo motor sobre a proposta; a IA propôs o "
    "programa, não os números.",
    "Não contempla projetos técnicos (água, esgoto, energia, drenagem) nem custos de obra.",
]


def _fmt(v: float, dec: int = 2) -> str:
    """Número em pt-BR (milhar com ponto, decimal com vírgula). O front não reformata (§2)."""
    s = f"{v:,.{dec}f}"
    return s.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def _crs_local(lon: float, lat: float) -> CRS:
    return CRS.from_proj4(
        f"+proj=aeqd +lat_0={lat} +lon_0={lon} +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs"
    )


def transformadores(geoms_wgs: Sequence[BaseGeometry]):
    """Devolve ``(to_local, to_wgs)`` centrados no centróide da união — meu CRS métrico."""
    uni = unary_union([g for g in geoms_wgs if g is not None and not g.is_empty])
    c = uni.centroid if not uni.is_empty else None
    lon, lat = (c.x, c.y) if c is not None else (0.0, 0.0)
    local = _crs_local(lon, lat)
    to_local = Transformer.from_crs("EPSG:4326", local, always_xy=True).transform
    to_wgs = Transformer.from_crs(local, "EPSG:4326", always_xy=True).transform
    return to_local, to_wgs


# ----------------------------- estrutura do layout -----------------------------
@dataclass
class Layout:
    """Geometria gerada (CRS MÉTRICO). ``lotes`` é a lista de polígonos individuais."""

    lotes: list[BaseGeometry] = field(default_factory=list)
    arruamento: Optional[BaseGeometry] = None
    areas_verdes: Optional[BaseGeometry] = None
    sistema_lazer: Optional[BaseGeometry] = None
    institucional: Optional[BaseGeometry] = None
    centerlines: list[BaseGeometry] = field(default_factory=list)
    via_largura_m: float = 12.0
    ignorados: list[str] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)
    # Fase 9.1 — flags de fidelidade (alvos/efetivo, arquétipo, esqueleto, topografia).
    meta: dict = field(default_factory=dict)
    # Fase 9.2 — faixa de mix (premium/padrao/compacto) e motivo de zona POR lote (paralelo a
    # ``lotes``). Vazio na Fase 9 (lote uniforme); preenchido pelo zoneamento heterogêneo.
    lote_faixas: list[str] = field(default_factory=list)
    lote_motivos: list[list[str]] = field(default_factory=list)


# ----------------------------- medição (pura) -----------------------------
def _lados_mrr(poly: BaseGeometry) -> tuple[float, float]:
    """(menor, maior) lado do retângulo mínimo rotacionado → testada × profundidade."""
    try:
        mrr = poly.minimum_rotated_rectangle
        pts = list(mrr.exterior.coords)[:-1]
    except Exception:  # noqa: BLE001 — geometria degenerada
        return 0.0, 0.0
    if len(pts) < 4:
        return 0.0, 0.0
    def d(a, b):
        return math.hypot(a[0] - b[0], a[1] - b[1])
    e1, e2 = d(pts[0], pts[1]), d(pts[1], pts[2])
    return (round(min(e1, e2), 2), round(max(e1, e2), 2))


def _area(geom: Optional[BaseGeometry]) -> float:
    return geom.area if geom is not None and not geom.is_empty else 0.0


@dataclass
class Medicao:
    quadro: dict
    indicadores: dict
    heatmap: dict


def medir(layout: Layout) -> Medicao:
    """Quadro de áreas + indicadores + heatmap a partir do ``Layout`` métrico (PURO)."""
    lotes = [g for g in layout.lotes if g is not None and not g.is_empty]
    vendavel = round(sum(_area(g) for g in lotes), 2)
    verdes = round(_area(layout.areas_verdes), 2)
    lazer = round(_area(layout.sistema_lazer), 2)
    inst = round(_area(layout.institucional), 2)
    arru = round(_area(layout.arruamento), 2)

    # Área líquida = área da UNIÃO de todas as camadas (robusto se houver encosto/folga).
    todas = [*lotes]
    for g in (layout.arruamento, layout.areas_verdes, layout.sistema_lazer, layout.institucional):
        if g is not None and not g.is_empty:
            todas.append(g)
    area_liquida = round(_area(unary_union(todas)), 2) if todas else 0.0

    def _uso(m2: float) -> dict:
        pct = round(m2 / area_liquida, 4) if area_liquida else 0.0
        return {"m2": m2, "m2_fmt": _fmt(m2), "pct_apo": pct, "pct_fmt": _fmt(pct * 100, 1) + "%"}

    quadro = {
        "area_liquida_m2": area_liquida,
        "area_liquida_fmt": _fmt(area_liquida),
        "vendavel": _uso(vendavel),
        "areas_verdes": _uso(verdes),
        "sistema_lazer": _uso(lazer),
        "institucional": _uso(inst),
        "arruamento": _uso(arru),
    }

    n = len(lotes)
    area_media = round(vendavel / n, 2) if n else None
    testadas = [_lados_mrr(g) for g in lotes]
    testada_media = round(sum(t[0] for t in testadas) / n, 2) if n else None
    profundidade_media = round(sum(t[1] for t in testadas) / n, 2) if n else None

    # Indicadores de via: do centerline quando há (gerador); senão estimados da área.
    via_w = layout.via_largura_m or 12.0
    if layout.centerlines:
        comp = round(sum(c.length for c in layout.centerlines), 2)
    elif arru > 0:
        comp = round(arru / via_w, 2)  # estimativa: área ÷ largura
    else:
        comp = None
    leito = round(comp * via_w * 0.55, 2) if comp else None  # ~55% leito carroçável
    calcadas = round((arru - leito), 2) if (comp and arru) else None

    indicadores = {
        "n_lotes": n,
        "area_media_m2": area_media,
        "area_media_fmt": _fmt(area_media) if area_media is not None else None,
        "testada_media_m": testada_media,
        "profundidade_media_m": profundidade_media,
        "comprimento_vias_m": comp,
        "leito_carrocavel_m2": leito,
        "calcadas_m2": calcadas,
    }

    heatmap = pontuar(lotes, layout.areas_verdes, layout.arruamento)
    return Medicao(quadro=quadro, indicadores=indicadores, heatmap=heatmap)


# ----------------------------- heatmap (scoring geométrico puro) -----------------------------
# Faixas de score (limites superiores inclusivos): 0–3, 3–5, 5–7, 7–9, 9–10.
_FAIXAS = [("0-3", 3.0), ("3-5", 5.0), ("5-7", 7.0), ("7-9", 9.0), ("9-10", 10.01)]
_PROX_VERDE_M = 8.0  # lote "de fundo contra verde" se a borda está a ≤ 8 m da área verde


def _score_lote(
    lote: BaseGeometry,
    area_max: float,
    verde: Optional[BaseGeometry],
    centro,
    raio_max: float,
) -> float:
    """Score 0–10 por atributos GEOMÉTRICOS medíveis (sem preço). Determinístico."""
    s = 5.0
    # área relativa (lote maior → melhor) — até +2
    if area_max > 0:
        s += 2.0 * (lote.area / area_max)
    # fundo contra verde (privacidade) — +2
    if verde is not None and not verde.is_empty and lote.distance(verde) <= _PROX_VERDE_M:
        s += 2.0
    # afastamento do centro/entrada (menos ruído na borda) — até +1
    if raio_max > 0 and centro is not None:
        s += 1.0 * min(lote.centroid.distance(centro) / raio_max, 1.0)
    return round(max(0.0, min(10.0, s)), 2)


def pontuar(
    lotes: Sequence[BaseGeometry],
    verde: Optional[BaseGeometry] = None,
    arruamento: Optional[BaseGeometry] = None,
) -> dict:
    """Heatmap de valorização: score por lote + distribuição em faixas. Sem preço absoluto —
    ordena QUALIDADE relativa; o R$/m² por faixa é input do usuário (não inventado)."""
    lotes = [g for g in lotes if g is not None and not g.is_empty]
    if not lotes:
        return {"score_medio": None, "faixas": [], "por_lote": [], "proveniencia": _PROV_HEATMAP}
    area_max = max(g.area for g in lotes)
    uni = unary_union(lotes)
    centro = uni.centroid
    raio_max = max(g.centroid.distance(centro) for g in lotes) or 1.0

    por_lote = []
    for i, g in enumerate(lotes, start=1):
        por_lote.append(
            {
                "lote_id": f"L{i:03d}",
                "score": _score_lote(g, area_max, verde, centro, raio_max),
                "area_m2": round(g.area, 2),
            }
        )
    scores = [p["score"] for p in por_lote]
    score_medio = round(sum(scores) / len(scores), 2)

    faixas = []
    n = len(scores)
    anterior = -0.01
    for rotulo, teto in _FAIXAS:
        cont = sum(1 for s in scores if anterior < s <= teto)
        anterior = teto
        if cont:
            faixas.append({"faixa": rotulo, "n": cont, "pct": round(cont / n, 4)})
    return {
        "score_medio": score_medio,
        "faixas": faixas,
        "por_lote": por_lote,
        "proveniencia": _PROV_HEATMAP,
    }


_PROV_HEATMAP = (
    "Score geométrico relativo por lote (área, fundo contra verde, afastamento) — ordena "
    "qualidade, NÃO é preço; o R$/m² por faixa é input do usuário."
)


# ----------------------------- ponte WGS84 ↔ métrico -----------------------------
def layout_de_geojson(
    lotes_geojson: Sequence[dict],
    arruamento: Optional[dict],
    areas_verdes: Optional[dict],
    sistema_lazer: Optional[dict],
    institucional: Optional[dict],
) -> tuple[Layout, object]:
    """Constrói um ``Layout`` MÉTRICO a partir de camadas GeoJSON (WGS84) e devolve também o
    ``to_wgs`` para reprojetar de volta. Usado pelo endpoint ``/medir`` (sem LLM)."""
    lotes_wgs = [shape(g) for g in lotes_geojson if g]
    outros_wgs = {
        "arruamento": shape(arruamento) if arruamento else None,
        "areas_verdes": shape(areas_verdes) if areas_verdes else None,
        "sistema_lazer": shape(sistema_lazer) if sistema_lazer else None,
        "institucional": shape(institucional) if institucional else None,
    }
    todas = [*lotes_wgs, *[g for g in outros_wgs.values() if g is not None]]
    to_local, to_wgs = transformadores(todas)
    layout = Layout(
        lotes=[transform(to_local, g) for g in lotes_wgs],
        arruamento=transform(to_local, outros_wgs["arruamento"]) if outros_wgs["arruamento"] else None,
        areas_verdes=transform(to_local, outros_wgs["areas_verdes"]) if outros_wgs["areas_verdes"] else None,
        sistema_lazer=transform(to_local, outros_wgs["sistema_lazer"]) if outros_wgs["sistema_lazer"] else None,
        institucional=transform(to_local, outros_wgs["institucional"]) if outros_wgs["institucional"] else None,
    )
    return layout, to_wgs


def geojson_do_layout(layout: Layout, to_wgs) -> dict:
    """Camadas do layout (métrico) → GeoJSON WGS84 para o mapa. Lotes vão como MultiPolygon."""
    def _gj(geom):
        if geom is None or geom.is_empty:
            return None
        return mapping(transform(to_wgs, geom))

    lotes_wgs = unary_union(layout.lotes) if layout.lotes else None
    return {
        "rotulo": "esquemático",
        "lotes": _gj(lotes_wgs),
        "arruamento": _gj(layout.arruamento),
        "areas_verdes": _gj(layout.areas_verdes),
        "sistema_lazer": _gj(layout.sistema_lazer),
        "institucional": _gj(layout.institucional),
    }


# ----------------------------- fidelidade (Fase 9.1) -----------------------------
TOL_CONVERGENCIA_PP = 0.03


def construir_fidelidade(med: "Medicao", layout: "Layout") -> dict:
    """Compara o quadro MEDIDO com o programa proposto (alvos em ``layout.meta``): convergência
    por item (lazer/institucional) com tolerância ou degradação rotulada + estado de viário e
    topografia. Determinístico — só leitura do que já foi medido (§2)."""
    q = med.quadro
    liq = q["area_liquida_m2"] or 1.0
    m = layout.meta or {}
    lazer_m = (q["sistema_lazer"]["m2"] + q["areas_verdes"]["m2"]) / liq
    inst_m = q["institucional"]["m2"] / liq

    areas: list[dict] = []
    alvo_l = m.get("lazer_alvo_pct", 0.0)
    if alvo_l > 0 or lazer_m > 0:
        if m.get("lazer_degradado"):
            usado = m.get("lazer_usado_pct", lazer_m)
            areas.append({
                "item": "lazer",
                "alvo_pct": alvo_l,
                "medido_pct": round(lazer_m, 4),
                "status": "degradado",
                "tol_pp": TOL_CONVERGENCIA_PP * 100,
                "leitura": (
                    f"lazer reduzido de {_fmt(alvo_l * 100, 1)}% para "
                    f"{_fmt(usado * 100, 1)}% — a gleba não comporta o programa preservando "
                    "lotes; verificar prioridades com urbanista."
                ),
            })
        else:
            atende = abs(lazer_m - alvo_l) <= TOL_CONVERGENCIA_PP
            areas.append({
                "item": "lazer",
                "alvo_pct": alvo_l,
                "medido_pct": round(lazer_m, 4),
                "status": "atendido" if atende else "atencao",
                "tol_pp": TOL_CONVERGENCIA_PP * 100,
                "leitura": (
                    f"lazer/verde materializado {_fmt(lazer_m * 100, 1)}% "
                    f"(alvo {_fmt(alvo_l * 100, 1)}%)."
                ),
            })

    alvo_i = m.get("inst_alvo_pct", 0.0)
    if alvo_i > 0 or inst_m > 0:
        areas.append({
            "item": "institucional",
            "alvo_pct": alvo_i,
            "medido_pct": round(inst_m, 4),
            "status": "atendido" if inst_m + 1e-6 >= alvo_i - TOL_CONVERGENCIA_PP else "atencao",
            "tol_pp": TOL_CONVERGENCIA_PP * 100,
            "leitura": (
                f"doação institucional {_fmt(inst_m * 100, 1)}% (alvo {_fmt(alvo_i * 100, 1)}%)."
            ),
        })

    descartados = m.get("trechos_descartados", 0)
    viario = {
        "arquetipo": m.get("arquetipo", "—"),
        "esqueleto_usado": bool(m.get("esqueleto_usado")),
        "trechos_descartados": descartados,
        "obs": (
            "viário a partir dos eixos sugeridos pela IA (snapados/regularizados)"
            if m.get("esqueleto_usado")
            else "grelha axial (sem esqueleto válido da IA)"
        ) + (f"; {descartados} trecho(s) descartado(s)" if descartados else ""),
    }
    topo = {
        "orientacao_por_declividade": bool(m.get("topo_aplicada")),
        "obs": (
            "quarteirões orientados às curvas de nível (DEM 2.5) — triagem, não terraplenagem"
            if m.get("topo_aplicada")
            else "sem orientação por topografia (DEM indisponível ou terreno plano)"
        ),
    }
    return {"areas": areas, "viario": viario, "topografia": topo}


# ----------------------------- mix medido (Fase 9.2) -----------------------------
def _pearson(xs: list[float], ys: list[float]) -> float:
    """Correlação de Pearson (0 se variância nula). Determinístico."""
    n = len(xs)
    if n < 2:
        return 0.0
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx <= 1e-12 or syy <= 1e-12:
        return 0.0
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    return sxy / math.sqrt(sxx * syy)


_ORDEM_FAIXA = ("premium", "padrao", "compacto")


def mix_medido(med: "Medicao", layout: "Layout") -> dict:
    """Distribuição de tamanhos por faixa, correlação tamanho×score (consequência da
    estratégia, NÃO meta), sobra/retalho e % de viário — tudo MEDIDO (§2)."""
    por_lote = med.heatmap.get("por_lote", [])
    faixas = layout.lote_faixas or []
    motivos = layout.lote_motivos or []
    n = len(por_lote)
    lotes_out, areas, scores, grupos = [], [], [], {}
    for i, p in enumerate(por_lote):
        fx = faixas[i] if i < len(faixas) else "padrao"
        mot = motivos[i] if i < len(motivos) else []
        lotes_out.append({
            "lote_id": p["lote_id"], "area_m2": p["area_m2"], "faixa": fx,
            "score": p["score"], "zona_motivo": mot,
        })
        areas.append(p["area_m2"])
        scores.append(p["score"])
        grupos.setdefault(fx, []).append(p["area_m2"])

    distribuicao = []
    for fx in _ORDEM_FAIXA:
        ar = grupos.get(fx)
        if ar:
            distribuicao.append({
                "faixa": fx, "n": len(ar), "pct": round(len(ar) / n, 4) if n else 0.0,
                "area_media_m2": round(sum(ar) / len(ar), 2),
            })

    liq = med.quadro["area_liquida_m2"] or 1.0
    retalho = float(layout.meta.get("sobra_retalho_m2", 0.0))
    return {
        "distribuicao": distribuicao,
        "correlacao_tamanho_score": round(_pearson(areas, scores), 3),
        "sobra_retalho_m2": round(retalho, 2),
        "sobra_retalho_pct": round(retalho / liq, 4),
        "arruamento_pct": med.quadro["arruamento"]["pct_apo"],
        "lotes": lotes_out,
    }
