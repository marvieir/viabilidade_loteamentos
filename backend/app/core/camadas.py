"""Camadas ambientais oficiais — interface de aquisição (PIPELINE, não agente).

A aquisição de cada camada é **download de um endpoint oficial conhecido + cache local**,
recortado pelo bounding box da gleba. NUNCA agente/LLM (regra inegociável nº 1 e nº 2 do
ARCHITECTURE.md): o cruzamento espacial é determinístico (shapely) e cada feição carrega
proveniência (camada + data de referência).

A FONTE é uma INTERFACE INJETÁVEL (mesmo padrão do resolvedor de jurisdição da Fase 1):

- PRODUÇÃO (default): `get_fonte_camadas()` devolve ``None`` → nenhuma camada consultada.
  É degradação honesta, não placeholder: o endpoint responde sem alertas e avisa que as
  camadas não foram consultadas. Para LIGAR a aquisição real, injete `FonteCamadasINDE`
  (ver `camadas_inde.py`) — decisão idêntica à do resolvedor de jurisdição, que mantém
  determinismo e testes 100% offline.
- TESTES: sobrescrito via ``app.dependency_overrides`` com um stub determinístico.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Protocol, runtime_checkable

from shapely.geometry.base import BaseGeometry

# bbox da gleba: (min_lon, min_lat, max_lon, max_lat) — igual a shapely `.bounds`.
BBox = tuple[float, float, float, float]


@dataclass(frozen=True)
class FeicaoHidrografia:
    """Curso d'água. ``largura_m=None`` = largura não informada pela camada."""

    geometria: BaseGeometry  # LineString/MultiLineString/Polygon (WGS84)
    largura_m: Optional[float] = None
    nome: Optional[str] = None


@dataclass(frozen=True)
class FeicaoUC:
    """Unidade de conservação."""

    geometria: BaseGeometry  # Polygon/MultiPolygon (WGS84)
    nome: str
    grupo: Optional[str] = None  # "Proteção Integral" | "Uso Sustentável"


@dataclass(frozen=True)
class FeicaoMineracao:
    """Processo minerário (ANM/SIGMINE)."""

    geometria: BaseGeometry  # Polygon/MultiPolygon (WGS84)
    processo: str
    fase: Optional[str] = None  # "concessão de lavra", "requerimento de pesquisa", ...


@dataclass
class Camadas:
    """Feições recortadas para o bbox da gleba + proveniência (data) por camada.

    ``data_*`` é ``None`` quando a camada não foi consultada — isso vira aviso honesto
    no relatório (não se inventa alerta nem ausência de alerta sobre camada não lida).
    """

    hidrografia: list[FeicaoHidrografia] = field(default_factory=list)
    unidades_conservacao: list[FeicaoUC] = field(default_factory=list)
    mineracao: list[FeicaoMineracao] = field(default_factory=list)
    data_hidrografia: Optional[str] = None
    data_uc: Optional[str] = None
    data_mineracao: Optional[str] = None
    avisos: list[str] = field(default_factory=list)


@runtime_checkable
class FonteCamadas(Protocol):
    """Contrato de aquisição: dado o bbox (e a UF, p/ recorte SIGMINE), devolve Camadas."""

    def coletar(self, bbox: BBox, uf: Optional[str]) -> Camadas: ...


def get_fonte_camadas() -> Optional[FonteCamadas]:
    """Dependência FastAPI da fonte de camadas.

    PRODUÇÃO: ``None`` (nenhuma fonte configurada) → degradação graciosa.
    TESTES: sobrescrito via ``app.dependency_overrides`` por um stub offline.
    """
    return None
