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
  calcularUrbano,
  type Aproveitamento,
  type ModalidadeUrbana,
  type Regime,
} from "@/lib/api";

const MODALIDADES: { valor: ModalidadeUrbana; rotulo: string }[] = [
  { valor: "loteamento_aberto", rotulo: "Loteamento aberto" },
  { valor: "loteamento_fechado", rotulo: "Loteamento fechado" },
  { valor: "condominio_lotes", rotulo: "Condomínio de lotes" },
  { valor: "condominio_edilicio", rotulo: "Condomínio edilício" },
  { valor: "desmembramento", rotulo: "Desmembramento" },
];

// Formatação de exibição (não é cálculo): os números vêm prontos do backend.
const m2 = (v: number) =>
  v.toLocaleString("pt-BR", { maximumFractionDigits: 2 }) + " m²";
const ha = (v: number) =>
  (v / 10_000).toLocaleString("pt-BR", { maximumFractionDigits: 2 }) + " ha";
const pct = (v: number) =>
  (v * 100).toLocaleString("pt-BR", { maximumFractionDigits: 1 }) + "%";

export function CardAproveitamento({ analiseId }: { analiseId: string }) {
  const [regime, setRegime] = useState<Regime>("URBANO");
  const [modalidade, setModalidade] =
    useState<ModalidadeUrbana>("loteamento_aberto");
  const [loteMin, setLoteMin] = useState(200);
  const [fmp, setFmp] = useState(20000);

  const [res, setRes] = useState<Aproveitamento | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(false);

  async function calcular() {
    setCarregando(true);
    setErro(null);
    try {
      const r =
        regime === "RURAL"
          ? await calcularRural(analiseId, fmp)
          : await calcularUrbano(analiseId, loteMin, modalidade);
      setRes(r);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Falha ao calcular.");
    } finally {
      setCarregando(false);
    }
  }

  const d = res?.descontos ?? null;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Aproveitamento</CardTitle>
        <CardDescription>
          Triagem: área aproveitável = área total − (mata ∪ APP ∪ faixas
          não-edificáveis). Vias e doação NÃO entram aqui — dependem do projeto
          urbanístico e da diretriz municipal. Cálculo no backend, com proveniência.
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
                setRes(null);
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
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <label className="flex flex-col gap-1 text-xs text-slate-600">
                Modalidade (rótulo)
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
              <Campo label="Lote mín. (m²)" value={loteMin} onChange={setLoteMin} />
            </div>
            <p className="rounded-lg bg-amber-50 p-3 text-xs text-amber-900">
              <span className="font-medium">Lote mínimo provisório.</span> Declarado
              por você (pendente extração da LUOS, Fase 1.8). O nº de lotes é um{" "}
              <span className="font-medium">teto</span> — vias e doação reduzem isso
              no projeto urbanístico e dependem da diretriz municipal.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <Campo
              label="FMP do município (m²)"
              value={fmp}
              step={1000}
              onChange={setFmp}
            />
            <p className="col-span-2 self-end text-xs text-slate-500">
              Fração Mínima de Parcelamento (FMP por município, INCRA). 20.000 m² = 2
              ha. Puxada da tabela quando disponível; na ausência aplica-se o piso de
              2 ha (confirmar no CCIR); editável aqui.
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

        {res?.premissa && (
          <p className="rounded-lg bg-slate-50 p-3 text-xs text-slate-600">
            <span className="font-medium">Premissa:</span> {res.premissa}
            {res.origem_lote ? (
              <>
                <br />
                <span className="font-medium">Origem do lote:</span>{" "}
                {res.origem_lote}
              </>
            ) : null}
          </p>
        )}

        {/* Descontos (mata ∪ APP ∪ faixas) */}
        {d && (
          <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-xs text-emerald-900">
            <p className="font-medium">
              Descontado da área total: {ha(d.area_restritiva_m2)} (
              {d.percentual_restritivo.toLocaleString("pt-BR")}%) — base aproveitável{" "}
              {ha(d.area_base_m2)} de {ha(d.area_total_m2)}.
            </p>
            <ul className="mt-1 list-inside list-disc">
              {d.itens.map((i) => (
                <li key={i.tipo}>
                  {i.rotulo}: {ha(i.area_m2)}
                </li>
              ))}
            </ul>
            {d.sobreposicao_m2 > 0 && (
              <p className="mt-1">
                (sobreposição entre faixas contada uma vez só:{" "}
                {ha(d.sobreposicao_m2)})
              </p>
            )}
            <p className="mt-1 text-emerald-700">{d.proveniencia}</p>
          </div>
        )}

        {erro && (
          <p className="rounded-lg bg-rose-50 p-3 text-sm text-rose-800">{erro}</p>
        )}

        {/* Resultado URBANO */}
        {res?.regime === "URBANO" && res.area_aproveitavel_m2 != null && (
          <>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <Metrica
                titulo="Área aproveitável"
                valor={ha(res.area_aproveitavel_m2)}
                sub={
                  res.pct_sobre_total != null
                    ? `${pct(res.pct_sobre_total)} da gleba`
                    : undefined
                }
                destaque
              />
              <Metrica titulo="Lote mínimo" valor={m2(res.lote_min_m2 ?? 0)} />
              <Metrica
                titulo="Lotes (teto)"
                valor={String(res.n_lotes_teto ?? 0)}
                sub="máximo, antes de vias/doação"
              />
            </div>
            {res.ressalva_urbano && (
              <p className="rounded-lg bg-slate-50 p-3 text-xs text-slate-500">
                {res.ressalva_urbano}
              </p>
            )}
          </>
        )}

        {/* Resultado RURAL */}
        {res?.regime === "RURAL" && res.rural && (
          <>
            <Table>
              <THead>
                <TR>
                  <TH>Regime rural</TH>
                  <TH>Área aproveitável</TH>
                  <TH>FMP</TH>
                  <TH>Origem da FMP</TH>
                  <TH>Parcelas</TH>
                </TR>
              </THead>
              <TBody>
                <TR>
                  <TD className="font-medium">Parcelamento rural</TD>
                  <TD>
                    {ha(res.rural.area_m2)}
                    {res.pct_sobre_total != null
                      ? ` (${pct(res.pct_sobre_total)} da gleba)`
                      : ""}
                  </TD>
                  <TD>{ha(res.rural.fmp_m2)}</TD>
                  <TD className="text-xs text-slate-500">{res.rural.fmp_origem}</TD>
                  <TD className="font-semibold">{res.rural.n_parcelas}</TD>
                </TR>
              </TBody>
            </Table>
            <p className="rounded-lg bg-amber-50 p-3 text-xs text-amber-900">
              {res.rural.flag_conversao}
            </p>
          </>
        )}
      </CardContent>
    </Card>
  );
}

function Metrica({
  titulo,
  valor,
  sub,
  destaque,
}: {
  titulo: string;
  valor: string;
  sub?: string;
  destaque?: boolean;
}) {
  return (
    <div
      className={`rounded-lg border p-3 ${
        destaque ? "border-emerald-200 bg-emerald-50" : "border-slate-200 bg-slate-50"
      }`}
    >
      <p className="text-xs text-slate-500">{titulo}</p>
      <p className="text-base font-semibold text-slate-900">{valor}</p>
      {sub && <p className="text-xs text-slate-500">{sub}</p>}
    </div>
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
