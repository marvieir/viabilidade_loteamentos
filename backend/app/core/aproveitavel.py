"""Consolidação das restrições que reduzem a área aproveitável (Fase 2.2+).

Une — SEM dupla contagem — as geometrias não-aproveitáveis dentro da gleba: cobertura
verde (vegetação) + faixas não-edificáveis do ambiental (APP de curso d'água, APP de massa
d'água, faixa não-edificável, servidão de linha de transmissão). Devolve a área da UNIÃO
(o que de fato sai do aproveitável) e o detalhamento por tipo (cuja soma pode exceder a
união, justamente pela sobreposição). Determinístico, em CRS métrico local (AEQD), nunca
em graus.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from pyproj import CRS, Transformer
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform, unary_union

# Rótulos legíveis por tipo de restrição (proveniência → frontend só renderiza).
ROTULOS = {
    "verde": "cobertura vegetal",
    "app": "APP de curso d'água",
    "app_massa_dagua": "APP de massa d'água",
    "faixa_nao_edificavel": "faixa não-edificável",
    "linhas_transmissao": "servidão de linha de transmissão",
}


@dataclass
class ItemRestricao:
    tipo: str
    rotulo: str
    area_m2: float


@dataclass
class Restricoes:
    area_restritiva_m2: float  # área da UNIÃO (o que sai do aproveitável)
    sobreposicao_m2: float  # soma das partes − união (quanto foi contado uma vez só)
    itens: list[ItemRestricao] = field(default_factory=list)


def _crs_local(lon: float, lat: float) -> CRS:
    return CRS.from_proj4(
        f"+proj=aeqd +lat_0={lat} +lon_0={lon} +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs"
    )


def consolidar(
    gleba: BaseGeometry, geometrias: dict[str, Optional[BaseGeometry]]
) -> Restricoes:
    """União das restrições dentro da gleba + área por tipo. ``geometrias`` em WGS84;
    valores ``None``/vazios são ignorados (degradação honesta)."""
    c = gleba.centroid
    local = _crs_local(c.x, c.y)
    to_local = Transformer.from_crs("EPSG:4326", local, always_xy=True).transform
    gleba_l = transform(to_local, gleba)

    partes: list[BaseGeometry] = []
    itens: list[ItemRestricao] = []
    soma = 0.0
    for nome, geom in geometrias.items():
        if geom is None or geom.is_empty:
            continue
        inter = transform(to_local, geom).intersection(gleba_l)
        if inter.is_empty:
            continue
        area = round(inter.area, 2)
        if area <= 0:
            continue
        partes.append(inter)
        soma += area
        itens.append(ItemRestricao(tipo=nome, rotulo=ROTULOS.get(nome, nome), area_m2=area))

    area_uniao = round(unary_union(partes).area, 2) if partes else 0.0
    return Restricoes(
        area_restritiva_m2=area_uniao,
        sobreposicao_m2=round(soma - area_uniao, 2),
        itens=itens,
    )
