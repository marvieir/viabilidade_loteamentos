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
# Endpoints Overpass (espelhos). O serviço público é gratuito e INSTÁVEL (limita/cai) — um único
# host fazia o pórtico cair no fallback toda vez que ele estava fora. Tenta em ordem até um responder.
# Override por env: VIAS_OVERPASS_URLS (lista separada por vírgula) ou VIAS_OVERPASS_URL (1 só).
_DEFAULT_OVERPASS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
)


def _urls_overpass() -> list[str]:
    bruto = os.getenv("VIAS_OVERPASS_URLS") or os.getenv("VIAS_OVERPASS_URL")
    if bruto:
        urls = [u.strip() for u in bruto.split(",") if u.strip()]
        if urls:
            return urls
    return list(_DEFAULT_OVERPASS)


# Compat: nome antigo ainda exportado (1º endpoint efetivo).
URL_OVERPASS = _urls_overpass()[0]
# Entorno consultado ao redor do bbox da gleba (graus): ~600 m pega a via de acesso mais próxima.
BUFFER_GRAUS = float(os.getenv("VIAS_BUFFER_GRAUS", "0.006"))
_TIMEOUT = max(int(os.getenv("VIAS_HTTP_TIMEOUT", "25")), 1)
# Tentativas POR endpoint antes de passar pro próximo (cobre 429/timeout transitório).
_TENTATIVAS = max(int(os.getenv("VIAS_TENTATIVAS", "2")), 1)


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
        # Falha-e-passa-pro-próximo: tenta cada espelho (com retry) até um responder. Só degrada
        # honesto se TODOS falharem — assim um Overpass fora não joga mais o pórtico no fallback.
        falhas: list[str] = []
        d = None
        for url in _urls_overpass():
            for tentativa in range(_TENTATIVAS):
                try:
                    req = urllib.request.Request(
                        url,
                        data=urllib.parse.urlencode({"data": ql}).encode(),
                        headers={
                            "User-Agent": "viabilidade-loteamentos/0.2",
                            "Accept": "application/json",
                        },
                    )
                    with urllib.request.urlopen(req, timeout=_TIMEOUT + 5) as resp:  # noqa: S310 (URL de config)
                        d = json.loads(resp.read().decode("utf-8"))
                    break
                except Exception as exc:  # noqa: BLE001 — tenta o próximo espelho
                    host = urllib.parse.urlparse(url).netloc or url
                    falhas.append(f"{host} ({type(exc).__name__})")
            if d is not None:
                break
        if d is None:
            return CoberturaVias(
                avisos=[f"Vias (OSM/Overpass) indisponíveis — tentativas: {'; '.join(falhas)}"[:300]]
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


class FonteViasComCache:
    """CACHE persistente por gleba em volta da fonte OSM. O Overpass público limita por IP (429) —
    em sessões com muitas regenerações ele cai e o pórtico ia pro fallback 'aleatório'. Agora: a
    PRIMEIRA consulta bem-sucedida é gravada em disco (chave = hash do WKB da gleba) e as demais
    leem do cache — determinístico, rápido e imune a quedas do Overpass. Falhou e não tem cache →
    degrada honesto (o chamador avisa)."""

    def __init__(self, interna: FonteVias, diretorio: str | os.PathLike):
        self.interna = interna
        self.diretorio = diretorio

    def _caminho(self, gleba: BaseGeometry):
        import hashlib
        from pathlib import Path

        chave = hashlib.sha256(gleba.wkb).hexdigest()[:24]
        return Path(self.diretorio) / f"{chave}.json"

    def vias(self, gleba: BaseGeometry) -> CoberturaVias:
        from shapely.geometry import mapping, shape

        caminho = self._caminho(gleba)
        if caminho.exists():
            try:
                d = json.loads(caminho.read_text(encoding="utf-8"))
                return CoberturaVias(
                    geometria=shape(d["geometria"]) if d.get("geometria") else None,
                    fonte=(d.get("fonte") or "OSM") + " · cache",
                    data_referencia=d.get("data_referencia"),
                    avisos=list(d.get("avisos") or []),
                )
            except Exception:  # noqa: BLE001 — cache corrompido → reconsulta
                pass
        cob = self.interna.vias(gleba)
        # Só cacheia consulta RESPONDIDA (com geometria ou "sem via mapeada" confirmado);
        # falha de rede NÃO é cacheada — a próxima geração tenta de novo.
        if cob.fonte is not None:
            try:
                caminho.parent.mkdir(parents=True, exist_ok=True)
                caminho.write_text(
                    json.dumps(
                        {
                            "geometria": mapping(cob.geometria) if cob.geometria is not None else None,
                            "fonte": cob.fonte,
                            "data_referencia": cob.data_referencia,
                            "avisos": cob.avisos,
                        }
                    ),
                    encoding="utf-8",
                )
            except Exception:  # noqa: BLE001 — cache é otimização; falha não derruba
                pass
        return cob


def get_fonte_vias() -> Optional[FonteVias]:
    """Fonte de vias p/ o pórtico. PADRÃO = OSM automático com CACHE persistente por gleba.
    Desligável com ``VIAS_OSM_AUTO=0`` (ex.: egress fechado / testes) → fallback do miolo loteado."""
    if os.getenv("VIAS_OSM_AUTO", "1").strip().lower() in ("0", "false", "no", "off"):
        return None
    from pathlib import Path

    padrao = Path(__file__).resolve().parent.parent / "perfis" / "vias"
    return FonteViasComCache(FonteViasOSM(), os.getenv("VIAS_CACHE_DIR", str(padrao)))
