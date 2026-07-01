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


class MunicipioComumOut(BaseModel):
    """Município comum às glebas agrupadas (Fase 8)."""

    cod_ibge: Optional[str]
    nome: Optional[str]
    uf: Optional[str]


class AgrupamentoOut(BaseModel):
    """Proveniência da união de 2+ KMZ contíguos (Fase 8). Ausente quando 1 só arquivo."""

    n_glebas: int
    arquivos: list[str]
    municipio_comum: MunicipioComumOut
    fronteira: Literal["compartilhada"]
    tolerancia_encosto_m: float
    area_total_m2: float
    proveniencia: str


class AnaliseOut(BaseModel):
    analise_id: str
    geometria: GeometriaOut
    jurisdicao: JurisdicaoOut
    origem_geometria: OrigemGeometriaOut
    avisos: list[str] = []
    # Fase 8 — presente apenas quando a análise nasceu de 2+ KMZ agrupados.
    agrupamento: Optional[AgrupamentoOut] = None


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


# Fase 9.10 — Ponte de reconciliação (teto teórico × estudo realista). PURO TEXTO/APRESENTAÇÃO:
# rotula o número de cada aba e cita o da outra. Nenhuma aba usa o número da outra em CONTA —
# a referência cruzada é só exibição (sem acoplamento de cálculo).
class RefCruzadaOut(BaseModel):
    fonte: str  # "urbanismo" | "aproveitamento"
    lotes: int


class ReconciliacaoAproveitamentoOut(BaseModel):
    papel: Literal["teto_teorico"] = "teto_teorico"
    lotes_teto: int
    lote_base_m2: float
    doacao_base_pct: float
    ref_estudo_massa: Optional[RefCruzadaOut] = None  # null → o front mostra o convite (não inventa)
    leitura: str


class ReconciliacaoUrbanismoOut(BaseModel):
    papel: Literal["estudo_geometrico"] = "estudo_geometrico"
    lotes_estudo: int
    lote_mediano_m2: float
    doacao_desenhada_pct: float
    ref_teto_regulatorio: Optional[RefCruzadaOut] = None  # null → convite (não inventa)
    leitura: str


class AreasCanonicasOut(BaseModel):
    """Fase 10 (Parte 1) — números canônicos de área (fonte ÚNICA). Toda aba que exibir gleba/
    vegetação/declividade/líquida usa ESTES — mesmo número em qualquer aba (catálogo §10)."""

    gleba_bruta_m2: float
    vegetacao_m2: float
    declividade_30_m2: float
    app_m2: float
    restricoes_fisicas_m2: float
    sobreposicao_m2: float = 0.0
    area_liquida_aproveitavel_m2: float


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
    # Fase 10 (Parte 1) — fonte canônica de área (a líquida que TODAS as abas leem).
    areas_canonicas: Optional[AreasCanonicasOut] = None
    # URBANO
    origem_lote: Optional[str] = None
    lote_min_m2: Optional[float] = None
    n_lotes_teto: Optional[int] = None  # teto: aproveitável ÷ lote mínimo (sem vias/doação)
    ressalva_urbano: Optional[str] = None
    # Fase 9.10 — ponte de reconciliação (rotula o teto e cita o estudo de massa). Só exibição.
    reconciliacao: Optional[ReconciliacaoAproveitamentoOut] = None
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
        "RESERVA_LEGAL",
        "MATA_ATLANTICA",
        "TERRA_INDIGENA",
        "TERRITORIO_QUILOMBOLA",
        "ASSENTAMENTO",
        "CAVERNA",
        "AREA_PROTECAO_MANANCIAL",
        "DUTOVIA",
        "PATRIMONIO_CULTURAL",
        "AREA_CONTAMINADA",
        "APCB",
    ]
    severidade: Literal["ALERTA", "INFORMATIVO"]
    intersecta: bool
    area_afetada_m2: Optional[float] = None
    largura_confirmada: Optional[bool] = None  # só em APP_HIDROGRAFIA
    detalhe: str
    proveniencia: ProvenienciaAmbientalOut


class BaciaHidrograficaOut(BaseModel):
    """Bacia hidrográfica (ANA) incidente na gleba. null se a fonte não foi configurada."""

    consultado: bool
    regiao_hidrografica: Optional[str] = None
    bacia: Optional[str] = None
    sub_bacia: Optional[str] = None
    fonte: Optional[str] = None
    avisos: list[str] = []


class ParcelaFundiariaOut(BaseModel):
    """Uma parcela registrada (SIGEF/SNCI) que intersecta a gleba."""

    codigo: Optional[str] = None
    area_ha: Optional[float] = None
    situacao: Optional[str] = None
    titular: Optional[str] = None


class MalhaFundiariaOut(BaseModel):
    """Malha fundiária (INCRA — SIGEF/SNCI) incidente. null se a fonte não foi configurada."""

    consultado: bool
    na_cobertura: bool = True  # False = gleba fora do footprint dos dados SIGEF carregados
    parcelas: list[ParcelaFundiariaOut] = []
    n_parcelas: int = 0
    cobertura_pct: Optional[float] = None  # % da gleba já coberto por parcela registrada
    fonte: Optional[str] = None
    avisos: list[str] = []


class AmbientalOut(BaseModel):
    alertas: list[AlertaAmbientalOut] = []
    geojson_overlays: dict = {}  # {app, faixa_nao_edificavel, app_massa_dagua, uc, mineracao, linhas_transmissao}
    avisos: list[str] = []
    sem_alertas: bool
    # Degradação por camada (Fase 2.1): quais fontes responderam e quais falharam.
    camadas_consultadas: list[str] = []
    camadas_indisponiveis: list[str] = []
    # Tier 2 — bacia hidrográfica (descritivo; null se AMBIENTAL_BACIA_PATH não configurado).
    bacia_hidrografica: Optional[BaciaHidrograficaOut] = None
    # Tier 1 — malha fundiária SIGEF/SNCI (null se FUNDIARIO_MALHA_PATH não configurado).
    malha_fundiaria: Optional[MalhaFundiariaOut] = None


# ----- Fase 2.2 — Área verde (cobertura vegetal) -----
class ProvenienciaVegetacaoOut(BaseModel):
    fonte: Optional[str] = None
    data_referencia: Optional[str] = None
    classes: list[str] = []
    ressalva: Optional[str] = None


class BiomaIncidenteOut(BaseModel):
    nome: str
    area_m2: float
    pct: float


class BiomaOut(BaseModel):
    """Bioma(s) IBGE incidente(s) na gleba + dominante. null se a fonte não foi configurada."""

    consultado: bool
    dominante: Optional[str] = None
    biomas: list[BiomaIncidenteOut] = []
    fonte: Optional[str] = None
    avisos: list[str] = []


class VegetacaoOut(BaseModel):
    area_total_m2: float
    area_verde_m2: Optional[float] = None      # None = não consultada (sem desconto)
    # Fase 10 (Parte 1): RENOMEADO de "líquida" → "parcial". Isto é gleba − SÓ vegetação; NÃO é a
    # área líquida aproveitável (essa é canônica, abaixo, e desconta também declividade + APP).
    area_parcial_veg_m2: Optional[float] = None  # area_total - area_verde (só vegetação)
    percentual_verde: Optional[float] = None
    # Fase 10 (Parte 1) — a líquida CANÔNICA (mesma das outras abas); a aba Ambiental a exibe.
    areas_canonicas: Optional[AreasCanonicasOut] = None
    geojson_verde: dict = {}
    proveniencia: Optional[ProvenienciaVegetacaoOut] = None
    avisos: list[str] = []
    consultada: bool
    # Fase 2.3 — severidade: null se vegetação OU camadas ambientais não consultadas.
    severidade: Optional["SeveridadeVerdeOut"] = None
    # Tier 2 — bioma IBGE (null se a fonte AMBIENTAL_BIOMA_PATH não foi configurada).
    bioma: Optional[BiomaOut] = None


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


# ----- Áreas úmidas / alagadas (nova dimensão ambiental) -----
class ProvenienciaAreasUmidasOut(BaseModel):
    fonte: Optional[str] = None
    data_referencia: Optional[str] = None
    classes: list[str] = []
    base_legal: Optional[str] = None
    ressalva: Optional[str] = None


class AreasUmidasOut(BaseModel):
    consultada: bool
    area_total_m2: float
    area_umida_m2: Optional[float] = None   # None = não consultada (sem marcação)
    pct_da_gleba: Optional[float] = None
    geojson_umidas: dict = {}               # overlay no mapa (área úmida/alagável)
    proveniencia: Optional[ProvenienciaAreasUmidasOut] = None
    avisos: list[str] = []


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


class FaixaFinaOut(BaseModel):
    """Faixa FINA de declividade (8 classes: 0-3, 3-6, …, 47-100%)."""

    classe: str  # ex.: "0-3%"
    area_m2: float
    pct: float


class FaixaMobilidadeOut(BaseModel):
    """Leitura de mobilidade (caminhabilidade/modais) por faixa de declividade."""

    chave: str
    faixa: str  # ex.: "10–20%"
    interpretacao: str  # ex.: "Ainda possível, mas começa o esforço"
    area_m2: float
    pct: float


class DeclividadeOut(BaseModel):
    consultada: bool
    fonte: Optional[str] = None
    declividade_media_pct: Optional[float] = None
    faixas: list[FaixaDeclividadeOut] = []
    flag_vedacao: Optional[FlagVedacaoOut] = None  # null se área ≥30% = 0
    proveniencia: Optional[str] = None
    avisos: list[str] = []
    # Fase 2.5+ — faixas finas (8 classes), mobilidade e relevo predominante (informativos).
    faixas_finas: list[FaixaFinaOut] = []
    mobilidade: list[FaixaMobilidadeOut] = []
    relevo_predominante: Optional[str] = None
    geojson_faixas: dict = {}  # FeatureCollection das faixas (camada colorida do mapa)


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
    # Índices informativos adicionais (Tier 1, paridade Urbia) — não entram no número.
    recuo_frontal_m: Optional[ParamProv] = None
    recuo_lateral_m: Optional[ParamProv] = None
    recuo_fundos_m: Optional[ParamProv] = None
    gabarito_m: Optional[ParamProv] = None  # gabarito/altura máxima
    permeabilidade_min_pct: Optional[ParamProv] = None  # taxa de permeabilidade mínima (fração)


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


# ----- Fase 3 — Pré-análise jurídica documental (dominial) -----
# Mesma disciplina da 1.8: o LLM LÊ e PROPÕE (com referência ao ato R-x/Av-y); o humano
# confirma; o número nunca passa por LLM. Ficha nasce status='proposto' — nada vira síntese
# sem o gate. NUNCA afirma "imóvel livre" — ausência de achado ≠ imóvel limpo.

TipoDocumento = Literal["matricula", "certidao"]
StatusFicha = Literal["proposto", "confirmado"]
SituacaoOnus = Literal["consta", "baixado", "cancelado"]


class CampoDoc(BaseModel):
    """Campo textual extraído + referência ao ato (R-x/Av-y) + página. valor=None = não
    encontrado no documento (o LLM NUNCA inventa)."""

    valor: Optional[str] = None
    ato: Optional[str] = None
    pagina: Optional[int] = None
    trecho: Optional[str] = None
    origem: OrigemParam = "proposto_llm"


class CampoAreaDoc(BaseModel):
    """Área registrada (m²) + proveniência. Numérica (entra no cross-check determinístico)."""

    valor: Optional[float] = None
    ato: Optional[str] = None
    pagina: Optional[int] = None
    trecho: Optional[str] = None
    origem: OrigemParam = "proposto_llm"


class ProprietarioDoc(BaseModel):
    """Proprietário (titular de direito real) extraído da matrícula. Fase 3.B: além do nome,
    captura CPF/CNPJ e o tipo (PF/PJ) — é a chave que personaliza o checklist de documentos
    (em nome de quem) e habilita o auto-download por CPF/CNPJ (Fase C)."""

    nome: Optional[str] = None
    documento: Optional[str] = None  # CPF (PF) ou CNPJ (PJ), como consta
    tipo: Optional[Literal["pf", "pj"]] = None
    # vigente = titular ATUAL; anterior = já transferiu/alienou a fração (titular do período,
    # entra só nas certidões de distribuidores/protesto — 10 anos). Default vigente.
    situacao: Literal["vigente", "anterior"] = "vigente"
    ato: Optional[str] = None  # R-x onde consta a aquisição
    pagina: Optional[int] = None
    trecho: Optional[str] = None
    origem: OrigemParam = "proposto_llm"


class IdentificacaoMatricula(BaseModel):
    matricula: Optional[CampoDoc] = None
    cartorio: Optional[CampoDoc] = None
    proprietario_atual: Optional[CampoDoc] = None  # mantido p/ compat (nome em texto)
    proprietarios: list[ProprietarioDoc] = []  # Fase 3.B: lista estruturada (PF/PJ + doc)
    area_registrada_m2: Optional[CampoAreaDoc] = None


class AchadoOnus(BaseModel):
    """Ônus real/gravame (hipoteca, alienação fiduciária, penhora, arresto, usufruto,
    servidão, inalienabilidade/impenhorabilidade). Achado sem ``ato`` não é confirmável."""

    tipo: str
    descricao: Optional[str] = None
    ato: Optional[str] = None  # "R-5"
    pagina: Optional[int] = None
    situacao: SituacaoOnus = "consta"
    trecho: Optional[str] = None
    origem: OrigemParam = "proposto_llm"


class Averbacao(BaseModel):
    """Averbação (reserva legal, APP, georreferenciamento, construção). Sem ``ato`` não
    é confirmável."""

    tipo: str
    descricao: Optional[str] = None
    ato: Optional[str] = None  # "Av-3"
    pagina: Optional[int] = None
    trecho: Optional[str] = None
    origem: OrigemParam = "proposto_llm"


class Indisponibilidade(BaseModel):
    """``consta=false`` é reportado como 'não encontrado no documento', NUNCA como
    'imóvel disponível' (fronteira §1 da spec)."""

    consta: bool = False
    obs: Optional[str] = None
    ato: Optional[str] = None


class DebitoAcao(BaseModel):
    descricao: Optional[str] = None
    valor: Optional[float] = None
    referencia: Optional[str] = None  # processo nº / inscrição


class FichaJuridica(BaseModel):
    """Ficha de UM documento (matrícula ou certidão). Proposta e confirmada usam o mesmo
    corpo; só ``status='confirmado'`` (via PUT, com ``validado_por``+``data_referencia``)
    alimenta a síntese."""

    tipo: TipoDocumento
    status: StatusFicha = "proposto"
    fonte_documento: Optional[str] = None
    # --- matrícula ---
    identificacao: Optional[IdentificacaoMatricula] = None
    onus: list[AchadoOnus] = []
    averbacoes: list[Averbacao] = []
    indisponibilidade: Optional[Indisponibilidade] = None
    # --- certidão ---
    orgao: Optional[CampoDoc] = None
    especie: Optional[CampoDoc] = None
    resultado: Optional[Literal["negativa", "positiva"]] = None
    debitos: list[DebitoAcao] = []
    acoes: list[DebitoAcao] = []
    # ---
    avisos: list[str] = []
    validado_por: Optional[str] = None
    data_referencia: Optional[str] = None


class FichaConfirmarIn(FichaJuridica):
    """Corpo do PUT: ficha revisada/editada + quem validou (proveniência da confirmação)."""

    validado_por: str


# --- Saída agregada do GET (determinística: consolida fichas confirmadas + alertas geo) ---
class DocumentoResumoOut(BaseModel):
    tipo: str
    status: str
    fonte: Optional[str] = None
    validado_por: Optional[str] = None
    data_referencia: Optional[str] = None
    # Fase 3.A (multi-matrícula): identidade por documento, p/ a tela listar cada matrícula
    # com sua área/dono (em vez de achatar tudo num número só).
    matricula: Optional[str] = None
    proprietario: Optional[str] = None
    area_m2: Optional[float] = None


class OnusOut(BaseModel):
    tipo: str
    descricao: Optional[str] = None
    ato: Optional[str] = None
    situacao: str = "consta"
    status: Literal["conforme", "atencao", "vedado"] = "atencao"
    proveniencia: str


class AverbacaoOut(BaseModel):
    tipo: str
    descricao: Optional[str] = None
    ato: Optional[str] = None
    proveniencia: str


class AreaCheckOut(BaseModel):
    """Cross-check determinístico: área da(s) matrícula(s) × área medida do KMZ (Fase 1).

    Multi-matrícula: ``area_matricula_m2`` é a SOMA das áreas das matrículas confirmadas
    (item 7c do roteiro: a soma das áreas tem de totalizar a área do imóvel)."""

    area_matricula_m2: Optional[float] = None  # SOMA das matrículas confirmadas
    area_kmz_m2: float
    divergencia_pct: Optional[float] = None  # null se não há área de matrícula confirmada
    status: Literal["conforme", "atencao", "indisponivel"]
    n_matriculas: int = 0  # quantas matrículas entraram na soma
    proveniencia: str


class CertidaoOut(BaseModel):
    orgao: Optional[str] = None
    especie: Optional[str] = None
    resultado: Optional[str] = None
    status: Literal["conforme", "atencao"]
    proveniencia: str


class SinteseRiscoOut(BaseModel):
    """Roll-up determinístico: achados dominiais confirmados + alertas geo (2.1/2.3/2.5)."""

    nivel: Literal["alto", "medio", "baixo"]
    criticos: list[str] = []
    atencao: list[str] = []
    resumo: str


class ProprietarioOut(BaseModel):
    """Proprietário consolidado (de todas as matrículas confirmadas), p/ o checklist."""

    nome: Optional[str] = None
    documento: Optional[str] = None
    tipo: Optional[Literal["pf", "pj"]] = None
    vigente: bool = True  # titular ATUAL (entra nas tributárias/registro); False = só 10 anos
    matriculas: list[str] = []  # em quais matrículas esse dono aparece
    proveniencia: str = ""


class AnexoOut(BaseModel):
    """Documento que o cliente baixou e anexou a um item do checklist (Fase C manual)."""

    id: str
    chave: str  # item do checklist a que pertence
    fonte_documento: str  # nome do arquivo
    data_referencia: str  # data do anexo (ISO)
    tamanho_bytes: int


class ItemChecklistOut(BaseModel):
    """Item do roteiro de documentos da advogada, já personalizado por dono/jurisdição.

    Determinístico (regras do roteiro; sem LLM). ``auto_disponivel`` marca os que a automação
    futura poderá puxar por CPF/CNPJ. ``status='anexado'`` quando o cliente subiu o documento."""

    chave: str
    titulo: str
    categoria: Literal[
        "registro", "titulo", "tributarias", "distribuidores", "protesto",
        "aprovacao", "projeto", "observacao",
    ]
    em_nome_de: list[str] = []
    obrigatorio: bool = True
    condicional: Optional[str] = None  # condição p/ aplicar (ex.: "se imóvel rural <5 anos")
    auto_disponivel: bool = False  # família B — chaveável por CPF/CNPJ (automação futura)
    status: Literal["pendente", "anexado"] = "pendente"
    anexos: list[AnexoOut] = []  # documentos que o cliente anexou a este item
    fonte_legal: str = ""  # referência ao roteiro (ex.: "Roteiro, item 4")
    observacao: Optional[str] = None


class JuridicoDocumentalOut(BaseModel):
    documentos: list[DocumentoResumoOut] = []
    onus: list[OnusOut] = []
    averbacoes: list[AverbacaoOut] = []
    area_check: Optional[AreaCheckOut] = None
    certidoes: list[CertidaoOut] = []
    proprietarios: list[ProprietarioOut] = []  # Fase 3.B
    checklist: list[ItemChecklistOut] = []  # Fase 3.B — roteiro personalizado
    sintese_risco: SinteseRiscoOut
    proveniencia: str
    avisos: list[str] = []


# ----- Fase 3.5 — Conformidade urbanística (consumo puro do perfil da 1.8) -----
# Confronta a gleba com os índices extraídos+confirmados da LUOS que hoje não entram no
# número (frente/CA/taxa de ocupação/split da doação). Checklist determinístico, cada item
# com proveniência por artigo (herdada da 1.8). NÃO altera o aproveitável.

StatusConformidade = Literal["considerado", "exigencia_projeto", "atencao", "nao_extraido"]


class ItemConformidadeOut(BaseModel):
    """Um índice da LUOS lido contra a gleba. ``status``:

    - ``considerado`` — já entra no número (lote mínimo, doação) — aqui só evidenciado;
    - ``exigencia_projeto`` — exigência legal que o projeto urbanístico deve atender
      (frente, CA, taxa de ocupação, repartição da doação);
    - ``atencao`` — inconsistência detectada (ex.: split da doação não fecha com o total);
    - ``nao_extraido`` — ausente do perfil confirmado → NÃO avaliado (nunca inventa).
    """

    parametro: str
    rotulo: str
    valor: Optional[str] = None  # formatado pelo backend (front não reformata, §2)
    status: StatusConformidade
    leitura: str  # interpretação determinística (com números já calculados no backend)
    proveniencia: Optional[str] = None  # artigo/página + documento + validado_por


class ConformidadeOut(BaseModel):
    avaliada: bool
    motivo: Optional[str] = None  # quando avaliada=false (sem perfil/zona) — honesto
    zona: Optional[str] = None
    modalidade: Optional[str] = None
    itens: list[ItemConformidadeOut] = []
    zonas_disponiveis: list[str] = []  # para o front montar o seletor sem inventar
    proveniencia: Optional[str] = None
    avisos: list[str] = []


# ----- Fase 4 — Financeira (fluxo de caixa do empreendimento) -----
# Aritmética PURA: sem LLM, sem rede. Toda premissa com proveniência (declarada × default
# rotulado); todo valor monetário acompanha *_fmt pt-BR gerado no backend (§2). A 4 MONTA o
# fluxo; a 5 (Econômica) AVALIA (sem VPL/TIR/payback aqui). NÃO altera o aproveitamento.


class LotesIn(BaseModel):
    origem: Literal["auto", "declarado"] = "auto"
    n: Optional[int] = None  # quando origem=declarado
    # Contexto vindo do aproveitamento já calculado (o front repassa o JSON que recebeu;
    # não recalcula — §2). origem=auto aplica a regra §3.1 (diretriz > teto).
    n_diretriz: Optional[int] = None
    n_teto: Optional[int] = None


class PerfilMesaIn(BaseModel):
    """Perfil de financiamento da mesa de vendas (4.1): fração das vendas que fecha neste
    prazo/taxa. PRICE; taxa 0 degrada para linear (= parcelado sem juros)."""

    participacao: float  # fração das vendas (a mesa inteira soma 1, validado)
    prazo_meses: int
    taxa_am: float = 0.0  # taxa de juros ao mês (0.01 = 1% a.m.)


class VendasIn(BaseModel):
    inicio_mes: int = 1
    duracao_meses: int = 1
    curva: Literal["linear", "custom"] = "linear"
    curva_custom: Optional[list[float]] = None  # % por mês; soma=1 (validado)
    modo: Literal["avista", "parcelado", "financiado"] = "avista"
    entrada_pct: float = 1.0  # parcelado/financiado: % no mês da venda
    n_parcelas: int = 0  # parcelado: nº de parcelas mensais após a entrada
    entrada_parcelas: int = 1  # financiado: entrada pode ser parcelada (default à vista)
    mesa: Optional[list[PerfilMesaIn]] = None  # financiado; None = mesa default ROTULADA


class AquisicaoIn(BaseModel):
    modo: Literal["permuta_vgv", "permuta_lotes", "compra", "nenhuma"] = "nenhuma"
    pct: Optional[float] = None  # permuta_vgv
    n: Optional[int] = None  # permuta_lotes
    valor: Optional[float] = None  # compra
    condicao: Literal["avista", "parcelado"] = "avista"  # compra
    inicio_mes: int = 0
    n_parcelas: int = 1
    itbi_pct: Optional[float] = None  # compra


class CustoUrbanizacaoIn(BaseModel):
    base: Literal["por_lote", "por_m2"] = "por_lote"
    valor: float = 0.0
    inicio_mes: int = 1
    duracao_meses: int = 1


class CustoPontualIn(BaseModel):
    valor: float = 0.0
    mes: int = 0


class CustoMarketingIn(BaseModel):
    pct_vgv_proprio: float = 0.0
    inicio_mes: int = 1
    duracao_meses: int = 1


class CustosIn(BaseModel):
    urbanizacao: CustoUrbanizacaoIn = Field(default_factory=CustoUrbanizacaoIn)
    projetos_aprovacao: CustoPontualIn = Field(
        default_factory=lambda: CustoPontualIn(valor=280000, mes=0)
    )
    topografia: CustoPontualIn = Field(
        default_factory=lambda: CustoPontualIn(valor=100000, mes=0)
    )
    spe_itbi_cartorio: Optional[CustoPontualIn] = None
    administracao_mensal: float = 0.0
    marketing: CustoMarketingIn = Field(default_factory=CustoMarketingIn)
    comissao_pct: float = 0.0
    # 4.1: base da comissão. None = default por modo (financiado → recebimento; senão →
    # venda). Corretor de loteamento recebe conforme a carteira paga (padrão TIV/mercado).
    comissao_base: Optional[Literal["recebimento", "venda"]] = None


class TributosIn(BaseModel):
    regime: Literal["presumido", "real", "outro"] = "presumido"
    aliquota_pct: float = 0.0593  # default ROTULADO (não é RET) — proveniência no bloco


class PremissasFinanceiraIn(BaseModel):
    lotes: LotesIn = Field(default_factory=LotesIn)
    eficiencia_projeto_pct: float = 1.0
    preco_lote: Optional[float] = None  # essencial (ou preco_m2) — sem default (422)
    preco_m2: Optional[float] = None
    area_lote_m2: Optional[float] = None  # 4.2: preço = preco_m2 × área do lote (como o curso)
    area_aproveitavel_m2: Optional[float] = None  # contexto p/ preco_m2 e urbanização por_m2
    vendas: VendasIn = Field(default_factory=VendasIn)
    inadimplencia_pct: float = 0.0  # 0 = ninguém deixa de pagar (a lição do −19M)
    # 4.1: inadimplência > 30% exige confirmação explícita (senão 422) — nunca silenciosa.
    confirmar_inadimplencia_alta: bool = False
    aquisicao: AquisicaoIn = Field(default_factory=AquisicaoIn)
    custos: CustosIn = Field(default_factory=CustosIn)
    tributos: TributosIn = Field(default_factory=TributosIn)
    # 4.2: parâmetros do semáforo (dashboard). Referência editável + capital opcional.
    margem_referencia_pct: float = 0.20  # default ROTULADO ("prática de mercado; defina a sua")
    capital_disponivel: Optional[float] = None  # se informado, compara com a exposição máxima


class PermutaOut(BaseModel):
    modo: str
    pct: Optional[float] = None
    valor: float = 0.0
    valor_fmt: str = "R$ 0,00"


class VgvOut(BaseModel):
    bruto: float  # VGV NOMINAL (lotes vendáveis × preço)
    bruto_fmt: str
    proprio: float
    proprio_fmt: str
    # 4.1 (modo financiado): juros do financiamento direto — separados do nominal.
    receita_financeira: float = 0.0
    receita_financeira_fmt: str = "R$ 0,00"
    geral: float = 0.0  # nominal + receita financeira
    geral_fmt: str = "R$ 0,00"
    permuta: PermutaOut


class BlocoOut(BaseModel):
    bloco: str
    total: float
    total_fmt: str
    proveniencia: str


class LinhaFluxoOut(BaseModel):
    mes: int
    entradas: float
    entradas_fmt: str
    saidas: float
    saidas_fmt: str
    liquido: float
    liquido_fmt: str
    acumulado: float
    acumulado_fmt: str


class ExposicaoOut(BaseModel):
    valor: float
    valor_fmt: str
    mes: int


class IndicadoresOut(BaseModel):
    resultado_nominal: float
    resultado_nominal_fmt: str
    margem_sobre_vgv_proprio: float
    exposicao_maxima: ExposicaoOut
    horizonte_meses: int


class CasoBaseOut(BaseModel):
    lotes: int  # caso-base (origem §3.1)
    lotes_vendaveis: int  # após eficiência de projeto e permuta por lotes
    origem_lotes: Literal["diretriz", "teto_fisico", "declarado"]
    aviso_lotes: Optional[str] = None


class FluxoVendaOut(BaseModel):
    """Fluxo de VENDAS (quando vende — nominal) ≠ fluxo de RECEBIMENTO (quando o caixa
    entra, em ``fluxo``). A diferença é a carteira financiada (4.1)."""

    mes: int
    lotes: float
    valor_nominal: float
    valor_nominal_fmt: str


class ResumoAnualOut(BaseModel):
    ano: int  # ano 1 = meses 0–11
    entradas: float
    entradas_fmt: str
    saidas: float
    saidas_fmt: str
    liquido: float
    liquido_fmt: str
    acumulado: float  # do último mês do ano
    acumulado_fmt: str


class VgvParteOut(BaseModel):
    nominal: float
    nominal_fmt: str
    receita_financeira: float = 0.0
    receita_financeira_fmt: str = "R$ 0,00"
    geral: float = 0.0
    geral_fmt: str = "R$ 0,00"


class ParticipanteOut(BaseModel):
    """Um lado da parceria (4.2). O incorporador carrega custos/resultado; o terrenista
    (no MVP) só recebe — split de custos entre sócios é evolução."""

    papel: Literal["incorporador", "terrenista"]
    pct: Optional[float] = None
    modo: Optional[str] = None  # parceria_vgv | permuta_lotes | None (compra)
    vgv: VgvParteOut
    recebimento_total: float
    recebimento_total_fmt: str
    custos_total: Optional[float] = None
    custos_total_fmt: Optional[str] = None
    resultado_nominal: Optional[float] = None
    resultado_nominal_fmt: Optional[str] = None
    margem: Optional[float] = None
    exposicao_maxima: Optional[ExposicaoOut] = None
    fluxo: list[LinhaFluxoOut] = []
    nota: Optional[str] = None  # rotulagem (custos 100% incorporador; tributo por parte)


class ParticipantesOut(BaseModel):
    incorporador: ParticipanteOut
    terrenista: Optional[ParticipanteOut] = None  # null no modo compra


class LeituraOut(BaseModel):
    """Semáforo do dashboard (4.2) — regra fixa, linguagem §1-A (NUNCA 'viável'). Slots
    da Fase 5 (vpl/tir/payback) nascem com status 'pendente'."""

    chave: str
    status: Literal["favoravel", "atencao", "desfavoravel", "pendente"]
    texto: str
    valor_fmt: Optional[str] = None


class FinanceiraOut(BaseModel):
    caso_base: CasoBaseOut
    vgv: VgvOut
    blocos: list[BlocoOut]
    fluxo_vendas: list[FluxoVendaOut] = []  # nominal vendido por mês (informativo)
    fluxo: list[LinhaFluxoOut]  # caixa (recebimento) — o insumo da Fase 5
    fluxo_resumo_anual: list[ResumoAnualOut] = []
    indicadores: IndicadoresOut
    participantes: Optional[ParticipantesOut] = None  # 4.2: os dois lados da parceria
    leituras: list[LeituraOut] = []  # 4.2: semáforo do dashboard
    # 4.1: guard de sanidade — nunca entregar um fluxo morto em silêncio.
    alerta_critico: Optional[str] = None
    proveniencia: str
    avisos: list[str] = []

# ----- Fase 5 — Econômica (avalia o fluxo da Financeira: VPL/TIR/paybacks/curva) -----


class CurvaVplIn(BaseModel):
    """Range da curva VPL×TMA (a sensibilidade do MVP — handoff §0.2)."""

    min_aa: float = 0.0
    max_aa: float = 0.40
    passo_pp: float = 1.0  # passo em pontos percentuais


class PremissasEconomicaIn(BaseModel):
    # TMA REAL (acima do IPCA — handoff §0.1), obrigatória SEM default (422 se ausente):
    # é a premissa que decide o veredito, não pode vir escondida.
    tma_aa_real: float
    curva: CurvaVplIn = Field(default_factory=CurvaVplIn)


class TmaOut(BaseModel):
    aa_real: float
    aa_real_fmt: str
    mensal: float  # equivalência composta (1+t)^(1/12) − 1
    origem: str = "declarado"
    data: str  # data da declaração (proveniência)


class VplOut(BaseModel):
    valor: float
    valor_fmt: str


class TirOut(BaseModel):
    """TIR honesta: null rotulado quando degenerada — NUNCA número inventado."""

    mensal: Optional[float] = None
    aa: Optional[float] = None
    aa_fmt: Optional[str] = None
    status: Literal["unica", "indefinida", "multipla_possivel"]
    avisos: list[str] = []


class PaybackOut(BaseModel):
    simples_mes: Optional[int] = None  # null = não recuperado no horizonte
    descontado_mes: Optional[int] = None
    avisos: list[str] = []


class PontoCurvaOut(BaseModel):
    tma_aa: float
    vpl: float
    vpl_fmt: str


class EconomicaOut(BaseModel):
    convencao: str  # moeda constante (Fisher) — explícita, nunca implícita (handoff §0.1)
    tma: TmaOut
    vpl: VplOut
    tir: TirOut
    payback: PaybackOut
    exposicao_descontada: ExposicaoOut
    indice_lucratividade: Optional[float] = None  # VPL ÷ |exposição descontada|
    curva_vpl_tma: list[PontoCurvaOut]
    leituras: list[LeituraOut]  # chaves vpl/tir/payback — o dashboard 4.2 compõe os slots
    proveniencia: str
    avisos: list[str] = []


# ----- Fase 6 — Localização (enriquecimento socioeconômico IBGE; INFORMATIVO, §1-A) -----
# Nenhum campo desta seção é lido por outro router (critério-coração nº 8): é contexto,
# não cálculo. Todo número formatável carrega o par valor + *_fmt pt-BR (gerado no backend).


class PopulacaoOut(BaseModel):
    disponivel: bool
    censo_2022: Optional[int] = None
    censo_2022_fmt: Optional[str] = None
    censo_2010: Optional[int] = None
    censo_2010_fmt: Optional[str] = None
    crescimento_total_pct: Optional[float] = None  # variação total 2010→2022 (fração)
    crescimento_total_fmt: Optional[str] = None
    crescimento_aa_pct: Optional[float] = None  # CAGR geométrico 12 anos (fração)
    crescimento_aa_fmt: Optional[str] = None
    densidade_hab_km2: Optional[float] = None
    densidade_fmt: Optional[str] = None
    area_km2: Optional[float] = None
    vs_uf: Optional[float] = None  # fração da população da UF (informativo)
    fonte: Optional[str] = None
    leitura: Optional[str] = None
    aviso: Optional[str] = None


class RendaOut(BaseModel):
    disponivel: bool
    pib_per_capita: Optional[float] = None
    pib_per_capita_fmt: Optional[str] = None
    ano: Optional[int] = None
    vs_uf: Optional[float] = None  # razão município ÷ UF (calculada no backend)
    vs_uf_fmt: Optional[str] = None
    vs_brasil: Optional[float] = None  # razão município ÷ Brasil
    vs_brasil_fmt: Optional[str] = None
    fonte: Optional[str] = None
    leitura: Optional[str] = None
    aviso: Optional[str] = None


class DeficitOut(BaseModel):
    valor: int
    valor_fmt: str
    fonte: str  # "FJP"
    ano: int


class FallbackEstoqueOut(BaseModel):
    domicilios_ocupados: int
    domicilios_ocupados_fmt: str
    moradores_por_domicilio: float
    moradores_por_domicilio_fmt: str
    fonte: str  # "IBGE Censo 2022"


class HabitacaoOut(BaseModel):
    disponivel: bool
    deficit: Optional[DeficitOut] = None  # FJP quando no recorte; null → exibe fallback
    fallback_estoque: Optional[FallbackEstoqueOut] = None  # estoque (NÃO é o déficit)
    fonte: Optional[str] = None
    aviso: Optional[str] = None


class GrupoEtarioOut(BaseModel):
    faixa: str  # "0-14" | "15-29" | "30-59" | "60+"
    pct: float
    pct_fmt: str


class FaixaEtariaOut(BaseModel):
    disponivel: bool
    fonte: Optional[str] = None
    grupos: list[GrupoEtarioOut] = []
    aviso: Optional[str] = None


class LocalizacaoMunicipioOut(BaseModel):
    cod_ibge: Optional[str] = None
    nome: Optional[str] = None
    uf: Optional[str] = None


class LocalizacaoOut(BaseModel):
    avaliada: bool
    cobertura: str  # COMPLETA (4 blocos) | PARCIAL (faltou algum) | INDISPONIVEL (fora do arquivo)
    municipio: LocalizacaoMunicipioOut
    populacao: PopulacaoOut
    renda: RendaOut
    habitacao: HabitacaoOut
    faixa_etaria: FaixaEtariaOut
    proveniencia: str
    avisos: list[str] = []


# ----- Fase 7 — Consolidação (laudo de triagem em PDF) -----
# Composição PURA do que as dimensões já devolveram (zero cálculo novo, §2). O laudo NUNCA
# emite veredito global de viabilidade (§1-A): tem luzes por dimensão + a ressalva-mestre.

LuzTipo = Literal["favoravel", "atencao", "restricao", "informativa", "nao_analisada"]


class LaudoIn(BaseModel):
    """Corpo do POST do laudo: os JSONs das dimensões JÁ EXECUTADAS (o front repassa o que
    o backend devolveu — não recalcula nada). Dimensão ausente → seção 'não analisada'."""

    aproveitamento: Optional[dict] = None
    ambiental: Optional[dict] = None
    vegetacao: Optional[dict] = None
    declividade: Optional[dict] = None
    juridico: Optional[dict] = None
    financeira: Optional[dict] = None
    economica: Optional[dict] = None
    localizacao: Optional[dict] = None


class LuzSemaforo(BaseModel):
    """Uma luz por dimensão, DERIVADA do que a dimensão já reporta — nunca juízo novo."""

    dimensao: str
    luz: LuzTipo
    justificativa: str


class ItemLaudo(BaseModel):
    rotulo: str
    valor: str
    proveniencia: Optional[str] = None


class SecaoLaudo(BaseModel):
    chave: str
    titulo: str
    analisada: bool
    luz: LuzTipo
    itens: list[ItemLaudo] = []
    avisos: list[str] = []  # ressalvas §1-A da própria dimensão


class FonteConsolidada(BaseModel):
    dimensao: str
    fonte: str


class LaudoData(BaseModel):
    """Modelo de dados do laudo — a fonte do PDF. Determinístico e auditável."""

    analise_id: str
    titulo: str
    data_geracao: str
    ressalva_capa: str  # §1-A na capa
    rodape: str  # §1-A no rodapé de TODA página
    semaforo: list[LuzSemaforo]
    secoes: list[SecaoLaudo]
    proveniencia_consolidada: list[FonteConsolidada]


# ===================== Fase 9 — Urbanismo (estudo de massa por IA) =====================
# IA na BORDA propõe o PROGRAMA; o Python MEDE toda a geometria e todos os números (§2).
# Rótulo "ESTUDO DE MASSA ESQUEMÁTICO" + avisos §1-A em TODA saída.

TipoLoteamento = Literal[
    "aberto", "fechado", "condominio_lotes", "desmembramento", "loteamento_rural"
]
PublicoAlvo = Literal["baixa", "media", "alta"]


class ProporUrbanismoIn(BaseModel):
    """Perfil declarado pelo usuário — condiciona o programa que o LLM propõe."""

    tipo_loteamento: TipoLoteamento = "aberto"
    publico_alvo: PublicoAlvo = "media"
    zona: Optional[str] = None  # Fase 9.4 — zona da LUOS (1.8) p/ o lote legal e a doação
    modalidade: Optional[str] = None
    overrides: Optional[dict] = None  # lote_alvo_m2, pct_lazer, largura_via_m, amenidades…
    # Fase 11.8 — teto de lote recomendado pelo operador (m²): sobrepõe o teto de mercado do perfil
    # (nunca abaixo do piso legal). Vazio = padrão do perfil.
    lote_max_m2: Optional[float] = None


class MedirUrbanismoIn(BaseModel):
    """Layout (GeoJSON WGS84) a medir — endpoint /medir, SEM LLM. ``lotes`` = um Polygon por
    lote (para contar e medir cada um); demais camadas como (Multi)Polygon único."""

    lotes: list[dict] = []
    arruamento: Optional[dict] = None
    areas_verdes: Optional[dict] = None
    sistema_lazer: Optional[dict] = None
    institucional: Optional[dict] = None


class ProgramaOut(BaseModel):
    """O que o LLM PROPÔS (proveniência) — estratégia, não medida."""

    lote_alvo_m2: float
    densidade: str
    pct_lazer: float
    amenidades: list[str]
    arquetipo_viario: str
    largura_via_m: float
    testada_m: float
    profundidade_m: float
    pct_institucional: float = 0.0
    # Fase 9.3 — calibração do perfil (o tamanho do lote emerge da quadra, mirando estes).
    publico_alvo: str = "media"
    testada_alvo_m: float = 12.0
    faixa_lote_m2: list[float] = []
    lote_alvo_origem: str = ""
    heuristicas: dict = {}  # heurísticas de valorização → score/R$/m² (não tamanho)
    origem: str
    justificativa: str


# Fase 9.3 — distribuição de tamanhos MEDIDA (o lote emerge da subdivisão da quadra).
class FaixaHistogramaOut(BaseModel):
    de: float
    ate: float
    n: int
    pct: float


class LoteOut(BaseModel):
    lote_id: str
    area_m2: float
    testada_m: float
    profundidade_m: float
    score: float
    quadra_id: Optional[str] = None


class DistribuicaoTamanhosOut(BaseModel):
    media_m2: float
    desvio_m2: float
    cv: float
    min_m2: float
    max_m2: float
    fora_da_faixa: int = 0  # Fase 9.4 — lotes fora de [piso,teto] legal (deve ser 0 — clamp)
    faixas: list[FaixaHistogramaOut] = []
    correlacao_tamanho_score: float  # reportada só p/ provar o DESACOPLAMENTO (não é meta)
    retalho_perdido_m2: float
    retalho_perdido_pct: float
    viario_pct: float
    lote_alvo_origem: str = ""
    faixa_lote_m2: list[float] = []
    lotes: list[LoteOut] = []


# Fase 9.4 — diretrizes municipais (hierarquia LUOS→mercado→federal) + conformidade legal.
class DiretrizesOut(BaseModel):
    fonte: str
    cobertura: str  # COMPLETA | BASE_FEDERAL
    confirmada: bool
    lote_min_zona_m2: Optional[float] = None
    piso_lote_efetivo_m2: float
    teto_lote_m2: float
    doacao_min_pct: Optional[float] = None
    doacao_split: Optional[dict] = None
    aviso: str = ""


class ConformidadeLegalOut(BaseModel):
    item: str
    exigido: Optional[float] = None
    medido: float
    unidade: str
    status: str  # atende | atende_com_folga | nao_atende | nao_avaliado
    leitura: str


class UsoAreaOut(BaseModel):
    m2: float
    m2_fmt: str
    pct_apo: float  # fração sobre a área líquida
    pct_fmt: str


class QuadroAreasOut(BaseModel):
    area_liquida_m2: float
    area_liquida_fmt: str
    vendavel: UsoAreaOut
    areas_verdes: UsoAreaOut  # TOTAL (compat); o front usa as linhas separadas abaixo
    # Fase 10 (Parte 2) — verde desmembrado: reserva (verde legítimo) × sobra geométrica (a reduzir).
    area_verde_reserva: Optional[UsoAreaOut] = None
    sobra_geometrica: Optional[UsoAreaOut] = None
    sistema_lazer: UsoAreaOut
    institucional: UsoAreaOut
    arruamento: UsoAreaOut


class IndicadoresUrbOut(BaseModel):
    n_lotes: int
    area_media_m2: Optional[float] = None
    area_media_fmt: Optional[str] = None
    testada_media_m: Optional[float] = None
    profundidade_media_m: Optional[float] = None
    comprimento_vias_m: Optional[float] = None
    leito_carrocavel_m2: Optional[float] = None
    calcadas_m2: Optional[float] = None


class FaixaHeatmapOut(BaseModel):
    faixa: str
    n: int
    pct: float


class LoteScoreOut(BaseModel):
    lote_id: str
    score: float
    area_m2: float


class HeatmapOut(BaseModel):
    score_medio: Optional[float] = None
    faixas: list[FaixaHeatmapOut] = []
    por_lote: list[LoteScoreOut] = []
    proveniencia: str = ""


class MedicaoUrbOut(BaseModel):
    """Saída de /medir (determinística, sem LLM): o quadro/indicadores/heatmap MEDIDOS."""

    rotulo: str = "ESTUDO DE MASSA ESQUEMÁTICO"
    geometria: dict  # camadas GeoJSON WGS84 (rotulado 'esquemático')
    quadro_areas: QuadroAreasOut
    indicadores: IndicadoresUrbOut
    heatmap: HeatmapOut
    avisos: list[str]


class ItemConformidadePrograma(BaseModel):
    item: str
    status: Literal["considerado", "atencao", "nao_avaliado"]
    leitura: str


# Fase 9.1 — fidelidade do traçado ao programa proposto (convergência + viário + topografia).
class ItemFidelidadeArea(BaseModel):
    item: str
    alvo_pct: Optional[float] = None
    medido_pct: Optional[float] = None
    status: str  # atendido | degradado | atencao
    tol_pp: Optional[float] = None
    leitura: Optional[str] = None


class FidelidadeViario(BaseModel):
    arquetipo: str
    esqueleto_usado: bool
    trechos_descartados: int
    obs: str


class FidelidadeTopografia(BaseModel):
    orientacao_por_declividade: bool
    obs: str


class FidelidadeOut(BaseModel):
    areas: list[ItemFidelidadeArea] = []
    viario: FidelidadeViario
    topografia: FidelidadeTopografia


class PropostaUrbanisticaOut(BaseModel):
    """Snapshot versionado: programa proposto pelo LLM + geometria/medidas do Python."""

    proposta_id: str
    versao: int
    rotulo: str = "ESTUDO DE MASSA ESQUEMÁTICO"
    perfil: dict  # {tipo_loteamento, publico_alvo}
    programa: ProgramaOut
    geometria: dict
    quadro_areas: QuadroAreasOut
    indicadores: IndicadoresUrbOut
    heatmap: HeatmapOut
    fidelidade: Optional[FidelidadeOut] = None  # Fase 9.1
    distribuicao_tamanhos: Optional[DistribuicaoTamanhosOut] = None  # Fase 9.3
    diretrizes: Optional[DiretrizesOut] = None  # Fase 9.4 (LUOS→mercado→federal)
    conformidade_legal: list[ConformidadeLegalOut] = []  # Fase 9.4 (medido × mínimo legal)
    conformidade_programa: list[ItemConformidadePrograma] = []
    # Fase 9.10 — ponte de reconciliação (rotula o estudo e cita o teto regulatório). Só exibição.
    reconciliacao: Optional[ReconciliacaoUrbanismoOut] = None
    esqueleto_ignorado: list[str] = []
    # Fase 10 (Parte 1) — a líquida CANÔNICA (mesma das abas Ambiental/Aproveitamento).
    areas_canonicas: Optional[AreasCanonicasOut] = None
    proveniencia: str
    avisos: list[str]


# ----- Fase 12 — autenticação / multi-tenant -----

class RegistrarIn(BaseModel):
    email: str = Field(..., description="e-mail de login")
    senha: str = Field(..., min_length=8, description="mínimo 8 caracteres")
    nome: Optional[str] = None


class LoginIn(BaseModel):
    email: str
    senha: str


class TokenOut(BaseModel):
    """O access token vai no corpo (front guarda em memória); o refresh vai em cookie httpOnly."""

    access_token: str
    token_type: str = "bearer"


class UsuarioOut(BaseModel):
    id: str
    email: str
    nome: Optional[str] = None
    papel: str
    criado_em: str


# ----- Fase 12 — análises salvas (área do cliente) -----

class AnaliseSalvarIn(BaseModel):
    titulo: str
    kmz_nome: Optional[str] = None
    gleba_geojson: Optional[dict] = None
    cidade: Optional[str] = None
    uf: Optional[str] = None
    area_ha: Optional[float] = None
    resultados: Optional[dict] = None


class AnaliseResumoOut(BaseModel):
    id: str
    titulo: str
    kmz_nome: Optional[str] = None
    cidade: Optional[str] = None
    uf: Optional[str] = None
    area_ha: Optional[float] = None
    criada_em: str
    atualizada_em: str


class AnaliseDetalheOut(AnaliseResumoOut):
    gleba_geojson: Optional[dict] = None
    resultados: Optional[dict] = None


# ----- Fase 12 — painel admin -----

class AdminMetricasOut(BaseModel):
    total_clientes: int
    total_analises: int
    novos_clientes_mes: int
    por_uf: dict  # {"SP": 3, ...}
    por_cidade: dict  # {"São Roque": 2, ...}


class AdminClienteOut(BaseModel):
    id: str
    email: str
    nome: Optional[str] = None
    papel: str
    ativo: bool
    criado_em: str
    n_analises: int
    cidades: list[str]
    ufs: list[str]


# ===== Tier 3 — Motor de custo de infraestrutura (paramétrico por disciplina) =====
# Determinístico: quantidades vêm do layout de Urbanismo; custos unitários vêm do
# perfil de custos PREENCHIDO PELO OPERADOR (proveniência própria). Indexado por padrão
# (econômico/médio/alto). Degrada honesto: sem perfil/sem layout → cobertura INDISPONIVEL.

class BaseOpcaoOut(BaseModel):
    chave: str
    rotulo: str


class DisciplinaCustoIn(BaseModel):
    chave: str
    base: str
    custo_economico: Optional[float] = None
    custo_medio: Optional[float] = None
    custo_alto: Optional[float] = None


class PerfilCustosIn(BaseModel):
    """Tabela de custos GLOBAL do operador (preenche uma vez; vale para todas as análises)."""

    bdi_pct: float = 0.0
    data_referencia: Optional[str] = None
    uf: Optional[str] = None
    fonte: Optional[str] = None
    observacao: Optional[str] = None
    disciplinas: list[DisciplinaCustoIn] = []


class DisciplinaCustoConfigOut(BaseModel):
    """Uma disciplina no editor do perfil (config + valores por padrão)."""

    chave: str
    rotulo: str
    base: str
    base_rotulo: str
    ancora: str
    bases_disponiveis: list[BaseOpcaoOut] = []
    custo_economico: Optional[float] = None
    custo_medio: Optional[float] = None
    custo_alto: Optional[float] = None


class PerfilCustosOut(BaseModel):
    bdi_pct: float = 0.0
    data_referencia: Optional[str] = None
    uf: Optional[str] = None
    fonte: Optional[str] = None
    observacao: Optional[str] = None
    padroes: list[BaseOpcaoOut] = []  # [{economico, Econômico}, ...]
    disciplinas: list[DisciplinaCustoConfigOut] = []
    configurado: bool = False  # já tem ao menos um custo preenchido


class DisciplinaCustoOut(BaseModel):
    chave: str
    rotulo: str
    base: str
    base_rotulo: str
    ancora: str
    unidade: str  # unidade da quantidade (m², m, lote, %)
    quantidade: Optional[float] = None
    quantidade_fmt: Optional[str] = None
    custo_unitario: Optional[float] = None
    custo_unitario_fmt: Optional[str] = None
    subtotal: Optional[float] = None
    subtotal_fmt: Optional[str] = None
    preenchido: bool = False
    aviso: Optional[str] = None


class CustoInfraOut(BaseModel):
    padrao: str
    padrao_rotulo: str
    cobertura: str  # COMPLETA | PARCIAL | INDISPONIVEL
    disciplinas: list[DisciplinaCustoOut] = []
    subtotal_direto: Optional[float] = None
    subtotal_direto_fmt: Optional[str] = None
    bdi_pct: float = 0.0
    bdi_valor: Optional[float] = None
    bdi_valor_fmt: Optional[str] = None
    total: Optional[float] = None
    total_fmt: Optional[str] = None
    custo_por_lote: Optional[float] = None
    custo_por_lote_fmt: Optional[str] = None
    custo_por_m2: Optional[float] = None
    custo_por_m2_fmt: Optional[str] = None
    n_lotes: Optional[int] = None
    area_urbanizada_m2: Optional[float] = None
    proveniencia: str = ""
    avisos: list[str] = []


# ===== Admin — custo real de LLM por análise (instrumentação uso_llm) =====
class CustoLinhaOut(BaseModel):
    chave: str  # analise_id | cod_ibge | modelo | dimensao
    rotulo: Optional[str] = None
    chamadas: int = 0
    custo_usd: float = 0.0
    custo_brl: float = 0.0
    detalhe: dict = {}  # ex.: {"urbanismo": {...}, "juridico": {...}}


class AdminCustosOut(BaseModel):
    n_registros: int = 0
    total_usd: float = 0.0
    total_brl: float = 0.0
    usd_brl: float = 5.5
    modelo_nao_tabelado: int = 0  # chamadas sem preço na tabela (ex.: Gemini)
    por_modelo: list[CustoLinhaOut] = []
    por_dimensao: list[CustoLinhaOut] = []
    por_analise: list[CustoLinhaOut] = []  # urbanismo + jurídico, por análise
    luos_por_municipio: list[CustoLinhaOut] = []
    avisos: list[str] = []
