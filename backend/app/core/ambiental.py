"""Motor ambiental (Fase 2) — interseção espacial determinística + buffers legais.

PURO: recebe a gleba (Polygon WGS84) e as camadas já coletadas (`Camadas`) e devolve
alertas + overlays GeoJSON. Não toca em rede (a aquisição é a fonte injetável). Buffers e
áreas são calculados em CRS MÉTRICO LOCAL (azimutal equidistante no centróide da gleba),
nunca em graus — coerente com a regra "geodésico, não área em graus" do ARCHITECTURE.md.

Determinismo: mesma gleba + mesmas camadas → mesmos alertas e overlays, sempre.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from pyproj import CRS, Transformer
from shapely.geometry import mapping
from shapely.ops import transform, unary_union

from app.core.camadas import Camadas

# Faixa de APP por largura do curso d'água (Lei 12.651/2012, art. 4º, I).
# (limite_superior_largura_m, buffer_m). Acima do último limite → APP_MAXIMA_M.
_FAIXAS_APP: list[tuple[float, float]] = [
    (10.0, 30.0),    # até 10 m de largura → 30 m
    (50.0, 50.0),    # 10 a 50 m → 50 m
    (200.0, 100.0),  # 50 a 200 m → 100 m
    (600.0, 200.0),  # 200 a 600 m → 200 m
]
APP_MINIMA_M = 30.0            # mínimo legal e default conservador (largura desconhecida)
APP_MAXIMA_M = 500.0           # acima de 600 m de largura
FAIXA_NAO_EDIFICAVEL_M = 15.0  # Lei 6.766/79, art. 4º, III (cada lado de águas)

# Faixa de servidão de linha de transmissão (Fase 2.1) — semi-faixa: buffer de CADA LADO
# da LT, por tensão. NBR 5422 / ARCHITECTURE.md §5 (20/40/70 m para 69/230/500 kV).
# (limite_superior_tensao_kV, semifaixa_m).
_FAIXAS_SERVIDAO: list[tuple[float, float]] = [
    (69.0, 20.0),    # até 69 kV → 20 m
    (230.0, 40.0),   # 69 a 230 kV → 40 m
]
SERVIDAO_MAXIMA_M = 70.0   # acima de 230 kV (ex.: 500 kV)
SERVIDAO_DEFAULT_M = 70.0  # tensão não confirmada → faixa máxima (triagem conservadora)

# Cada alerta é triagem, não veredito (restrição inegociável da Fase 2).
RESSALVA = (
    "caráter informativo — triagem conservadora, não veredito; "
    "verificar instrumento oficial junto ao órgão competente"
)

CAMADA_HIDRO = "ANA/IBGE — hidrografia"
CAMADA_UC = "ICMBio/CNUC — unidades de conservação"
CAMADA_MINERACAO = "SIGMINE/ANM — processos minerários"
CAMADA_LT = "ANEEL/SIGEL — linhas de transmissão"


def app_por_largura(largura_m: Optional[float]) -> float:
    """Buffer de APP (m) pela largura do curso. ``None`` → mínimo conservador de 30 m."""
    if largura_m is None:
        return APP_MINIMA_M
    for limite, buffer in _FAIXAS_APP:
        if largura_m <= limite:
            return buffer
    return APP_MAXIMA_M


def faixa_servidao(tensao_kv: Optional[float]) -> float:
    """Semi-faixa de servidão (m, de cada lado da LT) pela tensão. ``None`` → faixa máxima
    (70 m), como triagem conservadora — ``mais restritivo aplicável`` do ARCHITECTURE.md."""
    if tensao_kv is None:
        return SERVIDAO_DEFAULT_M
    for limite, faixa in _FAIXAS_SERVIDAO:
        if tensao_kv <= limite:
            return faixa
    return SERVIDAO_MAXIMA_M


def _crs_local(lon: float, lat: float) -> CRS:
    """CRS azimutal equidistante centrado na gleba — distâncias/áreas locais em metros."""
    return CRS.from_proj4(
        f"+proj=aeqd +lat_0={lat} +lon_0={lon} +x_0=0 +y_0=0 "
        "+datum=WGS84 +units=m +no_defs"
    )


@dataclass
class Alerta:
    tipo: str
    severidade: str
    intersecta: bool
    detalhe: str
    camada: str
    data_referencia: Optional[str]
    area_afetada_m2: Optional[float] = None
    largura_confirmada: Optional[bool] = None


@dataclass
class ResultadoAmbiental:
    alertas: list[Alerta] = field(default_factory=list)
    geojson_overlays: dict = field(default_factory=dict)
    avisos: list[str] = field(default_factory=list)
    sem_alertas: bool = True
    camadas_consultadas: list[str] = field(default_factory=list)
    camadas_indisponiveis: list[str] = field(default_factory=list)


def analisar(gleba, camadas: Camadas) -> ResultadoAmbiental:
    """Cruza a gleba contra as camadas e devolve alertas + overlays (determinístico)."""
    c = gleba.centroid
    local = _crs_local(c.x, c.y)
    to_local = Transformer.from_crs("EPSG:4326", local, always_xy=True).transform
    to_wgs = Transformer.from_crs(local, "EPSG:4326", always_xy=True).transform

    gleba_l = transform(to_local, gleba)

    alertas: list[Alerta] = []
    avisos: list[str] = list(camadas.avisos)
    overlays: dict = {}

    # --- Hidrografia → APP (Cód. Florestal) + faixa não-edificável (Lei 6.766) ---
    app_bands, faixa_bands = [], []
    largura_desconhecida = False
    for f in camadas.hidrografia:
        geom_l = transform(to_local, f.geometria)
        app_bands.append(geom_l.buffer(app_por_largura(f.largura_m)))
        faixa_bands.append(geom_l.buffer(FAIXA_NAO_EDIFICAVEL_M))
        if f.largura_m is None:
            largura_desconhecida = True

    if app_bands:
        app_union = unary_union(app_bands)
        faixa_union = unary_union(faixa_bands)
        overlays["app"] = mapping(transform(to_wgs, app_union))
        overlays["faixa_nao_edificavel"] = mapping(transform(to_wgs, faixa_union))

        inter_app = app_union.intersection(gleba_l)
        if not inter_app.is_empty and inter_app.area > 0:
            largura_conf = not largura_desconhecida
            detalhe = (
                "Faixa de APP de hidrografia incide sobre a gleba "
                f"(buffer ≥ {int(APP_MINIMA_M)} m, Cód. Florestal art. 4º, I)."
            )
            if not largura_conf:
                detalhe += " Largura do curso não confirmada — aplicado o mínimo de 30 m."
                avisos.append(
                    "largura do curso d'água não confirmada — "
                    "APP aplicada com mínimo de 30 m"
                )
            alertas.append(
                Alerta(
                    tipo="APP_HIDROGRAFIA",
                    severidade="ALERTA",
                    intersecta=True,
                    detalhe=detalhe,
                    camada=CAMADA_HIDRO,
                    data_referencia=camadas.data_hidrografia,
                    area_afetada_m2=round(inter_app.area, 2),
                    largura_confirmada=largura_conf,
                )
            )

        inter_faixa = faixa_union.intersection(gleba_l)
        if not inter_faixa.is_empty and inter_faixa.area > 0:
            alertas.append(
                Alerta(
                    tipo="FAIXA_NAO_EDIFICAVEL",
                    severidade="INFORMATIVO",
                    intersecta=True,
                    detalhe=(
                        "Faixa não-edificável de 15 m de águas (Lei 6.766/79 art. 4º, III); "
                        "a APP (maior buffer) prevalece como restrição."
                    ),
                    camada=CAMADA_HIDRO,
                    data_referencia=camadas.data_hidrografia,
                    area_afetada_m2=round(inter_faixa.area, 2),
                )
            )

    # --- Unidades de conservação ---
    ucs = []
    for f in camadas.unidades_conservacao:
        geom_l = transform(to_local, f.geometria)
        inter = geom_l.intersection(gleba_l)
        if not inter.is_empty and inter.area > 0:
            ucs.append(geom_l)
            alertas.append(
                Alerta(
                    tipo="UNIDADE_CONSERVACAO",
                    severidade="ALERTA",
                    intersecta=True,
                    detalhe="Sobreposição com unidade de conservação: "
                    + f.nome
                    + (f" ({f.grupo})" if f.grupo else ""),
                    camada=CAMADA_UC,
                    data_referencia=camadas.data_uc,
                    area_afetada_m2=round(inter.area, 2),
                )
            )
    if ucs:
        overlays["uc"] = mapping(transform(to_wgs, unary_union(ucs)))

    # --- Mineração ---
    minas = []
    for f in camadas.mineracao:
        geom_l = transform(to_local, f.geometria)
        inter = geom_l.intersection(gleba_l)
        if not inter.is_empty and inter.area > 0:
            minas.append(geom_l)
            alertas.append(
                Alerta(
                    tipo="MINERACAO",
                    severidade="ALERTA",
                    intersecta=True,
                    detalhe="Processo minerário ANM "
                    + f.processo
                    + (f" — {f.fase}" if f.fase else ""),
                    camada=CAMADA_MINERACAO,
                    data_referencia=camadas.data_mineracao,
                    area_afetada_m2=round(inter.area, 2),
                )
            )
    if minas:
        overlays["mineracao"] = mapping(transform(to_wgs, unary_union(minas)))

    # --- Linhas de transmissão (ANEEL) → faixa de servidão por tensão ---
    lt_bands = []
    tensao_desconhecida = False
    for f in camadas.linhas_transmissao:
        geom_l = transform(to_local, f.geometria)
        lt_bands.append(geom_l.buffer(faixa_servidao(f.tensao_kv)))
        if f.tensao_kv is None:
            tensao_desconhecida = True
    if lt_bands:
        lt_union = unary_union(lt_bands)
        overlays["linhas_transmissao"] = mapping(transform(to_wgs, lt_union))
        inter_lt = lt_union.intersection(gleba_l)
        if not inter_lt.is_empty and inter_lt.area > 0:
            detalhe = (
                "Faixa de servidão de linha de transmissão incide sobre a gleba "
                "(NBR 5422; largura por tensão)."
            )
            if tensao_desconhecida:
                detalhe += " Tensão não confirmada — aplicada a faixa máxima de 70 m."
                avisos.append(
                    "tensão da LT não confirmada — faixa de servidão aplicada no "
                    "máximo (70 m)"
                )
            alertas.append(
                Alerta(
                    tipo="FAIXA_SERVIDAO_LT",
                    severidade="ALERTA",
                    intersecta=True,
                    detalhe=detalhe,
                    camada=CAMADA_LT,
                    data_referencia=camadas.data_lt,
                    area_afetada_m2=round(inter_lt.area, 2),
                )
            )

    return ResultadoAmbiental(
        alertas=alertas,
        geojson_overlays=overlays,
        avisos=avisos,
        sem_alertas=len(alertas) == 0,
        camadas_consultadas=list(camadas.consultadas),
        camadas_indisponiveis=list(camadas.indisponiveis),
    )
