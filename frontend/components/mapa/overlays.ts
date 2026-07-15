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
  declividade_faixas: "#f59e0b", // mapa colorido de declividade (faixas; pintado por feição)
  areas_umidas: "#0d9488", // área úmida/alagável (APP candidata) — teal/azul-esverdeado
  reserva_legal: "#15803d", // Reserva Legal averbada no CAR — verde-escuro
  mata_atlantica: "#047857", // domínio Mata Atlântica (Lei 11.428) — verde-mata
  terra_indigena: "#c2410c", // Terra Indígena (FUNAI) — laranja-terra
  territorio_quilombola: "#a16207", // Território Quilombola — âmbar-escuro
  assentamento: "#9333ea", // Assentamento (INCRA) — roxo
  caverna: "#57534e", // Caverna (CECAV) + raio de influência — cinza-pedra
  area_protecao_manancial: "#0369a1", // Área de Proteção de Mananciais — azul-água
  dutovia: "#b91c1c", // Dutovia (gás/petróleo) + faixa — vermelho
  patrimonio_cultural: "#7c3aed", // Patrimônio cultural/arqueológico (IPHAN) — violeta
  area_contaminada: "#65a30d", // Área contaminada (CETESB) — verde-oliva (passivo)
  apcb: "#0891b2", // Área Prioritária Biodiversidade (MMA) — ciano (diretriz)
  fund_malha: "#9a3412", // Malha fundiária SIGEF/SNCI — marrom-terra (parcela cadastral)
  // Fase 9 — estudo de massa esquemático
  urb_lotes: "#6366f1",
  urb_quadras: "#475569", // contorno das quadras (faces da malha — Fase 9.7)
  urb_arruamento: "#64748b",
  urb_verde: "#16a34a",
  urb_verde_reservada: "#22c55e", // park manicurado — verde médio (Fase 11.6 cores distintas)
  urb_verde_sobra: "#a3e635", // verde remanescente — LIMA claro (amarelado), distinto do park
  urb_lazer: "#06b6d4", // cor de equipamento
  urb_institucional: "#f59e0b",
  urb_portico: "#db2777", // Fase 11.3 — pórtico/entrada: rosa/magenta (cor ÚNICA, não clasha c/ lote)
  urb_agua: "#0369a1", // U3 — lago criado: azul-água (profundo, distinto do ciano do lazer)
  urb_restricao: "#14532d", // Fase 11.6 — bosque preservado: verde-FLORESTA bem escuro (o mais escuro)
  urb_restricao_via_ok: "#8d9d4f", // ≥30% dentro da restrição: oliva (lote vedado; VIA permitida c/ laudo)
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
  // Fase 9.7 — viário como MALHA (cinza forte, sólido); quadras como contorno (sem preenchimento).
  urb_arruamento: { color: "#1f2937", weight: 1, fillColor: "#475569", fillOpacity: 0.7 },
  urb_quadras: { color: "#334155", weight: 1.5, fillColor: "#000000", fillOpacity: 0, dashArray: "5 4" },
  // Fase 11.6 — 3 verdes DISTINTOS (o operador via tudo igual): park = verde médio sólido;
  // remanescente = lima claro amarelado pontilhado; bosque = floresta bem escuro texturizado.
  urb_verde_reservada: { color: "#15803d", weight: 2, fillColor: "#22c55e", fillOpacity: 0.55 },
  urb_verde_sobra: { color: "#65a30d", weight: 1.5, fillColor: "#bef264", fillOpacity: 0.5, dashArray: "4 3" },
  urb_lazer: { color: "#0e7490", weight: 2, fillColor: "#22d3ee", fillOpacity: 0.5 },
  urb_institucional: { color: "#b45309", weight: 2, fillColor: "#f59e0b", fillOpacity: 0.5 },
  // Área úmida/alagável: teal com hachura "ondulada" (dash) — lê como água/charco, distinto do
  // verde (vegetação) e do azul de APP de hidrografia. Fica sobre o satélite sem virar bloco sólido.
  areas_umidas: { color: "#0f766e", weight: 2, fillColor: "#14b8a6", fillOpacity: 0.45, dashArray: "3 4" },
  // Reserva Legal (CAR): verde-escuro com hachura — área averbada de uso restrito, não loteável.
  reserva_legal: { color: "#14532d", weight: 2, fillColor: "#16a34a", fillOpacity: 0.4, dashArray: "6 3" },
  // Malha fundiária SIGEF/SNCI: contorno marrom forte, preenchimento leve — parcela cadastral
  // (lê como limite de propriedade registrada sobre o satélite, sem virar bloco opaco).
  fund_malha: { color: "#7c2d12", weight: 1.5, fillColor: "#c2410c", fillOpacity: 0.18 },
  // Fase 11.3 — PÓRTICO/ENTRADA: marcador ROSA/MAGENTA forte (cor única no mapa, borda grossa) —
  // lê como o componente "portaria" no acesso único, achável sobre o satélite e os lotes.
  urb_portico: { color: "#831843", weight: 3, fillColor: "#ec4899", fillOpacity: 0.95 },
  urb_agua: { color: "#075985", weight: 1.5, fillColor: "#38bdf8", fillOpacity: 0.75 },
  // Fase 10.2 — não-edificável (mata/≥30%/APP) = BOSQUE/ÁREA VERDE PRESERVADA, não um buraco. Verde
  // mata visível (textura pontilhada = natural/preservado), distinto do verde-parque reservado
  // (#22c55e, manicured) e do verde-sobra (pálido). Não compete com os lotes (fica ao fundo), mas
  // LÊ como amenidade preservada — não como vazio com satélite vazando. O dado/geometria não muda.
  urb_restricao: { color: "#052e16", weight: 1.5, fillColor: "#14532d", fillOpacity: 0.5, dashArray: "1 6" },
  urb_restricao_via_ok: { color: "#6b7d3a", weight: 1, fillColor: "#8d9d4f", fillOpacity: 0.45, dashArray: "4 4" },
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
  declividade_faixas: "Declividade (faixas)",
  areas_umidas: "Área úmida/alagável (APP candidata)",
  reserva_legal: "Reserva Legal (CAR)",
  mata_atlantica: "Domínio Mata Atlântica (Lei 11.428)",
  terra_indigena: "Terra Indígena (FUNAI)",
  territorio_quilombola: "Território Quilombola",
  assentamento: "Assentamento (INCRA)",
  caverna: "Caverna (CECAV) + raio",
  area_protecao_manancial: "Área de Proteção de Mananciais",
  dutovia: "Dutovia (gás/petróleo) + faixa",
  patrimonio_cultural: "Patrimônio cultural/arqueológico (IPHAN)",
  area_contaminada: "Área contaminada (CETESB)",
  apcb: "Área Prioritária Biodiversidade (MMA)",
  fund_malha: "Malha fundiária (SIGEF/SNCI)",
  urb_lotes: "Lotes (vendável)",
  urb_quadras: "Quadras (faces da malha)",
  urb_arruamento: "Sistema viário (malha)",
  urb_verde: "Áreas verdes",
  urb_verde_reservada: "Área verde (reservada)",
  urb_verde_sobra: "Verde remanescente",
  urb_lazer: "Sistema de lazer / clube",
  urb_institucional: "Institucional",
  urb_portico: "Pórtico / entrada",
  urb_agua: "Lago / espelho d'água (criado)",
  urb_restricao: "Mata/APP preservada (não-edificável — nem via, nem lote)",
  urb_restricao_via_ok: "Declividade ≥30% — LOTE vedado; via permitida (laudo geotécnico, Lei 6.766 art. 3º)",
};

// Cores das 8 faixas de declividade (verde→vermelho) — usadas no card E na camada do mapa.
export const CORES_FINA: Record<string, string> = {
  "0-3%": "#86efac",
  "3-6%": "#4ade80",
  "6-9%": "#16a34a",
  "9-12%": "#facc15",
  "12-20%": "#f59e0b",
  "20-30%": "#ef4444",
  "30-47%": "#b91c1c",
  "47-100%": "#7f1d1d",
};

// Fase 9.5/U1 — cores das faixas de score p/ colorir cada LOTE no mapa (heatmap real).
// Rampa SEQUENCIAL de um matiz (YlOrRd claro→escuro): score é MAGNITUDE, não categoria.
// Escolhida para NÃO colidir com as camadas temáticas (o azul/ciano antigo da faixa 3-5 era
// idêntico ao "Sistema de lazer/clube" — com o score v2 centrando em ~5, o mapa enchia de
// lotes ciano que pareciam clube). Validada p/ daltonismo (ΔE adjacente ≥13).
export const CORES_FAIXA: Record<string, string> = {
  "0-3": "#ffffb2", // score baixo (claro)
  "3-5": "#fecc5c",
  "5-7": "#fd8d3c",
  "7-9": "#f03b20",
  "9-10": "#bd0026", // score alto (escuro/quente)
};

// U1 — QUINTIL de valorização relativo à proposta (1 = 20% menos … 5 = 20% mais valorizados).
// É a cor primária do lote: o score absoluto raramente encosta em 0/10, então só as faixas
// absolutas "achatavam" o mapa; o quintil (do backend) garante o espectro completo sempre.
export const CORES_QUINTIL: Record<number, string> = {
  1: "#ffffb2",
  2: "#fecc5c",
  3: "#fd8d3c",
  4: "#f03b20",
  5: "#bd0026",
};
export const ROTULO_QUINTIL: Record<number, string> = {
  1: "20% menos valorizados",
  2: "2º quintil",
  3: "3º quintil",
  4: "4º quintil",
  5: "20% mais valorizados",
};
