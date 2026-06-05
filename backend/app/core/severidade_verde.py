"""Severidade do verde (Fase 2.3) — separa restrição dura de 'a verificar'.

Decompõe a cobertura vegetal da gleba em dois baldes por proteção legal, SEM mudar o
desconto conservador da 2.2 (todo o verde continua fora do aproveitável de triagem):
  - **restrição dura**: verde dentro de APP/UC (supressão em geral PROIBIDA);
  - **a verificar**:    verde fora dessas zonas (PODE ser liberado por laudo + licença).

Função pura e determinística, CRS métrico local (AEQD, igual à 2.2), só geometria (shapely).
NÃO emite parecer de supressão; classificar mata nativa/suprimível é laudo de campo, fora
do escopo. Reusa as geometrias que a 2.1 já produz (nada de dado externo novo).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pyproj import CRS, Transformer
from shapely.geometry import GeometryCollection, mapping
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform, unary_union

# Camadas que PROTEGEM a vegetação (supressão em geral proibida) → restrição dura.
CAMADAS_PROTECAO = ("app", "app_massa_dagua", "uc")
# Camadas que impedem CONSTRUIR (mesmo se a mata for suprimível, não vira área útil).
CAMADAS_NAO_EDIFICAVEL = ("faixa_nao_edificavel", "linhas_transmissao")

RESSALVA = (
    "Verde fora de APP/UC PODE ser suprimível mediante laudo de engenheiro ambiental e "
    "licença do órgão competente. Triagem, não parecer. Classificação de mata "
    "nativa/suprimível exige campo."
)


@dataclass
class BucketVerde:
    area_m2: float
    pct_do_verde: float
    geojson: dict = field(default_factory=dict)


@dataclass
class SeveridadeVerde:
    verde_total_m2: float
    restricao_dura: BucketVerde
    a_verificar: BucketVerde
    fontes_dura: list[str]
    potencial_desbloqueavel_m2: float


def _crs_local(lon: float, lat: float) -> CRS:
    return CRS.from_proj4(
        f"+proj=aeqd +lat_0={lat} +lon_0={lon} +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs"
    )


def classificar_severidade_verde(
    gleba: BaseGeometry,
    verde_geom: BaseGeometry,
    camadas: dict[str, BaseGeometry],
) -> SeveridadeVerde:
    """Divide o verde (∩ gleba) em restrição dura × a verificar. ``camadas`` em WGS84.

    Invariante: ``restricao_dura.area + a_verificar.area == verde_total`` (intersection +
    difference cobrem o verde sem dupla contagem). Determinístico.
    """
    c = gleba.centroid
    local = _crs_local(c.x, c.y)
    to_local = Transformer.from_crs("EPSG:4326", local, always_xy=True).transform
    to_wgs = Transformer.from_crs(local, "EPSG:4326", always_xy=True).transform

    gleba_l = transform(to_local, gleba)
    verde_l = transform(to_local, verde_geom).intersection(gleba_l)
    verde_total = round(verde_l.area, 2)

    # Zona de proteção da vegetação = união(APP ∪ massa d'água ∪ UC) que de fato existe.
    protecao: list[BaseGeometry] = []
    fontes: list[str] = []
    for nome in CAMADAS_PROTECAO:
        g = camadas.get(nome)
        if g is None or g.is_empty:
            continue
        gl = transform(to_local, g)
        if not gl.intersection(verde_l).is_empty:
            fontes.append(nome)
        protecao.append(gl)

    if protecao:
        zona = unary_union(protecao)
        dura_l = verde_l.intersection(zona)
        averif_l = verde_l.difference(zona)
    else:
        dura_l = GeometryCollection()
        averif_l = verde_l

    dura_area = round(dura_l.area, 2)
    averif_area = round(averif_l.area, 2)

    # Potencial desbloqueável = a_verificar − (faixa não-edif. ∪ servidão LT): suprimir mata
    # sob linhão/faixa não libera área construível. Clamp >= 0.
    naoedif = [
        transform(to_local, camadas[n])
        for n in CAMADAS_NAO_EDIFICAVEL
        if camadas.get(n) is not None and not camadas[n].is_empty
    ]
    if naoedif:
        potencial = max(round(averif_l.difference(unary_union(naoedif)).area, 2), 0.0)
    else:
        potencial = averif_area

    def _bucket(geom_l: BaseGeometry, area: float) -> BucketVerde:
        pct = round(area / verde_total, 4) if verde_total > 0 else 0.0
        gj = mapping(transform(to_wgs, geom_l)) if not geom_l.is_empty else {}
        return BucketVerde(area_m2=area, pct_do_verde=pct, geojson=gj)

    return SeveridadeVerde(
        verde_total_m2=verde_total,
        restricao_dura=_bucket(dura_l, dura_area),
        a_verificar=_bucket(averif_l, averif_area),
        fontes_dura=fontes,
        potencial_desbloqueavel_m2=potencial,
    )
