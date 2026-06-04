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


class DescontoVerdeOut(BaseModel):
    """Quanto de área verde foi removido do total antes do cálculo (triagem, Fase 2.2)."""

    area_total_m2: float
    area_verde_m2: float
    area_base_m2: float  # total − verde: a base efetivamente usada no aproveitamento
    percentual_verde: float
    proveniencia: str


class AproveitamentoOut(BaseModel):
    regime: Literal["URBANO", "RURAL"]
    premissa: str
    # Desconto de área verde (Fase 2.2): presente só quando a vegetação foi consultada.
    desconto_verde: Optional[DescontoVerdeOut] = None
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
        "MINERACAO",
        "UNIDADE_CONSERVACAO",
        "APP_HIDROGRAFIA",
        "APP_MASSA_DAGUA",
        "FAIXA_NAO_EDIFICAVEL",
        "FAIXA_SERVIDAO_LT",
    ]
    severidade: Literal["ALERTA", "INFORMATIVO"]
    intersecta: bool
    area_afetada_m2: Optional[float] = None
    largura_confirmada: Optional[bool] = None  # só em APP_HIDROGRAFIA
    detalhe: str
    proveniencia: ProvenienciaAmbientalOut


class AmbientalOut(BaseModel):
    alertas: list[AlertaAmbientalOut] = []
    geojson_overlays: dict = {}  # {app, faixa_nao_edificavel, app_massa_dagua, uc, mineracao, linhas_transmissao}
    avisos: list[str] = []
    sem_alertas: bool
    # Degradação por camada (Fase 2.1): quais fontes responderam e quais falharam.
    camadas_consultadas: list[str] = []
    camadas_indisponiveis: list[str] = []


# ----- Fase 2.2 — Área verde (cobertura vegetal) -----
class ProvenienciaVegetacaoOut(BaseModel):
    fonte: Optional[str] = None
    data_referencia: Optional[str] = None
    classes: list[str] = []
    ressalva: Optional[str] = None


class VegetacaoOut(BaseModel):
    area_total_m2: float
    area_verde_m2: Optional[float] = None      # None = não consultada (sem desconto)
    area_liquida_m2: Optional[float] = None    # area_total - area_verde
    percentual_verde: Optional[float] = None
    geojson_verde: dict = {}
    proveniencia: Optional[ProvenienciaVegetacaoOut] = None
    avisos: list[str] = []
    consultada: bool
