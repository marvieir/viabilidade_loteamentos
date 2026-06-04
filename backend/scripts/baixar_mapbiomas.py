#!/usr/bin/env python3
"""Pipeline de aquisição do raster MapBiomas → recorte GeoTIFF local (não agente).

Baixa um RECORTE pequeno da cobertura/uso MapBiomas ao redor da gleba e salva o GeoTIFF
que `app.core.vegetacao.FonteVegetacaoRaster` consome (Fase 2.2 — área verde). Use uma vez
por região (ou em refresh agendado) e aponte o resultado em `MAPBIOMAS_RASTER_PATH`.

    # 1) deps de aquisição (só p/ este script; não vão pro runtime):
    pip install earthengine-api
    # 2) autentique (abre o navegador uma vez):
    earthengine authenticate
    # 3) recorte ao redor da gleba (por KMZ ou por bbox), ano da coleção:
    python -m scripts.baixar_mapbiomas --kmz gleba.kmz --ano 2023 \
        --saida app/perfis/mapbiomas.tif
    # ou:  --bbox <minlon> <minlat> <maxlon> <maxlat>
    export MAPBIOMAS_RASTER_PATH=app/perfis/mapbiomas.tif

Por que GEE: o MapBiomas publica a coleção como Image no Earth Engine; pedir só o recorte
da gleba (poucos KB) evita baixar o mosaico nacional (GBs). `getDownloadURL` entrega o
recorte direto quando a região é pequena (uma gleba típica está MUITO abaixo do limite).

ATENÇÃO — validar ao vivo (egress deste ambiente = 403, não dá p/ testar aqui):
  * O ASSET e o padrão de banda abaixo seguem a convenção pública do MapBiomas, mas
    CONFIRME o id/banda da coleção vigente (mudam a cada coleção) — sobrescreva com
    `--asset` / `--banda` se preciso. A seleção de classes "verdes" vive em
    `app.core.vegetacao.CLASSES_VERDE_MAPBIOMAS` (ajustável por env).
  * O CRS/escala saem do asset (SIRGAS 2000, ~30 m). `FonteVegetacaoRaster` reprojeta.
"""

import argparse
import io
import sys
import zipfile

from shapely.geometry import box, mapping

from app.core import ingestao as ingestao_mod

# Convenção pública das coleções LULC do MapBiomas no Earth Engine. CONFIRME na coleção
# vigente antes de rodar (pode mudar o número da coleção / o sufixo de versão).
ASSET_PADRAO = (
    "projects/mapbiomas-public/assets/brazil/lulc/collection9/"
    "mapbiomas_collection90_integration_v1"
)
BANDA_PADRAO = "classification_{ano}"  # uma banda por ano na imagem de integração


def _bbox_do_kmz(caminho: str, buffer_graus: float) -> tuple[float, float, float, float]:
    with open(caminho, "rb") as f:
        res = ingestao_mod.ingerir(f.read())
    if not res.ok or not res.poligonos:
        sys.exit(f"KMZ não rendeu polígono utilizável: {res.erro or 'sem polígonos'}")
    minx, miny, maxx, maxy = res.poligonos[0].bounds
    for p in res.poligonos[1:]:
        x0, y0, x1, y1 = p.bounds
        minx, miny, maxx, maxy = min(minx, x0), min(miny, y0), max(maxx, x1), max(maxy, y1)
    return (minx - buffer_graus, miny - buffer_graus, maxx + buffer_graus, maxy + buffer_graus)


def main() -> None:
    ap = argparse.ArgumentParser(description="Recorte MapBiomas (área verde) → GeoTIFF local.")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--kmz", help="KMZ da gleba (bbox derivado dele + buffer).")
    src.add_argument(
        "--bbox", nargs=4, type=float, metavar=("MINLON", "MINLAT", "MAXLON", "MAXLAT")
    )
    ap.add_argument("--ano", type=int, required=True, help="Ano da coleção (ex.: 2023).")
    ap.add_argument("--saida", default="app/perfis/mapbiomas.tif")
    ap.add_argument("--asset", default=ASSET_PADRAO, help="Asset GEE da coleção (confirme).")
    ap.add_argument("--banda", default=BANDA_PADRAO, help="Padrão de banda; {ano} é interpolado.")
    ap.add_argument("--buffer-m", type=float, default=200.0, help="Folga ao redor da gleba.")
    ap.add_argument("--escala", type=float, default=30.0, help="Resolução em metros.")
    args = ap.parse_args()

    # importado aqui: dependência só desta etapa de aquisição (fora do runtime da API)
    try:
        import ee
        import urllib.request
    except ImportError:
        sys.exit("Instale earthengine-api:  pip install earthengine-api")

    buffer_graus = args.buffer_m / 111_320.0  # ~m→graus (aprox., suficiente p/ folga)
    if args.kmz:
        minx, miny, maxx, maxy = _bbox_do_kmz(args.kmz, buffer_graus)
    else:
        minx, miny, maxx, maxy = args.bbox

    ee.Initialize()
    regiao = ee.Geometry(mapping(box(minx, miny, maxx, maxy)))
    banda = args.banda.format(ano=args.ano)
    imagem = ee.Image(args.asset).select(banda).clip(regiao)

    url = imagem.getDownloadURL(
        {"region": regiao, "scale": args.escala, "format": "GEO_TIFF", "crs": "EPSG:4326"}
    )
    print(f"Baixando recorte ({banda}) → {args.saida} …")
    with urllib.request.urlopen(url, timeout=120) as r:
        dados = r.read()

    # getDownloadURL pode devolver GeoTIFF direto ou um .zip com o(s) .tif(s).
    if dados[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(dados)) as zf:
            nome_tif = next(n for n in zf.namelist() if n.lower().endswith(".tif"))
            dados = zf.read(nome_tif)
    with open(args.saida, "wb") as f:
        f.write(dados)
    print(f"OK — {len(dados)} bytes. Aponte:  export MAPBIOMAS_RASTER_PATH={args.saida}")


if __name__ == "__main__":
    main()
