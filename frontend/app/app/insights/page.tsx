"use client";

// AI Portfolio Insights — painel comparativo das áreas do usuário, FIEL ao mockup
// aprovado em docs/mockups/mockup-portfolio.html (fundo slate, tabela com cabeçalho
// marinho e zebra, chips de filtro, radar + painel Detalhe lado a lado, linha
// selecionável). O backend manda TUDO pronto (KPIs 0-100, *_fmt, destaques, radar,
// avisos); aqui só renderização — filtrar/ordenar/selecionar é apresentação, nunca
// cálculo. Célula sem dado = "não calculado".

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { RequireAuth } from "@/components/auth/RequireAuth";
import { Button } from "@/components/ui/button";
import {
  obterPortfolio,
  type Portfolio,
  type PortfolioLinha,
  type PortfolioRadar,
} from "@/lib/portfolio";

export default function PaginaInsights() {
  return (
    <RequireAuth>
      <Insights />
    </RequireAuth>
  );
}

// ----- tabela: colunas (acessor numérico SÓ para ordenar; exibição vem pronta) -----

type Col = {
  chave: string;
  rotulo: string;
  valor: (l: PortfolioLinha) => number | null;
  render: (l: PortfolioLinha) => React.ReactNode;
  melhor?: "max" | "min";
};

const fmtNum = (v: number | null, sufixo = "") =>
  v === null ? null : `${v.toLocaleString("pt-BR")}${sufixo}`;

const COLS: Col[] = [
  { chave: "area", rotulo: "ha bruto", valor: (l) => l.area_ha, render: (l) => fmtNum(l.area_ha) },
  {
    chave: "lotes", rotulo: "Lotes", melhor: "max",
    valor: (l) => l.kpis.n_lotes, render: (l) => fmtNum(l.kpis.n_lotes),
  },
  {
    chave: "vgv", rotulo: "VGV", melhor: "max",
    valor: (l) => l.kpis.vgv, render: (l) => l.kpis.vgv_fmt,
  },
  {
    chave: "vgv_ha", rotulo: "VGV/ha", melhor: "max",
    valor: (l) => l.kpis.vgv_por_ha, render: (l) => l.kpis.vgv_por_ha_fmt,
  },
  {
    chave: "margem", rotulo: "Margem", melhor: "max",
    valor: (l) => l.kpis.margem_pct, render: (l) => fmtNum(l.kpis.margem_pct, "%"),
  },
  {
    chave: "tir", rotulo: "TIR", melhor: "max",
    valor: (l) => l.kpis.tir_aa_pct, render: (l) => fmtNum(l.kpis.tir_aa_pct, "%"),
  },
  {
    chave: "expo", rotulo: "Exposição máx.", melhor: "min",
    valor: (l) => (l.kpis.exposicao_maxima === null ? null : Math.abs(l.kpis.exposicao_maxima)),
    render: (l) => l.kpis.exposicao_maxima_fmt,
  },
  {
    chave: "negativo", rotulo: "Meses negativo", melhor: "min",
    valor: (l) => l.kpis.meses_negativo, render: (l) => fmtNum(l.kpis.meses_negativo),
  },
];

// Chips de semáforo — cores do mockup (verde/âmbar/vermelho)
function chipCls(tom: "verde" | "ambar" | "verm") {
  return {
    verde: "bg-emerald-100 text-emerald-800",
    ambar: "bg-amber-100 text-amber-800",
    verm: "bg-rose-100 text-rose-800",
  }[tom];
}

function ChipAmbiental({ l }: { l: PortfolioLinha }) {
  const pct = l.kpis.pct_restrito;
  if (pct === null) return <span className="italic text-slate-300">não calculado</span>;
  const tom = pct < 15 ? "verde" : pct < 25 ? "ambar" : "verm";
  return (
    <span className={`inline-block whitespace-nowrap rounded-full px-2.5 py-0.5 text-[11px] font-bold ${chipCls(tom)}`}>
      {pct.toLocaleString("pt-BR")}% restrito
    </span>
  );
}

function ChipJuridico({ l }: { l: PortfolioLinha }) {
  const nivel = l.kpis.juridico_nivel;
  if (!nivel) return <span className="italic text-slate-300">não calculado</span>;
  const rotulo = { baixo: "risco baixo", medio: "risco médio", alto: "risco alto" }[
    nivel as "baixo" | "medio" | "alto"
  ];
  const tom = nivel === "baixo" ? "verde" : nivel === "medio" ? "ambar" : "verm";
  const div = l.kpis.divergencia_area_pct;
  return (
    <span
      className={`inline-block whitespace-nowrap rounded-full px-2.5 py-0.5 text-[11px] font-bold ${chipCls(tom)}`}
      title={div !== null ? `Divergência matrícula × KMZ: ${div.toLocaleString("pt-BR")}%` : undefined}
    >
      {div !== null && div > 5 ? `divergência ${div.toLocaleString("pt-BR")}%` : rotulo}
    </span>
  );
}

// ----- radar (scores prontos do backend; 4 eixos fixos, rótulos completos) -----

const EIXOS: (keyof PortfolioRadar)[] = ["ambiental", "urbanistico", "juridico", "financeiro"];

function Radar({ linha }: { linha: PortfolioLinha }) {
  const r = 80;
  const cx = 110;
  const cy = 105;
  const dirs = [
    [0, -1],
    [1, 0],
    [0, 1],
    [-1, 0],
  ];
  const pontos = EIXOS.map((chave, i) => {
    const v = linha.radar[chave] ?? 0;
    return `${cx + dirs[i][0] * r * (v / 100)},${cy + dirs[i][1] * r * (v / 100)}`;
  }).join(" ");
  const anel = (frac: number) =>
    dirs.map(([dx, dy]) => `${cx + dx * r * frac},${cy + dy * r * frac}`).join(" ");
  return (
    <div className="text-center">
      <svg
        width="310"
        height="230"
        viewBox="-72 -8 364 240"
        role="img"
        aria-label={`Radar de risco de ${linha.titulo}`}
      >
        {[1, 2 / 3, 1 / 3].map((f) => (
          <polygon key={f} points={anel(f)} fill="none" stroke="#e2e8f0" />
        ))}
        <line x1={cx} y1={cy - r} x2={cx} y2={cy + r} stroke="#e2e8f0" />
        <line x1={cx - r} y1={cy} x2={cx + r} y2={cy} stroke="#e2e8f0" />
        <polygon points={pontos} fill="rgba(255,145,77,.25)" stroke="#ff914d" strokeWidth="2" />
        <text x={cx} y={cy - r - 8} textAnchor="middle" fontSize="11" fill="#64748b">
          Ambiental {linha.radar.ambiental ?? "—"}
        </text>
        <text x={cx + r + 6} y={cy + 4} fontSize="11" fill="#64748b">
          Urbanístico {linha.radar.urbanistico ?? "—"}
        </text>
        <text x={cx} y={cy + r + 16} textAnchor="middle" fontSize="11" fill="#64748b">
          Jurídico {linha.radar.juridico ?? "—"}
        </text>
        <text x={cx - r - 6} y={cy + 4} textAnchor="end" fontSize="11" fill="#64748b">
          Financeiro {linha.radar.financeiro ?? "—"}
        </text>
      </svg>
    </div>
  );
}

// ----- painel Detalhe (mockup: grade de KPIs da linha selecionada) -----

function ItemDet({ rotulo, valor, nota }: { rotulo: string; valor: string | null; nota?: string | null }) {
  if (valor === null) return null;
  return (
    <div>
      <dt className="text-[10.5px] font-bold uppercase tracking-wide text-slate-400">{rotulo}</dt>
      <dd className="text-sm font-bold text-slate-900">
        {valor} {nota && <span className="text-[10px] font-normal text-slate-400">{nota}</span>}
      </dd>
    </div>
  );
}

function DetalheGrade({ l }: { l: PortfolioLinha }) {
  const k = l.kpis;
  return (
    <div className="min-w-0 flex-1">
      <dl className="grid grid-cols-2 gap-x-4 gap-y-3.5 sm:grid-cols-3">
        <ItemDet
          rotulo="VGV próprio × terrenista"
          valor={k.vgv_proprio_fmt}
          nota={k.permuta_modo ? `permuta ${k.permuta_pct?.toLocaleString("pt-BR")}% VGV` : null}
        />
        <ItemDet rotulo="Lucro nominal" valor={k.lucro_fmt} />
        <ItemDet
          rotulo={`VPL${k.tma_aa_pct !== null ? ` (TMA ${k.tma_aa_pct.toLocaleString("pt-BR")}%)` : ""}`}
          valor={k.vpl_fmt}
        />
        <ItemDet rotulo="Payback descontado" valor={fmtNum(k.payback_descontado_mes, " meses")} />
        <ItemDet rotulo="Receita média/lote" valor={k.receita_por_lote_fmt} />
        <ItemDet rotulo="Múltiplo de capital" valor={fmtNum(k.multiplo_capital, "×")} />
        <ItemDet rotulo="% vendável (área líq.)" valor={fmtNum(k.pct_vendavel, "%")} />
        <ItemDet rotulo="% viário" valor={fmtNum(k.pct_viario, "%")} />
        <ItemDet rotulo="Sobra geométrica" valor={fmtNum(k.pct_sobra, "%")} />
        <ItemDet rotulo="Verde total (bruta)" valor={fmtNum(k.pct_verde_bruta, "%")} />
        <ItemDet
          rotulo="Alertas ambientais"
          valor={
            k.alertas_criticos !== null
              ? `${k.alertas_criticos} crítico · ${k.alertas_informativos ?? 0} atenção`
              : null
          }
        />
        <ItemDet rotulo="Lotes/ha bruto" valor={fmtNum(k.lotes_por_ha)} />
        <ItemDet rotulo="Área média do lote" valor={fmtNum(k.area_media_m2, " m²")} />
        <ItemDet
          rotulo="Proposta urbanística"
          valor={k.urbanismo_versao !== null ? `v${k.urbanismo_versao}` : null}
          nota={k.urbanismo_origem}
        />
      </dl>
      <FaltamDimensoes l={l} />
    </div>
  );
}

const ROTULO_DIM: Record<string, string> = {
  urbanismo: "urbanismo",
  ambiental: "ambiental",
  aproveitamento: "aproveitamento",
  vegetacao: "área verde",
  declividade: "declividade",
  juridico: "jurídico",
  financeira: "financeira",
  economica: "econômica",
};

function FaltamDimensoes({ l }: { l: PortfolioLinha }) {
  const faltam = Object.keys(ROTULO_DIM).filter((d) => !l.dimensoes.includes(d));
  if (faltam.length === 0) return null;
  return (
    <p className="mt-4 rounded-lg bg-slate-50 px-3 py-2 text-xs leading-relaxed text-slate-500">
      {l.dimensoes.length === 0
        ? "Nenhuma dimensão calculada nesta análise ainda. "
        : "Ainda sem dados de: "}
      {l.dimensoes.length > 0 && (
        <b>{faltam.map((d) => ROTULO_DIM[d]).join(", ")}</b>
      )}
      {" — abra a análise, rode essas dimensões e clique em Salvar para completar o Raio-X."}
    </p>
  );
}

const ROTULO_EIXO: Record<string, string> = {
  ambiental: "Ambiental",
  urbanistico: "Urbanístico",
  juridico: "Jurídico",
  financeiro: "Financeiro",
};

// ----- página -----

const NOVENTA_DIAS_MS = 90 * 24 * 60 * 60 * 1000;

function Insights() {
  const [dados, setDados] = useState<Portfolio | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(true);
  const [ordem, setOrdem] = useState<{ chave: string; desc: boolean }>({ chave: "vgv", desc: true });
  const [filtroUf, setFiltroUf] = useState<string | null>(null);
  const [filtro90, setFiltro90] = useState(false);
  const [selecionada, setSelecionada] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const p = await obterPortfolio();
        setDados(p);
        // Abre na área MAIS COMPLETA (mais dimensões calculadas; empate = mais recente):
        // o Raio-X nasce rico em vez de abrir numa análise ainda vazia.
        const maisCompleta = [...p.linhas].sort(
          (a, b) => b.dimensoes.length - a.dimensoes.length,
        )[0];
        if (maisCompleta) setSelecionada(maisCompleta.id);
      } catch (e) {
        setErro(e instanceof Error ? e.message : "Falha ao carregar o portfólio.");
      } finally {
        setCarregando(false);
      }
    })();
  }, []);

  const ufs = useMemo(() => {
    const contagem = new Map<string, number>();
    for (const l of dados?.linhas ?? []) {
      if (l.uf) contagem.set(l.uf, (contagem.get(l.uf) ?? 0) + 1);
    }
    return [...contagem.entries()].sort((a, b) => b[1] - a[1]);
  }, [dados]);

  const linhasFiltradas = useMemo(() => {
    let base = dados?.linhas ?? [];
    if (filtroUf) base = base.filter((l) => l.uf === filtroUf);
    if (filtro90) {
      const corte = Date.now() - NOVENTA_DIAS_MS;
      base = base.filter((l) => l.atualizada_em && new Date(l.atualizada_em).getTime() >= corte);
    }
    return base;
  }, [dados, filtroUf, filtro90]);

  const linhasOrdenadas = useMemo(() => {
    const col = COLS.find((c) => c.chave === ordem.chave);
    if (!col) return linhasFiltradas;
    return [...linhasFiltradas].sort((a, b) => {
      const va = col.valor(a);
      const vb = col.valor(b);
      if (va === null && vb === null) return 0;
      if (va === null) return 1;
      if (vb === null) return -1;
      return ordem.desc ? vb - va : va - vb;
    });
  }, [linhasFiltradas, ordem]);

  const melhores = useMemo(() => {
    const m: Record<string, string | null> = {};
    for (const col of COLS) {
      if (!col.melhor) continue;
      let alvo: { id: string; v: number } | null = null;
      for (const l of linhasFiltradas) {
        const v = col.valor(l);
        if (v === null) continue;
        if (!alvo || (col.melhor === "max" ? v > alvo.v : v < alvo.v)) alvo = { id: l.id, v };
      }
      m[col.chave] = alvo?.id ?? null;
    }
    return m;
  }, [linhasFiltradas]);

  const linhaSelecionada =
    linhasFiltradas.find((l) => l.id === selecionada) ?? linhasFiltradas[0] ?? null;

  if (carregando) {
    return (
      <main className="grid min-h-screen place-items-center bg-[#f1f5f9]">
        <p className="text-sm text-slate-500">Carregando o portfólio…</p>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-[#f1f5f9] pb-16">
      <header className="sticky top-0 z-10 border-b border-slate-200 bg-white/95 backdrop-blur">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-3.5 sm:px-5">
          <div>
            <h1 className="text-xl font-extrabold tracking-tight text-[#1d1252]">
              Comparar áreas
            </h1>
            <p className="text-xs text-slate-500">
              {dados
                ? `Suas ${dados.total_analises} áreas analisadas, comparadas pela mesma régua — risco, aproveitamento e retorno.`
                : "…"}
            </p>
          </div>
          <Link href="/app">
            <Button variant="ghost">← Voltar às análises</Button>
          </Link>
        </div>
      </header>

      <div className="mx-auto mt-6 max-w-6xl space-y-6 px-4 sm:px-5">
        {erro && <p className="rounded-lg bg-rose-50 p-3 text-sm text-rose-800">{erro}</p>}

        {dados?.gate.status === "bloqueado" && (
          <div className="rounded-xl border border-slate-200 bg-white py-12 text-center shadow-sm">
            <div className="mx-auto grid h-14 w-14 place-items-center rounded-full bg-orange-50 text-2xl">
              🔒
            </div>
            <h2 className="mt-4 text-xl font-bold text-slate-900">
              Sua prévia gratuita de {dados.gate.previa_dias} dias terminou
            </h2>
            <p className="mx-auto mt-3 max-w-lg text-sm leading-relaxed text-slate-600">
              O comparador de áreas continua guardando as suas{" "}
              <b>{dados.total_analises} área(s) analisada(s)</b> — nada foi apagado. Para voltar
              a ver o comparativo, os destaques e o radar de risco, fale com a gente sobre os
              planos pagos.
            </p>
            <div className="mt-6 flex flex-col items-center gap-2">
              <Link href="/planos-mvp">
                <Button>Conhecer os planos</Button>
              </Link>
              <Link href="/app" className="text-xs text-slate-500 underline underline-offset-2">
                Continuar só com as análises individuais (grátis)
              </Link>
            </div>
          </div>
        )}

        {dados && dados.gate.status !== "bloqueado" && (
          <>
            {dados.gate.status === "previa" && (
              <div className="flex flex-col items-start justify-between gap-3 rounded-[14px] border-[1.5px] border-orange-300 bg-orange-50 px-5 py-3.5 sm:flex-row sm:items-center">
                <p className="max-w-3xl text-sm text-slate-700">
                  <b className="text-orange-700">Prévia do plano gratuito.</b> Você tem acesso
                  completo ao comparador de áreas por {dados.gate.previa_dias} dias. Depois
                  disso, o painel é exclusivo dos planos pagos — suas análises continuam salvas.
                </p>
                <div className="shrink-0 rounded-xl bg-laranja px-4 py-2 text-center text-white">
                  <p className="text-[15px] font-extrabold leading-tight">
                    Restam {dados.gate.dias_restantes} dias
                  </p>
                  <p className="text-[10px] font-semibold opacity-90">de prévia gratuita</p>
                </div>
              </div>
            )}

            {/* Chips de filtro (mockup) — apresentação: filtram tabela, radar e detalhe */}
            {dados.linhas.length > 0 && (
              <div className="flex flex-wrap gap-2.5 text-[13px]">
                <button
                  type="button"
                  onClick={() => setFiltroUf(null)}
                  className={`rounded-full border px-4 py-2 transition ${
                    filtroUf === null
                      ? "border-[#1d1252] bg-[#1d1252] font-bold text-white"
                      : "border-slate-300 bg-white text-slate-700 hover:border-slate-500"
                  }`}
                >
                  Todas ({dados.linhas.length})
                </button>
                {ufs.map(([uf, n]) => (
                  <button
                    key={uf}
                    type="button"
                    onClick={() => setFiltroUf(filtroUf === uf ? null : uf)}
                    className={`rounded-full border px-4 py-2 transition ${
                      filtroUf === uf
                        ? "border-[#1d1252] bg-[#1d1252] font-bold text-white"
                        : "border-slate-300 bg-white text-slate-700 hover:border-slate-500"
                    }`}
                  >
                    {uf} ({n})
                  </button>
                ))}
                <button
                  type="button"
                  onClick={() => setFiltro90(!filtro90)}
                  className={`rounded-full border px-4 py-2 transition ${
                    filtro90
                      ? "border-[#1d1252] bg-[#1d1252] font-bold text-white"
                      : "border-slate-300 bg-white text-slate-700 hover:border-slate-500"
                  }`}
                >
                  Últimos 90 dias
                </button>
              </div>
            )}

            {dados.total_analises === 0 && (
              <div className="rounded-xl border border-slate-200 bg-white py-12 text-center shadow-sm">
                <h2 className="text-lg font-bold text-slate-900">Seu portfólio ainda está vazio</h2>
                <p className="mx-auto mt-2 max-w-md text-sm text-slate-600">
                  Analise e salve pelo menos duas glebas para compará-las aqui pela mesma régua:
                  risco, aproveitamento e retorno.
                </p>
                <Link href="/app" className="mt-5 inline-block">
                  <Button>Analisar uma gleba</Button>
                </Link>
              </div>
            )}

            {dados.destaques.length > 0 && (
              <section>
                <h2 className="text-xs font-extrabold uppercase tracking-[1.5px] text-slate-400">
                  Destaques do portfólio
                </h2>
                <div className="mt-3 grid gap-3.5 sm:grid-cols-2 lg:grid-cols-4">
                  {dados.destaques.map((d) => (
                    <div
                      key={d.chave}
                      className="rounded-2xl border border-slate-200 bg-white p-[18px] shadow-sm"
                    >
                      <p className="text-xs font-semibold text-slate-500">{d.rotulo}</p>
                      <p className="mt-1.5 font-mono text-2xl font-extrabold text-[#1d1252]">
                        {d.valor_fmt}
                      </p>
                      <p className="mt-1 truncate text-[13px] font-semibold text-slate-900">
                        {d.titulo}
                        {d.cidade ? ` · ${d.cidade}${d.uf ? ` ${d.uf}` : ""}` : ""}
                      </p>
                      <p className="mt-2 border-t border-dashed border-slate-100 pt-1.5 text-[10.5px] text-slate-400">
                        {d.fonte}
                      </p>
                    </div>
                  ))}
                </div>
              </section>
            )}

            {linhasOrdenadas.length > 0 && (
              <section>
                <h2 className="text-xs font-extrabold uppercase tracking-[1.5px] text-slate-400">
                  Comparativo das áreas — clique no título da coluna para ordenar
                </h2>
                <div className="mt-3 overflow-x-auto rounded-2xl bg-white shadow-sm">
                  <table className="w-full min-w-[980px] border-collapse text-left text-[13px]">
                    <thead>
                      <tr className="bg-[#1d1252] text-white">
                        <th className="px-3 py-3 text-[11.5px] font-semibold">Área</th>
                        {COLS.map((c) => (
                          <th key={c.chave} className="whitespace-nowrap px-3 py-3 text-[11.5px] font-semibold">
                            <button
                              type="button"
                              className="inline-flex items-center gap-1 hover:text-orange-200"
                              onClick={() =>
                                setOrdem((o) =>
                                  o.chave === c.chave
                                    ? { chave: c.chave, desc: !o.desc }
                                    : { chave: c.chave, desc: c.melhor !== "min" },
                                )
                              }
                            >
                              {c.rotulo}
                              {ordem.chave === c.chave && (
                                <span className="text-laranja">{ordem.desc ? "▼" : "▲"}</span>
                              )}
                            </button>
                          </th>
                        ))}
                        <th className="px-3 py-3 text-[11.5px] font-semibold">Ambiental</th>
                        <th className="px-3 py-3 text-[11.5px] font-semibold">Jurídico</th>
                      </tr>
                    </thead>
                    <tbody>
                      {linhasOrdenadas.map((l, i) => (
                        <tr
                          key={l.id}
                          onClick={() => setSelecionada(l.id)}
                          className={`cursor-pointer border-b border-slate-100 last:border-0 ${
                            i % 2 === 1 ? "bg-slate-50" : "bg-white"
                          } ${linhaSelecionada?.id === l.id ? "!bg-orange-50" : "hover:bg-slate-100"}`}
                          title="Clique para ver o detalhe desta área"
                        >
                          <td className="px-3 py-2.5">
                            <p className="font-bold text-[#1d1252]">{l.titulo}</p>
                            <p className="text-[11px] text-slate-400">
                              {[l.cidade, l.uf].filter(Boolean).join(" · ")}
                              {l.atualizada_em
                                ? ` · ${new Date(l.atualizada_em).toLocaleDateString("pt-BR")}`
                                : ""}
                            </p>
                          </td>
                          {COLS.map((c) => {
                            const conteudo = c.render(l);
                            const eMelhor =
                              c.melhor && melhores[c.chave] === l.id && conteudo !== null;
                            return (
                              <td
                                key={c.chave}
                                className={`whitespace-nowrap px-3 py-2.5 font-mono ${
                                  eMelhor ? "font-extrabold text-emerald-700" : "text-slate-700"
                                }`}
                              >
                                {conteudo ?? (
                                  <span className="font-sans italic text-slate-300">—</span>
                                )}
                              </td>
                            );
                          })}
                          <td className="whitespace-nowrap px-3 py-2.5">
                            <ChipAmbiental l={l} />
                          </td>
                          <td className="whitespace-nowrap px-3 py-2.5">
                            <ChipJuridico l={l} />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {dados.avisos.map((a) => (
                  <p
                    key={a}
                    className="mt-2.5 rounded-[10px] border border-amber-200 bg-amber-50 px-4 py-2.5 text-[12.5px] text-amber-800"
                  >
                    ⚠ {a}
                  </p>
                ))}
              </section>
            )}

            {/* Raio-X da área selecionada: UM card — radar à esquerda, detalhe à direita.
                Sem pilha de gráficos e sem vazio: a tabela é o seletor, este card é a lupa. */}
            {linhaSelecionada && (
              <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <p className="text-sm font-bold text-[#1d1252]">
                    Raio-X da área · {linhaSelecionada.titulo}{" "}
                    <span className="text-[11px] font-normal text-slate-400">
                      (clique numa linha da tabela para trocar de área)
                    </span>
                  </p>
                  <p className="text-[11px] text-slate-400">
                    Radar: 100 = menor risco · fórmula aberta em &quot;como calculamos&quot;
                  </p>
                </div>
                <div className="mt-4 flex flex-col items-center gap-6 md:flex-row md:items-start">
                  <div className="shrink-0">
                    {EIXOS.every((e) => linhaSelecionada.radar[e] !== null) ? (
                      <Radar linha={linhaSelecionada} />
                    ) : (
                      <div className="grid h-[230px] w-[310px] place-items-center rounded-xl border border-dashed border-slate-300 bg-slate-50 px-6 text-center">
                        <div>
                          <p className="text-sm font-semibold text-slate-600">
                            Radar incompleto
                          </p>
                          <p className="mt-2 text-xs leading-relaxed text-slate-400">
                            Faltam:{" "}
                            {EIXOS.filter((e) => linhaSelecionada.radar[e] === null)
                              .map((e) => ROTULO_EIXO[e])
                              .join(", ")}
                            . Rode e salve essas análises para desenhar o radar.
                          </p>
                        </div>
                      </div>
                    )}
                  </div>
                  <DetalheGrade l={linhaSelecionada} />
                </div>
              </section>
            )}

            {dados.linhas.length > 0 && (
              <details className="rounded-xl border border-slate-200 bg-white p-4 text-sm shadow-sm">
                <summary className="cursor-pointer font-bold text-[#1d1252]">
                  Como calculamos (fórmulas abertas e origem dos números)
                </summary>
                <ul className="mt-3 space-y-1.5 text-[13px] text-slate-600">
                  {Object.entries(dados.radar_formula).map(([eixo, formula]) => (
                    <li key={eixo}>
                      <b className="capitalize">{eixo}:</b> {formula}
                    </li>
                  ))}
                </ul>
                <p className="mt-3 text-xs leading-relaxed text-slate-400">
                  Cada número vem da análise salva da própria área (dimensão indicada no
                  card/coluna) e reflete o que estava calculado no momento do último salvar. O
                  radar é régua de triagem da plataforma, com fórmula aberta — não é veredito
                  nem substitui os profissionais habilitados.
                </p>
              </details>
            )}
          </>
        )}
      </div>
    </main>
  );
}
