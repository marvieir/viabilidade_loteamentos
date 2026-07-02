// Fase 12.2 — cliente das "Minhas análises". Tudo autenticado (apiFetch injeta o Bearer).
// O front só transporta JSON; nenhum cálculo aqui.

import { apiFetch } from "@/lib/auth";
import type { Analise } from "@/lib/api";

export interface AnaliseResumo {
  id: string;
  titulo: string;
  kmz_nome: string | null;
  cidade: string | null;
  uf: string | null;
  area_ha: number | null;
  criada_em: string;
  atualizada_em: string;
  // Contorno da gleba normalizado (0..100, pronto p/ SVG) — vem do backend; o front só desenha.
  silhueta?: number[][][] | null;
}

export interface AnaliseDetalhe extends AnaliseResumo {
  gleba_geojson: GeoJSON.Polygon | null;
  resultados: Record<string, unknown> | null;
}

export interface SalvarPayload {
  titulo: string;
  kmz_nome?: string | null;
  gleba_geojson?: GeoJSON.Polygon | null;
  cidade?: string | null;
  uf?: string | null;
  area_ha?: number | null;
  resultados?: Record<string, unknown> | null;
  // id de trabalho atual — o backend guarda p/ o carregar reidratar sob o MESMO id
  // (jurídico/urbanismo/custos/financeira sobrevivem ao salvar→carregar).
  analise_id?: string | null;
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

export async function listarSalvas(): Promise<AnaliseResumo[]> {
  return apiFetch("/api/salvas").then(jsonOrThrow);
}

// Detalhe de uma salva (inclui o snapshot `resultados` p/ reidratar os cards no Abrir).
export async function obterSalva(id: string): Promise<AnaliseDetalhe> {
  return apiFetch(`/api/salvas/${id}`).then(jsonOrThrow);
}

export async function salvarAnalise(p: SalvarPayload): Promise<AnaliseDetalhe> {
  return apiFetch("/api/salvas", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(p),
  }).then(jsonOrThrow);
}

export async function atualizarAnalise(
  id: string,
  p: SalvarPayload,
): Promise<AnaliseDetalhe> {
  return apiFetch(`/api/salvas/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(p),
  }).then(jsonOrThrow);
}

export async function excluirAnalise(id: string): Promise<void> {
  const res = await apiFetch(`/api/salvas/${id}`, { method: "DELETE" });
  if (!res.ok && res.status !== 204) await jsonOrThrow(res);
}

// Reidrata a gleba no backend e devolve o objeto Analise (mesmo shape do upload).
export async function carregarAnalise(id: string): Promise<Analise> {
  return apiFetch(`/api/salvas/${id}/carregar`, { method: "POST" }).then(jsonOrThrow);
}
