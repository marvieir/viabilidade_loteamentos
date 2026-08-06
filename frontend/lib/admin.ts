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
  // Contato do modal obrigatório do 1º login — o admin precisa conseguir falar com o cliente.
  celular: string | null;
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
export interface ContagemUso {
  rotulo: string;
  n: number;
}
export interface CustoCliente {
  usuario_id: string;
  email: string;
  nome: string | null;
  n_analises_ia: number;
  n_regeneracoes: number;
  n_matriculas: number;
  chamadas: number;
  custo_usd: number;
  custo_brl: number;
}
export interface AdminCustos {
  n_registros: number;
  total_usd: number;
  total_brl: number;
  usd_brl: number;
  modelo_nao_tabelado: number;
  total_regeneracoes: number;
  total_matriculas: number;
  media_regeneracoes_por_analise: number;
  media_matriculas_por_analise: number;
  perfil_uso: ContagemUso[];
  por_cliente: CustoCliente[];
  por_modelo: CustoLinha[];
  por_dimensao: CustoLinha[];
  por_analise: CustoLinha[];
  luos_por_municipio: CustoLinha[];
  avisos: string[];
}

export async function obterCustos(): Promise<AdminCustos> {
  return apiFetch("/api/admin/custos").then(jsonOrThrow);
}

// ----- ADMIN-1 — gestão de contas -----

export async function alterarAtivoCliente(id: string, ativo: boolean): Promise<void> {
  await apiFetch(`/api/admin/clientes/${id}/ativo`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ativo }),
  }).then(jsonOrThrow);
}

// Exclusão DEFINITIVA — o backend exige o e-mail idêntico (dupla confirmação).
export async function excluirCliente(id: string, email: string): Promise<void> {
  const r = await apiFetch(
    `/api/admin/clientes/${id}?email=${encodeURIComponent(email)}`,
    { method: "DELETE" },
  );
  if (!r.ok) {
    let detalhe = `${r.status} ${r.statusText}`;
    try {
      const body = await r.json();
      if (body?.detail) detalhe = body.detail;
    } catch {
      /* corpo não-JSON */
    }
    throw new Error(detalhe);
  }
}
