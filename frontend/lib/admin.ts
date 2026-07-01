// Fase 12.3 — cliente do painel admin (somente leitura; exige papel admin no backend).

import { apiFetch } from "@/lib/auth";

export interface AdminMetricas {
  total_clientes: number;
  total_analises: number;
  novos_clientes_mes: number;
  por_uf: Record<string, number>;
  por_cidade: Record<string, number>;
}

export interface AdminCliente {
  id: string;
  email: string;
  nome: string | null;
  papel: string;
  ativo: boolean;
  criado_em: string;
  n_analises: number;
  cidades: string[];
  ufs: string[];
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

export async function obterMetricas(): Promise<AdminMetricas> {
  return apiFetch("/api/admin/metricas").then(jsonOrThrow);
}

export async function listarClientes(): Promise<AdminCliente[]> {
  return apiFetch("/api/admin/clientes").then(jsonOrThrow);
}

// Custo real de LLM medido (tokens de verdade), por análise/dimensão/modelo.
export interface CustoLinha {
  chave: string;
  rotulo: string | null;
  chamadas: number;
  custo_usd: number;
  custo_brl: number;
  detalhe: Record<string, number>;
}
export interface AdminCustos {
  n_registros: number;
  total_usd: number;
  total_brl: number;
  usd_brl: number;
  modelo_nao_tabelado: number;
  por_modelo: CustoLinha[];
  por_dimensao: CustoLinha[];
  por_analise: CustoLinha[];
  luos_por_municipio: CustoLinha[];
  avisos: string[];
}

export async function obterCustos(): Promise<AdminCustos> {
  return apiFetch("/api/admin/custos").then(jsonOrThrow);
}
