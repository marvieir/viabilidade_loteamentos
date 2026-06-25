// Cliente do backend. O front NUNCA calcula nem reformata números:
// só transporta JSON do FastAPI e o repassa aos componentes.

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8700";

export type Cobertura = "BASE_FEDERAL" | "PARCIAL_UF" | "COMPLETA";

export interface Geometria {
  area_m2: number;
  area_ha: number;
  perimetro_m: number;
  geojson: GeoJSON.Polygon;
}

export interface MunicipioRef {
  cod_ibge: string;
  municipio: string;
  uf: string;
}

// Candidato na divisa: município + fração da gleba que cai nele (% de área, 0–100).
export interface CandidatoRef extends MunicipioRef {
  pct_area: number;
}

export interface Jurisdicao {
  municipio: string | null;
  uf: string | null;
  cod_ibge: string | null;
  cobertura: Cobertura;
  origem: "detectado" | "aproximado" | "informado";
  cruza_divisa: boolean;
  candidatos: CandidatoRef[];
  nao_considerado: string[];
}

export interface OrigemGeometria {
  rota: "POLYGON_DIRETO" | "LINHA_FECHAVEL" | "POLYGON_REPARADO";
  descricao: string;
}

// Fase 8 — proveniência da união de 2+ KMZ contíguos (ausente quando 1 só arquivo).
export interface Agrupamento {
  n_glebas: number;
  arquivos: string[];
  municipio_comum: { cod_ibge: string | null; nome: string | null; uf: string | null };
  fronteira: "compartilhada";
  tolerancia_encosto_m: number;
  area_total_m2: number;
  proveniencia: string;
}

export interface Analise {
  analise_id: string;
  geometria: Geometria;
  jurisdicao: Jurisdicao;
  origem_geometria: OrigemGeometria;
  avisos: string[];
  agrupamento?: Agrupamento | null;
}

// Fase 8 — recusa diagnóstica do agrupamento (glebas não contíguas / sobrepostas / municípios).
export class GrupoRecusado extends Error {
  erro: string;
  detalhe: string;
  diagnostico: Record<string, unknown>;
  arquivos: string[];
  constructor(
    erro: string,
    detalhe: string,
    diagnostico: Record<string, unknown>,
    arquivos: string[]
  ) {
    super(detalhe || erro);
    this.name = "GrupoRecusado";
    this.erro = erro;
    this.detalhe = detalhe;
    this.diagnostico = diagnostico;
    this.arquivos = arquivos;
  }
}

// Recusa diagnóstica da ingestão (Fase 1.5): arquivo de topografia/CAD, etc.
export interface DiagnosticoIngestao {
  n_poligonos: number;
  n_linhas: number;
  motivo: string;
  detalhe: string;
  n_pontos?: number;
}

export class IngestaoRecusada extends Error {
  rota: string;
  diagnostico: DiagnosticoIngestao;
  orientacao: string;
  constructor(rota: string, diagnostico: DiagnosticoIngestao, orientacao: string) {
    super(diagnostico?.detalhe ?? "Geometria não ingerível.");
    this.name = "IngestaoRecusada";
    this.rota = rota;
    this.diagnostico = diagnostico;
    this.orientacao = orientacao;
  }
}

export type Regime = "URBANO" | "RURAL";

export type ModalidadeUrbana =
  | "loteamento_aberto"
  | "loteamento_fechado"
  | "condominio_lotes"
  | "condominio_edilicio"
  | "desmembramento";

export interface RuralResult {
  fmp_m2: number;
  n_parcelas: number;
  area_m2: number;
  fmp_origem: string; // "tabela INCRA" | "informado pelo usuário" | "default 2 ha (confirmar no CCIR)"
  flag_conversao: string;
  proveniencia: string;
}

// Fase 2.2 — restrições físicas/legais descontadas (mata ∪ APP ∪ faixas), sem dupla contagem.
export interface ItemRestricao {
  tipo: string;
  rotulo: string;
  area_m2: number;
}

export interface Descontos {
  area_total_m2: number;
  area_restritiva_m2: number; // união
  area_base_m2: number; // total − restritiva
  percentual_restritivo: number;
  sobreposicao_m2: number;
  itens: ItemRestricao[];
  proveniencia: string;
}

export interface CenarioOtimista {
  premissa: string;
  area_aproveitavel_m2: number;
  pct_sobre_total: number;
  n_lotes_teto?: number | null;
  ressalva: string;
}

// Fase 1.8 — cenário "com diretriz" (físico − doação municipal + lote legal da zona).
export type BaseDoacao = "total" | "liquida" | "combinada";

export interface CenarioDiretriz {
  zona: string;
  lote_min_m2_legal: number;
  doacao_pct: number;
  doacao_base: BaseDoacao;
  doacao_m2: number;
  area_aproveitavel_m2: number;
  pct_sobre_total?: number | null;
  n_lotes: number;
  proveniencia: string;
  ressalva: string;
}

export interface Aproveitamento {
  regime: Regime;
  premissa: string;
  descontos?: Descontos | null;
  cenario_otimista?: CenarioOtimista | null;
  cenario_diretriz?: CenarioDiretriz | null;
  aviso_diretriz?: string | null;
  area_aproveitavel_m2?: number | null;
  pct_sobre_total?: number | null;
  // URBANO
  origem_lote?: string | null;
  lote_min_m2?: number | null;
  n_lotes_teto?: number | null;
  ressalva_urbano?: string | null;
  // Fase 9.10 — ponte de reconciliação (teto teórico × estudo realista). Só exibição.
  reconciliacao?: ReconciliacaoAproveitamento | null;
  // Fase 10 (Parte 1) — líquida canônica (mesma das abas Ambiental/Urbanismo).
  areas_canonicas?: AreasCanonicas | null;
  // RURAL
  rural?: RuralResult | null;
}

// Fase 9.10 — ponte de reconciliação (texto interpolado pelo backend; o front só renderiza).
export interface RefCruzada {
  fonte: string;
  lotes: number;
}
export interface ReconciliacaoAproveitamento {
  papel: "teto_teorico";
  lotes_teto: number;
  lote_base_m2: number;
  doacao_base_pct: number;
  ref_estudo_massa?: RefCruzada | null;
  leitura: string;
}
export interface ReconciliacaoUrbanismo {
  papel: "estudo_geometrico";
  lotes_estudo: number;
  lote_mediano_m2: number;
  doacao_desenhada_pct: number;
  ref_teto_regulatorio?: RefCruzada | null;
  leitura: string;
}

async function jsonOrThrow(res: Response) {
  if (!res.ok) {
    let detalhe = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (body?.detail) detalhe = body.detail;
    } catch {
      /* corpo não-JSON */
    }
    throw new Error(detalhe);
  }
  return res.json();
}

// Aceita 1 arquivo (fluxo de hoje) ou 2+ (Fase 8 — projeto unificado por união geométrica).
const ERROS_AGRUPAMENTO = new Set([
  "GLEBAS_NAO_CONTIGUAS",
  "GLEBAS_SOBREPOSTAS",
  "MUNICIPIOS_DIFERENTES",
]);

export async function criarAnalise(kmz: File | File[]): Promise<Analise> {
  const arquivos = Array.isArray(kmz) ? kmz : [kmz];
  const form = new FormData();
  arquivos.forEach((f) => form.append("kmz", f));
  const res = await fetch(`${API_BASE}/api/analises`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    let body: unknown = null;
    try {
      body = await res.json();
    } catch {
      /* corpo não-JSON */
    }
    const b = body as Record<string, unknown> | null;
    // Recusa diagnóstica do agrupamento (Fase 8): glebas não contíguas/sobrepostas/municípios.
    if (b && typeof b.erro === "string" && ERROS_AGRUPAMENTO.has(b.erro)) {
      throw new GrupoRecusado(
        b.erro,
        String(b.detalhe ?? ""),
        (b.diagnostico as Record<string, unknown>) ?? {},
        (b.arquivos as string[]) ?? []
      );
    }
    // Recusa diagnóstica da ingestão (corpo estruturado, não {detail}).
    if (b && b.erro === "geometria_nao_ingerivel") {
      throw new IngestaoRecusada(
        String(b.rota),
        b.diagnostico as DiagnosticoIngestao,
        String(b.orientacao ?? "")
      );
    }
    throw new Error(
      (b?.detail as string) ?? `${res.status} ${res.statusText}`
    );
  }
  return res.json();
}

// Fase 7 — gera o laudo de triagem em PDF. O front apenas REPASSA os JSONs que cada card
// já recebeu do backend (não recalcula nada, §2); o backend compõe e devolve o PDF.
export async function gerarLaudo(
  analiseId: string,
  dims: Record<string, unknown>
): Promise<Blob> {
  const res = await fetch(`${API_BASE}/api/analises/${analiseId}/laudo`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(dims),
  });
  if (!res.ok) {
    throw new Error(`Falha ao gerar o laudo: ${res.status} ${res.statusText}`);
  }
  return res.blob();
}

// Autocomplete por NOME sobre a malha local (offline). O código IBGE volta no
// payload para resolver internamente — o usuário nunca digita nem vê o código.
export async function buscarMunicipios(q: string): Promise<MunicipioRef[]> {
  const termo = q.trim();
  if (termo.length === 0) return [];
  const res = await fetch(
    `${API_BASE}/api/municipios?q=${encodeURIComponent(termo)}`
  );
  return jsonOrThrow(res);
}

// Correção/seleção manual do município (override). Origem vira "informado".
export async function corrigirMunicipio(
  analiseId: string,
  codIbge: string
): Promise<Jurisdicao> {
  const res = await fetch(
    `${API_BASE}/api/analises/${analiseId}/municipio`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ cod_ibge: codIbge }),
    }
  );
  return jsonOrThrow(res);
}

// URBANO (triagem): área aproveitável = total − restrições; teto de lotes = aproveitável /
// lote mínimo. Vias e doação NÃO entram (projeto urbanístico + diretriz municipal).
export async function calcularUrbano(
  analiseId: string,
  loteMinM2: number,
  modalidade: ModalidadeUrbana = "loteamento_aberto",
  zona?: string | null
): Promise<Aproveitamento> {
  const res = await fetch(
    `${API_BASE}/api/analises/${analiseId}/aproveitamento`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        regime: "URBANO",
        modalidade,
        lote_min_m2: loteMinM2,
        ...(zona ? { zona } : {}),
      }),
    }
  );
  return jsonOrThrow(res);
}

// Parcelamento RURAL: nº de parcelas pela FMP do município (ou fmp_m2 informada).
export async function calcularRural(
  analiseId: string,
  fmpM2?: number
): Promise<Aproveitamento> {
  const res = await fetch(
    `${API_BASE}/api/analises/${analiseId}/aproveitamento`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        regime: "RURAL",
        ...(fmpM2 != null ? { fmp_m2: fmpM2 } : {}),
      }),
    }
  );
  return jsonOrThrow(res);
}

// ----- Fase 2 — Ambiental -----

export type TipoAlerta =
  | "MINERACAO"
  | "UNIDADE_CONSERVACAO"
  | "APP_HIDROGRAFIA"
  | "APP_MASSA_DAGUA"
  | "FAIXA_NAO_EDIFICAVEL"
  | "FAIXA_SERVIDAO_LT";

export interface ProvenienciaAmbiental {
  camada: string;
  data_referencia: string | null;
  ressalva: string;
}

export interface AlertaAmbiental {
  tipo: TipoAlerta;
  severidade: "ALERTA" | "INFORMATIVO";
  intersecta: boolean;
  area_afetada_m2?: number | null;
  largura_confirmada?: boolean | null;
  detalhe: string;
  proveniencia: ProvenienciaAmbiental;
}

export type ChaveOverlay =
  | "app"
  | "faixa_nao_edificavel"
  | "app_massa_dagua"
  | "uc"
  | "mineracao"
  | "linhas_transmissao"
  | "verde"
  | "verde_dura"
  | "verde_verificar"
  | "declividade_vedada"
  | "areas_umidas"
  // Fase 9 — camadas do estudo de massa esquemático (card de Urbanismo)
  | "urb_lotes"
  | "urb_quadras"
  | "urb_arruamento"
  | "urb_verde"
  | "urb_verde_reservada"
  | "urb_verde_sobra"
  | "urb_lazer"
  | "urb_institucional"
  | "urb_portico"
  | "urb_restricao";

export interface Ambiental {
  alertas: AlertaAmbiental[];
  geojson_overlays: Partial<Record<ChaveOverlay, GeoJSON.Geometry>>;
  avisos: string[];
  sem_alertas: boolean;
  camadas_consultadas: string[];
  camadas_indisponiveis: string[];
}

export async function buscarAmbiental(analiseId: string): Promise<Ambiental> {
  const res = await fetch(`${API_BASE}/api/analises/${analiseId}/ambiental`);
  return jsonOrThrow(res);
}

// ----- Fase 2.2 — Área verde (cobertura vegetal) -----
export interface ProvenienciaVegetacao {
  fonte: string | null;
  data_referencia: string | null;
  classes: string[];
  ressalva: string | null;
}

// Fase 10 (Parte 1) — números canônicos de área (fonte única; mesmo número em todas as abas).
export interface AreasCanonicas {
  gleba_bruta_m2: number;
  vegetacao_m2: number;
  declividade_30_m2: number;
  app_m2: number;
  restricoes_fisicas_m2: number;
  sobreposicao_m2?: number;
  area_liquida_aproveitavel_m2: number;
}

export interface Vegetacao {
  area_total_m2: number;
  area_verde_m2: number | null;
  // Fase 10 (Parte 1): RENOMEADO de area_liquida_m2 — é PARCIAL (só vegetação), não a líquida.
  area_parcial_veg_m2: number | null;
  percentual_verde: number | null;
  geojson_verde: GeoJSON.Geometry | Record<string, never>;
  areas_canonicas?: AreasCanonicas | null; // a líquida CANÔNICA (mesma das outras abas)
  proveniencia: ProvenienciaVegetacao | null;
  avisos: string[];
  consultada: boolean;
  severidade?: SeveridadeVerde | null;
}

// Fase 2.3 — severidade do verde (restrição dura × a verificar)
export interface BucketVerde {
  area_m2: number;
  pct_do_verde: number;
  geojson: GeoJSON.Geometry | Record<string, never>;
}

export interface SeveridadeVerde {
  verde_total_m2: number;
  restricao_dura: BucketVerde & { fontes: string[] };
  a_verificar: BucketVerde;
  potencial_desbloqueavel_m2: number;
  proveniencia: string;
  ressalva: string;
}

export async function buscarVegetacao(analiseId: string): Promise<Vegetacao> {
  const res = await fetch(`${API_BASE}/api/analises/${analiseId}/vegetacao`);
  return jsonOrThrow(res);
}

// ----- Áreas úmidas / alagadas (nova dimensão ambiental) -----
export interface ProvenienciaAreasUmidas {
  fonte: string | null;
  data_referencia: string | null;
  classes: string[];
  base_legal: string | null;
  ressalva: string | null;
}

export interface AreasUmidas {
  consultada: boolean;
  area_total_m2: number;
  area_umida_m2: number | null;
  pct_da_gleba: number | null;
  geojson_umidas: GeoJSON.Geometry | Record<string, never>;
  proveniencia: ProvenienciaAreasUmidas | null;
  avisos: string[];
}

export async function buscarAreasUmidas(analiseId: string): Promise<AreasUmidas> {
  const res = await fetch(`${API_BASE}/api/analises/${analiseId}/areas-umidas`);
  return jsonOrThrow(res);
}

// ----- Fase 2.5 — Declividade via DEM (faixas + flag legal ≥30%) -----
export interface FaixaDeclividade {
  classe: "suave" | "media" | "alta";
  limite: string;
  area_m2: number;
  pct: number;
}

export interface FlagVedacao {
  limite_pct: number;
  area_m2: number;
  pct_da_gleba: number;
  geojson: GeoJSON.Geometry | Record<string, never>;
  base_legal: string;
  ressalva: string;
}

export interface Declividade {
  consultada: boolean;
  fonte: string | null;
  declividade_media_pct: number | null;
  faixas: FaixaDeclividade[];
  flag_vedacao: FlagVedacao | null;
  proveniencia: string | null;
  avisos: string[];
}

export async function buscarDeclividade(
  analiseId: string
): Promise<Declividade> {
  const res = await fetch(`${API_BASE}/api/analises/${analiseId}/declividade`);
  return jsonOrThrow(res);
}

// ----- Fase 1.8 — Perfil municipal (extração assistida da LUOS) -----
export type OrigemParam = "proposto_llm" | "editado_humano";

export interface ParamProv {
  valor: number | null;
  artigo: string | null;
  pagina: number | null;
  trecho: string | null;
  origem: OrigemParam;
  base?: BaseDoacao | null; // só em doacao_pct
}

export interface DoacaoSplit {
  viario: number | null;
  verde: number | null;
  institucional: number | null;
  artigo: string | null;
  pagina: number | null;
}

export interface ZonaParams {
  lote_min_m2: ParamProv | null;
  frente_min_m: ParamProv | null;
  doacao_pct: ParamProv | null;
  doacao_split: DoacaoSplit | null;
  ca: ParamProv | null;
  taxa_ocupacao: ParamProv | null;
}

export interface ModalidadeOverride {
  doacao_pct: ParamProv | null;
  lote_min_m2: ParamProv | null;
}

export interface ZonaPerfil {
  codigo: string;
  descricao: string | null;
  params: ZonaParams;
  modalidades: Record<string, ModalidadeOverride>;
}

export interface PerfilMunicipal {
  cod_ibge: string;
  municipio: string | null;
  uf: string | null;
  status: "proposto" | "confirmado";
  fonte_documento: string | null;
  zonas: ZonaPerfil[];
  avisos: string[];
  validado_por: string | null;
  data_referencia: string | null;
}

// Dispara a extração assistida (LLM lê o PDF). Devolve RASCUNHO (status=proposto).
// 503 = sem credencial de LLM; 422 = PDF ilegível. NÃO persiste.
export async function extrairPerfil(
  codIbge: string,
  pdf: File,
  municipio?: string | null,
  uf?: string | null
): Promise<PerfilMunicipal> {
  const form = new FormData();
  form.append("pdf", pdf);
  const qs = new URLSearchParams();
  if (municipio) qs.set("municipio", municipio);
  if (uf) qs.set("uf", uf);
  const res = await fetch(
    `${API_BASE}/api/municipios/${codIbge}/perfil/extrair?${qs.toString()}`,
    { method: "POST", body: form }
  );
  return jsonOrThrow(res);
}

// Gate humano: confirma o perfil revisado/editado (status=confirmado) e persiste.
// É o ÚNICO caminho que torna o perfil utilizável no cálculo.
export async function confirmarPerfil(
  codIbge: string,
  perfil: PerfilMunicipal,
  validadoPor: string
): Promise<PerfilMunicipal> {
  const res = await fetch(`${API_BASE}/api/municipios/${codIbge}/perfil`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...perfil, validado_por: validadoPor }),
  });
  return jsonOrThrow(res);
}

// Perfil confirmado do município (404 → null: ainda não cadastrado).
export async function obterPerfil(
  codIbge: string
): Promise<PerfilMunicipal | null> {
  const res = await fetch(`${API_BASE}/api/municipios/${codIbge}/perfil`);
  if (res.status === 404) return null;
  return jsonOrThrow(res);
}

// ----- Fase 3 — Pré-análise jurídica documental (dominial) -----
export type TipoDocumento = "matricula" | "certidao";

export interface CampoDoc {
  valor: string | null;
  ato: string | null;
  pagina: number | null;
  trecho: string | null;
  origem: "proposto_llm" | "editado_humano";
}
export interface CampoAreaDoc {
  valor: number | null;
  ato: string | null;
  pagina: number | null;
  trecho: string | null;
  origem: "proposto_llm" | "editado_humano";
}
export interface IdentificacaoMatricula {
  matricula: CampoDoc | null;
  cartorio: CampoDoc | null;
  proprietario_atual: CampoDoc | null;
  area_registrada_m2: CampoAreaDoc | null;
}
export interface AchadoOnus {
  tipo: string;
  descricao: string | null;
  ato: string | null;
  pagina: number | null;
  situacao: "consta" | "baixado" | "cancelado";
  trecho: string | null;
  origem: "proposto_llm" | "editado_humano";
}
export interface Averbacao {
  tipo: string;
  descricao: string | null;
  ato: string | null;
  pagina: number | null;
  trecho: string | null;
  origem: "proposto_llm" | "editado_humano";
}
export interface Indisponibilidade {
  consta: boolean;
  obs: string | null;
  ato: string | null;
}

// Ficha de UM documento (rascunho proposto OU confirmada). É o que o extrair devolve e o
// PUT recebe (de volta editada). O front só edita/renderiza — nada de cálculo aqui.
export interface FichaJuridica {
  tipo: TipoDocumento;
  status: "proposto" | "confirmado";
  fonte_documento: string | null;
  identificacao: IdentificacaoMatricula | null;
  onus: AchadoOnus[];
  averbacoes: Averbacao[];
  indisponibilidade: Indisponibilidade | null;
  orgao: CampoDoc | null;
  especie: CampoDoc | null;
  resultado: "negativa" | "positiva" | null;
  debitos: unknown[];
  acoes: unknown[];
  avisos: string[];
  validado_por: string | null;
  data_referencia: string | null;
}

// Saída agregada do GET (consolidação determinística + roll-up de risco).
export interface OnusOut {
  tipo: string;
  descricao: string | null;
  ato: string | null;
  situacao: string;
  status: "conforme" | "atencao" | "vedado";
  proveniencia: string;
}
export interface AverbacaoOut {
  tipo: string;
  descricao: string | null;
  ato: string | null;
  proveniencia: string;
}
export interface AreaCheckOut {
  area_matricula_m2: number | null;
  area_kmz_m2: number;
  divergencia_pct: number | null;
  status: "conforme" | "atencao" | "indisponivel";
  proveniencia: string;
}
export interface CertidaoOut {
  orgao: string | null;
  especie: string | null;
  resultado: string | null;
  status: "conforme" | "atencao";
  proveniencia: string;
}
export interface DocumentoResumoOut {
  tipo: string;
  status: string;
  fonte: string | null;
  validado_por: string | null;
  data_referencia: string | null;
}
export interface SinteseRisco {
  nivel: "alto" | "medio" | "baixo";
  criticos: string[];
  atencao: string[];
  resumo: string;
}
export interface JuridicoDocumental {
  documentos: DocumentoResumoOut[];
  onus: OnusOut[];
  averbacoes: AverbacaoOut[];
  area_check: AreaCheckOut | null;
  certidoes: CertidaoOut[];
  sintese_risco: SinteseRisco;
  proveniencia: string;
  avisos: string[];
}

// Dispara a extração assistida (LLM lê o documento). RASCUNHO (status=proposto). NÃO persiste.
// Aceita PDF ou imagens (JPEG/PNG/WEBP) e MÚLTIPLOS arquivos (documento multipágina escaneado).
// 503 = sem credencial de LLM; 422 = documento ilegível/formato não suportado.
export async function extrairJuridico(
  analiseId: string,
  documentos: File[],
  tipo: TipoDocumento
): Promise<FichaJuridica> {
  const form = new FormData();
  documentos.forEach((d) => form.append("documentos", d));
  form.append("tipo", tipo);
  const res = await fetch(
    `${API_BASE}/api/analises/${analiseId}/juridico/extrair`,
    { method: "POST", body: form }
  );
  return jsonOrThrow(res);
}

// Gate humano: confirma a ficha revisada/editada (status=confirmado) e persiste.
export async function confirmarJuridico(
  analiseId: string,
  ficha: FichaJuridica,
  validadoPor: string
): Promise<FichaJuridica> {
  const res = await fetch(`${API_BASE}/api/analises/${analiseId}/juridico`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...ficha, validado_por: validadoPor }),
  });
  return jsonOrThrow(res);
}

// Ficha consolidada + síntese de risco (sempre 200; degrada honesto sem documento).
export async function buscarJuridico(
  analiseId: string
): Promise<JuridicoDocumental> {
  const res = await fetch(`${API_BASE}/api/analises/${analiseId}/juridico`);
  return jsonOrThrow(res);
}

// ----- Fase 3.5 — Conformidade urbanística (consumo puro do perfil da 1.8) -----
export type StatusConformidade =
  | "considerado"
  | "exigencia_projeto"
  | "atencao"
  | "nao_extraido";

export interface ItemConformidade {
  parametro: string;
  rotulo: string;
  valor: string | null;
  status: StatusConformidade;
  leitura: string; // texto já calculado/formatado pelo backend — não reformatar
  proveniencia: string | null;
}

export interface Conformidade {
  avaliada: boolean;
  motivo: string | null;
  zona: string | null;
  modalidade: string | null;
  itens: ItemConformidade[];
  zonas_disponiveis: string[];
  proveniencia: string | null;
  avisos: string[];
}

// Checklist da (zona, modalidade) contra a gleba. Sempre 200; degrada honesto
// (avaliada=false + motivo) sem perfil confirmado ou sem zona.
export async function buscarConformidade(
  analiseId: string,
  zona?: string | null,
  modalidade?: string | null
): Promise<Conformidade> {
  const qs = new URLSearchParams();
  if (zona) qs.set("zona", zona);
  if (modalidade) qs.set("modalidade", modalidade);
  const res = await fetch(
    `${API_BASE}/api/analises/${analiseId}/conformidade?${qs.toString()}`
  );
  return jsonOrThrow(res);
}

// ----- Fase 4 — Financeira (fluxo de caixa) -----
export interface PremissasFinanceira {
  lotes: {
    origem: "auto" | "declarado";
    n?: number | null;
    n_diretriz?: number | null;
    n_teto?: number | null;
  };
  eficiencia_projeto_pct?: number;
  preco_lote?: number | null;
  preco_m2?: number | null;
  area_aproveitavel_m2?: number | null;
  vendas?: Record<string, unknown>;
  inadimplencia_pct?: number;
  confirmar_inadimplencia_alta?: boolean;
  aquisicao?: Record<string, unknown>;
  custos?: Record<string, unknown>;
  tributos?: { regime?: string; aliquota_pct?: number };
}

// Perfil da mesa de vendas (4.1 — financiado/PRICE).
export interface PerfilMesa {
  participacao: number; // fração (a mesa soma 1)
  prazo_meses: number;
  taxa_am: number; // 0.01 = 1% a.m.
}

export interface BlocoFin {
  bloco: string;
  total: number;
  total_fmt: string;
  proveniencia: string;
}
export interface LinhaFluxo {
  mes: number;
  entradas: number;
  entradas_fmt: string;
  saidas: number;
  saidas_fmt: string;
  liquido: number;
  liquido_fmt: string;
  acumulado: number;
  acumulado_fmt: string;
}
export interface FluxoVenda {
  mes: number;
  lotes: number;
  valor_nominal: number;
  valor_nominal_fmt: string;
}

export interface ResumoAnual {
  ano: number;
  entradas: number;
  entradas_fmt: string;
  saidas: number;
  saidas_fmt: string;
  liquido: number;
  liquido_fmt: string;
  acumulado: number;
  acumulado_fmt: string;
}

// Fase 4.2 — split da parceria + semáforo de leituras
export interface VgvParte {
  nominal: number;
  nominal_fmt: string;
  receita_financeira: number;
  receita_financeira_fmt: string;
  geral: number;
  geral_fmt: string;
}
export interface Participante {
  papel: "incorporador" | "terrenista";
  pct: number | null;
  modo: string | null;
  vgv: VgvParte;
  recebimento_total: number;
  recebimento_total_fmt: string;
  custos_total: number | null;
  custos_total_fmt: string | null;
  resultado_nominal: number | null;
  resultado_nominal_fmt: string | null;
  margem: number | null;
  exposicao_maxima: { valor: number; valor_fmt: string; mes: number } | null;
  fluxo: LinhaFluxo[];
  nota: string | null;
}
export interface Participantes {
  incorporador: Participante;
  terrenista: Participante | null;
}
export interface Leitura {
  chave: string;
  status: "favoravel" | "atencao" | "desfavoravel" | "pendente";
  texto: string;
  valor_fmt: string | null;
}

export interface Financeira {
  caso_base: {
    lotes: number;
    lotes_vendaveis: number;
    origem_lotes: "diretriz" | "teto_fisico" | "declarado";
    aviso_lotes: string | null;
  };
  vgv: {
    bruto: number;
    bruto_fmt: string;
    proprio: number;
    proprio_fmt: string;
    receita_financeira: number;
    receita_financeira_fmt: string;
    geral: number;
    geral_fmt: string;
    permuta: { modo: string; pct: number | null; valor: number; valor_fmt: string };
  };
  blocos: BlocoFin[];
  fluxo_vendas: FluxoVenda[];
  fluxo: LinhaFluxo[];
  fluxo_resumo_anual: ResumoAnual[];
  indicadores: {
    resultado_nominal: number;
    resultado_nominal_fmt: string;
    margem_sobre_vgv_proprio: number;
    exposicao_maxima: { valor: number; valor_fmt: string; mes: number };
    horizonte_meses: number;
  };
  participantes: Participantes | null;
  leituras: Leitura[];
  alerta_critico: string | null;
  proveniencia: string;
  avisos: string[];
}

// Calcula e persiste o fluxo. 422 = premissa essencial ausente (ex.: preço) / curva inválida.
export async function calcularFinanceira(
  analiseId: string,
  premissas: PremissasFinanceira
): Promise<Financeira> {
  const res = await fetch(`${API_BASE}/api/analises/${analiseId}/financeira`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(premissas),
  });
  return jsonOrThrow(res);
}

// Última execução persistida (404 → null: ainda não rodou).
export async function obterFinanceira(
  analiseId: string
): Promise<Financeira | null> {
  const res = await fetch(`${API_BASE}/api/analises/${analiseId}/financeira`);
  if (res.status === 404) return null;
  return jsonOrThrow(res);
}

// ----- Fase 5 — Econômica (avalia o fluxo da Financeira: VPL/TIR/paybacks/curva) -----
export interface TmaEco {
  aa_real: number;
  aa_real_fmt: string;
  mensal: number;
  origem: string;
  data: string;
}
export interface TirEco {
  mensal: number | null;
  aa: number | null;
  aa_fmt: string | null;
  status: "unica" | "indefinida" | "multipla_possivel";
  avisos: string[];
}
export interface PaybackEco {
  simples_mes: number | null;
  descontado_mes: number | null;
  avisos: string[];
}
export interface PontoCurva {
  tma_aa: number;
  vpl: number;
  vpl_fmt: string;
}
export interface Economica {
  convencao: string;
  tma: TmaEco;
  vpl: { valor: number; valor_fmt: string };
  tir: TirEco;
  payback: PaybackEco;
  exposicao_descontada: { valor: number; valor_fmt: string; mes: number };
  indice_lucratividade: number | null;
  curva_vpl_tma: PontoCurva[];
  leituras: Leitura[]; // chaves vpl/tir/payback — o dashboard da Financeira compõe
  proveniencia: string;
  avisos: string[];
}

// Avalia e persiste. 409 = Financeira ainda não executada; 422 = TMA ausente/curva inválida.
export async function calcularEconomica(
  analiseId: string,
  tmaAaReal: number,
  curva?: { min_aa: number; max_aa: number; passo_pp: number }
): Promise<Economica> {
  const res = await fetch(`${API_BASE}/api/analises/${analiseId}/economica`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tma_aa_real: tmaAaReal, ...(curva ? { curva } : {}) }),
  });
  return jsonOrThrow(res);
}

// Última avaliação persistida (404 → null: ainda não rodou).
export async function obterEconomica(
  analiseId: string
): Promise<Economica | null> {
  const res = await fetch(`${API_BASE}/api/analises/${analiseId}/economica`);
  if (res.status === 404) return null;
  return jsonOrThrow(res);
}

// ----- Fase 6 — Localização (enriquecimento socioeconômico IBGE; INFORMATIVO, §1-A) -----
// O front só renderiza estes shapes; nenhum número é calculado/reformatado aqui (§2).
export interface Populacao {
  disponivel: boolean;
  censo_2022: number | null;
  censo_2022_fmt: string | null;
  censo_2010: number | null;
  censo_2010_fmt: string | null;
  crescimento_total_pct: number | null;
  crescimento_total_fmt: string | null;
  crescimento_aa_pct: number | null;
  crescimento_aa_fmt: string | null;
  densidade_hab_km2: number | null;
  densidade_fmt: string | null;
  area_km2: number | null;
  vs_uf: number | null;
  fonte: string | null;
  leitura: string | null;
  aviso: string | null;
}

export interface Renda {
  disponivel: boolean;
  pib_per_capita: number | null;
  pib_per_capita_fmt: string | null;
  ano: number | null;
  vs_uf: number | null;
  vs_uf_fmt: string | null;
  vs_brasil: number | null;
  vs_brasil_fmt: string | null;
  fonte: string | null;
  leitura: string | null;
  aviso: string | null;
}

export interface Deficit {
  valor: number;
  valor_fmt: string;
  fonte: string;
  ano: number;
}

export interface FallbackEstoque {
  domicilios_ocupados: number;
  domicilios_ocupados_fmt: string;
  moradores_por_domicilio: number;
  moradores_por_domicilio_fmt: string;
  fonte: string;
}

export interface Habitacao {
  disponivel: boolean;
  deficit: Deficit | null;
  fallback_estoque: FallbackEstoque | null;
  fonte: string | null;
  aviso: string | null;
}

export interface GrupoEtario {
  faixa: string;
  pct: number;
  pct_fmt: string;
}

export interface FaixaEtaria {
  disponivel: boolean;
  fonte: string | null;
  grupos: GrupoEtario[];
  aviso: string | null;
}

export interface Localizacao {
  avaliada: boolean;
  cobertura: "COMPLETA" | "PARCIAL" | "INDISPONIVEL";
  municipio: { cod_ibge: string | null; nome: string | null; uf: string | null };
  populacao: Populacao;
  renda: Renda;
  habitacao: Habitacao;
  faixa_etaria: FaixaEtaria;
  proveniencia: string;
  avisos: string[];
}

export async function buscarLocalizacao(analiseId: string): Promise<Localizacao> {
  const res = await fetch(`${API_BASE}/api/analises/${analiseId}/localizacao`);
  return jsonOrThrow(res);
}

// ----- Fase 9 — Urbanismo (estudo de massa esquemático proposto por IA) -----
// IA na BORDA propõe o PROGRAMA; o Python MEDE geometria e números (§2). O front só
// renderiza estes shapes — zero geo-matemática/recálculo aqui.
export type TipoLoteamento =
  | "aberto"
  | "fechado"
  | "condominio_lotes"
  | "desmembramento"
  | "loteamento_rural";
export type PublicoAlvo = "baixa" | "media" | "alta";

export interface ProgramaUrb {
  lote_alvo_m2: number;
  densidade: string;
  pct_lazer: number;
  amenidades: string[];
  arquetipo_viario: string;
  largura_via_m: number;
  testada_m: number;
  profundidade_m: number;
  pct_institucional: number;
  // Fase 9.3 — calibração do perfil (o tamanho emerge da quadra, mirando estes)
  publico_alvo: string;
  testada_alvo_m: number;
  faixa_lote_m2: number[];
  lote_alvo_origem: string;
  origem: string;
  justificativa: string;
}

export interface UsoArea {
  m2: number;
  m2_fmt: string;
  pct_apo: number;
  pct_fmt: string;
}

export interface QuadroAreas {
  area_liquida_m2: number;
  area_liquida_fmt: string;
  vendavel: UsoArea;
  areas_verdes: UsoArea;
  // Fase 10 (Parte 2) — verde desmembrado: reserva (legítimo) × sobra geométrica (a reduzir).
  area_verde_reserva?: UsoArea | null;
  sobra_geometrica?: UsoArea | null;
  sistema_lazer: UsoArea;
  institucional: UsoArea;
  arruamento: UsoArea;
}

export interface IndicadoresUrb {
  n_lotes: number;
  area_media_m2: number | null;
  area_media_fmt: string | null;
  testada_media_m: number | null;
  profundidade_media_m: number | null;
  comprimento_vias_m: number | null;
  leito_carrocavel_m2: number | null;
  calcadas_m2: number | null;
}

export interface FaixaHeatmap {
  faixa: string;
  n: number;
  pct: number;
}
export interface LoteScore {
  lote_id: string;
  score: number;
  area_m2: number;
}
export interface HeatmapUrb {
  score_medio: number | null;
  faixas: FaixaHeatmap[];
  por_lote: LoteScore[];
  proveniencia: string;
}

export interface GeometriaUrb {
  rotulo: string;
  // Fase 9.5 — parcelamento legível: 1 Feature por lote (geometria + props: lote_id, area_m2,
  // score, testada_m, profundidade_m, quadra_id, faixa_score). ``lotes`` (fundido) é fallback.
  lotes_features: GeoJSON.FeatureCollection | null;
  lotes: GeoJSON.Geometry | null;
  // Fase 9.7 — quadras como FACES da malha (cada face com área); viário agora é malha conexa.
  quadras: GeoJSON.FeatureCollection | null;
  arruamento:
    | (GeoJSON.Geometry & {
        conexo?: boolean;
        trechos?: number | null;
        hierarquia?: { tronco_m: number; local_m: number } | null;
      })
    | null;
  areas_verdes: GeoJSON.Geometry | null;
  // Fase 9.6 — verde separado p/ o mapa: bloco reservado (destaque) × sobra de ponta (discreto).
  areas_verdes_reservada: GeoJSON.Geometry | null;
  areas_verdes_sobra: GeoJSON.Geometry | null;
  // Fase 9.7 — clube como figura formada (forma=quadra); institucional como quadra (qualifica_legal).
  sistema_lazer: (GeoJSON.Geometry & { forma?: string; frente_via_m?: number | null }) | null;
  institucional:
    | (GeoJSON.Geometry & {
        frente_via_m?: number | null;
        circulo_inscrito_m?: number | null;
        declividade_pct?: number | null;
        qualifica_legal?: boolean;
      })
    | null;
  // Fase 11.3 — pórtico/entrada: marcador do acesso único (alto padrão) p/ o mapa.
  portico?: GeoJSON.Geometry | null;
  // Fase 9.8 — restrição recortada (mata/declividade/APP) p/ o mapa rotular (não "clarão").
  restricao_recortada?:
    | (GeoJSON.Geometry & { origem?: string[]; rotulo?: string; estilo_sugerido?: string })
    | null;
  // Fase 9.7/9.8 — diagnósticos: conectividade + ilhas + stubs podados + qualificação legal.
  viario_diagnostico?: {
    conexo: boolean;
    trechos: number;
    trechos_descartados: number;
    ilhas?: number;
    conexo_por_ilha?: boolean;
    stubs_podados?: number;
    viario_pct?: number;
    vendavel_pct?: number;
    // Fase 9.9 — traçado sinuoso (a IA propõe eixos curvos; o Python materializa).
    esqueleto_vazio?: boolean;
    esqueleto_origem?: string; // "llm" | "fallback_curva" | "grade"
    sinuosidade_media?: number; // >1.1 = curvo (1.0 = reto)
    eixos_curvos?: boolean;
    // Fase 9.11 — grade adaptativa por ilha (lado do quarteirão dimensionado por ilha, piso legal).
    grade_adaptativa?: boolean;
    ilhas_detalhe?: {
      ilha: number;
      area_m2: number;
      bbox_m: [number, number];
      lado_quadra_m: number | null;
      faces: number;
      motivo: string;
    }[];
    // Fase 9.12 — todo lote com frente para via + parser dos eixos da IA.
    lotes_sem_via_tratados?: number;
    lotes_fundidos_lateral?: number;
    // Fase 9.13 — fundo órfão fundido com a frente (exceção) + invariante de zero encravados.
    lotes_fundidos_fundo?: number;
    lotes_sem_via_final?: number;
    lotes_viraram_verde?: number;
    // Fase 9.14 — traçado inteligente: contorno + conectividade + bulbo + recuperação.
    trechos_contornando_restricao?: number;
    vias_mortas?: number;
    culdesacs_bulbo?: number;
    indice_conectividade?: number;
    porcoes_loteaveis?: number;
    porcoes_conectadas?: number;
    porcoes_isoladas_viraram_verde?: number;
    lotes_recuperados_de_sobra?: number;
    verde_reserva_m2?: number;
    verde_sobra_m2?: number;
    // Fase 10 (Parte 4) — alto padrão (tags do estudo).
    alto_padrao?: {
      porticos: number;
      institucional_na_entrada: boolean;
      arborizacao_viaria: boolean;
      portico_ponto?: number[] | null;
    };
    // Fase 10 (Parte 3) — loteamento único (travessia liga as porções).
    loteamento_conexo?: boolean;
    conexao?: {
      loteamento_conexo: boolean;
      porcoes_detectadas: number;
      porcoes_conectadas: number;
      barreira_reavaliada_contra_relevo: boolean;
      alerta_topografia: boolean;
      travessia?: {
        proposta_por?: string;
        ponto?: number[];
        greide_medido_pct?: number;
        extensao_m?: number;
        veredicto?: string;
        caixa_via_m?: number;
        alerta_topografia?: boolean;
        greide_indeterminado?: boolean;
        // Fase 10.3 — via de conexão por traçado DIAGONAL que cruza a faixa ≥30% (veda lote, não via).
        modelo?: string;            // "diagonal_minimax" | "reto"
        cruza_restricao?: boolean;
        exigencia_geotecnica?: boolean;
        nota_geotecnica?: string | null;
      } | null;
    };
    tracado_hierarquia?: string[];
    testada_media_m?: number;
    todos_lotes_com_frente_via?: boolean;
    eixos_ia_aceitos?: number;
    eixos_ia_descartados?: number;
    hierarquia: { tronco_m: number; local_m: number };
    obs: string;
  } | null;
  institucional_diagnostico?: {
    qualifica_legal: boolean;
    checks: Record<string, boolean>;
    frente_via_m?: number | null;
    circulo_inscrito_m?: number | null;
    declividade_pct?: number | null;
    obs: string;
  } | null;
}

export interface ItemConformidadePrograma {
  item: string;
  status: "considerado" | "atencao" | "nao_avaliado";
  leitura: string;
}

// Fase 9.1 — fidelidade do traçado ao programa (convergência + viário + topografia).
export interface ItemFidelidadeArea {
  item: string;
  alvo_pct: number | null;
  medido_pct: number | null;
  status: string; // atendido | degradado | atencao
  tol_pp: number | null;
  leitura: string | null;
}
export interface Fidelidade {
  areas: ItemFidelidadeArea[];
  viario: {
    arquetipo: string;
    esqueleto_usado: boolean;
    trechos_descartados: number;
    obs: string;
  };
  topografia: { orientacao_por_declividade: boolean; obs: string };
}

// Fase 9.3 — distribuição de tamanhos MEDIDA (o lote emerge da subdivisão da quadra).
export interface FaixaHistograma {
  de: number;
  ate: number;
  n: number;
  pct: number;
}
export interface LoteUrb {
  lote_id: string;
  area_m2: number;
  testada_m: number;
  profundidade_m: number;
  score: number;
  quadra_id: string | null;
}
export interface DistribuicaoTamanhos {
  media_m2: number;
  desvio_m2: number;
  cv: number;
  min_m2: number;
  max_m2: number;
  fora_da_faixa: number; // Fase 9.4 — clamp legal: deve ser 0
  faixas: FaixaHistograma[];
  correlacao_tamanho_score: number;
  retalho_perdido_m2: number;
  retalho_perdido_pct: number;
  viario_pct: number;
  lote_alvo_origem: string;
  faixa_lote_m2: number[];
  lotes: LoteUrb[];
}

// Fase 9.4 — diretrizes municipais (LUOS→mercado→federal) + conformidade legal.
export interface Diretrizes {
  fonte: string;
  cobertura: string; // COMPLETA | BASE_FEDERAL
  confirmada: boolean;
  lote_min_zona_m2: number | null;
  piso_lote_efetivo_m2: number;
  teto_lote_m2: number;
  doacao_min_pct: number | null;
  doacao_split: Record<string, number | null> | null;
  aviso: string;
}
export interface ConformidadeLegal {
  item: string;
  exigido: number | null;
  medido: number;
  unidade: string;
  status: string; // atende | atende_com_folga | nao_atende | nao_avaliado
  leitura: string;
}

export interface PropostaUrbanistica {
  proposta_id: string;
  versao: number;
  rotulo: string;
  perfil: { tipo_loteamento: TipoLoteamento; publico_alvo: PublicoAlvo };
  programa: ProgramaUrb;
  geometria: GeometriaUrb;
  quadro_areas: QuadroAreas;
  indicadores: IndicadoresUrb;
  heatmap: HeatmapUrb;
  fidelidade: Fidelidade | null;
  distribuicao_tamanhos: DistribuicaoTamanhos | null;
  diretrizes: Diretrizes | null;
  conformidade_legal: ConformidadeLegal[];
  conformidade_programa: ItemConformidadePrograma[];
  reconciliacao?: ReconciliacaoUrbanismo | null; // Fase 9.10 — ponte (estudo × teto regulatório)
  esqueleto_ignorado: string[];
  areas_canonicas?: AreasCanonicas | null; // Fase 10 (Parte 1) — líquida canônica (mesma das abas)
  proveniencia: string;
  avisos: string[];
}

// IA propõe o programa; o backend gera+mede e devolve o snapshot versionado.
// 503 = sem credencial de IA (use /medir com layout pronto ou configure ANTHROPIC_API_KEY).
export async function proporUrbanismo(
  analiseId: string,
  tipoLoteamento: TipoLoteamento,
  publicoAlvo: PublicoAlvo,
  zona?: string | null,
  overrides?: Record<string, unknown>,
  loteMaxM2?: number | null // Fase 11.8 — teto de lote recomendado pelo operador (m²)
): Promise<PropostaUrbanistica> {
  const res = await fetch(
    `${API_BASE}/api/analises/${analiseId}/urbanismo/propor`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        tipo_loteamento: tipoLoteamento,
        publico_alvo: publicoAlvo,
        ...(zona ? { zona } : {}),
        ...(overrides ? { overrides } : {}),
        ...(loteMaxM2 ? { lote_max_m2: loteMaxM2 } : {}),
      }),
    }
  );
  return jsonOrThrow(res);
}

// Lista as propostas (snapshots versionados) já geradas para a análise.
export async function listarUrbanismo(
  analiseId: string
): Promise<PropostaUrbanistica[]> {
  const res = await fetch(`${API_BASE}/api/analises/${analiseId}/urbanismo`);
  return jsonOrThrow(res);
}
