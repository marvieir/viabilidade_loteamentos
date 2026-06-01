"use client";

import { useState } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import {
  calcularTodasBases,
  type LoteamentoResult,
  type Modalidade,
} from "@/lib/api";

const rotuloBase: Record<string, string> = {
  total: "Loteamento — base sobre área total",
  liquida: "Loteamento — base sobre área líquida",
  combinada: "Loteamento — vias+doação combinados",
};

// Formatação de exibição (não é cálculo): os números vêm prontos do backend.
const m2 = (v: number) =>
  v.toLocaleString("pt-BR", { maximumFractionDigits: 2 }) + " m²";
const pct = (v: number) =>
  (v * 100).toLocaleString("pt-BR", { maximumFractionDigits: 2 }) + "%";

export function CardAproveitamento({ analiseId }: { analiseId: string }) {
  const [loteMin, setLoteMin] = useState(200);
  const [vias, setVias] = useState(11500);
  const [doacao, setDoacao] = useState(0.2);
  const [combinado, setCombinado] = useState(0.35);
  const [fator, setFator] = useState(0.74);

  const [desmembramento, setDesmembramento] = useState<Modalidade | null>(null);
  const [bases, setBases] = useState<LoteamentoResult[] | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(false);

  async function calcular() {
    setCarregando(true);
    setErro(null);
    try {
      const r = await calcularTodasBases(analiseId, {
        lote_min_m2: loteMin,
        vias_m2: vias,
        doacao_pct: doacao,
        combinado_pct: combinado,
        fator_aprov: fator,
      });
      setDesmembramento(r.desmembramento);
      setBases(r.bases);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Falha ao calcular.");
    } finally {
      setCarregando(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Aproveitamento</CardTitle>
        <CardDescription>
          Desmembramento e loteamento (3 bases de doação). Cálculo no backend; aqui
          só renderizamos o JSON com a proveniência de cada número.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
          <Campo label="Lote mín. (m²)" value={loteMin} onChange={setLoteMin} />
          <Campo label="Vias (m²)" value={vias} onChange={setVias} />
          <Campo
            label="Doação"
            value={doacao}
            step={0.01}
            onChange={setDoacao}
          />
          <Campo
            label="Combinado"
            value={combinado}
            step={0.01}
            onChange={setCombinado}
          />
          <Campo
            label="Fator desmemb."
            value={fator}
            step={0.01}
            onChange={setFator}
          />
        </div>

        <Button onClick={calcular} disabled={carregando}>
          {carregando ? "Calculando…" : "Calcular aproveitamento"}
        </Button>

        {erro && (
          <p className="rounded-lg bg-rose-50 p-3 text-sm text-rose-800">
            {erro}
          </p>
        )}

        {desmembramento && bases && (
          <Table>
            <THead>
              <TR>
                <TH>Modalidade</TH>
                <TH>Área aproveitável</TH>
                <TH>%</TH>
                <TH>Lotes</TH>
                <TH>Proveniência</TH>
              </TR>
            </THead>
            <TBody>
              <TR>
                <TD className="font-medium">Desmembramento</TD>
                <TD>{m2(desmembramento.area_aproveitavel_m2)}</TD>
                <TD>{pct(desmembramento.pct_aproveitamento)}</TD>
                <TD>{desmembramento.n_lotes}</TD>
                <TD className="text-xs text-slate-500">
                  {desmembramento.proveniencia}
                </TD>
              </TR>
              {bases.map((b) => (
                <TR key={b.base_doacao}>
                  <TD className="font-medium">{rotuloBase[b.base_doacao]}</TD>
                  <TD>{m2(b.area_aproveitavel_m2)}</TD>
                  <TD>{pct(b.pct_aproveitamento)}</TD>
                  <TD>{b.n_lotes}</TD>
                  <TD className="text-xs text-slate-500">{b.proveniencia}</TD>
                </TR>
              ))}
            </TBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}

function Campo({
  label,
  value,
  onChange,
  step = 1,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  step?: number;
}) {
  return (
    <label className="flex flex-col gap-1 text-xs text-slate-600">
      {label}
      <input
        type="number"
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="rounded-lg border border-slate-300 px-2 py-1 text-sm text-slate-900"
      />
    </label>
  );
}
