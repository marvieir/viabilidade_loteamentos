"""AMB-EXC — RECONCILIAÇÃO pós-vistoria: aplica os FATOS do laudo às manchas (incremento 3).

O laudo declara (estágio na Mata Atlântica; formação no Pampa/geral; achados de campo); a
consequência vem da régua (``ambiental_regua``) e vira EFEITO GEOMÉTRICO determinístico:

  - liberada/autorização → a mancha sai da restrição de vegetação (SOB PREMISSA rotulada:
    vale se o órgão autorizar — a plataforma nunca autoriza);
  - preservar ≥ pct → a mancha é DIVIDIDA: a fração legal fica restrita ("preservação
    obrigatória", rotulada com o artigo) e o restante é liberado. Corte determinístico no
    eixo longo do MRR; o lado preservado é o mais DISTANTE do centro da gleba (empurra a
    preservação para a borda — prática de fundo de mata; traçado esquemático, o projeto
    executivo define a poligonal exata);
  - vedada → nada muda (a mancha segue restrita), registrado no resumo;
  - achado de campo (banhado/nascente/…) → NOVA restrição com base legal, ∩ gleba.

Sentidos + e − no mesmo ato (bidirecional, como o operador descreveu). Determinístico
(regra 4); toda linha carrega proveniência (regra 3).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

from pyproj import CRS, Transformer
from shapely.geometry import mapping, shape
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform, unary_union

from app.core import ambiental_regua as regua
from app.core.ambiental_manchas import Mancha

ACAO_AJUSTE_ESTAGIO = "estagio"        # Mata Atlântica: declara o estágio
ACAO_AJUSTE_FORMACAO = "formacao"      # Pampa/geral: declara a formação
ACAO_AJUSTE_RESTRICAO = "nova_restricao"  # achado de campo (banhado/nascente/…)


@dataclass(frozen=True)
class AjusteLaudo:
    """Um ajuste declarado pelo laudo (entrada da reconciliação)."""

    acao: str                                # ACAO_AJUSTE_*
    mancha_id: Optional[str] = None          # p/ estagio/formacao
    assinatura: Optional[str] = None         # confere contra a mancha atual (drift do insumo)
    estagio: Optional[str] = None            # regua.ESTAGIOS_MA
    formacao: Optional[str] = None           # regua.FORMACOES_GERAIS
    tipo_restricao: Optional[str] = None     # banhado | nascente | app_curso_dagua | outro
    geojson: Optional[dict] = None           # p/ nova_restricao (WGS84)
    observacao: str = ""


@dataclass(frozen=True)
class ItemReconciliado:
    item_id: str            # "M1".."Mn" ou "R1".."Rn"
    area_m2: float
    decisao: str            # rótulo do fato declarado (estágio/formação/tipo)
    acao: str               # regua.ACAO_* ou "restricao_campo"
    base_legal: str
    leitura: str
    efeito_m2: float        # + libera aproveitável · − restringe · 0 sem mudança
    preservacao_m2: float = 0.0


@dataclass
class Reconciliacao:
    itens: list[ItemReconciliado] = field(default_factory=list)
    liberadas_wgs: Optional[BaseGeometry] = None       # sai da restrição de vegetação
    preservacao_wgs: Optional[BaseGeometry] = None     # fica restrita (preservação legal)
    novas_restricoes_wgs: Optional[BaseGeometry] = None  # achados de campo (restrição nova)
    avisos: list[str] = field(default_factory=list)

    @property
    def saldo_m2(self) -> float:
        return round(sum(i.efeito_m2 for i in self.itens), 2)


def _crs_local(lon: float, lat: float) -> CRS:
    return CRS.from_proj4(
        f"+proj=aeqd +lat_0={lat} +lon_0={lon} +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs"
    )


def _dividir_preservacao(
    geom_l: BaseGeometry, pct: float, centro_gleba_l
) -> tuple[BaseGeometry, BaseGeometry]:
    """Divide a mancha em (preservada, liberada) com ``area(preservada) ≥ pct·area`` por corte
    perpendicular ao EIXO LONGO do MRR (busca binária na posição do corte — determinística).
    O lado preservado é o mais distante do centro da gleba."""
    from shapely.geometry import Polygon

    mrr = geom_l.minimum_rotated_rectangle
    pts = list(mrr.exterior.coords)[:-1]
    if len(pts) < 4:
        return geom_l, geom_l.difference(geom_l)  # degenerada: tudo preservado

    def d(a, b):
        return math.hypot(a[0] - b[0], a[1] - b[1])

    # eixo longo = par de lados maiores; u = direção do eixo, origem no canto 0.
    if d(pts[0], pts[1]) >= d(pts[1], pts[2]):
        a0, a1, b0, b1 = pts[0], pts[1], pts[3], pts[2]
    else:
        a0, a1, b0, b1 = pts[1], pts[2], pts[0], pts[3]

    def interp(p, q, t):
        return (p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t)

    def faixa(t0, t1) -> BaseGeometry:
        quad = Polygon([interp(a0, a1, t0), interp(a0, a1, t1),
                        interp(b0, b1, t1), interp(b0, b1, t0)])
        return geom_l.intersection(quad)

    # Qual ponta fica preservada? A mais distante do centro da gleba (fundo de mata).
    ponta_ini = faixa(0.0, 0.25).centroid
    ponta_fim = faixa(0.75, 1.0).centroid
    pres_no_fim = (ponta_fim.distance(centro_gleba_l) >= ponta_ini.distance(centro_gleba_l))

    alvo = pct * geom_l.area
    lo, hi = 0.0, 1.0
    for _ in range(40):  # busca binária determinística na posição do corte
        mid = (lo + hi) / 2.0
        pres = faixa(mid, 1.0) if pres_no_fim else faixa(0.0, mid)
        a = pres.area
        if pres_no_fim:  # corte mais à frente → preservada menor; buscamos o MAIOR corte válido
            lo, hi = (mid, hi) if a >= alvo else (lo, mid)
        else:            # corte mais à frente → preservada maior; buscamos o MENOR corte válido
            lo, hi = (lo, mid) if a >= alvo else (mid, hi)
    corte = (lo if pres_no_fim else hi)
    preservada = faixa(corte, 1.0) if pres_no_fim else faixa(0.0, corte)
    # buffer(0) sanea a aresta compartilhada do corte (sliver degenerado → inválida no GEOS).
    preservada = preservada.buffer(0)
    liberada = geom_l.difference(preservada).buffer(0)
    return preservada, liberada


def reconciliar(
    gleba: BaseGeometry,
    manchas: list[Mancha],
    ajustes: list[AjusteLaudo],
    regime: regua.RegimeAmbiental,
    perimetro_urbano_pre_lei: Optional[bool],
    uf: Optional[str],
) -> Reconciliacao:
    """Aplica os ajustes do laudo. Mancha não ajustada segue como está (restrita). Ajuste com
    assinatura divergente da mancha atual é RECUSADO com aviso (o insumo mudou — regenerar a
    tela de manchas antes de aplicar)."""
    c = gleba.centroid
    local = _crs_local(c.x, c.y)
    to_local = Transformer.from_crs("EPSG:4326", local, always_xy=True).transform
    to_wgs = Transformer.from_crs(local, "EPSG:4326", always_xy=True).transform
    gleba_l = transform(to_local, gleba)
    centro_l = gleba_l.centroid

    por_id = {m.mancha_id: m for m in manchas}
    rec = Reconciliacao()
    liberadas_l: list[BaseGeometry] = []
    preservadas_l: list[BaseGeometry] = []
    novas_l: list[BaseGeometry] = []
    n_restr = 0

    for aj in ajustes:
        # ---- achado de campo: nova restrição ----
        if aj.acao == ACAO_AJUSTE_RESTRICAO:
            if not aj.geojson:
                rec.avisos.append("Nova restrição sem geometria — ignorada.")
                continue
            try:
                g_wgs = shape(aj.geojson)
            except Exception:  # noqa: BLE001
                rec.avisos.append("Nova restrição com GeoJSON inválido — ignorada.")
                continue
            g_l = transform(to_local, g_wgs).intersection(gleba_l)
            if g_l.is_empty:
                rec.avisos.append("Nova restrição fora da gleba — ignorada.")
                continue
            n_restr += 1
            base = regua.base_restricao_campo(aj.tipo_restricao or "outro", uf)
            novas_l.append(g_l)
            rec.itens.append(ItemReconciliado(
                item_id=f"R{n_restr}", area_m2=round(g_l.area, 2),
                decisao=(aj.tipo_restricao or "restrição de campo"),
                acao="restricao_campo", base_legal=base,
                leitura="Restrição constatada em campo pelo laudo — não edificável.",
                efeito_m2=round(-g_l.area, 2),
            ))
            continue

        # ---- enquadramento de mancha ----
        m = por_id.get(aj.mancha_id or "")
        if m is None:
            rec.avisos.append(f"Ajuste para mancha inexistente ({aj.mancha_id}) — ignorado.")
            continue
        if aj.assinatura and aj.assinatura != m.assinatura:
            rec.avisos.append(
                f"{m.mancha_id}: assinatura divergente (o insumo de vegetação mudou desde a "
                "tela) — ajuste recusado; recarregue as manchas."
            )
            continue

        if regime.codigo == "mata_atlantica":
            if not aj.estagio:
                rec.avisos.append(f"{m.mancha_id}: estágio não informado — ignorado.")
                continue
            cons = regua.consequencia_mata_atlantica(aj.estagio, perimetro_urbano_pre_lei)
            decisao = aj.estagio
        else:
            if not aj.formacao:
                rec.avisos.append(f"{m.mancha_id}: formação não informada — ignorada.")
                continue
            cons = regua.consequencia_geral(aj.formacao, regime)
            decisao = aj.formacao
        rec.avisos.extend(cons.avisos)

        g_l = transform(to_local, m._geom_wgs)
        if cons.acao == regua.ACAO_VEDADA:
            efeito, pres_m2 = 0.0, 0.0
        elif cons.acao == regua.ACAO_PRESERVAR:
            pres, lib = _dividir_preservacao(g_l, float(cons.pct_preservar or 0.0), centro_l)
            preservadas_l.append(pres)
            if not lib.is_empty:
                liberadas_l.append(lib)
            efeito, pres_m2 = round(lib.area, 2), round(pres.area, 2)
        else:  # liberada / autorização — sob premissa rotulada
            liberadas_l.append(g_l)
            efeito, pres_m2 = round(g_l.area, 2), 0.0

        rec.itens.append(ItemReconciliado(
            item_id=m.mancha_id, area_m2=m.area_m2, decisao=decisao,
            acao=cons.acao, base_legal=cons.base_legal, leitura=cons.leitura,
            efeito_m2=efeito, preservacao_m2=pres_m2,
        ))

    def _back(parts: list[BaseGeometry]) -> Optional[BaseGeometry]:
        vivos = [p.buffer(0) for p in parts if p is not None and not p.is_empty]
        vivos = [p for p in vivos if not p.is_empty]
        if not vivos:
            return None
        return transform(to_wgs, unary_union(vivos)).buffer(0)

    rec.liberadas_wgs = _back(liberadas_l)
    rec.preservacao_wgs = _back(preservadas_l)
    rec.novas_restricoes_wgs = _back(novas_l)
    return rec


# ----------------------------- aplicação no aproveitável -----------------------------

def aplicar_no_verde(
    verde_wgs: Optional[BaseGeometry], reconciliacao_geojson: Optional[dict]
) -> tuple[Optional[BaseGeometry], Optional[BaseGeometry]]:
    """Aplica a reconciliação SALVA (dict do store) sobre a geometria de vegetação:
    devolve ``(verde_ajustado, restricoes_extras)``. Sem reconciliação → passthrough.

    ``verde_ajustado`` = verde − liberadas (a preservação obrigatória é SUBCONJUNTO do verde
    que não foi liberado — permanece dentro dele). ``restricoes_extras`` = achados de campo
    (tratar como APP: bloqueiam via e lote)."""
    if not reconciliacao_geojson:
        return verde_wgs, None
    lib_gj = reconciliacao_geojson.get("liberadas")
    novas_gj = reconciliacao_geojson.get("novas_restricoes")
    verde_aj = verde_wgs
    if verde_wgs is not None and lib_gj:
        try:
            verde_aj = verde_wgs.difference(shape(lib_gj))
        except Exception:  # noqa: BLE001 — geometria salva corrompida → não aplica (honesto)
            return verde_wgs, (shape(novas_gj) if novas_gj else None)
    novas = None
    if novas_gj:
        try:
            novas = shape(novas_gj)
        except Exception:  # noqa: BLE001
            novas = None
    return verde_aj, novas


def serializar(rec: Reconciliacao) -> dict:
    """Snapshot persistível (GeoJSON) — o que o store guarda e ``aplicar_no_verde`` lê."""
    return {
        "itens": [i.__dict__ for i in rec.itens],
        "saldo_m2": rec.saldo_m2,
        "avisos": list(rec.avisos),
        "liberadas": mapping(rec.liberadas_wgs) if rec.liberadas_wgs is not None else None,
        "preservacao": (mapping(rec.preservacao_wgs)
                        if rec.preservacao_wgs is not None else None),
        "novas_restricoes": (mapping(rec.novas_restricoes_wgs)
                             if rec.novas_restricoes_wgs is not None else None),
    }
