"""Contratos de API (Pydantic v2). O frontend renderiza exatamente estes shapes."""

from typing import Literal, Optional

from pydantic import BaseModel, Field


# ----- POST /api/analises -----

class GeometriaOut(BaseModel):
    area_m2: float
    area_ha: float
    perimetro_m: float
    geojson: dict  # Polygon WGS84, para o mapa


class MunicipioOut(BaseModel):
    cod_ibge: str
    municipio: str
    uf: str


class CandidatoOut(MunicipioOut):
    """Candidato na divisa, com a fração da gleba que cai nele (% de área, 0–100)."""

    pct_area: float


class JurisdicaoOut(BaseModel):
    municipio: Optional[str]
    uf: Optional[str]
    cod_ibge: Optional[str]
    cobertura: Literal["BASE_FEDERAL", "PARCIAL_UF", "COMPLETA"]
    origem: Literal["detectado", "aproximado", "informado"] = "detectado"
    cruza_divisa: bool = False
    candidatos: list[CandidatoOut] = []
    nao_considerado: list[str] = []


class MunicipioIn(BaseModel):
    """Correção/seleção manual do município (override)."""

    cod_ibge: str


class OrigemGeometriaOut(BaseModel):
    """Proveniência da rota de ingestão (Fase 1.5)."""

    rota: Literal["POLYGON_DIRETO", "LINHA_FECHAVEL"]
    descricao: str


class AnaliseOut(BaseModel):
    analise_id: str
    geometria: GeometriaOut
    jurisdicao: JurisdicaoOut
    origem_geometria: OrigemGeometriaOut
    avisos: list[str] = []


# ----- POST /api/analises/{id}/aproveitamento -----

class LoteamentoIn(BaseModel):
    vias_m2: float = Field(ge=0)
    doacao_pct: float = Field(ge=0, le=1)
    base_doacao: Literal["total", "liquida", "combinada"]
    combinado_pct: float = Field(default=0.35, ge=0, le=1)


class DesmembramentoIn(BaseModel):
    fator_aprov: float = Field(default=0.74, gt=0, le=1)


ModalidadeUrbana = Literal[
    "desmembramento",
    "loteamento_aberto",
    "loteamento_fechado",
    "condominio_lotes",
    "condominio_edilicio",
]


class AproveitamentoIn(BaseModel):
    """Pedido de aproveitamento. ``regime`` é obrigatório (validado no router →
    422 ``regime_obrigatorio``); os demais campos dependem do regime escolhido."""

    regime: Optional[Literal["URBANO", "RURAL"]] = None
    # RURAL — FMP do município (puxada da tabela; editável se município não resolvido)
    fmp_m2: Optional[float] = Field(default=None, gt=0)
    # URBANO — lote declarado (pendente extração da LUOS, Fase 1.8)
    modalidade: Optional[ModalidadeUrbana] = None
    lote_min_m2: Optional[float] = Field(default=None, gt=0)
    loteamento: Optional[LoteamentoIn] = None
    desmembramento: DesmembramentoIn = Field(default_factory=DesmembramentoIn)


class ModalidadeOut(BaseModel):
    area_aproveitavel_m2: float
    pct_aproveitamento: float
    n_lotes: int
    proveniencia: str


class LoteamentoOut(ModalidadeOut):
    base_doacao: str


class RuralOut(BaseModel):
    fmp_m2: float
    n_parcelas: int
    area_m2: float
    fmp_origem: str  # "tabela INCRA" | "informado pelo usuário" | "default 2 ha (confirmar no CCIR)"
    flag_conversao: str
    proveniencia: str


class AproveitamentoOut(BaseModel):
    regime: Literal["URBANO", "RURAL"]
    premissa: str
    # URBANO
    origem_lote: Optional[str] = None
    desmembramento: Optional[ModalidadeOut] = None
    loteamento: Optional[LoteamentoOut] = None
    # RURAL
    rural: Optional[RuralOut] = None


# ----- GET /api/analises/{id}/ambiental (Fase 2) -----

class ProvenienciaAmbientalOut(BaseModel):
    camada: str
    data_referencia: Optional[str]
    ressalva: str


class AlertaAmbientalOut(BaseModel):
    tipo: Literal[
        "MINERACAO", "UNIDADE_CONSERVACAO", "APP_HIDROGRAFIA", "FAIXA_NAO_EDIFICAVEL"
    ]
    severidade: Literal["ALERTA", "INFORMATIVO"]
    intersecta: bool
    area_afetada_m2: Optional[float] = None
    largura_confirmada: Optional[bool] = None  # só em APP_HIDROGRAFIA
    detalhe: str
    proveniencia: ProvenienciaAmbientalOut


class AmbientalOut(BaseModel):
    alertas: list[AlertaAmbientalOut] = []
    geojson_overlays: dict = {}  # {app, faixa_nao_edificavel, uc, mineracao}
    avisos: list[str] = []
    sem_alertas: bool
