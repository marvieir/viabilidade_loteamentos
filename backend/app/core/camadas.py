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


@dataclass(frozen=True)
class FeicaoLinhaTransmissao:
    """Linha de transmissão (ANEEL/SIGEL) → faixa de servidão por tensão (NBR 5422)."""

    geometria: BaseGeometry  # LineString/MultiLineString (WGS84)
    tensao_kv: Optional[float] = None  # None = tensão não informada pela camada
    nome: Optional[str] = None


@dataclass(frozen=True)
class FeicaoMassaDagua:
    """Massa d'água: lago, lagoa ou reservatório (ANA Massa_dágua). Polígono → APP marginal
    (Cód. Florestal art. 4º, II/III). Distinta do curso d'água (linha)."""

    geometria: BaseGeometry  # Polygon/MultiPolygon (WGS84)
    nome: Optional[str] = None
    tipo: Optional[str] = None  # natural/artificial, se a fonte informar


@dataclass(frozen=True)
class FeicaoRestricao:
    """Restrição territorial GENÉRICA de triagem por interseção (mesma forma p/ várias camadas:
    Mata Atlântica, Terra Indígena, Quilombola, Assentamento, Caverna, APM, Dutovia…).

    Cada feição carrega a própria proveniência (``camada`` + ``data_referencia``) e o texto legal
    (``detalhe``), porque cada fonte tem origem/data distintas. ``buffer_m`` > 0 trata feição de
    PONTO/LINHA como faixa (caverna = raio de influência; dutovia = faixa non aedificandi)."""

    geometria: BaseGeometry  # Polygon/Line/Point (WGS84)
    tipo: str  # TERRA_INDIGENA | TERRITORIO_QUILOMBOLA | ASSENTAMENTO | MATA_ATLANTICA | CAVERNA | AREA_PROTECAO_MANANCIAL | DUTOVIA
    overlay_key: str  # chave do overlay no mapa
    camada: str  # rótulo de proveniência (fonte)
    nome: Optional[str] = None
    detalhe: Optional[str] = None
    severidade: str = "ALERTA"  # "ALERTA" | "INFORMATIVO"
    buffer_m: float = 0.0
    data_referencia: Optional[str] = None


@dataclass(frozen=True)
class FeicaoReservaLegal:
    """Reserva Legal averbada no CAR (SICAR). Polígono da RL do imóvel rural — área de uso
    restrito (Lei 12.651/2012, art. 12 e ss.), non aedificandi para parcelamento."""

    geometria: BaseGeometry  # Polygon/MultiPolygon (WGS84)
    cod_imovel: Optional[str] = None  # código do imóvel no CAR, se a fonte informar


@dataclass
class Camadas:
    """Feições recortadas para o bbox da gleba + proveniência (data) por camada.

    ``data_*`` é ``None`` quando a camada não foi consultada — isso vira aviso honesto
    no relatório (não se inventa alerta nem ausência de alerta sobre camada não lida).
    """

    hidrografia: list[FeicaoHidrografia] = field(default_factory=list)
    unidades_conservacao: list[FeicaoUC] = field(default_factory=list)
    mineracao: list[FeicaoMineracao] = field(default_factory=list)
    linhas_transmissao: list[FeicaoLinhaTransmissao] = field(default_factory=list)
    massas_dagua: list[FeicaoMassaDagua] = field(default_factory=list)
    reserva_legal: list[FeicaoReservaLegal] = field(default_factory=list)
    restricoes: list[FeicaoRestricao] = field(default_factory=list)  # camadas genéricas de interseção
    data_hidrografia: Optional[str] = None
    data_uc: Optional[str] = None
    data_mineracao: Optional[str] = None
    data_lt: Optional[str] = None
    data_massa_dagua: Optional[str] = None
    data_reserva_legal: Optional[str] = None
    # Degradação por camada (Fase 2.1): quais camadas foram efetivamente consultadas e
    # quais falharam — códigos curtos (SIGMINE/ANA/ICMBio/ANEEL). Uma fonte fora do ar
    # entra em ``indisponiveis`` sem derrubar as demais.
    consultadas: list[str] = field(default_factory=list)
    indisponiveis: list[str] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)


@runtime_checkable
class FonteCamadas(Protocol):
    """Contrato de aquisição: dado o bbox (e a UF, p/ recorte SIGMINE), devolve Camadas."""

    def coletar(self, bbox: BBox, uf: Optional[str]) -> Camadas: ...


def get_fonte_camadas() -> Optional[FonteCamadas]:
    """Dependência FastAPI da fonte de camadas.

    PRODUÇÃO: ``None`` por padrão (degradação graciosa). Para LIGAR a aquisição real
    (Fase 2.1), defina ``AMBIENTAL_FONTE_REAL=1`` → devolve ``FonteCamadasINDE`` (pipeline
    SIGMINE/ANA/ICMBio/ANEEL). Análogo ao ``MALHA_IBGE_PATH`` da jurisdição: o código fica
    pronto e desligável; ligar é um passo de operação, não de build.
    TESTES: sobrescrito via ``app.dependency_overrides`` por um stub offline.
    """
    import os

    if os.getenv("AMBIENTAL_FONTE_REAL"):
        from app.core.camadas_inde import FonteCamadasINDE

        return FonteCamadasINDE()
    return None
