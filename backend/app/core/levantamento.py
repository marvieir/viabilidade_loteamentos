"""Fase U9 — LEVANTAMENTO PLANIALTIMÉTRICO como fonte de topografia (curvas de nível REAIS).

O DEM de satélite (Copernicus 30 m) é grosseiro → curvas serrilhadas → traçado com cara de banda
reta. Quando o operador anexa o levantamento do agrimensor (curvas de 1/5 m), estas curvas — lisas
e precisas — SUBSTITUEM as do DEM como guia do traçado (ruas seguem a cota de verdade, estilo Urbia).

Formato: **DXF** (lido nativo por ``ezdxf``). DWG precisa ser convertido antes (o `.dxf` é o mesmo
dado; o agrimensor entrega os dois). Degrada honesto: DXF ilegível / sem camada de curva → None, e o
motor cai para o DEM (nunca quebra a geração). Georreferenciado em UTM → reprojeta p/ o frame métrico
do motor (mesmo ``to_local`` das outras camadas), então casa com a gleba sem alinhamento manual.

§1/§2: geometria e reprojeção em Python puro; nenhum número vem do LLM.
"""

from __future__ import annotations

from typing import Callable, Optional, Sequence

from pyproj import Transformer
from shapely.geometry import LineString
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform as shapely_transform

# Palavras que identificam a camada de curva de nível (varia por agrimensor). Casa "MDT1_CURVAS",
# "CURVAS_NIVEL", "CURVA DE NIVEL", etc.; exige a raiz "CURVA"/"NIVEL"/"MDT" p/ não pegar legenda.
_CHAVES_CAMADA = ("CURVA", "NIVEL", "NÍVEL", "MDT")
# SIRGAS 2000 / UTM 23S (São Roque, MC 45°). Parametrizável p/ outras zonas.
_EPSG_PADRAO = 31983
_L_MIN_CURVA_M = 20.0  # curva mais curta que isso é ruído (rótulo, marco) — descarta


def _pontos_da_entidade(e) -> list[tuple[float, float]]:
    """Extrai os vértices XY de uma entidade DXF de curva (SPLINE/LWPOLYLINE/POLYLINE/LINE)."""
    t = e.dxftype()
    try:
        if t == "SPLINE":
            return [(p[0], p[1]) for p in e.flattening(0.8)]
        if t == "LWPOLYLINE":
            return [(p[0], p[1]) for p in e.get_points("xy")]
        if t in ("POLYLINE", "POLYLINE3D"):
            return [(v.dxf.location.x, v.dxf.location.y) for v in e.vertices]
        if t == "LINE":
            return [(e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y)]
    except Exception:  # noqa: BLE001 — entidade degenerada → ignora
        return []
    return []


def extrair_contornos_dxf(
    caminho_dxf: str,
    to_local: Callable[[float, float], tuple[float, float]],
    dentro: Optional[BaseGeometry] = None,
    epsg_origem: int = _EPSG_PADRAO,
) -> list[LineString]:
    """Curvas de nível do levantamento (DXF), reprojetadas para o frame MÉTRICO do motor.

    - ``to_local``: transform (lon, lat) → x, y métrico local (o mesmo do resto do urbanismo).
    - ``dentro``: recorta as curvas à área aproveitável (opcional).
    - ``epsg_origem``: CRS do levantamento (default SIRGAS/UTM 23S).
    Devolve lista de ``LineString`` (vazia se o DXF não tiver camada de curva — degrada honesto)."""
    try:
        import ezdxf
    except ImportError:
        return []
    try:
        doc = ezdxf.readfile(caminho_dxf)
    except Exception:  # noqa: BLE001 — DXF ilegível/corrompido → degrada p/ o DEM
        return []

    utm_para_wgs = Transformer.from_crs(epsg_origem, 4326, always_xy=True).transform

    def para_local(x: float, y: float, z: float = 0.0):
        lon, lat = utm_para_wgs(x, y)
        mx, my = to_local(lon, lat)
        return (mx, my)

    curvas: list[LineString] = []
    for e in doc.modelspace():
        camada = (e.dxf.layer or "").upper()
        if not any(k in camada for k in _CHAVES_CAMADA):
            continue
        pts = _pontos_da_entidade(e)
        if len(pts) < 2:
            continue
        try:
            ls = LineString(pts)
            ls_local = shapely_transform(para_local, ls)
        except Exception:  # noqa: BLE001
            continue
        if dentro is not None and not dentro.is_empty:
            inter = ls_local.intersection(dentro)
            partes = inter.geoms if inter.geom_type == "MultiLineString" else [inter]
        else:
            partes = [ls_local]
        for parte in partes:
            if parte.geom_type == "LineString" and parte.length >= _L_MIN_CURVA_M:
                curvas.append(parte)
    return curvas


def espacar_uniforme(curvas: Sequence[LineString], orientacao_rad: float,
                     passo: int = 2) -> list[LineString]:
    """Afina as curvas p/ ruas espaçadas uniformemente: ordena DESCENDO a encosta (projeção no
    gradiente = perpendicular à cota) e mantém 1 a cada ``passo``. Evita o viário inchado de curvas
    coladas e a cobertura irregular (buraco → grade). ``passo=1`` mantém todas."""
    import math

    if passo <= 1 or len(curvas) <= 2:
        return list(curvas)
    gx, gy = -math.sin(orientacao_rad), math.cos(orientacao_rad)
    ordenadas = sorted(curvas, key=lambda c: c.centroid.x * gx + c.centroid.y * gy)
    return [c for i, c in enumerate(ordenadas) if i % passo == 0]
