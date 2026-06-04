#!/usr/bin/env python3
"""Pipeline da área verde SEM LOGIN — recorte ESA WorldCover → GeoTIFF local (não agente).

Alternativa ao MapBiomas que NÃO exige Google/Earth Engine. O ESA WorldCover (10 m, 2021)
é público e servido como Cloud-Optimized GeoTIFF na AWS Open Data: o `rasterio` (já é
dependência) lê só a JANELA da gleba direto por HTTP — sem autenticar, sem baixar o tile
inteiro. Salva o recorte que `app.core.vegetacao.FonteVegetacaoRaster` consome (Fase 2.2).

    cd backend
    python -m scripts.baixar_worldcover --kmz suagleba.kmz --saida app/perfis/verde.tif
    # ou:  --bbox <minlon> <minlat> <maxlon> <maxlat>
    export VEGETACAO_RASTER_PATH=app/perfis/verde.tif

Legenda WorldCover (o que conta como verde está em CLASSES_VERDE_WORLDCOVER):
  10 árvores · 20 arbustiva · 30 pastagem/campo · 40 agricultura · 50 construído
  60 solo exposto · 70 neve/gelo · 80 água · 90 área úmida herbácea · 95 mangue · 100 musgo

ATENÇÃO — o egress deste ambiente é 403, então a leitura remota NÃO foi testada aqui; a
lógica de amostragem tem teste offline (`tests/test_vegetacao_raster.py`, com rasterio).
Se a leitura por HTTP falhar na sua rede, baixe o tile do gleba manualmente (um arquivo
público) e rode com `--tile-local caminho.tif`.
"""

import argparse
import math
import os
import sys

from shapely.geometry import box

from app.core import ingestao as ingestao_mod

# COG público (AWS Open Data) — anônimo, sem credenciais.
URL_BASE = (
    "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/"
    "ESA_WorldCover_10m_2021_v200_{tile}_Map.tif"
)


def _tile_worldcover(lon: float, lat: float) -> str:
    """Tile de 3°×3° pelo canto inferior-esquerdo (ex.: gleba em SP → 'S24W048')."""
    lat3 = math.floor(lat / 3) * 3
    lon3 = math.floor(lon / 3) * 3
    ns = f"{'N' if lat3 >= 0 else 'S'}{abs(lat3):02d}"
    ew = f"{'E' if lon3 >= 0 else 'W'}{abs(lon3):03d}"
    return ns + ew


def _bbox(args, buffer_graus: float) -> tuple[float, float, float, float]:
    if args.bbox:
        minx, miny, maxx, maxy = args.bbox
    else:
        with open(args.kmz, "rb") as f:
            res = ingestao_mod.ingerir(f.read())
        if not res.ok or not res.poligonos:
            sys.exit(f"KMZ sem polígono utilizável: {res.erro or 'vazio'}")
        minx, miny, maxx, maxy = res.poligonos[0].bounds
        for p in res.poligonos[1:]:
            x0, y0, x1, y1 = p.bounds
            minx, miny = min(minx, x0), min(miny, y0)
            maxx, maxy = max(maxx, x1), max(maxy, y1)
    return (minx - buffer_graus, miny - buffer_graus, maxx + buffer_graus, maxy + buffer_graus)


def main() -> None:
    ap = argparse.ArgumentParser(description="Recorte ESA WorldCover (área verde) → GeoTIFF.")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--kmz", help="KMZ da gleba (bbox derivado dele + buffer).")
    src.add_argument("--bbox", nargs=4, type=float, metavar=("MINLON", "MINLAT", "MAXLON", "MAXLAT"))
    ap.add_argument("--saida", default="app/perfis/verde.tif")
    ap.add_argument("--buffer-m", type=float, default=200.0, help="Folga ao redor da gleba.")
    ap.add_argument(
        "--tile-local",
        help="Use um tile WorldCover já baixado (fallback se a leitura por HTTP falhar).",
    )
    args = ap.parse_args()

    import rasterio
    from rasterio.windows import from_bounds

    # GDAL/rasterio: acesso anônimo a HTTP/S3 público.
    os.environ.setdefault("AWS_NO_SIGN_REQUEST", "YES")
    os.environ.setdefault("GDAL_HTTP_MULTIRANGE", "YES")

    buffer_graus = args.buffer_m / 111_320.0
    minx, miny, maxx, maxy = _bbox(args, buffer_graus)
    cx, cy = (minx + maxx) / 2, (miny + maxy) / 2

    if args.tile_local:
        fonte = args.tile_local
    else:
        tile = _tile_worldcover(cx, cy)
        fonte = f"/vsicurl/{URL_BASE.format(tile=tile)}"
        print(f"Tile WorldCover: {tile}\nLendo janela de: {fonte}")

    with rasterio.open(fonte) as srcds:
        win = from_bounds(minx, miny, maxx, maxy, srcds.transform)
        dados = srcds.read(1, window=win)
        perfil = srcds.profile
        perfil.update(
            driver="GTiff",
            height=dados.shape[0],
            width=dados.shape[1],
            transform=srcds.window_transform(win),
            compress="deflate",
        )
        with rasterio.open(args.saida, "w", **perfil) as dst:
            dst.write(dados, 1)

    print(f"OK — recorte {dados.shape[1]}×{dados.shape[0]} px salvo em {args.saida}")
    print(f"Aponte:  export VEGETACAO_RASTER_PATH={args.saida}")


if __name__ == "__main__":
    main()
