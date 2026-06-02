"""Geometria geodésica — área e perímetro reais, nunca área em graus.

Usa pyproj.Geod (elipsoide WGS84). A área é calculada sobre o anel exterior e
descontada dos buracos (interiors), se houver. O perímetro é o do anel exterior.
"""

from pyproj import Geod
from shapely.geometry import Polygon

_GEOD = Geod(ellps="WGS84")


class GeometriaInvalida(Exception):
    """Polígono inválido (auto-interseção, anel aberto, etc.)."""


def _area_poligono(poligono: Polygon) -> float:
    """Área geodésica (m²) de um Polygon, descontando buracos. Sem validação."""
    lons, lats = poligono.exterior.coords.xy
    area, _ = _GEOD.polygon_area_perimeter(list(lons), list(lats))
    area = abs(area)
    for anel in poligono.interiors:
        ilons, ilats = anel.coords.xy
        area_buraco, _ = _GEOD.polygon_area_perimeter(list(ilons), list(ilats))
        area -= abs(area_buraco)
    return area


def medir(poligono: Polygon) -> tuple[float, float]:
    """Devolve (area_m2, perimetro_m) geodésicos. Lança GeometriaInvalida."""
    if poligono.is_empty:
        raise GeometriaInvalida("Polígono vazio.")
    if not poligono.is_valid:
        from shapely.validation import explain_validity

        raise GeometriaInvalida(f"Polígono inválido: {explain_validity(poligono)}")

    area = _area_poligono(poligono)
    lons, lats = poligono.exterior.coords.xy
    _, perimetro = _GEOD.polygon_area_perimeter(list(lons), list(lats))
    return area, abs(perimetro)


def area_geodesica(geom) -> float:
    """Área geodésica (m²) de Polygon/MultiPolygon/GeometryCollection.

    Usada para o **% de área por município** na divisa (decisão #4 da 1.7): a fração da
    gleba em cada município é uma razão de áreas geodésicas (não área em graus). Geometrias
    não-areais (linha/ponto, ex.: interseções degeneradas) contribuem 0.
    """
    if geom is None or geom.is_empty:
        return 0.0
    tipo = geom.geom_type
    if tipo == "Polygon":
        return _area_poligono(geom)
    if tipo in ("MultiPolygon", "GeometryCollection"):
        return sum(area_geodesica(g) for g in geom.geoms)
    return 0.0
