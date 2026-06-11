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


class IdentificacaoMatricula(BaseModel):
    matricula: Optional[CampoDoc] = None
    cartorio: Optional[CampoDoc] = None
    proprietario_atual: Optional[CampoDoc] = None
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
    """Cross-check determinístico: área da matrícula × área medida do KMZ (Fase 1)."""

    area_matricula_m2: Optional[float] = None
    area_kmz_m2: float
    divergencia_pct: Optional[float] = None  # null se não há área de matrícula confirmada
    status: Literal["conforme", "atencao", "indisponivel"]
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


class JuridicoDocumentalOut(BaseModel):
    documentos: list[DocumentoResumoOut] = []
    onus: list[OnusOut] = []
    averbacoes: list[AverbacaoOut] = []
    area_check: Optional[AreaCheckOut] = None
    certidoes: list[CertidaoOut] = []
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
    area_aproveitavel_m2: Optional[float] = None  # contexto p/ preco_m2 e urbanização por_m2
    vendas: VendasIn = Field(default_factory=VendasIn)
    inadimplencia_pct: float = 0.0  # 0 = ninguém deixa de pagar (a lição do −19M)
    # 4.1: inadimplência > 30% exige confirmação explícita (senão 422) — nunca silenciosa.
    confirmar_inadimplencia_alta: bool = False
    aquisicao: AquisicaoIn = Field(default_factory=AquisicaoIn)
    custos: CustosIn = Field(default_factory=CustosIn)
    tributos: TributosIn = Field(default_factory=TributosIn)


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


class FinanceiraOut(BaseModel):
    caso_base: CasoBaseOut
    vgv: VgvOut
    blocos: list[BlocoOut]
    fluxo_vendas: list[FluxoVendaOut] = []  # nominal vendido por mês (informativo)
    fluxo: list[LinhaFluxoOut]  # caixa (recebimento) — o insumo da Fase 5
    fluxo_resumo_anual: list[ResumoAnualOut] = []
    indicadores: IndicadoresOut
    # 4.1: guard de sanidade — nunca entregar um fluxo morto em silêncio.
    alerta_critico: Optional[str] = None
    proveniencia: str
    avisos: list[str] = []
