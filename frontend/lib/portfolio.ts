// AI Portfolio Insights — cliente do /api/portfolio. O backend agrega TUDO (KPIs,
// destaques, radar, avisos); aqui só transporte de JSON. O front nunca soma nada.

import { apiFetch } from "@/lib/auth";

export interface PortfolioGate {
  status: "liberado" | "previa" | "bloqueado";
  previa_dias: number;
  dias_restantes: number | null;
  primeiro_acesso: string | null;
  motivo: string;
}

export interface PortfolioKpis {
  n_lotes: number | null;
  area_media_m2: number | null;
  pct_vendavel: number | null;
  pct_viario: number | null;
  pct_sobra: number | null;
  pct_verde_bruta: number | null;
  lotes_por_ha: number | null;
  urbanismo_versao: number | null;
  urbanismo_origem: string | null;
  pct_restrito: number | null;
  alertas_criticos: number | null;
  alertas_informativos: number | null;
  juridico_nivel: string | null;
  divergencia_area_pct: number | null;
  vgv: number | null;
  vgv_fmt: string | null;
  vgv_por_ha: number | null;
  vgv_por_ha_fmt: string | null;
  vgv_proprio: number | null;
  vgv_proprio_fmt: string | null;
  permuta_modo: string | null;
  permuta_pct: number | null;
  margem_pct: number | null;
  lucro: number | null;
  lucro_fmt: string | null;
  exposicao_maxima: number | null;
  exposicao_maxima_fmt: string | null;
  exposicao_mes: number | null;
  multiplo_capital: number | null;
  receita_por_lote: number | null;
  receita_por_lote_fmt: string | null;
  meses_negativo: number | null;
  payback_descontado_mes: number | null;
  vpl: number | null;
  vpl_fmt: string | null;
  tir_aa_pct: number | null;
  tir_status: string | null;
  tma_aa_pct: number | null;
}

export interface PortfolioRadar {
  ambiental: number | null;
  juridico: number | null;
  urbanistico: number | null;
  financeiro: number | null;
}

export interface PortfolioLinha {
  id: string;
  titulo: string;
  cidade: string | null;
  uf: string | null;
  atualizada_em: string;
  area_ha: number | null;
  dimensoes: string[];
  kpis: PortfolioKpis;
  radar: PortfolioRadar;
  proveniencia: Record<string, string>;
}

export interface PortfolioDestaque {
  chave: string;
  rotulo: string;
  valor_fmt: string;
  analise_id: string;
  titulo: string;
  cidade: string | null;
  uf: string | null;
  fonte: string;
}

export interface Portfolio {
  gate: PortfolioGate;
  total_analises: number;
  com_dados: number;
  linhas: PortfolioLinha[];
  destaques: PortfolioDestaque[];
  radar_formula: Record<string, string>;
  avisos: string[];
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

export async function obterPortfolio(): Promise<Portfolio> {
  return apiFetch("/api/portfolio").then(jsonOrThrow);
}
