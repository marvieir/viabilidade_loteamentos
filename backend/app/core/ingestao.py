"""Camada de ingestão de geometria (Fase 1.5) — classifica o arquivo por CONTEÚDO.

Adaptador a montante do motor de geometria (que permanece puro: Polygon entra → área
sai). Decide, de forma determinística e sem inventar, entre três rotas:

  POLYGON_DIRETO  — ≥1 <Polygon>: usa direto (vários → o maior, com aviso no router).
  LINHA_FECHAVEL  — exatamente 1 <LineString> simples, fechada ou com gap ≤ tolerância:
                    fecha (declarando o gap) e converte em polígono.
  TOPOGRAFIA_CAD  — demais casos sem polígono (multi-linha, linha aberta além da
                    tolerância, auto-intersectada): recusa COM DIAGNÓSTICO → Fase 1.6.

Regras invioláveis: nunca fechar linha em silêncio (sempre declarar o gap); nunca
adivinhar qual linha é o perímetro quando há várias; recusa sempre diagnóstica.
"""

from dataclasses import dataclass, field

from pyproj import Geod
from shapely.geometry import LineString, Polygon

from app.core import kmz

_GEOD = Geod(ellps="WGS84")

# Tolerância de fechamento automático de linha (metros). Configurável por chamada.
TOLERANCIA_FECHAMENTO_M = 1.0

ORIENTACAO = (
    "Exporte a gleba como polígono fechado (uma feição <Polygon>), "
    "ou aguarde a importação assistida de topografia (fase futura)."
)


@dataclass
class Ingestao:
    """Resultado da ingestão: sucesso (com polígonos) ou recusa (com diagnóstico)."""

    ok: bool
    rota: str
    descricao: str = ""
    poligonos: list[Polygon] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)
    # apenas em recusa:
    erro: str | None = None
    diagnostico: dict | None = None
    orientacao: str | None = None


def _fmt_tol(tol: float) -> str:
    # exibe a tolerância no padrão pt-BR ("1,0 m")
    return f"{tol:.1f}".replace(".", ",")


def _gap_m(coords: list[tuple[float, float]]) -> float:
    """Distância geodésica entre o primeiro e o último ponto da linha (metros)."""
    (lon1, lat1), (lon2, lat2) = coords[0], coords[-1]
    _, _, dist = _GEOD.inv(lon1, lat1, lon2, lat2)
    return dist


def _recusa(
    rota: str, motivo: str, detalhe: str, n_poly: int, n_lin: int, n_pts: int
) -> Ingestao:
    diag = {
        "n_poligonos": n_poly,
        "n_linhas": n_lin,
        "motivo": motivo,
        "detalhe": detalhe,
    }
    if n_pts:
        diag["n_pontos"] = n_pts
    return Ingestao(
        ok=False,
        rota=rota,
        erro="geometria_nao_ingerivel",
        diagnostico=diag,
        orientacao=ORIENTACAO,
    )


def _linha_unica(
    coords: list[tuple[float, float]],
    n_poly: int,
    n_lin: int,
    n_pts: int,
    tolerancia_m: float,
) -> Ingestao:
    linha = LineString(coords)
    # auto-interseção tem precedência: não dá para fechar de forma confiável.
    if not linha.is_simple:
        return _recusa(
            "TOPOGRAFIA_CAD",
            "auto_intersecao",
            "linha única auto-intersectada (não simples)",
            n_poly,
            n_lin,
            n_pts,
        )

    fechada = coords[0] == coords[-1]
    if fechada:
        anel = coords
        descricao = "linha já fechada do arquivo (anel)"
        avisos: list[str] = []
    else:
        gap = _gap_m(coords)
        if gap > tolerancia_m:
            return _recusa(
                "TOPOGRAFIA_CAD",
                "linha_aberta",
                f"linha única aberta: gap de {gap:.2f} m > {_fmt_tol(tolerancia_m)} m",
                n_poly,
                n_lin,
                n_pts,
            )
        anel = [*coords, coords[0]]
        descricao = (
            f"linha fechada automaticamente (gap = {gap:.2f} m "
            f"≤ {_fmt_tol(tolerancia_m)} m)"
        )
        avisos = [
            f"Linha fechada automaticamente: gap de {gap:.2f} m "
            f"(≤ {_fmt_tol(tolerancia_m)} m de tolerância)."
        ]

    poly = Polygon(anel)
    if poly.is_empty or not poly.is_valid or poly.area == 0:
        # linha simples mas não forma polígono de área (poucos vértices, degenerada).
        return _recusa(
            "TOPOGRAFIA_CAD",
            "auto_intersecao",
            "linha única não forma um polígono válido",
            n_poly,
            n_lin,
            n_pts,
        )

    return Ingestao(
        ok=True,
        rota="LINHA_FECHAVEL",
        descricao=descricao,
        poligonos=[poly],
        avisos=avisos,
    )


def _reparar_poligonos(poligonos: list[Polygon]) -> tuple[list[Polygon], bool, list[str]]:
    """Repara <Polygon> auto-interseccionados via ``buffer(0)`` — determinístico e (no caso
    típico de export de CAD) preservando a área. Decisão do operador (Fase 1.8): reparar com
    AVISO em vez de recusar. Polígono já válido passa intacto; reparo que não produz polígono
    válido é mantido como veio → o motor recusa adiante (422 honesto). Multipolígono resultante
    (auto-interseção ambígua) → maior parte, com aviso explícito.

    Devolve ``(poligonos, reparou, avisos)``.
    """
    out: list[Polygon] = []
    reparados = 0
    avisos: list[str] = []
    for p in poligonos:
        if not p.is_empty and p.is_valid:
            out.append(p)
            continue
        rep = p.buffer(0)  # buffer 0 = limpeza topológica (distância 0; vale em graus)
        if rep.is_empty or not rep.is_valid:
            out.append(p)  # não deu para reparar → segue inválido (recusa diagnóstica adiante)
            continue
        if rep.geom_type == "MultiPolygon":
            rep = max(rep.geoms, key=lambda g: g.area)
            avisos.append(
                "Auto-interseção dividiu o polígono na correção; usada a MAIOR parte — "
                "confira o traçado no mapa."
            )
        out.append(rep)
        reparados += 1
    if reparados:
        avisos.insert(
            0,
            f"{reparados} polígono(s) com auto-interseção corrigido(s) automaticamente "
            "(buffer 0). Confira o traçado no mapa antes de confiar nos números.",
        )
    return out, reparados > 0, avisos


def ingerir(
    conteudo: bytes, tolerancia_m: float = TOLERANCIA_FECHAMENTO_M
) -> Ingestao:
    """Classifica o arquivo e devolve a rota com polígono(s) ou um diagnóstico.

    Pode levantar ``kmz.KmzInvalido`` (arquivo ilegível/malformado) — o router mapeia
    isso para 422 genérico, distinto da recusa diagnóstica de TOPOGRAFIA_CAD.
    """
    conteudo_kml = kmz.ler_conteudo(conteudo)
    n_poly = len(conteudo_kml.poligonos)
    n_lin = len(conteudo_kml.linhas)
    n_pts = conteudo_kml.n_pontos

    if n_poly >= 1:
        poligonos, reparou, avisos = _reparar_poligonos(conteudo_kml.poligonos)
        return Ingestao(
            ok=True,
            rota="POLYGON_REPARADO" if reparou else "POLYGON_DIRETO",
            descricao=(
                "polígono corrigido (auto-interseção) do arquivo"
                if reparou
                else "polígono direto do arquivo"
            ),
            poligonos=poligonos,
            avisos=avisos,
        )

    if n_lin == 1:
        return _linha_unica(
            conteudo_kml.linhas[0], n_poly, n_lin, n_pts, tolerancia_m
        )

    if n_lin >= 2:
        return _recusa(
            "TOPOGRAFIA_CAD",
            "multiplas_linhas",
            f"arquivo de topografia/CAD: {n_lin} linhas, {n_poly} polígonos",
            n_poly,
            n_lin,
            n_pts,
        )

    # Sem polígono e sem linha: nenhuma geometria de perímetro (pode ter só pontos).
    detalhe = f"nenhuma geometria de perímetro: {n_poly} polígonos, {n_lin} linhas"
    if n_pts:
        detalhe += f", {n_pts} pontos"
    return _recusa("SEM_GEOMETRIA", "sem_geometria", detalhe, n_poly, n_lin, n_pts)
