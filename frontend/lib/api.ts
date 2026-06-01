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

export interface Jurisdicao {
  municipio: string | null;
  uf: string | null;
  cod_ibge: string | null;
  cobertura: Cobertura;
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

export interface Modalidade {
  area_aproveitavel_m2: number;
  pct_aproveitamento: number;
  n_lotes: number;
  proveniencia: string;
}

export interface LoteamentoResult extends Modalidade {
  base_doacao: string;
}

export interface Aproveitamento {
  desmembramento: Modalidade;
  loteamento: LoteamentoResult;
}

export type BaseDoacao = "total" | "liquida" | "combinada";

export interface AproveitamentoParams {
  lote_min_m2: number;
  vias_m2: number;
  doacao_pct: number;
  combinado_pct: number;
  fator_aprov: number;
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

export async function calcularAproveitamento(
  analiseId: string,
  base: BaseDoacao,
  p: AproveitamentoParams
): Promise<Aproveitamento> {
  const res = await fetch(
    `${API_BASE}/api/analises/${analiseId}/aproveitamento`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        lote_min_m2: p.lote_min_m2,
        loteamento: {
          vias_m2: p.vias_m2,
          doacao_pct: p.doacao_pct,
          base_doacao: base,
          combinado_pct: p.combinado_pct,
        },
        desmembramento: { fator_aprov: p.fator_aprov },
      }),
    }
  );
  return jsonOrThrow(res);
}

// Conveniência: busca as três bases (cada uma é um cálculo do backend).
export async function calcularTodasBases(
  analiseId: string,
  p: AproveitamentoParams
): Promise<{ desmembramento: Modalidade; bases: LoteamentoResult[] }> {
  const ordem: BaseDoacao[] = ["total", "liquida", "combinada"];
  const resultados = await Promise.all(
    ordem.map((b) => calcularAproveitamento(analiseId, b, p))
  );
  return {
    desmembramento: resultados[0].desmembramento,
    bases: resultados.map((r) => r.loteamento),
  };
}
