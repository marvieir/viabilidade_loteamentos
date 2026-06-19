"""Fase 10 (Parte 1) — TAXONOMIA CANÔNICA DE ÁREAS: a fonte ÚNICA de "área líquida aproveitável".

O problema (medido): três funções calculavam "área líquida" subtraindo coisas diferentes
(`vegetacao.py` = gleba − vegetação; `aproveitavel.py` = gleba − restrições; `urbanismo_medida.py`
= união do que foi loteado), e nenhuma lia da outra → as abas se contradiziam. Este módulo é a
DEFINIÇÃO ÚNICA (catálogo §10): toda aba LÊ daqui, ninguém recalcula.

    GLEBA BRUTA
      − RESTRIÇÕES FÍSICAS não-edificáveis (vegetação ∪ declividade≥30% ∪ APP), SEM dupla contagem
      = ÁREA LÍQUIDA APROVEITÁVEL   ← o único "líquida/aproveitável" do produto

Determinístico, em CRS métrico local (AEQD), nunca em graus (§2). APP NÃO conta para verde/
institucional/viário (catálogo §1) — entra aqui como restrição física, sai ANTES da líquida.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from pyproj import CRS, Transformer
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform, unary_union


@dataclass
class AreasCanonicas:
    """Os números canônicos de área. ``*_m2`` em metros² (CRS métrico local). A líquida é o ÚNICO
    valor de "aproveitável" — toda aba que exibir gleba/vegetação/declividade/líquida usa estes."""

    gleba_bruta_m2: float
    vegetacao_m2: float
    declividade_30_m2: float
    app_m2: float
    restricoes_fisicas_m2: float        # área da UNIÃO (o que de fato sai da líquida)
    sobreposicao_m2: float              # soma das partes − união (descontado uma vez só)
    area_liquida_aproveitavel_m2: float  # gleba − união(restrições físicas)


def _crs_local(lon: float, lat: float) -> CRS:
    return CRS.from_proj4(
        f"+proj=aeqd +lat_0={lat} +lon_0={lon} +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs"
    )


def _area_intersec(geom: Optional[BaseGeometry], gleba_l: BaseGeometry, to_local) -> tuple[float, Optional[BaseGeometry]]:
    if geom is None or geom.is_empty:
        return 0.0, None
    inter = transform(to_local, geom).intersection(gleba_l)
    if inter.is_empty or inter.area <= 0:
        return 0.0, None
    return round(inter.area, 2), inter


def computar_areas_canonicas(
    gleba: BaseGeometry,
    vegetacao: Optional[BaseGeometry] = None,
    declividade: Optional[BaseGeometry] = None,
    app: Optional[BaseGeometry] = None,
) -> AreasCanonicas:
    """Calcula os números canônicos a partir da gleba (WGS84) e das três restrições físicas (WGS84,
    podem ser ``None``/vazias → degradação honesta, não inventa). A LÍQUIDA é gleba − UNIÃO das
    restrições (sem dupla contagem onde elas se sobrepõem). Esta é a única definição (catálogo §10)."""
    c = gleba.centroid
    to_local = Transformer.from_crs("EPSG:4326", _crs_local(c.x, c.y), always_xy=True).transform
    gleba_l = transform(to_local, gleba)
    gleba_bruta = round(gleba_l.area, 2)

    veg_a, veg_g = _area_intersec(vegetacao, gleba_l, to_local)
    dec_a, dec_g = _area_intersec(declividade, gleba_l, to_local)
    app_a, app_g = _area_intersec(app, gleba_l, to_local)

    partes = [g for g in (veg_g, dec_g, app_g) if g is not None]
    uniao = round(unary_union(partes).area, 2) if partes else 0.0
    soma = veg_a + dec_a + app_a
    liquida = round(max(gleba_bruta - uniao, 0.0), 2)
    return AreasCanonicas(
        gleba_bruta_m2=gleba_bruta,
        vegetacao_m2=veg_a,
        declividade_30_m2=dec_a,
        app_m2=app_a,
        restricoes_fisicas_m2=uniao,
        sobreposicao_m2=round(soma - uniao, 2),
        area_liquida_aproveitavel_m2=liquida,
    )
