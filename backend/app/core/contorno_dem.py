"""Opção B — extrai a VIA-TRONCO como a CURVA DE NÍVEL (isolinha) do DEM que atravessa a gleba.

Marching squares PURO-NUMPY (nenhuma dependência nova em produção — só numpy/shapely/pyproj do
stack geo) sobre a grade métrica do DEM; reprojeta a polilinha para o frame do motor (o mesmo da
área aproveitável). A via-tronco então SEGUE a declividade em vez de descer o morro em linha reta.
Determinístico: mesmo DEM → mesma espinha.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
from shapely.geometry import LineString, MultiLineString
from shapely.geometry.base import BaseGeometry
from shapely.ops import linemerge


def _segmentos_isolinha(z: np.ndarray, nivel: float) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    """Marching squares: segmentos da isolinha ``nivel`` em coords de GRADE (col, row fracionários).
    Corners por célula (TL,TR,BR,BL); cada aresta cruzada é interpolada linearmente. Célula com 2
    cruzamentos → 1 segmento; sela (4) → 2 segmentos (pareamento consecutivo — suficiente p/ a via)."""
    nrow, ncol = z.shape
    segs: list[tuple[tuple[float, float], tuple[float, float]]] = []
    for r in range(nrow - 1):
        for c in range(ncol - 1):
            # (x=col, y=row, valor) dos 4 cantos, sentido horário a partir do topo-esquerda
            cs = [(c, r, z[r, c]), (c + 1, r, z[r, c + 1]),
                  (c + 1, r + 1, z[r + 1, c + 1]), (c, r + 1, z[r + 1, c])]
            if any(not np.isfinite(v) for _, _, v in cs):
                continue
            cross: list[tuple[float, float]] = []
            for a, b in ((0, 1), (1, 2), (2, 3), (3, 0)):
                xa, ya, va = cs[a]
                xb, yb, vb = cs[b]
                if (va < nivel) != (vb < nivel):
                    t = (nivel - va) / (vb - va) if vb != va else 0.5
                    cross.append((xa + t * (xb - xa), ya + t * (yb - ya)))
            if len(cross) == 2:
                segs.append((cross[0], cross[1]))
            elif len(cross) == 4:
                segs.append((cross[0], cross[1]))
                segs.append((cross[2], cross[3]))
    return segs


def extrair_espinha(
    dem, to_local, dentro: Optional[BaseGeometry] = None,
    quantil: float = 0.5, simplify_m: float = 6.0, min_len_m: float = 60.0,
) -> Optional[LineString]:
    """Isolinha na cota do ``quantil`` (0.5 = mediana) do DEM, como LineString no FRAME DO MOTOR.

    ``dem`` = DEMRecorte (grade métrica + crs_proj4); ``to_local`` = WGS→frame do motor (o mesmo
    das geometrias). ``dentro`` (gleba no frame do motor) recorta a linha. Devolve a polilinha mais
    LONGA (≥ ``min_len_m``), suavizada; None se o DEM não permite (degradação honesta — sem inventar
    relevo). Reprojeção: grade → DEM-métrico → WGS → frame do motor."""
    try:
        if dem is None or getattr(dem, "elevacao", None) is None or not dem.crs_proj4:
            return None
        z = np.asarray(dem.elevacao, dtype=float)
        if z.ndim != 2 or z.size < 9:
            return None
        finito = z[np.isfinite(z)]
        if finito.size < 9:
            return None
        nivel = float(np.quantile(finito, quantil))
        segs = _segmentos_isolinha(z, nivel)
        if not segs:
            return None

        from pyproj import Transformer

        dem2wgs = Transformer.from_crs(dem.crs_proj4, "EPSG:4326", always_xy=True).transform

        def _para_frame(col: float, row: float) -> tuple[float, float]:
            xm = dem.x0_m + col * dem.px_m
            ym = dem.y0_m - row * dem.px_m  # row cresce p/ baixo → y decresce
            lon, lat = dem2wgs(xm, ym)
            return to_local(lon, lat)

        linhas = []
        for p0, p1 in segs:
            a = _para_frame(*p0)
            b = _para_frame(*p1)
            if a != b:
                linhas.append(LineString([a, b]))
        if not linhas:
            return None
        merged = linemerge(MultiLineString(linhas)) if len(linhas) > 1 else linhas[0]
        partes = list(getattr(merged, "geoms", [merged]))
        if dentro is not None and not dentro.is_empty:
            recort = []
            for ln in partes:
                inter = ln.intersection(dentro)
                recort += [g for g in getattr(inter, "geoms", [inter])
                           if g.geom_type == "LineString" and not g.is_empty]
            partes = recort or partes
        partes = [p for p in partes if p.length >= min_len_m]
        if not partes:
            return None
        maior = max(partes, key=lambda l: l.length)
        suave = maior.simplify(simplify_m)
        return suave if suave.length >= min_len_m else maior
    except Exception:  # noqa: BLE001 — B degrada para o traçado A (nunca derruba a geração)
        return None
