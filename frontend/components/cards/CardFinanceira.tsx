"use client";

import { useEffect, useState } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  calcularFinanceira,
  type Aproveitamento,
  type Financeira,
} from "@/lib/api";

// Premissas do formulário. TODOS os percentuais em % (100 = 100%) — escala única, sem o
// par traiçoeiro 0–1 (correção 4.1); o envio converte para fração. Nenhuma conta de
// resultado aqui: o backend calcula e formata (§2).
type LinhaMesa = { participacao: number; prazo_meses: number; taxa_am: number }; // % / meses / % a.m.

type Form = {
  preco_lote: number;
  eficiencia_pct: number; // % — 100 = sem perda
  inicio_mes: number;
  duracao_meses: number;
  modo: "avista" | "parcelado" | "financiado";
  entrada_pct: number; // %
  n_parcelas: number;
  permuta_modo: "permuta_vgv" | "permuta_lotes" | "compra" | "nenhuma";
  permuta_pct: number; // %
  permuta_n: number;
  compra_valor: number;
  urb_valor: number;
  urb_inicio: number;
  urb_duracao: number;
  projetos: number;
  topografia: number;
  admin_mensal: number;
  marketing_pct: number; // %
  marketing_inicio: number;
  marketing_duracao: number;
  comissao_pct: number; // %
  aliquota_pct: number; // %
  inadimplencia_pct: number; // % — 0 = ninguém deixa de pagar
};

const PADRAO: Form = {
  preco_lote: 100000, eficiencia_pct: 100, inicio_mes: 1, duracao_meses: 10,
  modo: "avista", entrada_pct: 15, n_parcelas: 36,
  permuta_modo: "permuta_vgv", permuta_pct: 20, permuta_n: 0, compra_valor: 0,
  urb_valor: 30000, urb_inicio: 1, urb_duracao: 6,
  projetos: 280000, topografia: 100000, admin_mensal: 10000,
  marketing_pct: 2, marketing_inicio: 1, marketing_duracao: 4,
  comissao_pct: 5, aliquota_pct: 5.93, inadimplencia_pct: 0,
};

// Mesa default (referência TIV 5.0 — rotulada também no backend).
const MESA_PADRAO: LinhaMesa[] = [
  { participacao: 5, prazo_meses: 12, taxa_am: 0 },
  { participacao: 20, prazo_meses: 30, taxa_am: 0.5 },
  { participacao: 40, prazo_meses: 60, taxa_am: 1 },
  { participacao: 35, prazo_meses: 120, taxa_am: 1 },
];

export function CardFinanceira({
  analiseId,
  aprov,
  onData,
  sinal,
}: {
  analiseId: string;
  aprov?: Aproveitamento | null;
  onData?: (d: Financeira) => void;
  sinal?: number;
}) {
  const [f, setF] = useState<Form>(PADRAO);
  const [mesa, setMesa] = useState<LinhaMesa[]>(MESA_PADRAO);
  const [confirmarInad, setConfirmarInad] = useState(false);
  const [data, setData] = useState<Financeira | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(false);

  const nDiretriz = aprov?.cenario_diretriz?.n_lotes ?? null;
  const nTeto = aprov?.n_lotes_teto ?? null;
  const temContexto = nDiretriz != null || nTeto != null;
  const inadAlta = f.inadimplencia_pct > 30;

  function set<K extends keyof Form>(k: K, v: Form[K]) {
    setF((s) => ({ ...s, [k]: v }));
  }
  function setMesaLinha(i: number, p: Partial<LinhaMesa>) {
    setMesa((m) => m.map((l, k) => (k === i ? { ...l, ...p } : l)));
  }

  async function calcular() {
    setCarregando(true);
    setErro(null);
    try {
      const vendas: Record<string, unknown> = {
        inicio_mes: f.inicio_mes, duracao_meses: f.duracao_meses, curva: "linear",
        modo: f.modo,
      };
      if (f.modo === "parcelado") {
        vendas.entrada_pct = f.entrada_pct / 100;
        vendas.n_parcelas = f.n_parcelas;
      }
      if (f.modo === "financiado") {
        vendas.entrada_pct = f.entrada_pct / 100;
        vendas.mesa = mesa.map((l) => ({
          participacao: l.participacao / 100,
          prazo_meses: l.prazo_meses,
          taxa_am: l.taxa_am / 100,
        }));
      }
      const premissas = {
        lotes: { origem: "auto" as const, n_diretriz: nDiretriz, n_teto: nTeto },
        eficiencia_projeto_pct: f.eficiencia_pct / 100,
        preco_lote: f.preco_lote,
        area_aproveitavel_m2: aprov?.area_aproveitavel_m2 ?? null,
        inadimplencia_pct: f.inadimplencia_pct / 100,
        confirmar_inadimplencia_alta: confirmarInad,
        vendas,
        aquisicao:
          f.permuta_modo === "permuta_vgv"
            ? { modo: "permuta_vgv", pct: f.permuta_pct / 100 }
            : f.permuta_modo === "permuta_lotes"
              ? { modo: "permuta_lotes", n: f.permuta_n }
              : f.permuta_modo === "compra"
                ? { modo: "compra", valor: f.compra_valor, condicao: "avista", inicio_mes: 0 }
                : { modo: "nenhuma" },
        custos: {
          urbanizacao: { base: "por_lote", valor: f.urb_valor, inicio_mes: f.urb_inicio, duracao_meses: f.urb_duracao },
          projetos_aprovacao: { valor: f.projetos, mes: 0 },
          topografia: { valor: f.topografia, mes: 0 },
          administracao_mensal: f.admin_mensal,
          marketing: { pct_vgv_proprio: f.marketing_pct / 100, inicio_mes: f.marketing_inicio, duracao_meses: f.marketing_duracao },
          comissao_pct: f.comissao_pct / 100,
        },
        tributos: { regime: "presumido", aliquota_pct: f.aliquota_pct / 100 },
      };
      const r = await calcularFinanceira(analiseId, premissas);
      setData(r);
      onData?.(r);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Falha ao calcular.");
    } finally {
      setCarregando(false);
    }
  }

  useEffect(() => {
    if (sinal && temContexto) calcular();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sinal]);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Financeira — fluxo de caixa</CardTitle>
        <CardDescription>
          Monta o fluxo de caixa mensal a partir dos lotes do motor e das premissas que você
          declara. No modo <strong>financiado</strong> (PRICE), o fluxo de vendas é separado
          do recebimento e os juros viram receita financeira. Valores nominais — VPL/TIR são
          a dimensão Econômica. Tributação é parâmetro (não é RET); confirme com contador.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {!temContexto && (
          <p className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
            Rode o <strong>Aproveitamento</strong> primeiro — daí saem os lotes do caso-base
            (cenário diretriz, ou teto físico com aviso de superestimação).
          </p>
        )}

        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          <Campo rotulo="Preço do lote (R$)" valor={f.preco_lote} on={(v) => set("preco_lote", v)} />
          <Campo rotulo="Eficiência do projeto (%) — 100 = sem perda" valor={f.eficiencia_pct} on={(v) => set("eficiencia_pct", v)} />
          <Campo rotulo="Vendas: início (mês)" valor={f.inicio_mes} on={(v) => set("inicio_mes", v)} />
          <Campo rotulo="Vendas: duração (meses)" valor={f.duracao_meses} on={(v) => set("duracao_meses", v)} />
          <div>
            <p className="text-[11px] text-slate-500">Modo de venda</p>
            <select
              value={f.modo}
              onChange={(e) => set("modo", e.target.value as Form["modo"])}
              className="w-full rounded-lg border border-slate-200 px-2 py-2 text-sm"
            >
              <option value="financiado">financiado (PRICE) — padrão de loteamento</option>
              <option value="avista">à vista</option>
              <option value="parcelado">parcelado sem juros</option>
            </select>
          </div>
          {(f.modo === "parcelado" || f.modo === "financiado") && (
            <Campo rotulo="Entrada (%)" valor={f.entrada_pct} on={(v) => set("entrada_pct", v)} />
          )}
          {f.modo === "parcelado" && (
            <Campo rotulo="Nº parcelas" valor={f.n_parcelas} on={(v) => set("n_parcelas", v)} />
          )}
        </div>

        {f.modo === "financiado" && (
          <div className="rounded-lg border border-indigo-200 bg-indigo-50/40 p-3">
            <p className="text-sm font-medium text-slate-700">Mesa de vendas (PRICE)</p>
            <p className="mb-2 text-[11px] text-slate-500">
              Como as vendas se repartem por prazo de financiamento. As participações devem
              somar 100%. Default: estrutura típica (referência TIV 5.0) — calibre com sua
              corretora.
            </p>
            <div className="space-y-1.5">
              {mesa.map((l, i) => (
                <div key={i} className="flex flex-wrap items-center gap-2 text-xs">
                  <input type="number" value={l.participacao} onChange={(e) => setMesaLinha(i, { participacao: parseFloat(e.target.value) || 0 })} className="w-20 rounded border border-slate-200 px-2 py-1.5" />
                  <span className="text-slate-500">% das vendas em</span>
                  <input type="number" value={l.prazo_meses} onChange={(e) => setMesaLinha(i, { prazo_meses: parseInt(e.target.value) || 1 })} className="w-20 rounded border border-slate-200 px-2 py-1.5" />
                  <span className="text-slate-500">meses a</span>
                  <input type="number" step={0.1} value={l.taxa_am} onChange={(e) => setMesaLinha(i, { taxa_am: parseFloat(e.target.value) || 0 })} className="w-20 rounded border border-slate-200 px-2 py-1.5" />
                  <span className="text-slate-500">% a.m.</span>
                  <button onClick={() => setMesa((m) => m.filter((_, k) => k !== i))} className="text-slate-400 hover:text-rose-600" title="remover">✕</button>
                </div>
              ))}
            </div>
            <div className="mt-2 flex items-center gap-3 text-xs">
              <button
                onClick={() => setMesa((m) => [...m, { participacao: 0, prazo_meses: 60, taxa_am: 1 }])}
                className="font-medium text-indigo-700 hover:text-indigo-900"
              >
                + perfil
              </button>
              <span className={mesa.reduce((s, l) => s + l.participacao, 0) === 100 ? "text-emerald-700" : "text-rose-600"}>
                soma: {mesa.reduce((s, l) => s + l.participacao, 0)}%
              </span>
              <span className="text-slate-400">comissão incide sobre o recebimento (carteira)</span>
            </div>
          </div>
        )}

        <details className="rounded-lg border border-slate-200 p-3">
          <summary className="cursor-pointer text-sm font-medium text-slate-700">
            Aquisição da gleba & custos & tributo
          </summary>
          <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3">
            <div>
              <p className="text-[11px] text-slate-500">Aquisição</p>
              <select
                value={f.permuta_modo}
                onChange={(e) => set("permuta_modo", e.target.value as Form["permuta_modo"])}
                className="w-full rounded-lg border border-slate-200 px-2 py-2 text-sm"
              >
                <option value="permuta_vgv">permuta % VGV</option>
                <option value="permuta_lotes">permuta em lotes</option>
                <option value="compra">compra</option>
                <option value="nenhuma">nenhuma</option>
              </select>
            </div>
            {f.permuta_modo === "permuta_vgv" && (
              <Campo rotulo="Permuta (% do VGV)" valor={f.permuta_pct} on={(v) => set("permuta_pct", v)} />
            )}
            {f.permuta_modo === "permuta_lotes" && (
              <Campo rotulo="Permuta (nº lotes)" valor={f.permuta_n} on={(v) => set("permuta_n", v)} />
            )}
            {f.permuta_modo === "compra" && (
              <Campo rotulo="Compra (R$)" valor={f.compra_valor} on={(v) => set("compra_valor", v)} />
            )}
            <Campo rotulo="Urbanização (R$/lote)" valor={f.urb_valor} on={(v) => set("urb_valor", v)} />
            <Campo rotulo="Urb.: início (mês)" valor={f.urb_inicio} on={(v) => set("urb_inicio", v)} />
            <Campo rotulo="Urb.: duração (meses)" valor={f.urb_duracao} on={(v) => set("urb_duracao", v)} />
            <Campo rotulo="Projetos+aprovação (R$)" valor={f.projetos} on={(v) => set("projetos", v)} />
            <Campo rotulo="Topografia (R$)" valor={f.topografia} on={(v) => set("topografia", v)} />
            <Campo rotulo="Administração (R$/mês)" valor={f.admin_mensal} on={(v) => set("admin_mensal", v)} />
            <Campo rotulo="Marketing (% do VGV próprio)" valor={f.marketing_pct} on={(v) => set("marketing_pct", v)} />
            <Campo rotulo="Comissão (%)" valor={f.comissao_pct} on={(v) => set("comissao_pct", v)} />
            <Campo rotulo="Tributo (% s/ receita recebida)" valor={f.aliquota_pct} on={(v) => set("aliquota_pct", v)} />
            <Campo rotulo="Inadimplência (%) — 0 = ninguém deixa de pagar" valor={f.inadimplencia_pct} on={(v) => set("inadimplencia_pct", v)} />
          </div>
          {inadAlta && (
            <label className="mt-3 flex items-start gap-2 rounded-lg border border-rose-200 bg-rose-50 p-3 text-xs text-rose-900">
              <input
                type="checkbox"
                checked={confirmarInad}
                onChange={(e) => setConfirmarInad(e.target.checked)}
                className="mt-0.5 accent-rose-600"
              />
              <span>
                Inadimplência de <strong>{f.inadimplencia_pct}%</strong> derruba as receitas
                drasticamente. Confirmo que é intencional.
              </span>
            </label>
          )}
          <p className="mt-2 text-[11px] text-amber-700">
            Tributo default 5,93% = Lucro Presumido efetivo (PIS+COFINS+IRPJ+CSLL) — NÃO é RET;
            confirme com contador. Eficiência &lt; 100% é regra de mercado sem âncora legal.
          </p>
        </details>

        <Button onClick={calcular} disabled={carregando || !temContexto}>
          {carregando ? "Calculando…" : "Calcular fluxo"}
        </Button>

        {erro && (
          <p className="rounded-lg bg-rose-50 p-3 text-sm text-rose-800">{erro}</p>
        )}

        {data && <Resultado d={data} />}
      </CardContent>
    </Card>
  );
}

function Campo({
  rotulo, valor, on, step,
}: {
  rotulo: string;
  valor: number;
  on: (v: number) => void;
  step?: number;
}) {
  return (
    <div>
      <p className="text-[11px] text-slate-500">{rotulo}</p>
      <input
        type="number"
        step={step ?? "any"}
        value={valor}
        onChange={(e) => on(parseFloat(e.target.value) || 0)}
        className="w-full rounded-lg border border-slate-200 px-2 py-2 text-sm"
      />
    </div>
  );
}

function Resultado({ d }: { d: Financeira }) {
  const ind = d.indicadores;
  const lucro = ind.resultado_nominal >= 0;
  const financiado = d.vgv.receita_financeira > 0;
  const mensalLongo = ind.horizonte_meses > 12;
  return (
    <div className="space-y-3">
      {d.alerta_critico && (
        <p className="rounded-lg border-2 border-rose-400 bg-rose-100 p-3 text-sm font-semibold text-rose-900">
          ⛔ {d.alerta_critico}
        </p>
      )}
      {d.caso_base.aviso_lotes && (
        <p className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
          {d.caso_base.aviso_lotes}
        </p>
      )}

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {financiado ? (
          <Kpi
            rotulo="VGV geral (nominal + financeira)"
            valor={d.vgv.geral_fmt}
            tom="emerald"
            sub={`nominal ${d.vgv.bruto_fmt} + juros ${d.vgv.receita_financeira_fmt}`}
          />
        ) : (
          <Kpi
            rotulo="VGV próprio"
            valor={d.vgv.proprio_fmt}
            sub={`${d.caso_base.lotes_vendaveis} lotes · origem ${d.caso_base.origem_lotes}`}
          />
        )}
        <Kpi rotulo="Resultado nominal" valor={ind.resultado_nominal_fmt} tom={lucro ? "emerald" : "rose"} sub={`margem ${(ind.margem_sobre_vgv_proprio * 100).toLocaleString("pt-BR", { maximumFractionDigits: 2 })}%`} />
        <Kpi rotulo="Exposição máx. de caixa" valor={ind.exposicao_maxima.valor_fmt} tom="rose" sub={`no mês ${ind.exposicao_maxima.mes}`} />
        <Kpi rotulo="Horizonte" valor={`${ind.horizonte_meses} meses`} sub={financiado ? `${d.caso_base.lotes_vendaveis} lotes · origem ${d.caso_base.origem_lotes}` : `VGV bruto ${d.vgv.bruto_fmt}`} />
      </div>

      {/* Fluxo: resumo ANUAL por default em horizontes longos; mensal sob expand (4.1). */}
      {mensalLongo ? (
        <>
          <TabelaAnual linhas={d.fluxo_resumo_anual} />
          <details className="rounded-xl border border-slate-200 p-3">
            <summary className="cursor-pointer text-sm font-medium text-slate-700">
              Fluxo mensal completo ({d.fluxo.length} meses)
            </summary>
            <div className="mt-2">
              <TabelaMensal linhas={d.fluxo} />
            </div>
          </details>
        </>
      ) : (
        <TabelaMensal linhas={d.fluxo} />
      )}

      <details className="rounded-lg border border-slate-200 p-3">
        <summary className="cursor-pointer text-sm font-medium text-slate-700">
          Blocos de custo & proveniência
        </summary>
        <ul className="mt-2 space-y-1 text-xs">
          {d.blocos.map((b) => (
            <li key={b.bloco} className="flex flex-wrap justify-between gap-2">
              <span className="font-medium text-slate-700">{b.bloco}</span>
              <span className="text-slate-600">{b.total_fmt}</span>
              <span className="w-full text-slate-400">{b.proveniencia}</span>
            </li>
          ))}
        </ul>
      </details>

      <div className="rounded-lg bg-amber-50 p-3 text-xs text-amber-900">
        {d.avisos.map((a) => (
          <p key={a}>• {a}</p>
        ))}
      </div>
    </div>
  );
}

function TabelaMensal({ linhas }: { linhas: Financeira["fluxo"] }) {
  return (
    <div className="overflow-x-auto rounded-xl border border-slate-200">
      <table className="w-full text-right text-xs">
        <thead className="bg-slate-50 text-slate-500">
          <tr>
            <th className="px-3 py-2 text-left">Mês</th>
            <th className="px-3 py-2">Entradas</th>
            <th className="px-3 py-2">Saídas</th>
            <th className="px-3 py-2">Líquido</th>
            <th className="px-3 py-2">Acumulado</th>
          </tr>
        </thead>
        <tbody>
          {linhas.map((l) => (
            <tr key={l.mes} className="border-t border-slate-100">
              <td className="px-3 py-1.5 text-left font-medium text-slate-700">{l.mes}</td>
              <td className="px-3 py-1.5 text-slate-600">{l.entradas_fmt}</td>
              <td className="px-3 py-1.5 text-slate-600">{l.saidas_fmt}</td>
              <td className={`px-3 py-1.5 ${l.liquido >= 0 ? "text-emerald-700" : "text-rose-700"}`}>{l.liquido_fmt}</td>
              <td className={`px-3 py-1.5 font-medium ${l.acumulado >= 0 ? "text-slate-800" : "text-rose-700"}`}>{l.acumulado_fmt}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function TabelaAnual({ linhas }: { linhas: Financeira["fluxo_resumo_anual"] }) {
  return (
    <div className="overflow-x-auto rounded-xl border border-slate-200">
      <table className="w-full text-right text-xs">
        <thead className="bg-slate-50 text-slate-500">
          <tr>
            <th className="px-3 py-2 text-left">Ano</th>
            <th className="px-3 py-2">Entradas</th>
            <th className="px-3 py-2">Saídas</th>
            <th className="px-3 py-2">Líquido</th>
            <th className="px-3 py-2">Acumulado</th>
          </tr>
        </thead>
        <tbody>
          {linhas.map((l) => (
            <tr key={l.ano} className="border-t border-slate-100">
              <td className="px-3 py-1.5 text-left font-medium text-slate-700">{l.ano}</td>
              <td className="px-3 py-1.5 text-slate-600">{l.entradas_fmt}</td>
              <td className="px-3 py-1.5 text-slate-600">{l.saidas_fmt}</td>
              <td className={`px-3 py-1.5 ${l.liquido >= 0 ? "text-emerald-700" : "text-rose-700"}`}>{l.liquido_fmt}</td>
              <td className={`px-3 py-1.5 font-medium ${l.acumulado >= 0 ? "text-slate-800" : "text-rose-700"}`}>{l.acumulado_fmt}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const TOM: Record<string, string> = {
  slate: "border-slate-200 bg-white text-slate-900",
  emerald: "border-emerald-200 bg-emerald-50 text-emerald-900",
  rose: "border-rose-200 bg-rose-50 text-rose-900",
};

function Kpi({
  rotulo, valor, sub, tom = "slate",
}: {
  rotulo: string;
  valor: string;
  sub?: string;
  tom?: "slate" | "emerald" | "rose";
}) {
  return (
    <div className={`rounded-xl border p-3 shadow-sm ${TOM[tom]}`}>
      <p className="text-[11px] opacity-70">{rotulo}</p>
      <p className="mt-0.5 text-lg font-bold tracking-tight">{valor}</p>
      {sub && <p className="text-[11px] opacity-70">{sub}</p>}
    </div>
  );
}
