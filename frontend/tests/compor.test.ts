// Fase 5, critério 10: os slots vpl/tir/payback do dashboard são preenchidos quando a
// Econômica existe — composição PURA de dois JSONs do backend, zero cálculo no front.

import { describe, expect, it } from "vitest";
import { comporLeituras } from "@/lib/compor";
import type { Economica, Leitura } from "@/lib/api";

const FINANCEIRA: Leitura[] = [
  { chave: "resultado_nominal", status: "favoravel", texto: "Resultado nominal positivo sob as premissas declaradas.", valor_fmt: "R$ 3.375.600,00" },
  { chave: "margem", status: "favoravel", texto: "Margem ≥ referência.", valor_fmt: "42,195%" },
  { chave: "vpl", status: "pendente", texto: "Disponível na dimensão Econômica (Fase 5).", valor_fmt: null },
  { chave: "tir", status: "pendente", texto: "Disponível na dimensão Econômica (Fase 5).", valor_fmt: null },
  { chave: "payback", status: "pendente", texto: "Disponível na dimensão Econômica (Fase 5).", valor_fmt: null },
];

const ECONOMICA = {
  leituras: [
    { chave: "vpl", status: "favoravel", texto: "VPL de R$ 3.128.359,33 à TMA real de 12,00% a.a. — o fluxo cria valor sob as premissas declaradas.", valor_fmt: "R$ 3.128.359,33" },
    { chave: "tir", status: "favoravel", texto: "TIR real acima da TMA informada, sob as premissas declaradas.", valor_fmt: "12.342,17% a.a." },
    { chave: "payback", status: "favoravel", texto: "Payback simples no mês 3; descontado no mês 3 (sob as premissas declaradas).", valor_fmt: "mês 3 / 3" },
  ],
} as unknown as Economica;

describe("comporLeituras (slots do dashboard 4.2 × Econômica Fase 5)", () => {
  it("sem econômica: slots permanecem pendentes (intactos)", () => {
    expect(comporLeituras(FINANCEIRA, null)).toEqual(FINANCEIRA);
    expect(comporLeituras(FINANCEIRA, undefined)).toEqual(FINANCEIRA);
  });

  it("com econômica: vpl/tir/payback saem de 'pendente' para as leituras dela", () => {
    const out = comporLeituras(FINANCEIRA, ECONOMICA);
    const porChave = new Map(out.map((l) => [l.chave, l]));
    for (const chave of ["vpl", "tir", "payback"]) {
      expect(porChave.get(chave)!.status).toBe("favoravel");
      expect(porChave.get(chave)!.texto).toContain("sob as premissas declaradas");
    }
    expect(porChave.get("vpl")!.valor_fmt).toBe("R$ 3.128.359,33");
  });

  it("leituras próprias da financeira nunca são tocadas; ordem preservada", () => {
    const out = comporLeituras(FINANCEIRA, ECONOMICA);
    expect(out[0]).toEqual(FINANCEIRA[0]); // resultado_nominal intacto
    expect(out[1]).toEqual(FINANCEIRA[1]); // margem intacta
    expect(out.map((l) => l.chave)).toEqual(FINANCEIRA.map((l) => l.chave));
  });

  it("slot sem leitura correspondente na econômica permanece pendente", () => {
    const soVpl = {
      leituras: [ECONOMICA.leituras[0]],
    } as unknown as Economica;
    const out = comporLeituras(FINANCEIRA, soVpl);
    const porChave = new Map(out.map((l) => [l.chave, l]));
    expect(porChave.get("vpl")!.status).toBe("favoravel");
    expect(porChave.get("tir")!.status).toBe("pendente");
    expect(porChave.get("payback")!.status).toBe("pendente");
  });
});
