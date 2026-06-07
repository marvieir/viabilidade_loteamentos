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
    """Proveniência da rota de ingestão (Fase 1.5; POLYGON_REPARADO desde a 1.8)."""

    rota: Literal["POLYGON_DIRETO", "LINHA_FECHAVEL", "POLYGON_REPARADO"]
    descricao: str


class AnaliseOut(BaseModel):
    analise_id: str
    geometria: GeometriaOut
    jurisdicao: JurisdicaoOut
    origem_geometria: OrigemGeometriaOut
    avisos: list[str] = []


# ----- POST /api/analises/{id}/aproveitamento -----

ModalidadeUrbana = Literal[
    "desmembramento",
    "loteamento_aberto",
    "loteamento_fechado",
    "condominio_lotes",
    "condominio_edilicio",
]


class AproveitamentoIn(BaseModel):
    """Pedido de aproveitamento (TRIAGEM). ``regime`` é obrigatório (validado no router →
    422 ``regime_obrigatorio``). Vias e doação NÃO entram no headline: dependem do projeto
    urbanístico e da diretriz municipal. ``zona`` (Fase 1.8) liga o ``cenario_diretriz``
    quando há perfil municipal CONFIRMADO — aditivo, nunca altera o headline."""

    regime: Optional[Literal["URBANO", "RURAL"]] = None
    # RURAL — FMP do município (puxada da tabela; editável se município não resolvido)
    fmp_m2: Optional[float] = Field(default=None, gt=0)
    # URBANO — lote declarado (interino até a 1.8 confirmar a LUOS); modalidade é rótulo
    modalidade: Optional[ModalidadeUrbana] = None
    lote_min_m2: Optional[float] = Field(default=None, gt=0)
    # URBANO + perfil municipal confirmado (Fase 1.8): zona declarada da LUOS → cenário diretriz.
    zona: Optional[str] = None


class RuralOut(BaseModel):
    fmp_m2: float
    n_parcelas: int
    area_m2: float  # área aproveitável (após restrições) usada na divisão por FMP
    fmp_origem: str  # "tabela INCRA" | "informado pelo usuário" | "default 2 ha (confirmar no CCIR)"
    flag_conversao: str
    proveniencia: str


class ItemRestricaoOut(BaseModel):
    tipo: str  # verde | app | app_massa_dagua | faixa_nao_edificavel | linhas_transmissao
    rotulo: str
    area_m2: float


class DescontosOut(BaseModel):
    """Restrições removidas do total antes do cálculo (triagem, Fase 2.2).

    ``area_restritiva_m2`` é a UNIÃO (sem dupla contagem) — a soma dos ``itens`` pode ser
    maior, pela sobreposição (ex.: mata ribeirinha que é APP e verde ao mesmo tempo)."""

    area_total_m2: float
    area_restritiva_m2: float
    area_base_m2: float  # total − restritiva: a base usada no aproveitamento
    percentual_restritivo: float
    sobreposicao_m2: float
    itens: list[ItemRestricaoOut] = []
    proveniencia: str


class CenarioOtimistaOut(BaseModel):
    """Cenário HIPOTÉTICO (Fase 2.3): aproveitável se o verde 'a verificar' for liberado.

    NÃO é o headline de triagem — é o teto se a supressão do verde a verificar (fora de
    zonas não-edificáveis) for autorizada por laudo + licença."""

    premissa: str
    area_aproveitavel_m2: float
    pct_sobre_total: float
    n_lotes_teto: Optional[int] = None  # urbano
    ressalva: str


class AproveitamentoOut(BaseModel):
    regime: Literal["URBANO", "RURAL"]
    premissa: str
    # Descontos de área não-aproveitável (Fase 2.2): presente quando há fonte consultada.
    descontos: Optional[DescontosOut] = None
    # Cenário otimista (Fase 2.3): null se severidade indisponível. INFORMATIVO.
    cenario_otimista: Optional[CenarioOtimistaOut] = None
    # Cenário diretriz (Fase 1.8): físico − doação municipal + lote legal da ZONA declarada.
    # null se não houver perfil CONFIRMADO p/ a zona. ADITIVO — não altera o headline.
    cenario_diretriz: Optional["CenarioDiretrizOut"] = None
    # Aviso quando a zona foi declarada mas não há perfil/zona p/ computar o cenário diretriz.
    aviso_diretriz: Optional[str] = None
    # Área que sobra após as restrições físicas/legais (mata ∪ APP ∪ faixas). Vale p/ os 2
    # regimes. Vias e doação NÃO descontadas (entram no projeto/diretriz municipal).
    area_aproveitavel_m2: Optional[float] = None
    pct_sobre_total: Optional[float] = None
    # URBANO
    origem_lote: Optional[str] = None
    lote_min_m2: Optional[float] = None
    n_lotes_teto: Optional[int] = None  # teto: aproveitável ÷ lote mínimo (sem vias/doação)
    ressalva_urbano: Optional[str] = None
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
    # Fase 2.3 — severidade: null se vegetação OU camadas ambientais não consultadas.
    severidade: Optional["SeveridadeVerdeOut"] = None


# ----- Fase 2.3 — Severidade do verde (restrição dura × a verificar) -----
class BucketVerdeOut(BaseModel):
    area_m2: float
    pct_do_verde: float
    geojson: dict = {}


class RestricaoDuraOut(BucketVerdeOut):
    fontes: list[str] = []  # quais camadas incidiram (app/app_massa_dagua/uc)


class SeveridadeVerdeOut(BaseModel):
    verde_total_m2: float
    restricao_dura: RestricaoDuraOut
    a_verificar: BucketVerdeOut
    potencial_desbloqueavel_m2: float  # a_verificar − (faixa ∪ servidão); clamp >= 0
    proveniencia: str
    ressalva: str


# ----- Fase 2.5 — Declividade via DEM (faixas + flag legal ≥30%) -----
class FaixaDeclividadeOut(BaseModel):
    classe: Literal["suave", "media", "alta"]
    limite: str  # ex.: "≤8%", "8–20%", ">20%"
    area_m2: float
    pct: float  # fração da área medida dentro da gleba


class FlagVedacaoOut(BaseModel):
    """Área com declividade ≥30% = vedação de parcelamento (Lei 6.766/79). null se área=0."""

    limite_pct: float
    area_m2: float
    pct_da_gleba: float
    geojson: dict = {}  # overlay vermelho + entra na união do aproveitável
    base_legal: str
    ressalva: str


class DeclividadeOut(BaseModel):
    consultada: bool
    fonte: Optional[str] = None
    declividade_media_pct: Optional[float] = None
    faixas: list[FaixaDeclividadeOut] = []
    flag_vedacao: Optional[FlagVedacaoOut] = None  # null se área ≥30% = 0
    proveniencia: Optional[str] = None
    avisos: list[str] = []


# ----- Fase 1.8 — Perfil municipal (extração assistida da LUOS) -----
# A IA fica na BORDA (lê e PROPÕE com citação); nada entra no cálculo sem status=confirmado
# e proveniência por artigo (ARCHITECTURE §2). Mesmas formas são persistidas e devolvidas.

OrigemParam = Literal["proposto_llm", "editado_humano"]
BaseDoacao = Literal["total", "liquida", "combinada"]


class ParamProv(BaseModel):
    """Um índice da LUOS + sua proveniência por artigo. ``valor=None`` = não encontrado
    (o LLM NUNCA inventa número). Valor sem ``artigo`` não é confirmável (gate da 1.8)."""

    valor: Optional[float] = None
    artigo: Optional[str] = None  # "Art. 12, I"
    pagina: Optional[int] = None
    trecho: Optional[str] = None  # verbatim da LUOS, para o humano conferir
    origem: OrigemParam = "proposto_llm"
    base: Optional[BaseDoacao] = None  # só em doacao_pct: sobre o que o % incide


class DoacaoSplit(BaseModel):
    """Repartição da doação (viário/verde/institucional). Dado de perfil — não entra no
    número (o total é ``doacao_pct``); persiste p/ a dimensão Jurídica (Fase 3)."""

    viario: Optional[float] = None
    verde: Optional[float] = None
    institucional: Optional[float] = None
    artigo: Optional[str] = None
    pagina: Optional[int] = None


class ZonaParams(BaseModel):
    """Índices por zona. Apenas ``lote_min_m2`` e ``doacao_pct`` entram no número (decisão
    vetável §6-B); o resto é perfil para a Jurídica (Fase 3)."""

    lote_min_m2: Optional[ParamProv] = None
    frente_min_m: Optional[ParamProv] = None
    doacao_pct: Optional[ParamProv] = None
    doacao_split: Optional[DoacaoSplit] = None
    ca: Optional[ParamProv] = None
    taxa_ocupacao: Optional[ParamProv] = None


class ModalidadeOverride(BaseModel):
    """Override por modalidade quando a LUOS diferencia (ex.: desmembramento isento de
    doação → ``doacao_pct.valor = 0``; 0 é VÁLIDO, distinto de 'não considerado')."""

    doacao_pct: Optional[ParamProv] = None
    lote_min_m2: Optional[ParamProv] = None


class ZonaPerfil(BaseModel):
    codigo: str  # "ZR1"
    descricao: Optional[str] = None
    params: ZonaParams = Field(default_factory=ZonaParams)
    modalidades: dict[str, ModalidadeOverride] = {}


class PerfilMunicipal(BaseModel):
    """Perfil municipal extraído da LUOS. Nasce ``proposto`` (não alimenta cálculo);
    só ``confirmado`` (via PUT, com ``validado_por`` + ``data_referencia``) é utilizável."""

    cod_ibge: str
    municipio: Optional[str] = None
    uf: Optional[str] = None
    status: Literal["proposto", "confirmado"] = "proposto"
    fonte_documento: Optional[str] = None
    zonas: list[ZonaPerfil] = []
    avisos: list[str] = []
    validado_por: Optional[str] = None
    data_referencia: Optional[str] = None


class PerfilConfirmarIn(PerfilMunicipal):
    """Corpo do PUT: perfil revisado/editado + quem validou. O router força
    ``status=confirmado`` e carimba ``data_referencia`` (hoje, se ausente)."""

    validado_por: str  # obrigatório no PUT (proveniência de quem confirmou)


class CenarioDiretrizOut(BaseModel):
    """Cenário 'com diretriz' (Fase 1.8): aproveitável físico − doação municipal, com lote
    mínimo LEGAL da zona. ADITIVO ao headline (§7-A decisão A). Determinístico."""

    zona: str
    lote_min_m2_legal: float  # substitui o declarado
    doacao_pct: float  # 0 é válido (modalidade isenta), distinto de "não considerado"
    doacao_base: BaseDoacao
    doacao_m2: float
    area_aproveitavel_m2: float  # físico − doação
    pct_sobre_total: Optional[float] = None
    n_lotes: int  # floor(aprov_diretriz / lote_legal)
    proveniencia: str
    ressalva: str
