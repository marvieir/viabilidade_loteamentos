"""Motor de declividade (Fase 2.5) — DEM → faixas de declividade + flag legal ≥30%.

TRIAGEM, não laudo (spec `docs/fase-2.5-declividade.md`): a partir do polígono da gleba e de
um recorte de DEM, calcula declividade média, % por faixa (suave/média/alta) e a **área com
declividade ≥30%** — vedação de parcelamento da Lei 6.766/79 art. 3º §ún III. Determinístico,
cálculo só no backend, **em CRS métrico** (AEQD local; slope é rise/run e exige metros).

Separação de responsabilidades (igual à 2.2):
  - ``FonteDEM`` (injetável) faz I/O + reprojeção → entrega um GRID JÁ MÉTRICO (`DEMRecorte`).
    Produção (`FonteDEMCopernicusAuto`) lê o COG Copernicus por HTTP e reprojeta (rasterio,
    só no container). Testes injetam um stub com grid sintético.
  - ``analisar_declividade`` é matemática pura (numpy/shapely/pyproj) → roda offline.

Fonte PADRÃO keyless: Copernicus GLO-30 Public (AWS Open Data), DSM 30 m. Ressalva honesta:
DSM inclui vegetação/edificação (pode superestimar sob mata) e 30 m é orientativo — NÃO
substitui levantamento topográfico.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass, field
from typing import Optional, Protocol, runtime_checkable

from pyproj import Transformer
from shapely.geometry import box, mapping
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform as shp_transform
from shapely.ops import unary_union

BASE_LEGAL_VEDACAO = "Lei 6.766/79 art. 3º §ún III"
RESSALVA_VEDACAO = (
    "Parcelamento vedado em declividade ≥30%, salvo atendidas exigências específicas das "
    "autoridades competentes."
)
RESSALVA_DSM = (
    "DEM de SUPERFÍCIE (DSM) 30 m — orientativo; pode superestimar a declividade sob "
    "vegetação/edificação; NÃO substitui levantamento topográfico."
)

# Limiares das faixas (%), configuráveis por env. Suave ≤ S; média S–M; alta > M.
LIMIAR_SUAVE_PCT = float(os.getenv("DECLIVIDADE_LIMIAR_SUAVE", "8"))
LIMIAR_MEDIA_PCT = float(os.getenv("DECLIVIDADE_LIMIAR_MEDIA", "20"))
# Flag legal — vedação de parcelamento (não é faixa, é regra da Lei 6.766).
LIMIAR_VEDACAO_PCT = 30.0

FONTE_COPERNICUS = "Copernicus GLO-30 Public (AWS Open Data) — DSM 30 m"


def _proj4_aeqd(lon: float, lat: float) -> str:
    return (
        f"+proj=aeqd +lat_0={lat} +lon_0={lon} +x_0=0 +y_0=0 "
        "+datum=WGS84 +units=m +no_defs"
    )


@dataclass
class DEMRecorte:
    """Recorte de DEM **já em grid MÉTRICO** (north-up, pixel quadrado). ``elevacao=None``
    = DEM não amostrado (degradação honesta). ``crs_proj4`` é o CRS métrico do grid; o canto
    superior-esquerdo do pixel [0,0] fica em ``(x0_m, y0_m)`` e cresce para baixo/direita."""

    elevacao: Optional["object"] = None  # numpy.ndarray 2D (metros); None = não consultado
    px_m: float = 0.0
    x0_m: float = 0.0
    y0_m: float = 0.0
    crs_proj4: Optional[str] = None
    fonte: Optional[str] = None
    data_referencia: Optional[str] = None
    avisos: list[str] = field(default_factory=list)


@runtime_checkable
class FonteDEM(Protocol):
    def amostrar(self, gleba: BaseGeometry) -> DEMRecorte: ...


@dataclass
class FaixaDeclividade:
    classe: str
    limite: str
    area_m2: float
    pct: float


@dataclass
class FlagVedacao:
    limite_pct: float
    area_m2: float
    pct_da_gleba: float
    geojson: dict
    base_legal: str
    ressalva: str


@dataclass
class ResultadoDeclividade:
    consultada: bool
    fonte: Optional[str]
    declividade_media_pct: Optional[float]
    faixas: list[FaixaDeclividade]
    flag_vedacao: Optional[FlagVedacao]
    geojson_vedacao: dict  # = flag_vedacao.geojson (atalho p/ a união do aproveitável)
    proveniencia: Optional[str]
    avisos: list[str]
    # Faixa de declividade ACENTUADA (>20%, "alta") em WGS84 — íngreme mas LEGAL (abaixo do veto
    # de 30%). O motor de urbanismo a usa como penalidade SUAVE: prefere terreno plano para os
    # lotes e empurra verde/preservação para a encosta. Vazia quando não há DEM (degrada honesto).
    geojson_acentuada: dict = field(default_factory=dict)


def analisar_declividade(
    gleba: BaseGeometry, dem: Optional[DEMRecorte]
) -> ResultadoDeclividade:
    """Mede a declividade dentro da gleba (grid métrico) → média, faixas, flag ≥30%.

    Determinístico. Pixels fora da gleba ou sem elevação (NaN) são ignorados. A área ≥30% é
    poligonizada (mancha pixelada, fiel ao dado 30 m) em WGS84 para alimentar a união do
    aproveitável e o overlay do mapa. Degrada honesto se o DEM não foi amostrado.
    """
    import numpy as np

    if dem is None or dem.elevacao is None:
        avisos = list(dem.avisos) if dem is not None else []
        if not avisos:
            avisos = ["DEM não consultado (fonte de declividade não configurada)."]
        return ResultadoDeclividade(
            consultada=False,
            fonte=dem.fonte if dem is not None else None,
            declividade_media_pct=None,
            faixas=[],
            flag_vedacao=None,
            geojson_vedacao={},
            proveniencia=None,
            avisos=avisos,
        )

    elev = np.asarray(dem.elevacao, dtype="float64")
    px = dem.px_m
    h, w = elev.shape

    # Declividade por pixel: gradiente em metros → rise/run → %. np.gradient(f, dy, dx).
    gy, gx = np.gradient(elev, px, px)
    slope_pct = np.hypot(gx, gy) * 100.0

    # Máscara: dentro da gleba E elevação/declividade finitas. Centro de cada pixel no CRS
    # métrico do grid; gleba reprojetada de WGS84 para o mesmo CRS.
    to_metric = Transformer.from_crs("EPSG:4326", dem.crs_proj4, always_xy=True).transform
    gleba_m = shp_transform(to_metric, gleba)
    cols = dem.x0_m + (np.arange(w) + 0.5) * px
    rows = dem.y0_m - (np.arange(h) + 0.5) * px
    xx, yy = np.meshgrid(cols, rows)
    try:
        from shapely import contains_xy

        dentro = contains_xy(gleba_m, xx.ravel(), yy.ravel()).reshape(h, w)
    except Exception:  # noqa: BLE001 — shapely < 2.0 (não esperado): cai p/ prepared loop
        from shapely.prepared import prep
        from shapely.geometry import Point

        pg = prep(gleba_m)
        dentro = np.array(
            [pg.contains(Point(x, y)) for x, y in zip(xx.ravel(), yy.ravel())]
        ).reshape(h, w)

    mask = dentro & np.isfinite(elev) & np.isfinite(slope_pct)
    n_in = int(mask.sum())
    px_area = px * px

    if n_in == 0:
        return ResultadoDeclividade(
            consultada=True,
            fonte=dem.fonte,
            declividade_media_pct=None,
            faixas=[],
            flag_vedacao=None,
            geojson_vedacao={},
            proveniencia=_proveniencia(dem),
            avisos=[*dem.avisos, "Nenhum pixel de DEM dentro da gleba.", RESSALVA_DSM],
        )

    sp = slope_pct[mask]
    media = round(float(sp.mean()), 2)
    total_in = n_in * px_area

    def _faixa(classe, limite, sel) -> FaixaDeclividade:
        area = round(float(sel.sum()) * px_area, 2)
        return FaixaDeclividade(
            classe=classe,
            limite=limite,
            area_m2=area,
            pct=round(area / total_in, 4) if total_in else 0.0,
        )

    suave = mask & (slope_pct <= LIMIAR_SUAVE_PCT)
    media_f = mask & (slope_pct > LIMIAR_SUAVE_PCT) & (slope_pct <= LIMIAR_MEDIA_PCT)
    alta = mask & (slope_pct > LIMIAR_MEDIA_PCT)
    faixas = [
        _faixa("suave", f"≤{_n(LIMIAR_SUAVE_PCT)}%", suave),
        _faixa("media", f"{_n(LIMIAR_SUAVE_PCT)}–{_n(LIMIAR_MEDIA_PCT)}%", media_f),
        _faixa("alta", f">{_n(LIMIAR_MEDIA_PCT)}%", alta),
    ]

    to_wgs = Transformer.from_crs(dem.crs_proj4, "EPSG:4326", always_xy=True).transform

    def _poligonizar(sel) -> dict:
        """Une os pixels selecionados (boxes no CRS métrico) e reprojeta p/ WGS84."""
        if int(sel.sum()) == 0:
            return {}
        boxes = []
        idx_r, idx_c = np.where(sel)
        for r, c in zip(idx_r.tolist(), idx_c.tolist()):
            x_esq = dem.x0_m + c * px
            y_sup = dem.y0_m - r * px
            boxes.append(box(x_esq, y_sup - px, x_esq + px, y_sup))
        return mapping(shp_transform(to_wgs, unary_union(boxes)))

    # Flag legal ≥30% — poligoniza os pixels vedados (boxes no CRS métrico) → WGS84.
    vedado = mask & (slope_pct >= LIMIAR_VEDACAO_PCT)
    geojson_vedacao = _poligonizar(vedado)
    flag = None
    n_vedado = int(vedado.sum())
    if n_vedado > 0:
        area_vedada = round(n_vedado * px_area, 2)
        flag = FlagVedacao(
            limite_pct=LIMIAR_VEDACAO_PCT,
            area_m2=area_vedada,
            pct_da_gleba=round(area_vedada / total_in, 4) if total_in else 0.0,
            geojson=geojson_vedacao,
            base_legal=BASE_LEGAL_VEDACAO,
            ressalva=RESSALVA_VEDACAO,
        )

    # Faixa ACENTUADA (>20%, "alta") — íngreme mas LEGAL; entra como penalidade suave no motor de
    # urbanismo (lote no plano, verde na encosta). Inclui o ≥30% (já vedado por lei): overlap
    # inofensivo, pois o lote já o evita por outra via.
    geojson_acentuada = _poligonizar(alta)

    return ResultadoDeclividade(
        consultada=True,
        fonte=dem.fonte,
        declividade_media_pct=media,
        faixas=faixas,
        flag_vedacao=flag,
        geojson_vedacao=geojson_vedacao,
        proveniencia=_proveniencia(dem),
        avisos=[*dem.avisos, RESSALVA_DSM],
        geojson_acentuada=geojson_acentuada,
    )


def _n(v: float) -> str:
    return str(int(v)) if float(v).is_integer() else str(v)


def _proveniencia(dem: DEMRecorte) -> str:
    fonte = dem.fonte or "DEM"
    data = f", {dem.data_referencia}" if dem.data_referencia else ""
    return f"{fonte}{data}; declividade em CRS métrico (AEQD local), janela do DEM por /vsicurl"


# ---------------------------------------------------------------------------
# Fontes de DEM (produção). Reprojeção raster → grid métrico via rasterio (só container).
# ---------------------------------------------------------------------------

# COG público Copernicus GLO-30 Public (AWS Open Data, anônimo, SEM chave). Tiles 1°×1°.
COPERNICUS_COG_URL = (
    "https://copernicus-dem-30m.s3.eu-central-1.amazonaws.com/"
    "Copernicus_DSM_COG_10_{ns}{lat:02d}_00_{ew}{lon:03d}_00_DEM/"
    "Copernicus_DSM_COG_10_{ns}{lat:02d}_00_{ew}{lon:03d}_00_DEM.tif"
)


def _tile_copernicus(lon: float, lat: float) -> str:
    """Nome de tile 1°×1° pelo canto inferior-esquerdo (lat/lon inteiros)."""
    lat_i = math.floor(lat)
    lon_i = math.floor(lon)
    ns = "N" if lat_i >= 0 else "S"
    ew = "E" if lon_i >= 0 else "W"
    return COPERNICUS_COG_URL.format(ns=ns, lat=abs(lat_i), ew=ew, lon=abs(lon_i))


def _tiles_da_gleba_dem(bounds: tuple[float, float, float, float]) -> list[str]:
    minx, miny, maxx, maxy = bounds
    cantos = [
        (minx, miny), (maxx, miny), (minx, maxy), (maxx, maxy),
        ((minx + maxx) / 2, (miny + maxy) / 2),
    ]
    urls: list[str] = []
    for lon, lat in cantos:
        u = _tile_copernicus(lon, lat)
        if u not in urls:
            urls.append(u)
    return urls


def _gdal_anon_http_env() -> None:
    os.environ.setdefault("AWS_NO_SIGN_REQUEST", "YES")
    os.environ.setdefault("GDAL_HTTP_MULTIRANGE", "YES")
    os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
    os.environ.setdefault("CPL_VSIL_CURL_ALLOWED_EXTENSIONS", ".tif")


def _amostrar_para_grid_metrico(
    fontes: list[str], gleba: BaseGeometry, fonte_nome: str, buffer_m: float = 60.0
) -> DEMRecorte:
    """Lê a janela da gleba de uma ou mais fontes raster (arquivo OU /vsicurl/ COG) e
    **reprojeta para um grid métrico AEQD** (30 m), unindo tiles. Degrada honesto."""
    from datetime import date

    try:
        import numpy as np
        import rasterio
        from affine import Affine
        from rasterio.warp import reproject, Resampling
    except Exception as exc:  # noqa: BLE001 — sem rasterio → degrada
        return DEMRecorte(
            fonte=fonte_nome,
            avisos=[f"Declividade indisponível — {type(exc).__name__}: {exc}"[:180]],
        )

    c = gleba.centroid
    proj4 = _proj4_aeqd(c.x, c.y)
    to_metric = Transformer.from_crs("EPSG:4326", proj4, always_xy=True).transform
    minx, miny, maxx, maxy = shp_transform(to_metric, gleba).bounds
    minx, miny, maxx, maxy = minx - buffer_m, miny - buffer_m, maxx + buffer_m, maxy + buffer_m

    px = 30.0
    w = max(int(math.ceil((maxx - minx) / px)), 1)
    h = max(int(math.ceil((maxy - miny) / px)), 1)
    dst_transform = Affine.translation(minx, maxy) * Affine.scale(px, -px)
    dst = np.full((h, w), np.nan, dtype="float32")

    erros: list[str] = []
    leu_algo = False
    for fonte in fontes:
        try:
            with rasterio.open(fonte) as src:
                tmp = np.full((h, w), np.nan, dtype="float32")
                reproject(
                    source=rasterio.band(src, 1),
                    destination=tmp,
                    src_transform=src.transform,
                    src_crs=src.crs,
                    src_nodata=src.nodata,
                    dst_transform=dst_transform,
                    dst_crs=proj4,
                    dst_nodata=np.nan,
                    resampling=Resampling.bilinear,
                )
                dst = np.where(np.isnan(dst), tmp, dst)
                leu_algo = True
        except Exception as exc:  # noqa: BLE001 — tile ausente/oceano/egress: tenta o próximo
            erros.append(f"{type(exc).__name__}: {exc}")
            continue

    if not leu_algo or not np.isfinite(dst).any():
        bruto = erros[0] if erros else "sem dado de elevação na janela"
        if any(k in bruto for k in ("curl", "HTTP", "Connection", "timed out", "403", "404")):
            aviso = (
                "Declividade indisponível — não foi possível ler o DEM Copernicus por HTTP "
                "(egress bloqueado?). Libere o acesso ao bucket público ou use DEM_RASTER_PATH."
            )
        else:
            aviso = f"Declividade indisponível — DEM não cobre a gleba ({bruto})."
        return DEMRecorte(fonte=fonte_nome, avisos=[aviso[:200]])

    return DEMRecorte(
        elevacao=dst,
        px_m=px,
        x0_m=minx,
        y0_m=maxy,
        crs_proj4=proj4,
        fonte=fonte_nome,
        data_referencia=date.today().isoformat(),
    )


class FonteDEMCopernicusAuto:
    """Lê o Copernicus GLO-30 Public DIRETO do COG por HTTP, escolhendo o(s) tile(s) pela
    posição da gleba. Keyless — funciona para qualquer KMZ; requisito: egress ao bucket."""

    fonte = FONTE_COPERNICUS

    def amostrar(self, gleba: BaseGeometry) -> DEMRecorte:
        _gdal_anon_http_env()
        fontes = [f"/vsicurl/{u}" for u in _tiles_da_gleba_dem(gleba.bounds)]
        return _amostrar_para_grid_metrico(fontes, gleba, self.fonte)


class FonteDEMRasterLocal:
    """DEM de arquivo LOCAL (offline/override) — mesmo reprojetor da fonte automática."""

    def __init__(self, caminho: str, fonte: Optional[str] = None):
        self.caminho = caminho
        self.fonte = fonte or f"DEM local ({os.path.basename(caminho)})"

    def amostrar(self, gleba: BaseGeometry) -> DEMRecorte:
        return _amostrar_para_grid_metrico([self.caminho], gleba, self.fonte)


class FonteDEMOpenTopography:
    """Fallback OPCIONAL gated por ``OPENTOPOGRAPHY_API_KEY`` (COP30 global). Não necessário
    no caminho padrão (keyless). Baixa o recorte da gleba e reusa o reprojetor métrico."""

    URL = "https://portal.opentopography.org/API/globaldem"

    def __init__(self, api_key: str, dem_type: str = "COP30"):
        self.api_key = api_key
        self.dem_type = dem_type
        self.fonte = f"OpenTopography {dem_type} — DSM 30 m"

    def amostrar(self, gleba: BaseGeometry) -> DEMRecorte:
        import tempfile
        import urllib.parse
        import urllib.request

        minx, miny, maxx, maxy = gleba.bounds
        params = urllib.parse.urlencode(
            {
                "demtype": self.dem_type,
                "south": miny, "north": maxy, "west": minx, "east": maxx,
                "outputFormat": "GTiff", "API_Key": self.api_key,
            }
        )
        try:
            with urllib.request.urlopen(f"{self.URL}?{params}", timeout=60) as resp:
                dados = resp.read()
            with tempfile.NamedTemporaryFile(suffix=".tif", delete=False) as tf:
                tf.write(dados)
                caminho = tf.name
            return _amostrar_para_grid_metrico([caminho], gleba, self.fonte)
        except Exception as exc:  # noqa: BLE001 — degrada honesto
            return DEMRecorte(
                fonte=self.fonte,
                avisos=[f"Declividade indisponível (OpenTopography) — {type(exc).__name__}."],
            )


def get_fonte_dem() -> Optional[FonteDEM]:
    """Escolhe a fonte de DEM (degrada honesto se nenhuma servir):

    1. ``DEM_RASTER_PATH`` → arquivo LOCAL (offline/override).
    2. ``DEM_FONTE`` (default ``copernicus_auto``): ``copernicus_auto`` (keyless, COG por HTTP)
       ou ``opentopography`` (fallback gated por ``OPENTOPOGRAPHY_API_KEY``; sem chave → cai no
       Copernicus keyless). ``none``/``off`` → desliga (``None``).
    3. senão → ``None`` (não desconta, não inventa).
    """
    caminho = os.getenv("DEM_RASTER_PATH")
    if caminho:
        return FonteDEMRasterLocal(caminho)
    fonte = os.getenv("DEM_FONTE", "copernicus_auto").strip().lower()
    if fonte in ("none", "off", "0", "false", "no"):
        return None
    if fonte == "opentopography":
        key = os.getenv("OPENTOPOGRAPHY_API_KEY")
        if key:
            return FonteDEMOpenTopography(key)
    return FonteDEMCopernicusAuto()
