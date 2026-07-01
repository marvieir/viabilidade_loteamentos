"use client";

import { useEffect, useState } from "react";
import { StatusChip } from "@/components/ui/status";
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
  type PerfilMunicipal,
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

const LOTE_MIN_DEFAULT = 200;

// Lote mínimo LEGAL efetivo de (zona, modalidade) num perfil CONFIRMADO. Espelha o
// backend (core/aproveitamento._param_zona): override da modalidade quando houver, senão
// o da zona. Não é cálculo — só seleciona qual número confirmado o backend usaria, para
// pré-preencher o formulário. `null` = zona sem lote legal confirmado (não chuta).
function loteMinLegalDaZona(
  perfil: PerfilMunicipal | null | undefined,
  zonaCodigo: string,
  modalidade: ModalidadeUrbana,
): number | null {
  if (!perfil || perfil.status !== "confirmado" || !zonaCodigo) return null;
  const zona = perfil.zonas.find((z) => z.codigo === zonaCodigo);
  if (!zona) return null;
  const ov = zona.modalidades?.[modalidade]?.lote_min_m2;
  if (ov?.valor != null && ov.valor > 0) return ov.valor;
  const p = zona.params?.lote_min_m2;
  if (p?.valor != null && p.valor > 0) return p.valor;
  return null;
}

export function CardAproveitamento({
  analiseId,
  perfil,
  onData,
  sinal,
}: {
  analiseId: string;
  perfil?: PerfilMunicipal | null;
  onData?: (d: Aproveitamento) => void;
  sinal?: number;
}) {
  const [regime, setRegime] = useState<Regime>("URBANO");
  const [modalidade, setModalidade] =
    useState<ModalidadeUrbana>("loteamento_aberto");
  const [loteMin, setLoteMin] = useState(LOTE_MIN_DEFAULT);
  // true quando `loteMin` veio da LUOS confirmada (zona selecionada), não digitado à mão.
  const [loteMinDaLuos, setLoteMinDaLuos] = useState(false);
  const [fmp, setFmp] = useState(20000);
  // Zona declarada (Fase 1.8) — dropdown das zonas do perfil CONFIRMADO. "" = sem cenário.
  const [zona, setZona] = useState("");
  const zonasConfirmadas =
    perfil?.status === "confirmado" ? perfil.zonas : [];

  // Sincroniza o lote mínimo do formulário com a zona/modalidade confirmada da LUOS, para
  // o teto físico do headline usar o lote LEGAL (não o default). O backend continua sendo
  // quem calcula — aqui só escolhemos o número de entrada. Edição manual desliga o vínculo.
  function aplicarLoteDaZona(zonaCodigo: string, mod: ModalidadeUrbana) {
    const legal = loteMinLegalDaZona(perfil, zonaCodigo, mod);
    if (legal != null) {
      setLoteMin(legal);
      setLoteMinDaLuos(true);
    } else {
      setLoteMinDaLuos(false);
    }
  }

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
          : await calcularUrbano(analiseId, loteMin, modalidade, zona || null);
      setRes(r);
      onData?.(r);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Falha ao calcular.");
    } finally {
      setCarregando(false);
    }
  }

  useEffect(() => {
    if (sinal) calcular();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sinal]);

  const d = res?.descontos ?? null;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex flex-wrap items-center gap-2">
          <span>Aproveitamento</span>
          <StatusChip className="ml-auto" estado={res ? "ok" : "pendente"} />
        </CardTitle>
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
                  onChange={(e) => {
                    const m = e.target.value as ModalidadeUrbana;
                    setModalidade(m);
                    if (zona) aplicarLoteDaZona(zona, m);
                  }}
                  className="rounded-lg border border-slate-300 px-2 py-1.5 text-sm text-slate-900"
                >
                  {MODALIDADES.map((m) => (
                    <option key={m.valor} value={m.valor}>
                      {m.rotulo}
                    </option>
                  ))}
                </select>
              </label>
              <Campo
                label="Lote mín. (m²)"
                value={loteMin}
                onChange={(v) => {
                  setLoteMin(v);
                  setLoteMinDaLuos(false); // edição manual rompe o vínculo com a LUOS
                }}
              />
            </div>
            {zonasConfirmadas.length > 0 && (
              <label className="flex flex-col gap-1 text-xs text-slate-600">
                Zona (LUOS confirmada) — liga o cenário com diretriz
                <select
                  value={zona}
                  onChange={(e) => {
                    const z = e.target.value;
                    setZona(z);
                    if (z) aplicarLoteDaZona(z, modalidade);
                    else setLoteMinDaLuos(false);
                  }}
                  className="rounded-lg border border-slate-300 px-2 py-1.5 text-sm text-slate-900"
                >
                  <option value="">— sem diretriz (só teto físico) —</option>
                  {zonasConfirmadas.map((z) => (
                    <option key={z.codigo} value={z.codigo}>
                      {z.codigo}
                      {z.descricao ? ` · ${z.descricao}` : ""}
                    </option>
                  ))}
                </select>
              </label>
            )}
            {loteMinDaLuos ? (
              <p className="rounded-lg bg-emerald-50 p-3 text-xs text-emerald-900">
                <span className="font-medium">Lote mínimo legal.</span> Puxado da LUOS
                confirmada para a zona <span className="font-medium">{zona}</span>{" "}
                (Fase 1.8) — você pode sobrescrever. O nº de lotes é um{" "}
                <span className="font-medium">teto</span>; a doação entra no{" "}
                <span className="font-medium">cenário com diretriz</span> abaixo, não
                neste teto físico.
              </p>
            ) : (
              <p className="rounded-lg bg-amber-50 p-3 text-xs text-amber-900">
                <span className="font-medium">Lote mínimo provisório.</span> Declarado
                por você (selecione a zona da LUOS confirmada para puxar o lote legal). O
                nº de lotes é um <span className="font-medium">teto</span> — vias e
                doação reduzem isso no projeto urbanístico e dependem da diretriz
                municipal.
              </p>
            )}
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

        {/* Resultado URBANO — com zona LUOS confirmada o HEADLINE é o cenário com diretriz
            (lote legal + doação já aplicados); o teto físico cai para linha secundária.
            Sem zona, o headline segue sendo o teto físico. Veto da spec 1.8 (decisão A). */}
        {res?.regime === "URBANO" &&
          res.area_aproveitavel_m2 != null &&
          (res.cenario_diretriz ? (
            <>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                <Metrica
                  titulo="Área aproveitável (com diretriz)"
                  valor={ha(res.cenario_diretriz.area_aproveitavel_m2)}
                  sub={
                    res.cenario_diretriz.pct_sobre_total != null
                      ? `${pct(res.cenario_diretriz.pct_sobre_total)} da gleba · doação descontada`
                      : "doação descontada"
                  }
                  destaque
                />
                <Metrica
                  titulo="Lote mínimo legal"
                  valor={m2(res.cenario_diretriz.lote_min_m2_legal)}
                  sub={`zona ${res.cenario_diretriz.zona}`}
                />
                <Metrica
                  titulo="Lotes"
                  valor={String(res.cenario_diretriz.n_lotes)}
                  sub="lote legal + doação aplicados"
                />
              </div>
              <div className="rounded-lg border border-indigo-200 bg-indigo-50 p-3">
                <p className="text-xs text-indigo-800">
                  Lote legal {m2(res.cenario_diretriz.lote_min_m2_legal)} · doação{" "}
                  {pct(res.cenario_diretriz.doacao_pct)} (base{" "}
                  {res.cenario_diretriz.doacao_base}) ={" "}
                  {ha(res.cenario_diretriz.doacao_m2)} descontados.
                </p>
                <p className="mt-1 text-xs text-indigo-700">
                  {res.cenario_diretriz.proveniencia}
                </p>
                <p className="mt-1 text-xs text-indigo-600">
                  {res.cenario_diretriz.ressalva}
                </p>
              </div>
              {/* Teto físico — agora secundário (sem doação, lote declarado) */}
              <p className="rounded-lg bg-slate-50 p-3 text-xs text-slate-500">
                <span className="font-medium">Teto físico (sem doação):</span>{" "}
                {res.n_lotes_teto ?? 0} lotes em {ha(res.area_aproveitavel_m2)} com lote{" "}
                {m2(res.lote_min_m2 ?? 0)}. {res.ressalva_urbano}
              </p>
            </>
          ) : (
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
          ))}

        {/* Fase 9.10 — PONTE de reconciliação: rotula o teto e cita o estudo de massa (texto
            interpolado pelo backend; o front só renderiza). Mata a estranheza do 120 vs 51. */}
        {res?.regime === "URBANO" && res.reconciliacao && (
          <div className="rounded-lg border border-amber-200 bg-amber-50 p-3">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-amber-700">
              Teto teórico × estudo de massa
            </p>
            <p className="mt-1 text-xs text-amber-900">{res.reconciliacao.leitura}</p>
            {res.reconciliacao.ref_estudo_massa && (
              <p className="mt-1 text-[11px] text-amber-700">
                Faixa honesta: ~{res.reconciliacao.lotes_teto} (teto legal) → ~
                {res.reconciliacao.ref_estudo_massa.lotes} (estudo realista).
              </p>
            )}
          </div>
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

        {/* Cenário diretriz (Fase 1.8): com zona confirmada ele vira o HEADLINE acima.
            Aqui fica só o aviso quando NÃO deu para computá-lo (zona sem lote legal etc.). */}
        {res?.aviso_diretriz && !res.cenario_diretriz && (
          <p className="rounded-lg bg-slate-50 p-3 text-xs text-slate-500">
            {res.aviso_diretriz}
          </p>
        )}

        {/* Cenário otimista (Fase 2.3) — hipotético, claramente separado do headline */}
        {res?.cenario_otimista && (
          <div className="rounded-lg border border-dashed border-yellow-300 bg-yellow-50 p-3">
            <p className="text-sm font-medium text-yellow-900">
              Cenário otimista (hipotético) ·{" "}
              {ha(res.cenario_otimista.area_aproveitavel_m2)} (
              {pct(res.cenario_otimista.pct_sobre_total)} da gleba)
              {res.cenario_otimista.n_lotes_teto != null
                ? ` · até ${res.cenario_otimista.n_lotes_teto} lotes`
                : ""}
            </p>
            <p className="mt-1 text-xs text-yellow-800">
              {res.cenario_otimista.premissa}.
            </p>
            <p className="mt-1 text-xs text-yellow-700">
              {res.cenario_otimista.ressalva}
            </p>
          </div>
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
