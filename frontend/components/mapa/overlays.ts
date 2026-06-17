import type { ChaveOverlay } from "@/lib/api";

// Cores e rótulos das camadas no mapa (legenda + overlays). Fonte única — usada pelo
// MapaLeaflet, pela legenda do mapa-herói e pelos cards que empurram overlays.
export const CORES_OVERLAY: Record<ChaveOverlay, string> = {
  app: "#3b82f6",
  faixa_nao_edificavel: "#06b6d4",
  app_massa_dagua: "#0ea5e9",
  uc: "#16a34a",
  mineracao: "#d97706",
  linhas_transmissao: "#a855f7",
  verde: "#65a30d", // cobertura vegetal (Fase 2.2)
  verde_dura: "#dc2626", // verde em APP/UC = restrição dura (Fase 2.3)
  verde_verificar: "#eab308", // verde fora de APP/UC = a verificar (Fase 2.3)
  declividade_vedada: "#b91c1c", // declividade ≥30% vedada (Fase 2.5)
  // Fase 9 — estudo de massa esquemático
  urb_lotes: "#6366f1",
  urb_arruamento: "#64748b",
  urb_verde: "#16a34a",
  urb_verde_reservada: "#16a34a", // verde escuro saturado (bloco)
  urb_verde_sobra: "#86efac", // verde claro (remanescente)
  urb_lazer: "#06b6d4", // cor de equipamento
  urb_institucional: "#f59e0b",
};

// Fase 9.6 — estilo POR camada (contraste sobre satélite, borda própria). Sem entrada → default.
export interface EstiloOverlay {
  color: string;
  weight: number;
  fillColor: string;
  fillOpacity: number;
  dashArray?: string;
}
export const ESTILO_OVERLAY: Partial<Record<ChaveOverlay, EstiloOverlay>> = {
  urb_verde_reservada: { color: "#14532d", weight: 2, fillColor: "#22c55e", fillOpacity: 0.55 },
  urb_verde_sobra: { color: "#16a34a", weight: 1, fillColor: "#86efac", fillOpacity: 0.22, dashArray: "4 3" },
  urb_lazer: { color: "#0e7490", weight: 2, fillColor: "#22d3ee", fillOpacity: 0.5 },
  urb_institucional: { color: "#b45309", weight: 2, fillColor: "#f59e0b", fillOpacity: 0.5 },
  urb_arruamento: { color: "#334155", weight: 1, fillColor: "#64748b", fillOpacity: 0.4 },
};

export const ROTULO_OVERLAY: Record<ChaveOverlay, string> = {
  app: "APP (hidrografia)",
  faixa_nao_edificavel: "Faixa não-edificável",
  app_massa_dagua: "APP de massa d'água",
  uc: "Unidade de conservação",
  mineracao: "Mineração (ANM)",
  linhas_transmissao: "Faixa de servidão (LT/ANEEL)",
  verde: "Cobertura vegetal",
  verde_dura: "Verde em APP/UC (restrição dura)",
  verde_verificar: "Verde a verificar",
  declividade_vedada: "Declividade ≥30% (vedada)",
  urb_lotes: "Lotes (vendável)",
  urb_arruamento: "Sistema viário",
  urb_verde: "Áreas verdes",
  urb_verde_reservada: "Área verde (reservada)",
  urb_verde_sobra: "Verde remanescente",
  urb_lazer: "Sistema de lazer / clube",
  urb_institucional: "Institucional",
};

// Fase 9.5 — cores das faixas de score (frio→quente) p/ colorir cada LOTE no mapa (heatmap real).
export const CORES_FAIXA: Record<string, string> = {
  "0-3": "#2563eb", // frio
  "3-5": "#06b6d4",
  "5-7": "#84cc16",
  "7-9": "#f59e0b",
  "9-10": "#ef4444", // quente
};
