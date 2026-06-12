// Composição dos slots do dashboard da Financeira (4.2) com a Econômica (Fase 5).
// PURA composição de dois JSONs do backend — zero cálculo no front (§2): os slots
// vpl/tir/payback nascem "pendente" na Financeira e, quando a Econômica existe,
// são substituídos pelas leituras dela (mesma chave). Nada é derivado aqui.

import type { Economica, Leitura } from "@/lib/api";

const SLOTS_FASE5 = new Set(["vpl", "tir", "payback"]);

export function comporLeituras(
  financeira: Leitura[],
  economica: Economica | null | undefined
): Leitura[] {
  if (!economica) return financeira;
  const porChave = new Map(economica.leituras.map((l) => [l.chave, l]));
  return financeira.map((l) =>
    l.status === "pendente" && SLOTS_FASE5.has(l.chave)
      ? porChave.get(l.chave) ?? l
      : l
  );
}
