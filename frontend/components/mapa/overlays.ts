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
};
