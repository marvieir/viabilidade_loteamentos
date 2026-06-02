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
  calcularRural,
  calcularTodasBases,
  type LoteamentoResult,
  type Modalidade,
  type ModalidadeUrbana,
  type Regime,
  type RuralResult,
} from "@/lib/api";

const MODALIDADES: { valor: ModalidadeUrbana; rotulo: string }[] = [
  { valor: "loteamento_aberto", rotulo: "Loteamento aberto" },
  { valor: "loteamento_fechado", rotulo: "Loteamento fechado" },
  { valor: "condominio_lotes", rotulo: "Condomínio de lotes" },
  { valor: "condominio_edilicio", rotulo: "Condomínio edilício" },
  { valor: "desmembramento", rotulo: "Desmembramento" },
];

const rotuloBase: Record<string, string> = {
  total: "Loteamento — base sobre área total",
  liquida: "Loteamento — base sobre área líquida",
  combinada: "Loteamento — vias+doação combinados",
};

// Formatação de exibição (não é cálculo): os números vêm prontos do backend.
const m2 = (v: number) =>
  v.toLocaleString("pt-BR", { maximumFractionDigits: 2 }) + " m²";
const ha = (v: number) =>
  (v / 10_000).toLocaleString("pt-BR", { maximumFractionDigits: 2 }) + " ha";
const pct = (v: number) =>
  (v * 100).toLocaleString("pt-BR", { maximumFractionDigits: 2 }) + "%";

export function CardAproveitamento({ analiseId }: { analiseId: string }) {
  const [regime, setRegime] = useState<Regime>("URBANO");

  // URBANO
  const [modalidade, setModalidade] =
    useState<ModalidadeUrbana>("loteamento_aberto");
  const [loteMin, setLoteMin] = useState(200);
  const [vias, setVias] = useState(11500);
  const [doacao, setDoacao] = useState(0.2);
  const [combinado, setCombinado] = useState(0.35);
  const [fator, setFator] = useState(0.74);
  // RURAL
  const [fmp, setFmp] = useState(20000);

  const [desmembramento, setDesmembramento] = useState<Modalidade | null>(null);
  const [bases, setBases] = useState<LoteamentoResult[] | null>(null);
  const [rural, setRural] = useState<RuralResult | null>(null);
  const [premissa, setPremissa] = useState<string | null>(null);
  const [origemLote, setOrigemLote] = useState<string | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(false);

  function limpar() {
    setDesmembramento(null);
    setBases(null);
    setRural(null);
    setPremissa(null);
    setOrigemLote(null);
  }

  async function calcular() {
    setCarregando(true);
    setErro(null);
    try {
      if (regime === "RURAL") {
        const r = await calcularRural(analiseId, fmp);
        limpar();
        setRural(r.rural ?? null);
        setPremissa(r.premissa);
      } else {
        const r = await calcularTodasBases(
          analiseId,
          {
            lote_min_m2: loteMin,
            vias_m2: vias,
            doacao_pct: doacao,
            combinado_pct: combinado,
            fator_aprov: fator,
          },
          modalidade
        );
        limpar();
        setDesmembramento(r.desmembramento);
        setBases(r.bases);
        setPremissa("parcelamento URBANO (Lei 6.766/79)");
        setOrigemLote(
          "declarado pelo usuário (pendente extração da LUOS — Fase 1.8)"
        );
      }
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
          Primeiro o regime do parcelamento: URBANO (Lei 6.766) ou RURAL (FMP do
          INCRA). Cálculo no backend; aqui só renderizamos o JSON com a
          proveniência.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Seletor de regime */}
        <div className="flex flex-wrap gap-2">
          {(["URBANO", "RURAL"] as Regime[]).map((r) => (
            <button
              key={r}
              type="button"
              onClick={() => {
                setRegime(r);
                limpar();
                setErro(null);
              }}
              className={`rounded-lg border px-3 py-1.5 text-sm font-medium transition-colors ${
                regime === r
                  ? "border-slate-900 bg-slate-900 text-white"
                  : "border-slate-300 bg-white text-slate-700 hover:bg-slate-50"
              }`}
            >
              {r === "URBANO" ? "Urbano (Lei 6.766)" : "Rural (FMP / INCRA)"}
            </button>
          ))}
        </div>

        {regime === "URBANO" ? (
          <div className="space-y-3">
            <label className="flex flex-col gap-1 text-xs text-slate-600">
              Modalidade (obrigatória)
              <select
                value={modalidade}
                onChange={(e) =>
                  setModalidade(e.target.value as ModalidadeUrbana)
                }
                className="rounded-lg border border-slate-300 px-2 py-1.5 text-sm text-slate-900"
              >
                {MODALIDADES.map((m) => (
                  <option key={m.valor} value={m.valor}>
                    {m.rotulo}
                  </option>
                ))}
              </select>
            </label>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
              <Campo
                label="Lote mín. (m²)"
                value={loteMin}
                onChange={setLoteMin}
              />
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
            <p className="rounded-lg bg-amber-50 p-3 text-xs text-amber-900">
              <span className="font-medium">Lote mínimo provisório.</span> O valor
              acima é <span className="font-medium">declarado por você</span>{" "}
              (proveniência: &quot;declarado pelo usuário — pendente extração da
              LUOS, Fase 1.8&quot;). A leitura automática das diretrizes municipais
              (lote/vias/doação por modalidade) entra na próxima fase.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            <Campo
              label="FMP do município (m²)"
              value={fmp}
              step={1000}
              onChange={setFmp}
            />
            <p className="col-span-2 self-end text-xs text-slate-500">
              Piso de parcelamento rural (módulo fiscal/FMP, INCRA). 20.000 m² = 2
              ha. Puxado da tabela do município quando disponível; editável aqui.
            </p>
          </div>
        )}

        <Button onClick={calcular} disabled={carregando}>
          {carregando
            ? "Calculando…"
            : regime === "RURAL"
              ? "Calcular parcelas rurais"
              : "Calcular aproveitamento"}
        </Button>

        {premissa && (
          <p className="rounded-lg bg-slate-50 p-3 text-xs text-slate-600">
            <span className="font-medium">Premissa:</span> {premissa}
            {origemLote ? (
              <>
                <br />
                <span className="font-medium">Origem do lote:</span> {origemLote}
              </>
            ) : null}
          </p>
        )}

        {erro && (
          <p className="rounded-lg bg-rose-50 p-3 text-sm text-rose-800">{erro}</p>
        )}

        {/* RURAL */}
        {rural && (
          <Table>
            <THead>
              <TR>
                <TH>Regime rural</TH>
                <TH>Área</TH>
                <TH>FMP</TH>
                <TH>Parcelas</TH>
                <TH>Proveniência</TH>
              </TR>
            </THead>
            <TBody>
              <TR>
                <TD className="font-medium">Parcelamento rural</TD>
                <TD>
                  {m2(rural.area_m2)} ({ha(rural.area_m2)})
                </TD>
                <TD>
                  {m2(rural.fmp_m2)} ({ha(rural.fmp_m2)})
                </TD>
                <TD className="font-semibold">{rural.n_parcelas}</TD>
                <TD className="text-xs text-slate-500">{rural.proveniencia}</TD>
              </TR>
            </TBody>
          </Table>
        )}
        {rural && (
          <p className="rounded-lg bg-amber-50 p-3 text-xs text-amber-900">
            {rural.flag_conversao}
          </p>
        )}

        {/* URBANO */}
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
