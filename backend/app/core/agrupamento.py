"""Agrupamento de glebas vizinhas (Fase 8) — união geométrica determinística.

Adaptador a MONTANTE do pipeline (espírito da ingestão, §4-A): recebe geometrias já
parseadas (cada uma pela ingestão existente) e decide, sem inventar, entre **uma união
válida** (vira a geometria da análise) ou uma **recusa diagnóstica**. As dimensões a
jusante não sabem que a gleba veio de vários arquivos — recebem um Polygon como sempre.

Regra (§3 da spec), puramente topológica + tolerância de encosto:
  1. município comum (detecção a cargo do chamador); divergiu → MUNICIPIOS_DIFERENTES.
  2. interiores se cruzam (overlap parcial OU containment) → GLEBAS_SOBREPOSTAS.
  3. ``unary_union`` é Polygon único → ACEITA (compartilham fronteira-linha).
  4. união é MultiPolygon (desconexo) → tenta pontar folga ≤ tolerância (encosto de
     digitalização); se ainda desconexo → GLEBAS_NAO_CONTIGUAS (distingue vão de toque
     em ponto).

Sem LLM, sem rede — geometria pura. As unidades de ``tolerancia`` e das áreas/distâncias
no diagnóstico são as do CRS das geometrias recebidas (o router reprojeta para metros).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Sequence

from shapely.geometry import Polygon
from shapely.ops import snap, unary_union

# Erros nomeados (o router mapeia para 422 com corpo estruturado).
ERRO_NAO_CONTIGUAS = "GLEBAS_NAO_CONTIGUAS"
ERRO_SOBREPOSTAS = "GLEBAS_SOBREPOSTAS"
ERRO_MUNICIPIOS = "MUNICIPIOS_DIFERENTES"

# Tolerância numérica para "interiores se cruzam" (descarta toque de borda/ponto, que tem
# área de interseção nula). Bem abaixo de qualquer sobreposição real.
_EPS_AREA = 1e-9


@dataclass
class Agrupamento:
    """Resultado: união aceita (``ok=True``) ou recusa diagnóstica (``ok=False``)."""

    ok: bool
    uniao: Optional[Polygon] = None
    n_glebas: int = 0
    fronteira: Optional[str] = None  # "compartilhada" quando aceito
    tolerancia: float = 0.0
    encostou: bool = False  # True se a folga ≤ tolerância foi pontada (encosto)
    # apenas em recusa:
    erro: Optional[str] = None
    detalhe: Optional[str] = None
    diagnostico: dict = field(default_factory=dict)


def _aceita(uniao: Polygon, n: int, tol: float, encostou: bool = False) -> Agrupamento:
    return Agrupamento(
        ok=True,
        uniao=uniao,
        n_glebas=n,
        fronteira="compartilhada",
        tolerancia=tol,
        encostou=encostou,
    )


def _pontar(geoms: Sequence[Polygon], tol: float):
    """Tenta fechar folgas ≤ ``tol`` ENTRE ARESTAS quase-coincidentes (encosto de
    digitalização) via ``snap`` vértice-a-vértice. NÃO ponta toque em ponto (os vértices
    já coincidem; não há aresta a criar) — então criterion 4 (toque em ponto) continua
    recusado. Devolve a geometria pontada (Polygon se uniu; MultiPolygon se não)."""
    base = unary_union(list(geoms))
    snapped = [snap(g, base, tol) for g in geoms]
    return unary_union(snapped)


def _min_gap(geoms: Sequence[Polygon]) -> float:
    """Menor distância entre as bordas de qualquer par (unidades do CRS)."""
    n = len(geoms)
    dists = [
        geoms[i].distance(geoms[j])
        for i in range(n)
        for j in range(i + 1, n)
    ]
    return min(dists) if dists else 0.0


def _toque_em_ponto(geoms: Sequence[Polygon]) -> bool:
    """Algum par encosta APENAS num ponto (fronteira de comprimento zero)."""
    n = len(geoms)
    for i in range(n):
        for j in range(i + 1, n):
            if geoms[i].touches(geoms[j]) and geoms[i].intersection(geoms[j]).length == 0:
                return True
    return False


def agrupar(
    geoms: Sequence[Polygon],
    municipios: Optional[Sequence[Optional[str]]] = None,
    tolerancia: float = 0.0,
) -> Agrupamento:
    """Une glebas contíguas do mesmo município, ou recusa com diagnóstico.

    ``geoms`` são polígonos já válidos (parseados pela ingestão). ``municipios`` é a lista
    de ``cod_ibge`` detectados (alinhada a ``geoms``); ``None`` numa posição = não detectado
    (não dispara divergência). ``tolerancia`` é a folga de encosto (mesma da ingestão), nas
    unidades do CRS de ``geoms``.
    """
    n = len(geoms)
    if n == 0:
        return Agrupamento(
            ok=False,
            n_glebas=0,
            tolerancia=tolerancia,
            erro=ERRO_NAO_CONTIGUAS,
            detalhe="nenhuma geometria para agrupar",
            diagnostico={"motivo": "vazio"},
        )

    # 1. Mesmo município (a detecção é do chamador). Divergência → recusa antes de geometria.
    if municipios is not None:
        distintos = sorted({m for m in municipios if m})
        if len(distintos) > 1:
            return Agrupamento(
                ok=False,
                n_glebas=n,
                tolerancia=tolerancia,
                erro=ERRO_MUNICIPIOS,
                detalhe=(
                    "glebas em municípios diferentes — só agrupamos áreas do mesmo "
                    "município"
                ),
                diagnostico={"municipios": distintos},
            )

    # 2. Sobreposição: interiores se cruzam (cobre overlap parcial e containment).
    for i in range(n):
        for j in range(i + 1, n):
            inter = geoms[i].intersection(geoms[j])
            if inter.area > _EPS_AREA:
                return Agrupamento(
                    ok=False,
                    n_glebas=n,
                    tolerancia=tolerancia,
                    erro=ERRO_SOBREPOSTAS,
                    detalhe=(
                        "glebas se sobrepõem (área em duplicidade) — verifique os arquivos"
                    ),
                    diagnostico={"sobreposicao": inter.area, "par": [i, j]},
                )

    # 3. Contiguidade: união é polígono único?
    uniao = unary_union(list(geoms))
    if uniao.geom_type == "Polygon":
        return _aceita(uniao, n, tolerancia)

    # 4. Desconexo: tentar pontar folga ≤ tolerância (encosto), exceto toque em ponto.
    if tolerancia > 0:
        pontado = _pontar(geoms, tolerancia)
        if pontado.geom_type == "Polygon":
            return _aceita(pontado, n, tolerancia, encostou=True)

    # 5. Recusa: distinguir toque em ponto de vão real (mensagem diagnóstica).
    if _toque_em_ponto(geoms):
        return Agrupamento(
            ok=False,
            n_glebas=n,
            tolerancia=tolerancia,
            erro=ERRO_NAO_CONTIGUAS,
            detalhe=(
                "glebas não são contíguas (apenas tocam em um ponto) — só agrupamos "
                "áreas com fronteira comum"
            ),
            diagnostico={"motivo": "toque_em_ponto"},
        )
    gap = _min_gap(geoms)
    return Agrupamento(
        ok=False,
        n_glebas=n,
        tolerancia=tolerancia,
        erro=ERRO_NAO_CONTIGUAS,
        detalhe=(
            "glebas não são contíguas (há vão entre elas) — só agrupamos áreas com "
            "fronteira comum"
        ),
        diagnostico={"motivo": "vao", "gap": gap},
    )
