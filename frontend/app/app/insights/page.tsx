"use client";

// AI Portfolio Insights — painel comparativo das áreas do usuário (fase
// Dashboard-Portfólio; mockups aprovados em docs/mockups/). O backend manda TUDO
// pronto (KPIs 0-100, destaques, radar com fórmula, avisos); aqui só renderização —
// ordenar a tabela é apresentação, nunca cálculo. Célula sem dado = "não calculado".

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { RequireAuth } from "@/components/auth/RequireAuth";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
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
  melhor?: "max" | "min"; // pinta o melhor valor da coluna
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

function ChipAmbiental({ l }: { l: PortfolioLinha }) {
  const pct = l.kpis.pct_restrito;
  if (pct === null) return <span className="italic text-slate-300">não calculado</span>;
  const variant = pct < 15 ? "success" : pct < 25 ? "warning" : "neutral";
  const extra = pct >= 25 ? "!bg-rose-100 !text-rose-800" : "";
  return (
    <Badge variant={variant} className={extra}>
      {pct.toLocaleString("pt-BR")}% restrito
    </Badge>
  );
}

function ChipJuridico({ l }: { l: PortfolioLinha }) {
  const nivel = l.kpis.juridico_nivel;
  if (!nivel) return <span className="italic text-slate-300">não calculado</span>;
  const rotulo = { baixo: "risco baixo", medio: "risco médio", alto: "risco alto" }[
    nivel as "baixo" | "medio" | "alto"
  ];
  const variant = nivel === "baixo" ? "success" : nivel === "medio" ? "warning" : "neutral";
  const extra = nivel === "alto" ? "!bg-rose-100 !text-rose-800" : "";
  const div = l.kpis.divergencia_area_pct;
  return (
    <Badge
      variant={variant}
      className={extra}
      title={div !== null ? `Divergência matrícula × KMZ: ${div.toLocaleString("pt-BR")}%` : undefined}
    >
      {rotulo}
    </Badge>
  );
}

// ----- radar (renderização de scores prontos do backend; 4 eixos fixos) -----

const EIXOS: { chave: keyof PortfolioRadar; rotulo: string }[] = [
  { chave: "ambiental", rotulo: "Ambiental" },
  { chave: "urbanistico", rotulo: "Urbanístico" },
  { chave: "juridico", rotulo: "Jurídico" },
  { chave: "financeiro", rotulo: "Financeiro" },
];

function Radar({ linha }: { linha: PortfolioLinha }) {
  const r = 78;
  const cx = 105;
  const cy = 100;
  // topo, direita, baixo, esquerda (mesma ordem de EIXOS)
  const dirs = [
    [0, -1],
    [1, 0],
    [0, 1],
    [-1, 0],
  ];
  const pontos = EIXOS.map(({ chave }, i) => {
    const v = linha.radar[chave] ?? 0;
    return [cx + dirs[i][0] * r * (v / 100), cy + dirs[i][1] * r * (v / 100)];
  })
    .map(([x, y]) => `${x},${y}`)
    .join(" ");
  const anel = (frac: number) =>
    dirs.map(([dx, dy]) => `${cx + dx * r * frac},${cy + dy * r * frac}`).join(" ");
  return (
    <div className="text-center">
      <svg width="210" height="200" viewBox="0 0 210 200" role="img" aria-label={`Radar de risco de ${linha.titulo}`}>
        {[1, 2 / 3, 1 / 3].map((f) => (
          <polygon key={f} points={anel(f)} fill="none" stroke="#e2e8f0" />
        ))}
        <line x1={cx} y1={cy - r} x2={cx} y2={cy + r} stroke="#e2e8f0" />
        <line x1={cx - r} y1={cy} x2={cx + r} y2={cy} stroke="#e2e8f0" />
        <polygon points={pontos} fill="rgba(255,145,77,.25)" stroke="#ff914d" strokeWidth="2" />
        <text x={cx} y={cy - r - 6} textAnchor="middle" fontSize="10" fill="#64748b">
          Ambiental {linha.radar.ambiental ?? "—"}
        </text>
        <text x={cx + r + 4} y={cy + 3} fontSize="10" fill="#64748b">
          Urb. {linha.radar.urbanistico ?? "—"}
        </text>
        <text x={cx} y={cy + r + 14} textAnchor="middle" fontSize="10" fill="#64748b">
          Jurídico {linha.radar.juridico ?? "—"}
        </text>
        <text x={cx - r - 4} y={cy + 3} textAnchor="end" fontSize="10" fill="#64748b">
          Fin. {linha.radar.financeiro ?? "—"}
        </text>
      </svg>
      <p className="text-sm font-semibold text-slate-800">{linha.titulo}</p>
      <p className="text-xs text-slate-400">
        {[linha.cidade, linha.uf].filter(Boolean).join(" · ")}
      </p>
    </div>
  );
}

// ----- página -----

function Insights() {
  const [dados, setDados] = useState<Portfolio | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(true);
  const [ordem, setOrdem] = useState<{ chave: string; desc: boolean }>({ chave: "vgv", desc: true });

  useEffect(() => {
    (async () => {
      try {
        setDados(await obterPortfolio());
      } catch (e) {
        setErro(e instanceof Error ? e.message : "Falha ao carregar o portfólio.");
      } finally {
        setCarregando(false);
      }
    })();
  }, []);

  const linhasOrdenadas = useMemo(() => {
    if (!dados) return [];
    const col = COLS.find((c) => c.chave === ordem.chave);
    if (!col) return dados.linhas;
    // Ordenação é APRESENTAÇÃO (nulls sempre por último, independente da direção).
    return [...dados.linhas].sort((a, b) => {
      const va = col.valor(a);
      const vb = col.valor(b);
      if (va === null && vb === null) return 0;
      if (va === null) return 1;
      if (vb === null) return -1;
      return ordem.desc ? vb - va : va - vb;
    });
  }, [dados, ordem]);

  const melhores = useMemo(() => {
    const m: Record<string, string | null> = {};
    if (!dados) return m;
    for (const col of COLS) {
      if (!col.melhor) continue;
      let alvo: { id: string; v: number } | null = null;
      for (const l of dados.linhas) {
        const v = col.valor(l);
        if (v === null) continue;
        if (!alvo || (col.melhor === "max" ? v > alvo.v : v < alvo.v)) alvo = { id: l.id, v };
      }
      m[col.chave] = alvo?.id ?? null;
    }
    return m;
  }, [dados]);

  if (carregando) {
    return (
      <main className="grid min-h-screen place-items-center bg-creme-100">
        <p className="text-sm text-slate-500">Carregando o portfólio…</p>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-creme-100 pb-16">
      <header className="sticky top-0 z-10 border-b border-slate-200 bg-white/95 backdrop-blur">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-3.5 sm:px-5">
          <div>
            <h1 className="text-lg font-bold tracking-tight">AI Portfolio Insights</h1>
            <p className="text-xs text-slate-500">
              Suas áreas analisadas, comparadas pela mesma régua — risco, aproveitamento e retorno.
            </p>
          </div>
          <Link href="/app">
            <Button variant="ghost">← Voltar às análises</Button>
          </Link>
        </div>
      </header>

      <div className="mx-auto mt-6 max-w-6xl space-y-6 px-4 sm:px-5">
        {erro && (
          <p className="rounded-lg bg-rose-50 p-3 text-sm text-rose-800">{erro}</p>
        )}

        {dados?.gate.status === "bloqueado" && (
          <Card>
            <CardContent className="py-12 text-center">
              <div className="mx-auto grid h-14 w-14 place-items-center rounded-full bg-orange-50 text-2xl">
                🔒
              </div>
              <h2 className="mt-4 text-xl font-bold text-slate-900">
                Sua prévia gratuita de {dados.gate.previa_dias} dias terminou
              </h2>
              <p className="mx-auto mt-3 max-w-lg text-sm leading-relaxed text-slate-600">
                O AI Portfolio Insights continua guardando e comparando as suas{" "}
                <b>{dados.total_analises} área(s) analisada(s)</b> — nada foi apagado. Para
                voltar a ver o comparativo, os destaques e o radar de risco, fale com a gente
                sobre os planos pagos.
              </p>
              <div className="mt-6 flex flex-col items-center gap-2">
                <Link href="/planos-mvp">
                  <Button>Conhecer os planos</Button>
                </Link>
                <Link href="/app" className="text-xs text-slate-500 underline underline-offset-2">
                  Continuar só com as análises individuais (grátis)
                </Link>
              </div>
            </CardContent>
          </Card>
        )}

        {dados && dados.gate.status !== "bloqueado" && (
          <>
            {dados.gate.status === "previa" && (
              <div className="flex flex-col items-start justify-between gap-3 rounded-xl border border-orange-200 bg-orange-50 px-4 py-3 sm:flex-row sm:items-center">
                <p className="text-sm text-slate-700">
                  <b className="text-orange-700">Prévia do plano gratuito.</b> Você tem acesso
                  completo ao painel por {dados.gate.previa_dias} dias a partir do primeiro
                  acesso. Suas análises continuam salvas depois disso.
                </p>
                <div className="shrink-0 rounded-lg bg-laranja px-4 py-2 text-center text-white">
                  <p className="text-sm font-bold leading-tight">
                    Restam {dados.gate.dias_restantes} dias
                  </p>
                  <p className="text-[10px] opacity-90">de prévia gratuita</p>
                </div>
              </div>
            )}

            {dados.total_analises === 0 && (
              <Card>
                <CardContent className="py-12 text-center">
                  <h2 className="text-lg font-bold text-slate-900">
                    Seu portfólio ainda está vazio
                  </h2>
                  <p className="mx-auto mt-2 max-w-md text-sm text-slate-600">
                    Analise e salve pelo menos duas glebas para compará-las aqui pela mesma
                    régua: risco, aproveitamento e retorno.
                  </p>
                  <Link href="/app" className="mt-5 inline-block">
                    <Button>Analisar uma gleba</Button>
                  </Link>
                </CardContent>
              </Card>
            )}

            {dados.destaques.length > 0 && (
              <section>
                <h2 className="text-xs font-bold uppercase tracking-wider text-slate-400">
                  Destaques do portfólio
                </h2>
                <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                  {dados.destaques.map((d) => (
                    <Card key={d.chave}>
                      <CardContent className="p-4">
                        <p className="text-xs font-medium text-slate-500">{d.rotulo}</p>
                        <p className="mt-1 font-mono text-2xl font-bold text-marinho-900">
                          {d.valor_fmt}
                        </p>
                        <p className="mt-1 truncate text-[13px] font-semibold text-slate-700">
                          {d.titulo}
                          {d.cidade ? ` · ${d.cidade}${d.uf ? ` ${d.uf}` : ""}` : ""}
                        </p>
                        <p className="mt-2 border-t border-dashed border-slate-100 pt-1.5 text-[10px] text-slate-400">
                          {d.fonte}
                        </p>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              </section>
            )}

            {dados.linhas.length > 0 && (
              <section>
                <h2 className="text-xs font-bold uppercase tracking-wider text-slate-400">
                  Comparativo das áreas — clique no título da coluna para ordenar
                </h2>
                <div className="mt-3 overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
                  <table className="w-full min-w-[900px] border-collapse text-left text-sm">
                    <thead>
                      <tr className="border-b border-slate-200 bg-slate-50 text-xs text-slate-500">
                        <th className="px-3 py-2.5 font-semibold">Área</th>
                        {COLS.map((c) => (
                          <th key={c.chave} className="whitespace-nowrap px-3 py-2.5 font-semibold">
                            <button
                              type="button"
                              className="inline-flex items-center gap-1 hover:text-slate-800"
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
                        <th className="px-3 py-2.5 font-semibold">Ambiental</th>
                        <th className="px-3 py-2.5 font-semibold">Jurídico</th>
                      </tr>
                    </thead>
                    <tbody>
                      {linhasOrdenadas.map((l) => (
                        <tr key={l.id} className="border-b border-slate-100 last:border-0">
                          <td className="px-3 py-2.5">
                            <p className="font-semibold text-slate-800">{l.titulo}</p>
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
                                  eMelhor ? "font-bold text-emerald-700" : "text-slate-700"
                                }`}
                                title={
                                  c.chave === "vgv" || c.chave === "vgv_ha"
                                    ? l.proveniencia["financeira"]
                                    : c.chave === "lotes"
                                      ? l.proveniencia["urbanismo"]
                                      : undefined
                                }
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
                    className="mt-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800"
                  >
                    ⚠ {a}
                  </p>
                ))}
              </section>
            )}

            {dados.linhas.some((l) => EIXOS.every((e) => l.radar[e.chave] !== null)) && (
              <section>
                <h2 className="text-xs font-bold uppercase tracking-wider text-slate-400">
                  Radar de risco por área (100 = menor risco)
                </h2>
                <Card className="mt-3">
                  <CardContent className="p-4">
                    <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
                      {dados.linhas
                        .filter((l) => EIXOS.every((e) => l.radar[e.chave] !== null))
                        .map((l) => (
                          <Radar key={l.id} linha={l} />
                        ))}
                    </div>
                    {dados.linhas.some((l) => EIXOS.some((e) => l.radar[e.chave] === null)) && (
                      <p className="mt-3 text-xs text-slate-400">
                        Áreas sem as 4 dimensões calculadas não entram no radar — rode e salve
                        as análises que faltam.
                      </p>
                    )}
                  </CardContent>
                </Card>
              </section>
            )}

            {dados.linhas.length > 0 && (
              <details className="rounded-xl border border-slate-200 bg-white p-4 text-sm shadow-sm">
                <summary className="cursor-pointer font-semibold text-slate-700">
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
                  card/coluna) e reflete o que estava calculado no momento do último salvar.
                  O radar é régua de triagem da plataforma, com fórmula aberta — não é
                  veredito nem substitui os profissionais habilitados.
                </p>
              </details>
            )}
          </>
        )}
      </div>
    </main>
  );
}
