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
    # Fase 9.6 — verde SEPARADO para o mapa: bloco reservado (limpo) × sobra de ponta (9.4).
    # ``areas_verdes`` (acima) continua sendo o TOTAL (reservada ∪ sobra) p/ o quadro/conformidade.
    areas_verdes_reservada: Optional[BaseGeometry] = None
    sobra_ponta: Optional[BaseGeometry] = None
    centerlines: list[BaseGeometry] = field(default_factory=list)
    via_largura_m: float = 12.0
    ignorados: list[str] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)
    # Fase 9.1 — flags de fidelidade (alvos/efetivo, arquétipo, esqueleto, topografia).
    meta: dict = field(default_factory=dict)
    # Fase 9.3 — id da quadra de cada lote (paralelo a ``lotes``); o tamanho emerge da quadra.
    lote_quadra: list[str] = field(default_factory=list)
    # Fase 9.7 — MALHA: quadras (faces) p/ desenhar o contorno; eixos da malha p/ medir via;
    # diagnósticos de conectividade do viário e de qualificação legal do institucional/clube.
    quadras: list[BaseGeometry] = field(default_factory=list)
    eixos_malha: list[BaseGeometry] = field(default_factory=list)
    viario_diagnostico: dict = field(default_factory=dict)
    institucional_diagnostico: dict = field(default_factory=dict)
    sistema_lazer_diagnostico: dict = field(default_factory=dict)
    # Fase 9.8 — restrição recortada (mata/declividade/APP que o motor não loteou) p/ o mapa
    # rotular (em vez do "clarão"); ``restricao_origem`` = de onde veio (vegetacao/declividade/app).
    restricao_recortada: Optional[BaseGeometry] = None
    restricao_origem: list[str] = field(default_factory=list)


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


def _uniao(geoms) -> Optional[BaseGeometry]:
    """``unary_union`` robusto a geometria inválida (a gleba real gera diferenças inválidas que
    fazem o GEOS estourar). Valida com ``buffer(0)`` e, se ainda assim falhar, une incremental."""
    parts = [g for g in geoms if g is not None and not g.is_empty]
    if not parts:
        return None
    try:
        return unary_union(parts)
    except Exception:  # noqa: BLE001 — TopologyException → valida e une incremental
        acc = None
        for g in parts:
            try:
                v = g if g.is_valid else g.buffer(0)
                acc = v if acc is None else unary_union([acc, v])
            except Exception:  # noqa: BLE001
                continue
        return acc


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
    # Fase 10 (Parte 2) — VERDE DESMEMBRADO (catálogo §5/§10): a "área verde" honesta é só a RESERVA
    # (doação/programa); a SOBRA geométrica (faces sem aproveitamento) é sobra a MINIMIZAR, NUNCA
    # "área verde". O cálculo já existia (areas_verdes_reservada × sobra_ponta); aqui expõe separado.
    verde_reserva = round(_area(layout.areas_verdes_reservada), 2)
    sobra_geom = round(_area(layout.sobra_ponta), 2)
    lazer = round(_area(layout.sistema_lazer), 2)
    inst = round(_area(layout.institucional), 2)
    arru = round(_area(layout.arruamento), 2)

    # Área líquida = área da UNIÃO de todas as camadas (robusto se houver encosto/folga).
    todas = [*lotes]
    for g in (layout.arruamento, layout.areas_verdes, layout.sistema_lazer, layout.institucional):
        if g is not None and not g.is_empty:
            todas.append(g)
    area_liquida = round(_area(_uniao(todas)), 2) if todas else 0.0

    def _uso(m2: float) -> dict:
        pct = round(m2 / area_liquida, 4) if area_liquida else 0.0
        return {"m2": m2, "m2_fmt": _fmt(m2), "pct_apo": pct, "pct_fmt": _fmt(pct * 100, 1) + "%"}

    quadro = {
        "area_liquida_m2": area_liquida,
        "area_liquida_fmt": _fmt(area_liquida),
        "vendavel": _uso(vendavel),
        "areas_verdes": _uso(verdes),  # TOTAL (compat) — o front usa as linhas separadas abaixo
        # Fase 10 (Parte 2) — linhas SEPARADAS: verde de verdade × sobra geométrica.
        "area_verde_reserva": _uso(verde_reserva),  # doação/programa (verde legítimo)
        "sobra_geometrica": _uso(sobra_geom),        # ⚠️ NÃO é área verde — sobra a minimizar
        "sistema_lazer": _uso(lazer),
        "institucional": _uso(inst),
        "arruamento": _uso(arru),
    }

    n = len(lotes)
    area_media = round(vendavel / n, 2) if n else None
    testadas = [_lados_mrr(g) for g in lotes]
    testada_media = round(sum(t[0] for t in testadas) / n, 2) if n else None
    profundidade_media = round(sum(t[1] for t in testadas) / n, 2) if n else None

    # Indicadores de via: do comprimento da MALHA (9.7 — eixos_malha) quando há; senão do
    # centerline da IA; senão estimado da área.
    via_w = layout.via_largura_m or 12.0
    if layout.eixos_malha:
        comp = round(sum(c.length for c in layout.eixos_malha), 2)
    elif layout.centerlines:
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
    """Score 0–10 por POSIÇÃO (cota/verde/lazer/ruído) — DESACOPLADO do tamanho (Fase 9.3 §3:
    o valor da posição vai para o R$/m², não para a área). Sem preço. Determinístico."""
    s = 5.0
    # fundo contra verde (privacidade/vista) — +3
    if verde is not None and not verde.is_empty and lote.distance(verde) <= _PROX_VERDE_M:
        s += 3.0
    # afastamento do centro/entrada (sossego, menos ruído da via) — até +2
    if raio_max > 0 and centro is not None:
        s += 2.0 * min(lote.centroid.distance(centro) / raio_max, 1.0)
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
    uni = _uniao(lotes)
    centro = uni.centroid if uni is not None else lotes[0].centroid
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


def _faixa_de_score(score) -> Optional[str]:
    """Faixa de score do lote (mesmos limites do heatmap) — p/ colorir o mapa lote a lote."""
    if score is None:
        return None
    anterior = -0.01
    for rotulo, teto in _FAIXAS:
        if anterior < score <= teto:
            return rotulo
        anterior = teto
    return _FAIXAS[-1][0]


def geojson_do_layout(layout: Layout, to_wgs, por_lote=None) -> dict:
    """Camadas do layout (métrico) → GeoJSON WGS84 para o mapa.

    Fase 9.5 — PARCELAMENTO LEGÍVEL: ``lotes_features`` é uma FeatureCollection com **uma Feature
    por lote** (geometria + props que JÁ existem, casadas por índice: ``por_lote[i]``,
    ``layout.lote_quadra[i]``, ``_lados_mrr``). NENHUM número novo — só deixa de fundir. O
    ``lotes`` (MultiPolygon unido) permanece por compatibilidade/fallback."""
    por_lote = por_lote or []

    def _gj(geom):
        if geom is None or geom.is_empty:
            return None
        return mapping(transform(to_wgs, geom))

    feats = []
    for i, geom in enumerate(layout.lotes):
        if geom is None or geom.is_empty:
            continue
        t, p = _lados_mrr(geom)  # testada/profundidade — exatamente como já se mede
        pl = por_lote[i] if i < len(por_lote) else {}
        score = pl.get("score")
        feats.append({
            "type": "Feature",
            "geometry": mapping(transform(to_wgs, geom)),
            "properties": {
                "lote_id": pl.get("lote_id", f"L{i + 1:03d}"),
                "area_m2": pl.get("area_m2"),
                "score": score,
                "testada_m": t,
                "profundidade_m": p,
                "quadra_id": layout.lote_quadra[i] if i < len(layout.lote_quadra) else None,
                "faixa_score": _faixa_de_score(score),
            },
        })

    # Fase 9.7 — QUADRAS como FeatureCollection (cada face da malha, contorno p/ o mapa).
    quadras_feats = []
    for i, q in enumerate(layout.quadras, start=1):
        if q is None or q.is_empty:
            continue
        quadras_feats.append({
            "type": "Feature",
            "geometry": mapping(transform(to_wgs, q)),
            "properties": {"quadra_id": f"Q{i}", "area_m2": round(q.area, 2)},
        })

    # Fase 9.7 — viário como MALHA (conexo/hierarquia) e áreas públicas FORMADAS (frente/forma).
    vdiag = layout.viario_diagnostico or {}
    viario_gj = _gj(layout.arruamento)
    if viario_gj is not None:
        viario_gj = {**viario_gj, "conexo": bool(vdiag.get("conexo")),
                     "trechos": vdiag.get("trechos"), "hierarquia": vdiag.get("hierarquia")}
    idiag = layout.institucional_diagnostico or {}
    inst_gj = _gj(layout.institucional)
    if inst_gj is not None:
        inst_gj = {**inst_gj, "frente_via_m": idiag.get("frente_via_m"),
                   "circulo_inscrito_m": idiag.get("circulo_inscrito_m"),
                   "declividade_pct": idiag.get("declividade_pct"),
                   "qualifica_legal": bool(idiag.get("qualifica_legal"))}
    cdiag = layout.sistema_lazer_diagnostico or {}
    lazer_gj = _gj(layout.sistema_lazer)
    if lazer_gj is not None:
        lazer_gj = {**lazer_gj, "forma": cdiag.get("forma", "quadra"),
                    "frente_via_m": cdiag.get("frente_via_m")}

    return {
        "rotulo": "esquemático",
        "lotes_features": {"type": "FeatureCollection", "features": feats},  # 9.5 — lote a lote
        "lotes": _gj(_uniao(layout.lotes)) if layout.lotes else None,  # fundido (compat)
        "quadras": {"type": "FeatureCollection", "features": quadras_feats},  # 9.7 — faces
        "arruamento": viario_gj,  # 9.7 — malha conexa (não mais subtração)
        # Fase 9.6 — verde separado p/ o mapa: bloco reservado (destaque) × sobra de ponta
        # (discreto); ``areas_verdes`` (total) é o que o quadro/conformidade usam (idêntico).
        "areas_verdes": _gj(layout.areas_verdes),
        "areas_verdes_reservada": _gj(layout.areas_verdes_reservada),
        "areas_verdes_sobra": _gj(layout.sobra_ponta),
        "sistema_lazer": lazer_gj,  # 9.7 — figura formada (forma=quadra), não círculo
        "institucional": inst_gj,  # 9.7 — quadra formada (qualifica_legal + checks)
        "viario_diagnostico": vdiag,
        "institucional_diagnostico": idiag,
        # Fase 9.8 — restrição recortada (mata/declividade/APP) p/ o mapa rotular (não "clarão").
        "restricao_recortada": _restricao_gj(layout, to_wgs),
    }


def _restricao_gj(layout: "Layout", to_wgs) -> Optional[dict]:
    """A restrição que o motor recortou (não loteou) → GeoJSON rotulado p/ o mapa. ``None`` se
    não houve restrição (não inventa). Apresentação: o número/cálculo vive nos cards ambientais."""
    g = layout.restricao_recortada
    if g is None or g.is_empty:
        return None
    gj = mapping(transform(to_wgs, g))
    gj = dict(gj)
    gj["origem"] = list(layout.restricao_origem)
    gj["rotulo"] = (
        "Área não-edificável (mata/declividade/APP) — ver cards Ambiental/Vegetação/Declividade"
    )
    # Fase 9.13 — dica de APRESENTAÇÃO p/ o front: a restrição é mostrada DISCRETA (hachura/contorno
    # esmaecido, ao fundo), não bloco sólido que compete com o parcelamento. O dado não muda.
    gj["estilo_sugerido"] = "hachura_discreta"
    return gj


# ----------------------------- fidelidade (Fase 9.1) -----------------------------
TOL_CONVERGENCIA_PP = 0.03


def construir_fidelidade(med: "Medicao", layout: "Layout") -> dict:
    """Compara o quadro MEDIDO com o programa proposto (alvos em ``layout.meta``): convergência
    por item (lazer/institucional) com tolerância ou degradação rotulada + estado de viário e
    topografia. Determinístico — só leitura do que já foi medido (§2)."""
    q = med.quadro
    liq = q["area_liquida_m2"] or 1.0
    m = layout.meta or {}
    # Fidelidade do lazer usa a RESERVA original (9.4): a sobra de ponta anexada ao verde
    # entra no quadro/doação, mas NÃO conta como "lazer materializado" do programa.
    lazer_m = m.get("lazer_reservado_pct")
    if lazer_m is None:
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


# ----------------------------- distribuição de tamanhos (Fase 9.3) -----------------------------
def _pearson(xs: list[float], ys: list[float]) -> float:
    """Correlação de Pearson (0 se variância nula). Determinístico — usada só p/ REPORTAR o
    desacoplamento tamanho×score (não é meta)."""
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


def distribuicao_tamanhos(med: "Medicao", layout: "Layout") -> dict:
    """Distribuição dos tamanhos de lote (média/desvio/cv + histograma por faixa de área),
    retalho e % viário. O tamanho EMERGE da subdivisão da quadra (Fase 9.3) — aqui só se MEDE.
    Reporta a correlação tamanho×score apenas como prova de DESACOPLAMENTO (não é meta)."""
    por_lote = med.heatmap.get("por_lote", [])
    quadras = layout.lote_quadra or []
    lados = [_lados_mrr(g) for g in layout.lotes if g is not None and not g.is_empty]
    n = len(por_lote)
    lotes_out, areas, scores = [], [], []
    for i, p in enumerate(por_lote):
        testada, prof = (lados[i] if i < len(lados) else (0.0, 0.0))
        lotes_out.append({
            "lote_id": p["lote_id"], "area_m2": p["area_m2"], "testada_m": testada,
            "profundidade_m": prof, "score": p["score"],
            "quadra_id": quadras[i] if i < len(quadras) else None,
        })
        areas.append(p["area_m2"])
        scores.append(p["score"])

    media = round(sum(areas) / n, 2) if n else 0.0
    if n >= 2:
        var = sum((a - media) ** 2 for a in areas) / n
        desvio = round(math.sqrt(var), 2)
    else:
        desvio = 0.0
    cv = round(desvio / media, 4) if media else 0.0

    # Histograma por faixas de 50 m² do mínimo ao máximo (até ~8 baldes) — vê massa e cauda.
    faixas = []
    if areas:
        lo = int(min(areas) // 50 * 50)
        hi = int(max(areas) // 50 * 50 + 50)
        passo = 50 if (hi - lo) <= 400 else int(((hi - lo) / 8) // 50 * 50 or 50)
        b = lo
        while b < hi:
            cont = sum(1 for a in areas if b <= a < b + passo)
            if cont:
                faixas.append({"de": b, "ate": b + passo, "n": cont,
                               "pct": round(cont / n, 4) if n else 0.0})
            b += passo

    liq = med.quadro["area_liquida_m2"] or 1.0
    retalho = float(layout.meta.get("sobra_retalho_m2", 0.0))
    # Fase 9.4 — clamp legal: nº de lotes FORA da faixa [piso, teto] (deve ser 0 por construção).
    piso = float(layout.meta.get("piso_lote_m2", 0.0))
    teto = float(layout.meta.get("teto_lote_m2", 1e12))
    fora = sum(1 for a in areas if a < piso - 0.5 or a > teto + 0.5)
    return {
        "media_m2": media,
        "desvio_m2": desvio,
        "cv": cv,
        "min_m2": round(min(areas), 2) if areas else 0.0,
        "max_m2": round(max(areas), 2) if areas else 0.0,
        "fora_da_faixa": fora,
        "faixas": faixas,
        "correlacao_tamanho_score": round(_pearson(areas, scores), 3),
        "retalho_perdido_m2": round(retalho, 2),
        "retalho_perdido_pct": round(retalho / liq, 4),
        "viario_pct": med.quadro["arruamento"]["pct_apo"],
        "lote_alvo_origem": layout.meta.get("lote_alvo_origem", ""),
        "faixa_lote_m2": layout.meta.get("faixa_lote_m2", []),
        "lotes": lotes_out,
    }


def reconciliacao_urbanismo(med: "Medicao", lotes_teto=None) -> dict:
    """PONTE (Fase 9.10) — APRESENTAÇÃO, zero cálculo novo: rotula o ESTUDO geométrico e cita o
    teto regulatório. Números JÁ medidos: n_lotes, mediana do lote, doação DESENHADA (mesma do
    quadro/conformidade). ``lotes_teto`` vem da aba Aproveitamento (mesma fórmula/cenário) —
    ``None`` se indisponível (convite, não inventa). §1-A: 'estudo/estimativa/verificar'."""
    q = med.quadro
    liq = q["area_liquida_m2"] or 1.0
    doa = round((q["areas_verdes"]["m2"] + q["sistema_lazer"]["m2"]
                 + q["institucional"]["m2"] + q["arruamento"]["m2"]) / liq, 4)
    areas = sorted(p["area_m2"] for p in med.heatmap.get("por_lote", []) if p.get("area_m2"))
    mediana = round(areas[len(areas) // 2], 2) if areas else 0.0
    n = med.indicadores["n_lotes"]
    base = (
        f"Estudo de massa geométrico — lotes do perfil (~{_fmt(mediana)} m²), doação desenhada "
        f"(~{_fmt(doa * 100, 1)}%), vias conectadas e áreas públicas formadas, contornando a área "
        "não-edificável."
    )
    if lotes_teto is not None:
        ref = {"fonte": "aproveitamento", "lotes": int(lotes_teto)}
        leitura = base + (
            f" Teto regulatório da zona: ~{int(lotes_teto)} lotes (aba Aproveitamento), assumindo "
            "lote mínimo e doação mínima. Verificar com urbanista."
        )
    else:
        ref = None
        leitura = base + (
            " Rode o Aproveitamento com a zona declarada para ver o teto regulatório."
        )
    return {
        "papel": "estudo_geometrico",
        "lotes_estudo": int(n),
        "lote_mediano_m2": mediana,
        "doacao_desenhada_pct": doa,
        "ref_teto_regulatorio": ref,
        "leitura": leitura,
    }


def conformidade_legal(med: "Medicao", layout: "Layout", diretrizes: dict) -> list[dict]:
    """Confronta o que foi MEDIDO com os MÍNIMOS do município (LUOS/1.8) + piso federal. Mede,
    não decide (§1-A): cada item recebe atende / atende_com_folga / não_atende / não_avaliado."""
    q = med.quadro
    liq = q["area_liquida_m2"] or 1.0
    areas = [g.area for g in layout.lotes if g is not None and not g.is_empty]
    itens: list[dict] = []

    def _status(medido, exigido):
        if exigido is None:
            return "nao_avaliado"
        if medido + 1e-6 < exigido:
            return "nao_atende"
        return "atende_com_folga" if medido > exigido * 1.25 + 1e-9 else "atende"

    # lote mínimo (piso efetivo) — o menor lote medido ≥ piso?
    piso = float(diretrizes.get("piso_lote_efetivo_m2", 125.0))
    exig_lote = diretrizes.get("lote_min_zona_m2") or 125.0
    min_lote = round(min(areas), 2) if areas else 0.0
    itens.append({
        "item": "lote_minimo", "exigido": round(exig_lote, 2), "medido": min_lote,
        "unidade": "m2", "status": _status(min_lote, exig_lote),
        "leitura": f"menor lote {_fmt(min_lote)} m² — piso efetivo {_fmt(piso)} m² "
                   f"(zona {_fmt(exig_lote)} m² / federal 125 m²).",
    })

    # doação total (verde + institucional + viário) × mínimo do município.
    doa_med = round((q["areas_verdes"]["m2"] + q["sistema_lazer"]["m2"]
                     + q["institucional"]["m2"] + q["arruamento"]["m2"]) / liq, 4)
    doa_exig = diretrizes.get("doacao_min_pct")
    itens.append({
        "item": "doacao", "exigido": doa_exig, "medido": doa_med, "unidade": "pct",
        "status": _status(doa_med, doa_exig),
        "leitura": f"doação medida {_fmt(doa_med * 100, 1)}% (viário+verde+lazer+institucional)"
                   + (f" — mínimo {_fmt((doa_exig or 0) * 100, 1)}%." if doa_exig is not None
                      else " — mínimo não confirmado na LUOS."),
    })

    split = diretrizes.get("doacao_split") or {}
    # Quando a LUOS confirma a DOAÇÃO TOTAL mas não detalha o split → texto explica (não "vago").
    _sem_split = (
        f" — a LUOS confirma a doação total ({_fmt((doa_exig or 0) * 100, 1)}%), mas não "
        "detalha o split verde/institucional; verificar na prefeitura."
        if doa_exig is not None else " — mínimo do município não confirmado na LUOS."
    )
    verde_med = round((q["areas_verdes"]["m2"] + q["sistema_lazer"]["m2"]) / liq, 4)
    itens.append({
        "item": "area_verde", "exigido": split.get("verde"), "medido": verde_med,
        "unidade": "pct", "status": _status(verde_med, split.get("verde")),
        "leitura": f"verde/lazer medido {_fmt(verde_med * 100, 1)}%"
                   + (f" — mínimo {_fmt((split.get('verde') or 0) * 100, 1)}%."
                      if split.get("verde") is not None else _sem_split),
    })
    inst_med = round(q["institucional"]["m2"] / liq, 4)
    itens.append({
        "item": "institucional", "exigido": split.get("institucional"), "medido": inst_med,
        "unidade": "pct", "status": _status(inst_med, split.get("institucional")),
        "leitura": f"institucional medido {_fmt(inst_med * 100, 1)}%"
                   + (f" — mínimo {_fmt((split.get('institucional') or 0) * 100, 1)}%."
                      if split.get("institucional") is not None else _sem_split),
    })
    return itens
