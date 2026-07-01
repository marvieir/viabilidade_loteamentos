"""Silhueta normalizada da gleba para miniaturas (thumbnails) na área "Minhas análises".

O backend converte o GeoJSON salvo num contorno simplificado e NORMALIZADO (viewBox 0..100,
eixo Y invertido p/ SVG) — o front apenas desenha os pontos recebidos (regra §2: nenhuma
geo-matemática em JavaScript). Determinístico e barato (roda na listagem).
"""

from __future__ import annotations

from typing import Optional

from shapely.geometry import shape

_TAM = 100.0  # viewBox 0..100
_MARGEM = 6.0
_MAX_PARTES = 4  # multipolígono: desenha as N maiores porções


def silhueta(geojson: Optional[dict]) -> Optional[list[list[list[float]]]]:
    """Anéis externos da gleba normalizados para 0..100 (y invertido). ``None`` se inválida."""
    if not geojson:
        return None
    try:
        g = shape(geojson)
        if g.is_empty:
            return None
        # Simplificação relativa ao tamanho (contorno leve p/ thumbnail, forma preservada).
        minx, miny, maxx, maxy = g.bounds
        diag = max(maxx - minx, maxy - miny)
        if diag <= 0:
            return None
        g = g.simplify(diag / 80.0, preserve_topology=True)
        polys = list(g.geoms) if hasattr(g, "geoms") else [g]
        polys = sorted(
            (p for p in polys if getattr(p, "exterior", None) is not None),
            key=lambda p: p.area,
            reverse=True,
        )[:_MAX_PARTES]
        if not polys:
            return None

        # Normaliza o CONJUNTO (mesma escala p/ todas as partes), centralizado com margem.
        minx, miny, maxx, maxy = (
            min(p.bounds[0] for p in polys),
            min(p.bounds[1] for p in polys),
            max(p.bounds[2] for p in polys),
            max(p.bounds[3] for p in polys),
        )
        util = _TAM - 2 * _MARGEM
        escala = util / max(maxx - minx, maxy - miny)
        off_x = (_TAM - (maxx - minx) * escala) / 2.0
        off_y = (_TAM - (maxy - miny) * escala) / 2.0

        aneis: list[list[list[float]]] = []
        for p in polys:
            pts = [
                [
                    round((x - minx) * escala + off_x, 1),
                    round(_TAM - ((y - miny) * escala + off_y), 1),  # y invertido (SVG)
                ]
                for x, y in p.exterior.coords
            ]
            if len(pts) >= 4:
                aneis.append(pts)
        return aneis or None
    except Exception:  # noqa: BLE001 — thumbnail é decorativo; nunca quebra a listagem
        return None
