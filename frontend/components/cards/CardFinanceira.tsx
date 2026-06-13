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
  type Economica,
  type Financeira,
} from "@/lib/api";
import { comporLeituras } from "@/lib/compor";

/* Wizard de 6 passos (Fase 4.2). O ESTADO mora no front; o número de cada passo vem do
   backend (POST a cada avanço) — nada é calculado aqui (§2). Microcopy em todo campo. */

type LinhaMesa = { participacao: number; prazo_meses: number; taxa_am: number };

type Form = {
  precoModo: "m2" | "lote";
  preco_m2: number;
  area_lote_m2: number;
  preco_lote: number;
  override_lotes: boolean;
  lotes_n: number;
  // parceria
  aq_modo: "permuta_vgv" | "permuta_lotes" | "compra";
  terrenista_pct: number; // %
  permuta_n: number;
  compra_valor: number;
  // venda
  inicio_mes: number;
  duracao_meses: number;
  modo: "financiado" | "avista" | "parcelado";
  entrada_pct: number; // %
  n_parcelas: number;
  // custos
  urb_valor: number;
  urb_inicio: number;
  urb_duracao: number;
  projetos: number;
  topografia: number;
  admin_mensal: number;
  marketing_pct: number; // %
  comissao_pct: number; // %
  // tributos
  aliquota_pct: number; // %
  inadimplencia_pct: number; // %
  margem_referencia_pct: number; // %
  capital_disponivel: number; // 0 = não informado
};

const PADRAO: Form = {
  precoModo: "lote", preco_m2: 350, area_lote_m2: 263.21, preco_lote: 100000,
  override_lotes: false, lotes_n: 0,
  aq_modo: "permuta_vgv", terrenista_pct: 20, permuta_n: 0, compra_valor: 0,
  inicio_mes: 1, duracao_meses: 10, modo: "financiado", entrada_pct: 15, n_parcelas: 36,
  urb_valor: 30000, urb_inicio: 1, urb_duracao: 6, projetos: 280000, topografia: 100000,
  admin_mensal: 10000, marketing_pct: 2, comissao_pct: 5,
  aliquota_pct: 5.93, inadimplencia_pct: 0, margem_referencia_pct: 20, capital_disponivel: 0,
};

const MESA_PADRAO: LinhaMesa[] = [
  { participacao: 5, prazo_meses: 12, taxa_am: 0 },
  { participacao: 20, prazo_meses: 30, taxa_am: 0.5 },
  { participacao: 40, prazo_meses: 60, taxa_am: 1 },
  { participacao: 35, prazo_meses: 120, taxa_am: 1 },
];

const PASSOS = ["Lotes & Preço", "Parceria", "Venda", "Custos", "Tributos", "Resultado"];

export function CardFinanceira({
  analiseId, aprov, onData, sinal, econ,
}: {
  analiseId: string;
  aprov?: Aproveitamento | null;
  onData?: (d: Financeira) => void;
  sinal?: number;
  econ?: Economica | null; // Fase 5: preenche os slots vpl/tir/payback do semáforo
}) {
  const [f, setF] = useState<Form>(PADRAO);
  const [mesa, setMesa] = useState<LinhaMesa[]>(MESA_PADRAO);
  const [confirmarInad, setConfirmarInad] = useState(false);
  const [passo, setPasso] = useState(1);
  const [prev, setPrev] = useState<Financeira | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(false);

  const nDiretriz = aprov?.cenario_diretriz?.n_lotes ?? null;
  const nTeto = aprov?.n_lotes_teto ?? null;
  const temContexto = nDiretriz != null || nTeto != null;
  const inadAlta = f.inadimplencia_pct > 30;

  function set<K extends keyof Form>(k: K, v: Form[K]) { setF((s) => ({ ...s, [k]: v })); }
  function setMesaLinha(i: number, p: Partial<LinhaMesa>) {
    setMesa((m) => m.map((l, k) => (k === i ? { ...l, ...p } : l)));
  }

  function premissas() {
    const vendas: Record<string, unknown> = {
      inicio_mes: f.inicio_mes, duracao_meses: f.duracao_meses, curva: "linear", modo: f.modo,
    };
    if (f.modo === "parcelado") { vendas.entrada_pct = f.entrada_pct / 100; vendas.n_parcelas = f.n_parcelas; }
    if (f.modo === "financiado") {
      vendas.entrada_pct = f.entrada_pct / 100;
      vendas.mesa = mesa.map((l) => ({ participacao: l.participacao / 100, prazo_meses: l.prazo_meses, taxa_am: l.taxa_am / 100 }));
    }
    return {
      lotes: f.override_lotes
        ? { origem: "declarado" as const, n: f.lotes_n }
        : { origem: "auto" as const, n_diretriz: nDiretriz, n_teto: nTeto },
      eficiencia_projeto_pct: 1,
      ...(f.precoModo === "lote"
        ? { preco_lote: f.preco_lote }
        : { preco_m2: f.preco_m2, area_lote_m2: f.area_lote_m2 }),
      area_aproveitavel_m2: aprov?.area_aproveitavel_m2 ?? null,
      inadimplencia_pct: f.inadimplencia_pct / 100,
      confirmar_inadimplencia_alta: confirmarInad,
      margem_referencia_pct: f.margem_referencia_pct / 100,
      ...(f.capital_disponivel > 0 ? { capital_disponivel: f.capital_disponivel } : {}),
      vendas,
      aquisicao:
        f.aq_modo === "permuta_vgv" ? { modo: "permuta_vgv", pct: f.terrenista_pct / 100 }
        : f.aq_modo === "permuta_lotes" ? { modo: "permuta_lotes", n: f.permuta_n }
        : { modo: "compra", valor: f.compra_valor, condicao: "avista", inicio_mes: 0 },
      custos: {
        urbanizacao: { base: "por_lote", valor: f.urb_valor, inicio_mes: f.urb_inicio, duracao_meses: f.urb_duracao },
        projetos_aprovacao: { valor: f.projetos, mes: 0 },
        topografia: { valor: f.topografia, mes: 0 },
        administracao_mensal: f.admin_mensal,
        marketing: { pct_vgv_proprio: f.marketing_pct / 100, inicio_mes: f.inicio_mes, duracao_meses: Math.max(1, Math.round(f.duracao_meses / 2)) },
        comissao_pct: f.comissao_pct / 100,
      },
      tributos: { regime: "presumido", aliquota_pct: f.aliquota_pct / 100 },
    };
  }

  async function recalc(): Promise<Financeira | null> {
    setCarregando(true); setErro(null);
    try {
      const r = await calcularFinanceira(analiseId, premissas());
      setPrev(r); onData?.(r); return r;
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Falha ao calcular."); return null;
    } finally { setCarregando(false); }
  }

  async function avancar() {
    const r = await recalc();
    if (r) setPasso((s) => Math.min(6, s + 1));
  }

  useEffect(() => {
    if (sinal && temContexto) { recalc().then(() => setPasso(6)); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sinal]);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Financeira — análise guiada</CardTitle>
        <CardDescription>
          Seis passos, uma pergunta de negócio por vez. Cada campo tem ajuda; os defaults vêm
          pré-preenchidos e rotulados <em>(edite)</em>. No fim, o painel com a divisão
          incorporador/terrenista e o semáforo sob as suas premissas (pré-análise, não veredito).
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {!temContexto && (
          <p className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
            Rode o <strong>Aproveitamento</strong> primeiro — daí saem os lotes do caso-base.
          </p>
        )}

        {/* Barra de progresso */}
        <div className="flex flex-wrap gap-1">
          {PASSOS.map((nome, i) => {
            const n = i + 1;
            return (
              <button
                key={nome}
                onClick={() => n < passo && setPasso(n)}
                disabled={n > passo}
                className={`flex-1 rounded-lg px-2 py-1.5 text-xs font-medium ${
                  n === passo ? "bg-slate-900 text-white"
                  : n < passo ? "bg-emerald-100 text-emerald-800"
                  : "bg-slate-100 text-slate-400"
                }`}
              >
                {n}. {nome}
              </button>
            );
          })}
        </div>

        {erro && <p className="rounded-lg bg-rose-50 p-3 text-sm text-rose-800">{erro}</p>}

        {/* PASSO 1 — Lotes & Preço */}
        {passo === 1 && (
          <Passo titulo="Quantos lotes e a quanto?">
            <div className="mb-2 flex items-center gap-2 text-xs">
              <span className="rounded-full bg-slate-100 px-2 py-0.5 font-medium text-slate-700">
                lotes: {f.override_lotes ? f.lotes_n : (nDiretriz ?? nTeto ?? "—")}
              </span>
              {!f.override_lotes && nDiretriz != null && <Badge>origem: diretriz</Badge>}
              {!f.override_lotes && nDiretriz == null && nTeto != null && <Badge tom="amber">origem: teto físico — pode superestimar</Badge>}
              <label className="ml-auto flex items-center gap-1 text-slate-500">
                <input type="checkbox" checked={f.override_lotes} onChange={(e) => set("override_lotes", e.target.checked)} />
                sobrescrever
              </label>
            </div>
            {f.override_lotes && <Campo rotulo="Nº de lotes" ajuda="Total de lotes do caso-base que você quer projetar." valor={f.lotes_n} on={(v) => set("lotes_n", v)} />}
            <div className="flex gap-2 text-xs">
              {(["lote", "m2"] as const).map((m) => (
                <button key={m} onClick={() => set("precoModo", m)} className={`rounded-lg px-3 py-1.5 font-medium ${f.precoModo === m ? "bg-slate-900 text-white" : "bg-slate-100 text-slate-600"}`}>
                  {m === "lote" ? "R$ por lote" : "R$/m² × área do lote"}
                </button>
              ))}
            </div>
            {f.precoModo === "lote" ? (
              <Campo rotulo="Preço por lote (R$)" ajuda="Quanto você vende cada lote (preço de tabela)." valor={f.preco_lote} on={(v) => set("preco_lote", v)} />
            ) : (
              <div className="grid grid-cols-2 gap-3">
                <Campo rotulo="Preço por m² (R$)" ajuda="Valor do metro quadrado de lote na região." valor={f.preco_m2} on={(v) => set("preco_m2", v)} />
                <Campo rotulo="Área do lote (m²)" ajuda="Metragem média do lote (ex.: 263 m²)." valor={f.area_lote_m2} on={(v) => set("area_lote_m2", v)} />
              </div>
            )}
            <Parcial rotulo="VGV bruto" valor={prev?.vgv.bruto_fmt} />
          </Passo>
        )}

        {/* PASSO 2 — Parceria */}
        {passo === 2 && (
          <Passo titulo="Como o terreno é pago e como divide?">
            <select value={f.aq_modo} onChange={(e) => set("aq_modo", e.target.value as Form["aq_modo"])} className="w-full rounded-lg border border-slate-200 px-2 py-2 text-sm">
              <option value="permuta_vgv">Parceria — % do VGV ao terrenista</option>
              <option value="permuta_lotes">Permuta em lotes (nº de lotes ao terrenista)</option>
              <option value="compra">Compra (paga o terreno)</option>
            </select>
            {f.aq_modo === "permuta_vgv" && (
              <>
                <Campo rotulo="Terrenista (% do VGV)" ajuda="Fatia do faturamento que vai ao dono da terra. Incorporador fica com o resto." valor={f.terrenista_pct} on={(v) => set("terrenista_pct", v)} />
                <p className="text-xs text-slate-500">incorporador {100 - f.terrenista_pct}% · terrenista {f.terrenista_pct}%</p>
              </>
            )}
            {f.aq_modo === "permuta_lotes" && (
              <Campo rotulo="Lotes ao terrenista" ajuda="Quantos lotes o dono da terra recebe (saem dos vendáveis do incorporador)." valor={f.permuta_n} on={(v) => set("permuta_n", v)} />
            )}
            {f.aq_modo === "compra" && (
              <Campo rotulo="Valor da compra (R$)" ajuda="Preço pago pela gleba (entra como saída no mês 0)." valor={f.compra_valor} on={(v) => set("compra_valor", v)} />
            )}
            <Parcial rotulo="VGV incorporador" valor={prev?.participantes?.incorporador.vgv.nominal_fmt}
              extra={prev?.participantes?.terrenista ? `terrenista ${prev.participantes.terrenista.vgv.nominal_fmt}` : "terrenista: não participa (compra)"} />
          </Passo>
        )}

        {/* PASSO 3 — Venda */}
        {passo === 3 && (
          <Passo titulo="Como você vende?">
            <div className="grid grid-cols-2 gap-3">
              <Campo rotulo="Início das vendas (mês)" ajuda="Mês em que a primeira venda acontece." valor={f.inicio_mes} on={(v) => set("inicio_mes", v)} />
              <Campo rotulo="Duração (meses)" ajuda="Em quantos meses você espera vender tudo." valor={f.duracao_meses} on={(v) => set("duracao_meses", v)} />
            </div>
            <div>
              <p className="text-[11px] text-slate-500">Modo de venda</p>
              <select value={f.modo} onChange={(e) => set("modo", e.target.value as Form["modo"])} className="w-full rounded-lg border border-slate-200 px-2 py-2 text-sm">
                <option value="financiado">Financiado (PRICE, corrigido por IPCA) — padrão de loteamento</option>
                <option value="avista">À vista</option>
                <option value="parcelado">Parcelado sem juros</option>
              </select>
            </div>
            {(f.modo === "parcelado" || f.modo === "financiado") && (
              <Campo rotulo="Entrada (%)" ajuda="Quanto o comprador paga no ato da compra." valor={f.entrada_pct} on={(v) => set("entrada_pct", v)} />
            )}
            {f.modo === "parcelado" && <Campo rotulo="Nº de parcelas" ajuda="Em quantas vezes o saldo é dividido (sem juros)." valor={f.n_parcelas} on={(v) => set("n_parcelas", v)} />}
            {f.modo === "financiado" && (
              <div className="rounded-lg border border-indigo-200 bg-indigo-50/40 p-3">
                <p className="text-sm font-medium text-slate-700">Mesa de vendas (PRICE, corrigido por IPCA) <Badge>default — edite</Badge></p>
                <p className="mb-2 text-[11px] text-slate-500">Como as vendas se repartem por prazo de financiamento (soma = 100%). Referência TIV 5.0 — calibre com sua corretora.</p>
                <p className="mb-2 text-[11px] text-amber-700">A parcela já corrige por IPCA. O <strong>% a.m.</strong> abaixo é o juro <strong>real, além do IPCA</strong> (contrato “IPCA + X”): use <strong>0</strong> para correção pura. Tudo em R$ de hoje — o IPCA cancela no fluxo.</p>
                {mesa.map((l, i) => (
                  <div key={i} className="flex flex-wrap items-center gap-2 py-0.5 text-xs">
                    <input type="number" value={l.participacao} onChange={(e) => setMesaLinha(i, { participacao: parseFloat(e.target.value) || 0 })} className="w-16 rounded border border-slate-200 px-2 py-1" />
                    <span className="text-slate-500">% em</span>
                    <input type="number" value={l.prazo_meses} onChange={(e) => setMesaLinha(i, { prazo_meses: parseInt(e.target.value) || 1 })} className="w-16 rounded border border-slate-200 px-2 py-1" />
                    <span className="text-slate-500">meses a</span>
                    <input type="number" step={0.1} value={l.taxa_am} onChange={(e) => setMesaLinha(i, { taxa_am: parseFloat(e.target.value) || 0 })} className="w-16 rounded border border-slate-200 px-2 py-1" />
                    <span className="text-slate-500" title="Juro real além do IPCA. 0 = só correção IPCA.">% a.m. (real, +IPCA)</span>
                    <button onClick={() => setMesa((m) => m.filter((_, k) => k !== i))} className="text-slate-400 hover:text-rose-600">✕</button>
                  </div>
                ))}
                <div className="mt-1 flex items-center gap-3 text-xs">
                  <button onClick={() => setMesa((m) => [...m, { participacao: 0, prazo_meses: 60, taxa_am: 1 }])} className="font-medium text-indigo-700">+ perfil</button>
                  <span className={mesa.reduce((s, l) => s + l.participacao, 0) === 100 ? "text-emerald-700" : "text-rose-600"}>soma: {mesa.reduce((s, l) => s + l.participacao, 0)}%</span>
                </div>
              </div>
            )}
            <Parcial rotulo="VGV geral (nominal + financeira)" valor={prev?.vgv.geral_fmt}
              extra={prev && prev.vgv.receita_financeira > 0 ? `juros ${prev.vgv.receita_financeira_fmt}` : undefined} />
          </Passo>
        )}

        {/* PASSO 4 — Custos */}
        {passo === 4 && (
          <Passo titulo="Quanto custa fazer?">
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              <Campo rotulo="Urbanização (R$/lote)" ajuda="Custo de infraestrutura por lote (terraplenagem, redes, vias)." valor={f.urb_valor} on={(v) => set("urb_valor", v)} />
              <Campo rotulo="Urb.: início (mês)" ajuda="Quando a obra começa." valor={f.urb_inicio} on={(v) => set("urb_inicio", v)} />
              <Campo rotulo="Urb.: duração (meses)" ajuda="Em quanto tempo a obra é executada." valor={f.urb_duracao} on={(v) => set("urb_duracao", v)} />
              <Campo rotulo="Projetos+aprovação (R$)" ajuda="Projetos e taxas de aprovação na prefeitura." badge valor={f.projetos} on={(v) => set("projetos", v)} />
              <Campo rotulo="Topografia (R$)" ajuda="Levantamento topográfico e georreferenciamento." badge valor={f.topografia} on={(v) => set("topografia", v)} />
              <Campo rotulo="Administração (R$/mês)" ajuda="Custo fixo mensal do empreendimento (equipe, escritório)." valor={f.admin_mensal} on={(v) => set("admin_mensal", v)} />
              <Campo rotulo="Marketing (% do VGV próprio)" ajuda="Verba de divulgação como % do faturamento do incorporador." valor={f.marketing_pct} on={(v) => set("marketing_pct", v)} />
              <Campo rotulo="Comissão (%)" ajuda="Comissão de venda. No financiado, incide sobre o recebimento (carteira)." valor={f.comissao_pct} on={(v) => set("comissao_pct", v)} />
            </div>
            <Parcial rotulo="Total de custos" valor={prev ? prev.blocos.filter((b) => !["tributos"].includes(b.bloco)).reduce((s, b) => s + b.total, 0).toLocaleString("pt-BR", { style: "currency", currency: "BRL" }) : undefined}
              extra={prev && prev.caso_base.lotes_vendaveis ? `${prev.caso_base.lotes_vendaveis} lotes vendáveis` : undefined} />
          </Passo>
        )}

        {/* PASSO 5 — Tributos */}
        {passo === 5 && (
          <Passo titulo="Qual regime e quanto de imposto?">
            <Campo rotulo="Tributo (% s/ receita recebida)" ajuda="Alíquota efetiva sobre a receita. Default 5,93% (Lucro Presumido) — NÃO é RET; confirme com contador." badge valor={f.aliquota_pct} on={(v) => set("aliquota_pct", v)} />
            <Campo rotulo="Inadimplência (%) — 0 = ninguém deixa de pagar" ajuda="% dos recebimentos que não entram. Comece com 0 e teste cenários." valor={f.inadimplencia_pct} on={(v) => set("inadimplencia_pct", v)} />
            {inadAlta && (
              <label className="flex items-start gap-2 rounded-lg border border-rose-200 bg-rose-50 p-3 text-xs text-rose-900">
                <input type="checkbox" checked={confirmarInad} onChange={(e) => setConfirmarInad(e.target.checked)} className="mt-0.5 accent-rose-600" />
                <span>Inadimplência de <strong>{f.inadimplencia_pct}%</strong> derruba as receitas. Confirmo que é intencional.</span>
              </label>
            )}
            <div className="grid grid-cols-2 gap-3">
              <Campo rotulo="Margem de referência (%)" ajuda="Margem que você considera boa. Vira o critério verde do semáforo." badge valor={f.margem_referencia_pct} on={(v) => set("margem_referencia_pct", v)} />
              <Campo rotulo="Capital disponível (R$) — opcional" ajuda="Quanto de caixa você tem. Se informado, o semáforo compara com a exposição máxima." valor={f.capital_disponivel} on={(v) => set("capital_disponivel", v)} />
            </div>
            <Parcial rotulo="Imposto estimado" valor={prev ? (prev.blocos.find((b) => b.bloco === "tributos")?.total_fmt ?? "R$ 0,00") : undefined} />
          </Passo>
        )}

        {/* PASSO 6 — Dashboard (slots vpl/tir/payback compostos com a Econômica, se houver) */}
        {passo === 6 && prev && <Dashboard d={prev} econ={econ} />}

        {/* Navegação */}
        <div className="flex items-center justify-between pt-1">
          <button onClick={() => setPasso((s) => Math.max(1, s - 1))} disabled={passo === 1} className="text-sm text-slate-500 hover:text-slate-800 disabled:opacity-40">← Voltar</button>
          {passo < 6 ? (
            <Button onClick={avancar} disabled={carregando || !temContexto || (inadAlta && passo === 5 && !confirmarInad)}>
              {carregando ? "Calculando…" : "Próximo →"}
            </Button>
          ) : (
            <Button onClick={recalc} disabled={carregando}>{carregando ? "Atualizando…" : "Recalcular"}</Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

/* ---------- blocos de UI ---------- */
function Passo({ titulo, children }: { titulo: string; children: React.ReactNode }) {
  return (
    <div className="space-y-3 rounded-xl border border-slate-200 p-4">
      <p className="text-sm font-semibold text-slate-800">{titulo}</p>
      {children}
    </div>
  );
}

function Campo({
  rotulo, ajuda, valor, on, badge,
}: {
  rotulo: string; ajuda: string; valor: number; on: (v: number) => void; badge?: boolean;
}) {
  return (
    <div>
      <p className="flex items-center gap-1.5 text-[11px] font-medium text-slate-600">
        {rotulo} {badge && <Badge>default — edite</Badge>}
      </p>
      <input type="number" step="any" value={valor} onChange={(e) => on(parseFloat(e.target.value) || 0)} className="w-full rounded-lg border border-slate-200 px-2 py-2 text-sm" />
      <p className="mt-0.5 text-[11px] text-slate-400">{ajuda}</p>
    </div>
  );
}

function Badge({ children, tom = "slate" }: { children: React.ReactNode; tom?: "slate" | "amber" }) {
  const c = tom === "amber" ? "bg-amber-100 text-amber-800" : "bg-slate-200 text-slate-600";
  return <span className={`rounded-full px-1.5 py-0.5 text-[10px] font-semibold ${c}`}>{children}</span>;
}

function Parcial({ rotulo, valor, extra }: { rotulo: string; valor?: string; extra?: string }) {
  return (
    <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3">
      <p className="text-[11px] text-emerald-700">{rotulo}</p>
      <p className="text-lg font-bold text-emerald-900">{valor ?? "— avance para calcular"}</p>
      {extra && <p className="text-[11px] text-emerald-700">{extra}</p>}
    </div>
  );
}

/* ---------- Dashboard (passo 6) ---------- */
const TOM: Record<string, string> = {
  slate: "border-slate-200 bg-white text-slate-900",
  emerald: "border-emerald-200 bg-emerald-50 text-emerald-900",
  rose: "border-rose-200 bg-rose-50 text-rose-900",
};
const SEMA: Record<string, { cor: string; rotulo: string }> = {
  favoravel: { cor: "bg-emerald-500", rotulo: "favorável" },
  atencao: { cor: "bg-amber-500", rotulo: "atenção" },
  desfavoravel: { cor: "bg-rose-500", rotulo: "desfavorável" },
  pendente: { cor: "bg-slate-300", rotulo: "Fase 5" },
};

function Dashboard({ d, econ }: { d: Financeira; econ?: Economica | null }) {
  const ind = d.indicadores;
  const lucro = ind.resultado_nominal >= 0;
  const inc = d.participantes?.incorporador;
  const ter = d.participantes?.terrenista;
  // Composição de dois JSONs do backend (§2): zero cálculo aqui.
  const leituras = comporLeituras(d.leituras, econ);
  return (
    <div className="space-y-4">
      {d.alerta_critico && (
        <p className="rounded-lg border-2 border-rose-400 bg-rose-100 p-3 text-sm font-semibold text-rose-900">⛔ {d.alerta_critico}</p>
      )}

      {/* Números-mestre */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Kpi rotulo="VGV geral" valor={d.vgv.geral_fmt} tom="emerald" sub={d.vgv.receita_financeira > 0 ? `nominal + juros ${d.vgv.receita_financeira_fmt}` : "nominal"} />
        <Kpi rotulo="Resultado nominal" valor={ind.resultado_nominal_fmt} tom={lucro ? "emerald" : "rose"} sub={`margem ${(ind.margem_sobre_vgv_proprio * 100).toLocaleString("pt-BR", { maximumFractionDigits: 2 })}%`} />
        <Kpi rotulo="Exposição máx. de caixa" valor={ind.exposicao_maxima.valor_fmt} tom="rose" sub={`no mês ${ind.exposicao_maxima.mes}`} />
        <Kpi rotulo="Horizonte" valor={`${ind.horizonte_meses} meses`} sub={`${d.caso_base.lotes_vendaveis} lotes · ${d.caso_base.origem_lotes}`} />
      </div>

      {/* Semáforo */}
      <div className="rounded-xl border border-slate-200 p-4">
        <p className="mb-2 text-sm font-semibold text-slate-800">Leitura sob as premissas declaradas</p>
        <ul className="space-y-1.5">
          {leituras.map((l) => (
            <li key={l.chave} className="flex items-center gap-2 text-sm">
              <span className={`h-2.5 w-2.5 rounded-full ${SEMA[l.status].cor}`} />
              <span className="text-slate-700">{l.texto}</span>
              {l.valor_fmt && <span className="ml-auto font-medium text-slate-600">{l.valor_fmt}</span>}
              {l.status === "pendente" && <span className="ml-auto text-[11px] text-slate-400">{SEMA[l.status].rotulo}</span>}
            </li>
          ))}
        </ul>
      </div>

      {/* Parceria */}
      {inc && (
        <div className="rounded-xl border border-slate-200 p-4">
          <p className="mb-2 text-sm font-semibold text-slate-800">Divisão da parceria</p>
          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-lg border border-indigo-200 bg-indigo-50 p-3">
              <p className="text-xs text-indigo-700">Incorporador {inc.pct != null ? `· ${(inc.pct * 100).toLocaleString("pt-BR", { maximumFractionDigits: 0 })}%` : ""}</p>
              <p className="text-base font-bold text-indigo-900">{inc.vgv.geral_fmt}</p>
              <p className="text-[11px] text-indigo-700">resultado {inc.resultado_nominal_fmt}</p>
            </div>
            <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
              <p className="text-xs text-slate-600">Terrenista {ter?.pct != null ? `· ${(ter.pct * 100).toLocaleString("pt-BR", { maximumFractionDigits: 0 })}%` : ""}</p>
              <p className="text-base font-bold text-slate-800">{ter ? ter.vgv.geral_fmt : "não participa (compra)"}</p>
              {ter && <p className="text-[11px] text-slate-500">recebe {ter.recebimento_total_fmt}{ter.modo ? ` · ${ter.modo}` : ""}</p>}
            </div>
          </div>
          {inc.nota && <p className="mt-2 text-[11px] text-slate-400">{inc.nota}</p>}
        </div>
      )}

      {/* Fluxo: anual + mensal sob expand */}
      <TabelaAnual linhas={d.fluxo_resumo_anual} />
      <details className="rounded-xl border border-slate-200 p-3">
        <summary className="cursor-pointer text-sm font-medium text-slate-700">Fluxo mensal ({d.fluxo.length} meses) & blocos de custo</summary>
        <div className="mt-2"><TabelaMensal linhas={d.fluxo} /></div>
        <ul className="mt-2 space-y-1 text-xs">
          {d.blocos.map((b) => (
            <li key={b.bloco} className="flex flex-wrap justify-between gap-2">
              <span className="font-medium text-slate-700">{b.bloco}</span><span className="text-slate-600">{b.total_fmt}</span>
              <span className="w-full text-slate-400">{b.proveniencia}</span>
            </li>
          ))}
        </ul>
      </details>

      <div className="rounded-lg bg-amber-50 p-3 text-xs text-amber-900">
        {d.avisos.map((a) => <p key={a}>• {a}</p>)}
      </div>
    </div>
  );
}

function TabelaMensal({ linhas }: { linhas: Financeira["fluxo"] }) {
  return <Tabela cab="Mês" linhas={linhas.map((l) => ({ k: l.mes, a: l.entradas_fmt, b: l.saidas_fmt, c: l.liquido_fmt, cn: l.liquido >= 0, d: l.acumulado_fmt, dn: l.acumulado >= 0 }))} />;
}
function TabelaAnual({ linhas }: { linhas: Financeira["fluxo_resumo_anual"] }) {
  return <Tabela cab="Ano" linhas={linhas.map((l) => ({ k: l.ano, a: l.entradas_fmt, b: l.saidas_fmt, c: l.liquido_fmt, cn: l.liquido >= 0, d: l.acumulado_fmt, dn: l.acumulado >= 0 }))} />;
}
function Tabela({ cab, linhas }: { cab: string; linhas: { k: number; a: string; b: string; c: string; cn: boolean; d: string; dn: boolean }[] }) {
  return (
    <div className="overflow-x-auto rounded-xl border border-slate-200">
      <table className="w-full text-right text-xs">
        <thead className="bg-slate-50 text-slate-500"><tr>
          <th className="px-3 py-2 text-left">{cab}</th><th className="px-3 py-2">Entradas</th><th className="px-3 py-2">Saídas</th><th className="px-3 py-2">Líquido</th><th className="px-3 py-2">Acumulado</th>
        </tr></thead>
        <tbody>
          {linhas.map((l) => (
            <tr key={l.k} className="border-t border-slate-100">
              <td className="px-3 py-1.5 text-left font-medium text-slate-700">{l.k}</td>
              <td className="px-3 py-1.5 text-slate-600">{l.a}</td>
              <td className="px-3 py-1.5 text-slate-600">{l.b}</td>
              <td className={`px-3 py-1.5 ${l.cn ? "text-emerald-700" : "text-rose-700"}`}>{l.c}</td>
              <td className={`px-3 py-1.5 font-medium ${l.dn ? "text-slate-800" : "text-rose-700"}`}>{l.d}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Kpi({ rotulo, valor, sub, tom = "slate" }: { rotulo: string; valor: string; sub?: string; tom?: "slate" | "emerald" | "rose" }) {
  return (
    <div className={`rounded-xl border p-3 shadow-sm ${TOM[tom]}`}>
      <p className="text-[11px] opacity-70">{rotulo}</p>
      <p className="mt-0.5 text-lg font-bold tracking-tight">{valor}</p>
      {sub && <p className="text-[11px] opacity-70">{sub}</p>}
    </div>
  );
}
