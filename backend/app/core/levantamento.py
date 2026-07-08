"""Fase U9 — LEVANTAMENTO PLANIALTIMÉTRICO como fonte de topografia (curvas de nível REAIS).

O DEM de satélite (Copernicus 30 m) é grosseiro → curvas serrilhadas → traçado com cara de banda
reta. Quando o operador anexa o levantamento do agrimensor (curvas de 1/5 m), estas curvas — lisas
e precisas — SUBSTITUEM as do DEM como guia do traçado (ruas seguem a cota de verdade, estilo Urbia).

Fluxo real: o levantamento (UTM/SIRGAS) e a gleba (do KMZ, WGS) estão AMBOS em coordenada de mundo,
então casam sozinhos — extraímos as curvas em WGS (armazenáveis, independentes de frame) e cada
análise reprojeta p/ o seu frame métrico (mesmo ``to_local`` das outras camadas). Sem alinhamento
manual. Degrada honesto: sem levantamento / DXF ilegível → o motor cai para o DEM (nunca quebra).

Formato: **DXF** (lido nativo por ``ezdxf``). **DWG** é convertido antes via ``dwg2dxf`` (libredwg,
se presente no PATH/bundle) — é o mesmo dado. §1/§2: geometria/reprojeção em Python puro, nada do LLM.
"""

from __future__ import annotations

import math
import os
import shutil
import subprocess
import tempfile
from typing import Callable, Optional, Sequence

from pyproj import Transformer
from shapely.geometry import LineString
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform as shapely_transform

# Palavras que identificam a camada de curva de nível (varia por agrimensor): casa "MDT1_CURVAS",
# "CURVAS_NIVEL", "CURVA DE NIVEL"… mas exige a raiz p/ não pegar legenda/selo.
_CHAVES_CAMADA = ("CURVA", "NIVEL", "NÍVEL", "MDT")
_EPSG_PADRAO = 31983          # SIRGAS 2000 / UTM 23S (São Roque, MC 45°). Parametrizável.
_L_MIN_CURVA_M = 20.0         # curva mais curta que isso é ruído (rótulo/marco) — descarta


def _pontos_da_entidade(e) -> list[tuple[float, float]]:
    """Vértices XY de uma entidade DXF de curva (SPLINE/LWPOLYLINE/POLYLINE/LINE)."""
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
    except Exception:  # noqa: BLE001 — entidade degenerada
        return []
    return []


def converter_dwg_para_dxf(caminho: str) -> Optional[str]:
    """DWG → DXF via ``dwg2dxf`` (libredwg). Devolve o caminho do DXF (temporário) ou None se o
    conversor não estiver disponível. DXF entra direto (retorna o próprio caminho)."""
    if caminho.lower().endswith(".dxf"):
        return caminho
    exe = shutil.which("dwg2dxf") or os.getenv("DWG2DXF_BIN")
    if not exe or not os.path.exists(caminho):
        return None
    saida = tempfile.mktemp(suffix=".dxf")
    try:
        r = subprocess.run([exe, "-y", "-o", saida, caminho], capture_output=True, timeout=120)
        return saida if os.path.exists(saida) and os.path.getsize(saida) > 0 else None
    except Exception:  # noqa: BLE001 — conversor falhou → degrada p/ o DEM
        return None


def extrair_contornos_wgs(caminho: str, epsg_origem: int = _EPSG_PADRAO) -> list[LineString]:
    """Curvas de nível do levantamento (DXF/DWG) em **WGS84** (lon/lat) — formato de ARMAZENAMENTO
    (independente de frame). UTM → WGS. Lista vazia se não houver camada de curva / arquivo ruim."""
    try:
        import ezdxf
    except ImportError:
        return []
    dxf = converter_dwg_para_dxf(caminho)
    if dxf is None:
        return []
    try:
        doc = ezdxf.readfile(dxf)
    except Exception:  # noqa: BLE001 — DXF ilegível/corrompido → degrada p/ o DEM
        return []
    utm_para_wgs = Transformer.from_crs(epsg_origem, 4326, always_xy=True).transform
    curvas: list[LineString] = []
    for e in doc.modelspace():
        camada = (e.dxf.layer or "").upper()
        if not any(k in camada for k in _CHAVES_CAMADA):
            continue
        pts = _pontos_da_entidade(e)
        if len(pts) < 2:
            continue
        try:
            ls = LineString([utm_para_wgs(x, y) for x, y in pts])
        except Exception:  # noqa: BLE001
            continue
        if ls.is_valid and not ls.is_empty:
            curvas.append(ls)
    return curvas


def reprojetar_para_frame(
    curvas_wgs: Sequence[LineString],
    to_local: Callable[[float, float], tuple[float, float]],
    dentro: Optional[BaseGeometry] = None,
    orientacao_rad: float = 0.0,
    passo: int = 1,
) -> list[LineString]:
    """Curvas WGS → frame MÉTRICO do motor (via ``to_local``), recortadas à área ``dentro`` e
    (opcional) ESPAÇADAS 1 a cada ``passo`` descendo a encosta (evita viário inchado de curvas
    coladas). Devolve ``LineString`` no frame local, prontas p/ ``gerar_layout(contornos=...)``."""
    locais: list[LineString] = []
    for ls in curvas_wgs:
        try:
            loc = shapely_transform(lambda x, y, z=None: to_local(x, y), ls)
        except Exception:  # noqa: BLE001
            continue
        partes = [loc]
        if dentro is not None and not dentro.is_empty:
            inter = loc.intersection(dentro)
            partes = inter.geoms if inter.geom_type == "MultiLineString" else [inter]
        for parte in partes:
            if parte.geom_type == "LineString" and parte.length >= _L_MIN_CURVA_M:
                locais.append(parte)
    return espacar_uniforme(locais, orientacao_rad, passo)


def espacar_uniforme(curvas: Sequence[LineString], orientacao_rad: float,
                     passo: int = 2) -> list[LineString]:
    """Afina p/ ruas espaçadas: ordena DESCENDO a encosta (projeção no gradiente ⟂ à cota) e mantém
    1 a cada ``passo``. Cobertura pareja (sem buraco→grade). ``passo<=1`` mantém todas."""
    if passo <= 1 or len(curvas) <= 2:
        return list(curvas)
    gx, gy = -math.sin(orientacao_rad), math.cos(orientacao_rad)
    ordenadas = sorted(curvas, key=lambda c: c.centroid.x * gx + c.centroid.y * gy)
    return [c for i, c in enumerate(ordenadas) if i % passo == 0]


def extrair_contornos_dxf(
    caminho_dxf: str,
    to_local: Callable[[float, float], tuple[float, float]],
    dentro: Optional[BaseGeometry] = None,
    epsg_origem: int = _EPSG_PADRAO,
    passo: int = 1,
) -> list[LineString]:
    """Conveniência: extrai (WGS) e reprojeta p/ o frame local numa chamada (usada em teste/lab)."""
    return reprojetar_para_frame(
        extrair_contornos_wgs(caminho_dxf, epsg_origem), to_local, dentro, passo=passo
    )
