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
  rota: "POLYGON_DIRETO" | "LINHA_FECHAVEL";
  descricao: string;
}

export interface Analise {
  analise_id: string;
  geometria: Geometria;
  jurisdicao: Jurisdicao;
  origem_geometria: OrigemGeometria;
  avisos: string[];
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

export interface Aproveitamento {
  regime: Regime;
  premissa: string;
  descontos?: Descontos | null;
  area_aproveitavel_m2?: number | null;
  pct_sobre_total?: number | null;
  // URBANO
  origem_lote?: string | null;
  lote_min_m2?: number | null;
  n_lotes_teto?: number | null;
  ressalva_urbano?: string | null;
  // RURAL
  rural?: RuralResult | null;
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

export async function criarAnalise(kmz: File): Promise<Analise> {
  const form = new FormData();
  form.append("kmz", kmz);
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
  modalidade: ModalidadeUrbana = "loteamento_aberto"
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
  | "verde";

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

export interface Vegetacao {
  area_total_m2: number;
  area_verde_m2: number | null;
  area_liquida_m2: number | null;
  percentual_verde: number | null;
  geojson_verde: GeoJSON.Geometry | Record<string, never>;
  proveniencia: ProvenienciaVegetacao | null;
  avisos: string[];
  consultada: boolean;
}

export async function buscarVegetacao(analiseId: string): Promise<Vegetacao> {
  const res = await fetch(`${API_BASE}/api/analises/${analiseId}/vegetacao`);
  return jsonOrThrow(res);
}
