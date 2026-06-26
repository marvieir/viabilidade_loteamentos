"""Fonte de VIAS (ruas do entorno da gleba) — OpenStreetMap via Overpass API.

Serve para posicionar o PÓRTICO/entrada do loteamento DE FRENTE à via de acesso mais próxima.
Requisito GERAL (vale p/ qualquer terreno no mundo, não customizado por KMZ/localidade): o OSM
tem a malha viária global. Determinístico: mesma gleba + mesmas vias → mesmo ponto de acesso.
Sem rede / sem via mapeada → degrada (``geometria=None``) e o motor cai no fallback (contato
mais perto do miolo loteado). NUNCA inventa via.
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import date
from typing import Optional, Protocol, runtime_checkable

from shapely.geometry import LineString
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

# Tipos de via DIRIGÍVEIS (acesso de veículo) — exclui trilha/calçada/ciclovia/escada.
OSM_HIGHWAYS = (
    "motorway|trunk|primary|secondary|tertiary|unclassified|residential|living_street|"
    "service|track|road|motorway_link|trunk_link|primary_link|secondary_link|tertiary_link"
)
URL_OVERPASS = os.getenv("VIAS_OVERPASS_URL", "https://overpass-api.de/api/interpreter")
# Entorno consultado ao redor do bbox da gleba (graus): ~600 m pega a via de acesso mais próxima.
BUFFER_GRAUS = float(os.getenv("VIAS_BUFFER_GRAUS", "0.006"))
_TIMEOUT = max(int(os.getenv("VIAS_HTTP_TIMEOUT", "25")), 1)


@dataclass
class CoberturaVias:
    """Vias do entorno (WGS84). ``geometria=None`` = não consultada / nenhuma via."""

    geometria: Optional[BaseGeometry] = None  # MultiLineString (WGS84)
    fonte: Optional[str] = None
    data_referencia: Optional[str] = None
    avisos: list[str] = field(default_factory=list)


@runtime_checkable
class FonteVias(Protocol):
    def vias(self, gleba: BaseGeometry) -> CoberturaVias: ...


class FonteViasOSM:
    """Consulta o Overpass do OSM as vias dirigíveis no entorno da gleba (bbox + buffer)."""

    def vias(self, gleba: BaseGeometry) -> CoberturaVias:
        minx, miny, maxx, maxy = gleba.bounds
        b = BUFFER_GRAUS
        bbox = f"{miny - b},{minx - b},{maxy + b},{maxx + b}"  # S,W,N,E (ordem do Overpass)
        ql = (
            f'[out:json][timeout:{_TIMEOUT}];'
            f'way["highway"~"^({OSM_HIGHWAYS})$"]({bbox});out geom;'
        )
        try:
            req = urllib.request.Request(
                URL_OVERPASS,
                data=urllib.parse.urlencode({"data": ql}).encode(),
                headers={
                    "User-Agent": "viabilidade-loteamentos/0.2",
                    "Accept": "application/json",
                },
            )
            with urllib.request.urlopen(req, timeout=_TIMEOUT + 5) as resp:  # noqa: S310 (URL de config)
                d = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001 — sem rede/Overpass fora → degrada honesto
            return CoberturaVias(
                avisos=[f"Vias (OSM/Overpass) indisponíveis — {type(exc).__name__}: {exc}"[:200]]
            )

        linhas = []
        for el in d.get("elements", []):
            g = el.get("geometry") or []
            pts = [(p["lon"], p["lat"]) for p in g if "lon" in p and "lat" in p]
            if len(pts) >= 2:
                linhas.append(LineString(pts))
        if not linhas:
            return CoberturaVias(
                fonte="OpenStreetMap (Overpass)",
                data_referencia=date.today().isoformat(),
                avisos=["Nenhuma via mapeada no entorno da gleba (OSM)."],
            )
        return CoberturaVias(
            geometria=unary_union(linhas),
            fonte="OpenStreetMap (Overpass)",
            data_referencia=date.today().isoformat(),
        )


def get_fonte_vias() -> Optional[FonteVias]:
    """Fonte de vias p/ o pórtico. PADRÃO = OSM automático (qualquer gleba, sem config). Desligável
    com ``VIAS_OSM_AUTO=0`` (ex.: egress fechado / testes) → motor usa o fallback do miolo loteado."""
    if os.getenv("VIAS_OSM_AUTO", "1").strip().lower() in ("0", "false", "no", "off"):
        return None
    return FonteViasOSM()
