"""Contratos de API (Pydantic v2). O frontend renderiza exatamente estes shapes."""

from typing import Literal, Optional

from pydantic import BaseModel, Field


# ----- POST /api/analises -----

class GeometriaOut(BaseModel):
    area_m2: float
    area_ha: float
    perimetro_m: float
    geojson: dict  # Polygon WGS84, para o mapa


class JurisdicaoOut(BaseModel):
    municipio: Optional[str]
    uf: Optional[str]
    cod_ibge: Optional[str]
    cobertura: Literal["BASE_FEDERAL", "PARCIAL_UF", "COMPLETA"]
    nao_considerado: list[str] = []


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


class AproveitamentoIn(BaseModel):
    lote_min_m2: float = Field(gt=0)
    loteamento: LoteamentoIn
    desmembramento: DesmembramentoIn = Field(default_factory=DesmembramentoIn)


class ModalidadeOut(BaseModel):
    area_aproveitavel_m2: float
    pct_aproveitamento: float
    n_lotes: int
    proveniencia: str


class LoteamentoOut(ModalidadeOut):
    base_doacao: str


class AproveitamentoOut(BaseModel):
    desmembramento: ModalidadeOut
    loteamento: LoteamentoOut
