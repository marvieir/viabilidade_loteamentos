"""Regressão: a leitura por janela (pyogrio) deve ser CRS-robusta.

Bug visto em produção (Mac): a camada de Reserva Legal SUMIU porque o arquivo do CAR não
estava em WGS84 — o bbox (WGS84) era aplicado no CRS do arquivo (UTM/SIRGAS) e a janela não
casava, retornando 0 feições. Agora o bbox é reprojetado p/ o CRS do arquivo na entrada e a
geometria de volta p/ WGS84 na saída."""

import numpy as np
import pytest
from pyproj import Transformer
from shapely import wkb
from shapely.geometry import Polygon

from app.core.camadas_inde import _e_wgs84, _ler_vetor_local_bbox

# Polígono perto da gleba de São Roque (WGS84) e o bbox da gleba.
_POLY_WGS = Polygon(
    [(-47.098, -23.522), (-47.094, -23.522), (-47.094, -23.518), (-47.098, -23.518)]
)
_BBOX = (-47.105, -23.529, -47.092, -23.514)


def _grava_gpkg(path, crs):
    from pyogrio.raw import write as ogr_write

    if crs == "EPSG:4326":
        poly = _POLY_WGS
    else:
        t = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
        xs, ys = t.transform(*_POLY_WGS.exterior.coords.xy)
        poly = Polygon(zip(xs, ys))
    ogr_write(
        str(path),
        geometry=np.array([wkb.dumps(poly)], dtype=object),
        field_data=[np.array(["SP-3550605-XYZ"])],
        fields=["cod_imovel"],
        geometry_type="Polygon",
        crs=crs,
    )


@pytest.mark.parametrize("crs", ["EPSG:31983", "EPSG:4674", "EPSG:4326"])
def test_le_janela_em_qualquer_crs_devolve_wgs84(tmp_path, crs):
    caminho = tmp_path / f"rl_{crs.replace(':', '_')}.gpkg"
    _grava_gpkg(caminho, crs)
    feats = _ler_vetor_local_bbox(str(caminho), _BBOX)
    assert len(feats) == 1, f"{crs}: janela não casou (regressão de CRS)"
    geom, props = feats[0]
    # devolvido em WGS84 (centroide na posição certa em lon/lat)
    cx, cy = geom.centroid.x, geom.centroid.y
    assert -47.10 < cx < -47.09 and -23.53 < cy < -23.51, f"{crs}: geometria não veio em WGS84"
    assert props.get("cod_imovel") == "SP-3550605-XYZ"


def test_e_wgs84():
    assert _e_wgs84("EPSG:4326")
    assert not _e_wgs84("EPSG:31983")
    assert not _e_wgs84("EPSG:4674")


def test_first_array_safe():
    """Regressão: campo lido como array (campo-lista do GDAL) NÃO pode estourar
    'truth value of an array is ambiguous' — era o que derrubava SICAR-RL e MATA-ATL."""
    import numpy as np

    from app.core.camadas_inde import _first

    # valor-array não derruba (antes: ValueError)
    assert _first({"cod_imovel": np.array([10, 20, 30])}, "cod_imovel") == "[10 20 30]"
    # casos normais seguem corretos
    assert _first({"cod_imovel": "SP-A"}, "cod_imovel") == "SP-A"
    assert _first({"x": None}, "cod_imovel") is None
    assert _first({"cod_imovel": float("nan")}, "cod_imovel") is None
    assert _first({"COD_IMOVEL": "SP-B"}, "cod_imovel") == "SP-B"  # case-insensitive
