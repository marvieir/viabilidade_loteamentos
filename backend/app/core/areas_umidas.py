"""Motor de áreas úmidas / alagadas (nova dimensão ambiental).

TRIAGEM, não laudo: identifica a área ÚMIDA/ALAGÁVEL (campo alagado, brejo, banhado,
várzea, área pantanosa) sobre a gleba e a marca como restrição NÃO-EDIFICÁVEL candidata —
costuma ser APP pelo Código Florestal (Lei 12.651/2012, art. 4º). NÃO delimita nem enquadra
APP (isso é do engenheiro ambiental). Determinístico: mesma gleba + mesma cobertura → mesma
área. Área em CRS MÉTRICO LOCAL (AEQD no centróide), nunca em graus.

Reusa O MESMO mecanismo da vegetação (raster COG por ``/vsicurl/``, ``rasterio.mask`` →
``rasterio.features.shapes``): só muda o CONJUNTO DE CLASSES filtrado. A fonte é injetável:
- DEFAULT (sem provisionar nada): MapBiomas classe 11 (campo alagado e área pantanosa) + água
  (33), lido do COG NACIONAL público no Google Cloud Storage (anônimo, sem login). É a legenda
  brasileira, captura o alagado sazonal que o WorldCover (10 m) não pega.
- ALTERNATIVA: ESA WorldCover classe 90 (área úmida herbácea) via ``AREAS_UMIDAS_FONTE=worldcover``.
- OVERRIDE: recorte raster LOCAL em ``AREAS_UMIDAS_RASTER_PATH``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional, Protocol, runtime_checkable

from pyproj import CRS, Transformer
from shapely.geometry import mapping
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform

# Reuso do maquinário raster da vegetação (mesmo COG, mesma leitura por janela) — só o
# conjunto de classes muda. Manter num lugar só evita duplicar ~70 linhas de rasterio.
from app.core.vegetacao import (
    WORLDCOVER_COG_URL,
    _extrair_cobertura,
    _gdal_anon_http_env,
    _tiles_da_gleba,
)

RESSALVA_UMIDA = (
    "triagem — área úmida/alagável potencial (APP candidata, Lei 12.651/2012 Cód. Florestal "
    "art. 4º); delimitação fina e enquadramento de APP dependem de laudo de engenheiro "
    "ambiental (fora do escopo da plataforma)"
)
BASE_LEGAL_UMIDA = "Lei 12.651/2012 (Código Florestal) art. 4º — área úmida/alagável (APP candidata)"

# ESA WorldCover (fonte PADRÃO, pública, sem login): 90 = área úmida herbácea (alagável).
CLASSES_UMIDA_WORLDCOVER = {90}
# MapBiomas (legenda BR): 11 = Campo Alagado e Área Pantanosa; 33 = Rio, Lago e Oceano (água).
CLASSES_UMIDA_MAPBIOMAS = {11, 33}
CLASSES_UMIDA_PADRAO = CLASSES_UMIDA_WORLDCOVER


@dataclass
class CoberturaUmida:
    """Cobertura úmida devolvida pela fonte. ``geometria=None`` = não consultada."""

    geometria: Optional[BaseGeometry] = None  # polígono(s) de área úmida (WGS84)
    fonte: Optional[str] = None
    data_referencia: Optional[str] = None
    classes: list[str] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)


@runtime_checkable
class FonteAreasUmidas(Protocol):
    def areas_umidas(self, gleba: BaseGeometry) -> CoberturaUmida: ...


@dataclass
class ResultadoAreasUmidas:
    area_total_m2: float
    area_umida_m2: Optional[float]
    pct_da_gleba: Optional[float]
    geojson_umidas: dict
    proveniencia: Optional[dict]
    avisos: list[str]
    consultada: bool


def _crs_local(lon: float, lat: float) -> CRS:
    return CRS.from_proj4(
        f"+proj=aeqd +lat_0={lat} +lon_0={lon} +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs"
    )


def analisar_areas_umidas(
    gleba: BaseGeometry, cobertura: Optional[CoberturaUmida]
) -> ResultadoAreasUmidas:
    """Mede a área úmida dentro da gleba (determinístico). Não inventa: sem fonte → não consultada."""
    c = gleba.centroid
    local = _crs_local(c.x, c.y)
    to_local = Transformer.from_crs("EPSG:4326", local, always_xy=True).transform
    to_wgs = Transformer.from_crs(local, "EPSG:4326", always_xy=True).transform
    gleba_l = transform(to_local, gleba)
    area_total = round(gleba_l.area, 2)

    # Sem fonte configurada → NÃO consultada (não inventa).
    if cobertura is None:
        return ResultadoAreasUmidas(
            area_total, None, None, {}, None,
            ["Áreas úmidas não consultadas (fonte de dados não configurada)."],
            consultada=False,
        )
    # Sem geometria: distingue "fonte LIDA, porém zero área úmida" de "não consultada/falha".
    # Honesto: se a fonte respondeu (``cobertura.fonte`` setado), foi CONSULTADA com resultado
    # ZERO — com proveniência —, não a mesma coisa que "não deu p/ consultar".
    if cobertura.geometria is None:
        if cobertura.fonte:
            prov = {
                "fonte": cobertura.fonte,
                "data_referencia": cobertura.data_referencia,
                "classes": list(cobertura.classes),
                "base_legal": BASE_LEGAL_UMIDA,
                "ressalva": RESSALVA_UMIDA,
            }
            return ResultadoAreasUmidas(
                area_total, 0.0, 0.0, {}, prov, list(cobertura.avisos), consultada=True
            )
        avisos = list(cobertura.avisos) or [
            "Áreas úmidas não consultadas (fonte de dados não configurada)."
        ]
        return ResultadoAreasUmidas(area_total, None, None, {}, None, avisos, consultada=False)

    umida_in = transform(to_local, cobertura.geometria).intersection(gleba_l)
    area_umida = round(umida_in.area, 2) if not umida_in.is_empty else 0.0
    pct = round(area_umida / area_total * 100, 2) if area_total > 0 else 0.0
    geojson = mapping(transform(to_wgs, umida_in)) if not umida_in.is_empty else {}
    prov = {
        "fonte": cobertura.fonte,
        "data_referencia": cobertura.data_referencia,
        "classes": list(cobertura.classes),
        "base_legal": BASE_LEGAL_UMIDA,
        "ressalva": RESSALVA_UMIDA,
    }
    return ResultadoAreasUmidas(
        area_total, area_umida, pct, geojson, prov, list(cobertura.avisos), consultada=True
    )


def _coletar(
    fontes: list[str],
    gleba: BaseGeometry,
    classes: set[int],
    fonte_nome: str,
    data_ref: Optional[str] = None,
) -> CoberturaUmida:
    """Lê o(s) raster(es) e devolve a cobertura úmida (reusa o extrator da vegetação).

    ``data_ref`` (ex.: ano do mapa MapBiomas) sobrescreve a data de referência só quando a
    fonte foi REALMENTE lida (proveniência honesta: a data é a do mapa, não a do fetch)."""
    cv = _extrair_cobertura(fontes, gleba, classes, fonte_nome, assunto="área úmida/alagável")
    data = data_ref if (data_ref and cv.fonte) else cv.data_referencia
    return CoberturaUmida(
        geometria=cv.geometria,
        fonte=cv.fonte,
        data_referencia=data,
        classes=cv.classes,
        avisos=cv.avisos,
    )


class FonteAreasUmidasRaster:
    """Lê um recorte raster LOCAL (MapBiomas ou outro) e devolve a área úmida da gleba.

    Modo offline / override Brasil: o recorte (ex.: MapBiomas) é apontado por
    ``AREAS_UMIDAS_RASTER_PATH``. Classes default = MapBiomas {11, 33} (úmida + água).
    """

    def __init__(
        self,
        caminho: str,
        classes: Optional[set[int]] = None,
        fonte: Optional[str] = None,
    ):
        self.caminho = caminho
        self.classes = classes or _classes_env() or CLASSES_UMIDA_MAPBIOMAS
        self.fonte = fonte or os.getenv("AREAS_UMIDAS_FONTE_NOME") or "MapBiomas (campo alagado + água)"

    def areas_umidas(self, gleba: BaseGeometry) -> CoberturaUmida:
        return _coletar([self.caminho], gleba, self.classes, self.fonte)


# COG nacional PÚBLICO do MapBiomas (Google Cloud Storage, anônimo, SEM login) — confirmado
# tiled (256×256), leitura por janela via /vsicurl funciona como no WorldCover. Coleção/ano
# sobrescrevíveis por env (a coleção mais nova muda de tempos em tempos).
MAPBIOMAS_COG_URL = (
    "https://storage.googleapis.com/mapbiomas-public/initiatives/brasil/"
    "collection_{colecao}/lulc/coverage/brazil_coverage_{ano}.tif"
)


class FonteAreasUmidasMapBiomasAuto:
    """Lê o MapBiomas (cobertura nacional) DIRETO do COG público por HTTP, filtrando as classes
    úmidas/água {11, 33}. Lê só a janela da gleba (range requests) — funciona p/ qualquer KMZ
    do Brasil SEM recorte manual. Único requisito: egress ao bucket público no deploy.
    """

    def __init__(
        self,
        classes: Optional[set[int]] = None,
        fonte: Optional[str] = None,
        url: Optional[str] = None,
    ):
        self.classes = classes or _classes_env() or CLASSES_UMIDA_MAPBIOMAS
        self.colecao = os.getenv("MAPBIOMAS_COLECAO", "10")
        self.ano = os.getenv("MAPBIOMAS_ANO", "2024")
        self.url = (
            url
            or os.getenv("AREAS_UMIDAS_MAPBIOMAS_URL")
            or MAPBIOMAS_COG_URL.format(colecao=self.colecao, ano=self.ano)
        )
        self.fonte = (
            fonte
            or os.getenv("AREAS_UMIDAS_FONTE_NOME")
            or f"MapBiomas Col.{self.colecao} ({self.ano}) — campo alagado + água"
        )

    def areas_umidas(self, gleba: BaseGeometry) -> CoberturaUmida:
        _gdal_anon_http_env()
        return _coletar([f"/vsicurl/{self.url}"], gleba, self.classes, self.fonte, data_ref=self.ano)


class FonteAreasUmidasWorldCoverAuto:
    """Lê o ESA WorldCover DIRETO do COG público por HTTP (mesmo tile/janela da vegetação),
    filtrando a classe 90 (área úmida herbácea). Funciona para QUALQUER KMZ sem recorte manual.
    """

    def __init__(self, classes: Optional[set[int]] = None, fonte: Optional[str] = None):
        self.classes = classes or _classes_env() or CLASSES_UMIDA_WORLDCOVER
        self.fonte = (
            fonte or os.getenv("AREAS_UMIDAS_FONTE_NOME") or "ESA WorldCover 10m (2021, COG) — úmida"
        )

    def areas_umidas(self, gleba: BaseGeometry) -> CoberturaUmida:
        _gdal_anon_http_env()
        fontes = [
            f"/vsicurl/{WORLDCOVER_COG_URL.format(tile=t)}" for t in _tiles_da_gleba(gleba.bounds)
        ]
        return _coletar(fontes, gleba, self.classes, self.fonte)


def _classes_env() -> Optional[set[int]]:
    bruto = os.getenv("AREAS_UMIDAS_CLASSES")
    if not bruto:
        return None
    return {int(x) for x in bruto.replace(";", ",").split(",") if x.strip()}


def get_fonte_areas_umidas() -> Optional[FonteAreasUmidas]:
    """Escolhe a fonte de áreas úmidas (degrada honesto se nenhuma servir):

    1. ``AREAS_UMIDAS_RASTER_PATH`` → recorte LOCAL (override; classes MapBiomas {11,33} default).
    2. senão, modo AUTOMÁTICO (default ``MapBiomas`` classe 11 + água via COG/HTTP — captura o
       alagado sazonal BR que o WorldCover não pega). Trocável por ``AREAS_UMIDAS_FONTE=worldcover``.
       Desligável com ``AREAS_UMIDAS_AUTO=0`` (ex.: egress fechado / testes).
    3. senão → ``None`` (não marca, não inventa).
    """
    caminho = os.getenv("AREAS_UMIDAS_RASTER_PATH")
    if caminho:
        return FonteAreasUmidasRaster(caminho)
    if os.getenv("AREAS_UMIDAS_AUTO", "1").strip().lower() in ("0", "false", "no", "off"):
        return None
    if os.getenv("AREAS_UMIDAS_FONTE", "mapbiomas").strip().lower() == "worldcover":
        return FonteAreasUmidasWorldCoverAuto()
    return FonteAreasUmidasMapBiomasAuto()
