"""Caminho RASTER da Fase 2.2 (FonteVegetacaoRaster).

Roda só onde `rasterio` está instalado (runtime de produção). Aqui no sandbox não há
rasterio → pula. No Mac do operador valida a amostragem real contra um GeoTIFF sintético
de classes conhecidas, sem depender do MapBiomas ao vivo.
"""

import numpy as np
import pytest
from shapely.geometry import Polygon

rasterio = pytest.importorskip("rasterio")

from app.core.vegetacao import FonteVegetacaoRaster, analisar_vegetacao  # noqa: E402

# Gleba pequena (≈ algumas centenas de metros) sobre a qual desenhamos o raster.
GLEBA = Polygon(
    [(-47.140, -23.530), (-47.120, -23.530), (-47.120, -23.520), (-47.140, -23.520)]
)


def _raster_sintetico(caminho, classe_verde=3, classe_outra=15):
    """10×10 px sobre o bbox da gleba; metade esquerda = verde, metade direita = outra."""
    from rasterio.transform import from_bounds

    minx, miny, maxx, maxy = GLEBA.bounds
    n = 10
    dados = np.full((n, n), classe_outra, dtype="uint8")
    dados[:, : n // 2] = classe_verde  # metade esquerda é vegetação
    transform = from_bounds(minx, miny, maxx, maxy, n, n)
    with rasterio.open(
        caminho, "w", driver="GTiff", height=n, width=n, count=1,
        dtype="uint8", crs="EPSG:4326", transform=transform,
    ) as dst:
        dst.write(dados, 1)


def test_raster_detecta_e_mede_verde(tmp_path):
    tif = tmp_path / "veg.tif"
    _raster_sintetico(tif, classe_verde=3)
    fonte = FonteVegetacaoRaster(str(tif), classes={3})

    cobertura = fonte.cobertura_verde(GLEBA)
    assert cobertura.geometria is not None
    res = analisar_vegetacao(GLEBA, cobertura)
    assert res.consultada is True
    # metade esquerda do raster é verde → ~50% da gleba
    assert 40 <= res.percentual_verde <= 60, res.percentual_verde


def test_raster_sem_classe_verde_degrada(tmp_path):
    tif = tmp_path / "veg.tif"
    _raster_sintetico(tif, classe_verde=3)
    # nenhuma classe da gleba está no conjunto "verde" pedido → sem geometria
    fonte = FonteVegetacaoRaster(str(tif), classes={99})
    cobertura = fonte.cobertura_verde(GLEBA)
    assert cobertura.geometria is None
    res = analisar_vegetacao(GLEBA, cobertura)
    assert res.consultada is False


def test_raster_inexistente_degrada_sem_derrubar():
    fonte = FonteVegetacaoRaster("/caminho/inexistente.tif", classes={3})
    cobertura = fonte.cobertura_verde(GLEBA)
    assert cobertura.geometria is None
    assert cobertura.avisos and "indispon" in cobertura.avisos[0].lower()
