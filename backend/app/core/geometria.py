"""Geometria geodésica — área e perímetro reais, nunca área em graus.

Usa pyproj.Geod (elipsoide WGS84). A área é calculada sobre o anel exterior e
descontada dos buracos (interiors), se houver. O perímetro é o do anel exterior.
"""

from pyproj import Geod
from shapely.geometry import Polygon

_GEOD = Geod(ellps="WGS84")


class GeometriaInvalida(Exception):
    """Polígono inválido (auto-interseção, anel aberto, etc.)."""


def medir(poligono: Polygon) -> tuple[float, float]:
    """Devolve (area_m2, perimetro_m) geodésicos. Lança GeometriaInvalida."""
    if poligono.is_empty:
        raise GeometriaInvalida("Polígono vazio.")
    if not poligono.is_valid:
        from shapely.validation import explain_validity

        raise GeometriaInvalida(f"Polígono inválido: {explain_validity(poligono)}")

    lons, lats = poligono.exterior.coords.xy
    area, perimetro = _GEOD.polygon_area_perimeter(list(lons), list(lats))
    area = abs(area)
    perimetro = abs(perimetro)

    for anel in poligono.interiors:
        ilons, ilats = anel.coords.xy
        area_buraco, _ = _GEOD.polygon_area_perimeter(list(ilons), list(ilats))
        area -= abs(area_buraco)

    return area, perimetro
