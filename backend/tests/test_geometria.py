"""Critério de aceite #1 — área geodésica (não área em graus), ±0,5% vs. UTM."""

import pytest
from pyproj import Transformer
from shapely.geometry import Polygon
from shapely.ops import transform

from app.core import geometria
from tests.conftest import RET_INVALIDO, RET_RETANGULO


def _area_utm(poly: Polygon) -> float:
    """Área de referência independente, projetando para a zona UTM do centróide."""
    lon, lat = poly.centroid.x, poly.centroid.y
    zona = int((lon + 180) // 6) + 1
    epsg = (32700 if lat < 0 else 32600) + zona
    t = Transformer.from_crs("EPSG:4326", f"EPSG:{epsg}", always_xy=True)
    return transform(lambda x, y: t.transform(x, y), poly).area


def test_area_geodesica_bate_utm():
    poly = Polygon([*RET_RETANGULO, RET_RETANGULO[0]])
    area, perimetro = geometria.medir(poly)

    ref = _area_utm(poly)
    assert abs(area - ref) / ref < 0.005  # ±0,5%

    # Sanidade: não é área em graus (seria ~0.0002 → absurdamente pequena).
    assert area > 100_000  # retângulo ~0.02°×0.01° em SP ≈ 2,3 ha em m²
    assert perimetro > 0


def test_geometria_invalida_lanca():
    poly = Polygon([*RET_INVALIDO, RET_INVALIDO[0]])
    with pytest.raises(geometria.GeometriaInvalida):
        geometria.medir(poly)
