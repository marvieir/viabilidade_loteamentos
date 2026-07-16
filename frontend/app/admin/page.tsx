"use client";

// Fase 12.3 — painel admin (cards). Protegido: exige login E papel admin. O backend
// também barra (requer_admin); aqui é só a UX (não confiar só no front para autorizar).

import { useEffect, useState } from "react";
import Link from "next/link";
import { RequireAuth } from "@/components/auth/RequireAuth";
import { useAuth } from "@/components/auth/AuthProvider";
import {
  listarClientes,
  obterCustos,
  obterMetricas,
  type AdminCliente,
  type AdminCustos,
  type AdminMetricas,
} from "@/lib/admin";

export default function AdminPage() {
  return (
    <RequireAuth>
      <PainelAdmin />
    </RequireAuth>
  );
}

function PainelAdmin() {
  const { usuario, sair } = useAuth();
  const [metricas, setMetricas] = useState<AdminMetricas | null>(null);
  const [clientes, setClientes] = useState<AdminCliente[]>([]);
  const [custos, setCustos] = useState<AdminCustos | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(true);

  const ehAdmin = usuario?.papel === "admin";

  useEffect(() => {
    if (!ehAdmin) {
      setCarregando(false);
      return;
    }
    (async () => {
      try {
        const [m, c, cu] = await Promise.all([
          obterMetricas(),
          listarClientes(),
          obterCustos(),
        ]);
        setMetricas(m);
        setClientes(c);
        setCustos(cu);
      } catch (e) {
        setErro(e instanceof Error ? e.message : "Falha ao carregar o painel.");
      } finally {
        setCarregando(false);
      }
    })();
  }, [ehAdmin]);

  if (!ehAdmin) {
    return (
      <main className="grid min-h-screen place-items-center px-4">
        <div className="max-w-sm rounded-2xl border border-slate-200 bg-white p-8 text-center shadow-sm">
          <h1 className="text-lg font-bold">Acesso restrito</h1>
          <p className="mt-2 text-sm text-slate-500">
            Esta área é exclusiva do administrador.
          </p>
          <Link
            href="/app"
            className="mt-5 inline-block rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white"
          >
            Voltar
          </Link>
        </div>
      </main>
    );
  }

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-10 flex h-14 items-center justify-between border-b border-slate-200 bg-white/95 px-5 backdrop-blur">
        <div className="flex items-center gap-2.5">
          <div className="grid h-8 w-8 place-items-center rounded-lg bg-gradient-to-br from-indigo-600 to-violet-600 text-xs font-bold text-white shadow-sm">
            A
          </div>
          <div className="leading-tight">
            <p className="text-sm font-bold tracking-tight">Painel do administrador</p>
            <p className="text-[11px] text-slate-500">{usuario?.email}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Link
            href="/app"
            className="inline-flex h-9 items-center rounded-lg border border-slate-200 bg-white px-3.5 text-sm font-medium text-slate-700 shadow-sm transition-colors hover:bg-slate-50"
          >
            Voltar ao app
          </Link>
          <button
            type="button"
            onClick={sair}
            className="inline-flex h-9 items-center rounded-lg border border-transparent px-3.5 text-sm font-medium text-slate-600 transition-colors hover:bg-slate-100"
          >
            Sair
          </button>
        </div>
      </header>

      <main className="mx-auto w-full max-w-6xl space-y-6 p-5">
        {carregando && <p className="text-sm text-slate-500">Carregando…</p>}
        {erro && (
          <p className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{erro}</p>
        )}

        {metricas && (
          <>
            <section className="grid gap-4 sm:grid-cols-3">
              <Cartao titulo="Clientes cadastrados" valor={metricas.total_clientes} />
              <Cartao titulo="Análises realizadas" valor={metricas.total_analises} />
              <Cartao titulo="Novos clientes no mês" valor={metricas.novos_clientes_mes} />
            </section>

            <section className="grid gap-4 sm:grid-cols-2">
              <CartaoDistribuicao
                titulo="Análises por estado (UF)"
                dados={metricas.por_uf}
              />
              <CartaoDistribuicao
                titulo="Análises por cidade"
                dados={metricas.por_cidade}
              />
            </section>

            <section className="rounded-2xl border border-slate-200 bg-white shadow-sm">
              <h2 className="border-b border-slate-100 px-4 py-3 text-sm font-semibold text-slate-700">
                Clientes
              </h2>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="text-[11px] uppercase tracking-wide text-slate-400">
                    <tr>
                      <th className="px-4 py-2 font-medium">E-mail</th>
                      <th className="px-4 py-2 font-medium">Cadastro</th>
                      <th className="px-4 py-2 font-medium">Análises</th>
                      <th className="px-4 py-2 font-medium">Cidades</th>
                      <th className="px-4 py-2 font-medium">UFs</th>
                    </tr>
                  </thead>
                  <tbody>
                    {clientes.map((c) => (
                      <tr key={c.id} className="border-t border-slate-100">
                        <td className="px-4 py-2">
                          {c.email}
                          {c.papel === "admin" && (
                            <span className="ml-2 rounded-full bg-indigo-100 px-2 py-0.5 text-[10px] font-medium text-indigo-700">
                              admin
                            </span>
                          )}
                        </td>
                        <td className="px-4 py-2 text-slate-500">
                          {new Date(c.criado_em).toLocaleDateString("pt-BR")}
                        </td>
                        <td className="px-4 py-2">{c.n_analises}</td>
                        <td className="px-4 py-2 text-slate-600">
                          {c.cidades.join(", ") || "—"}
                        </td>
                        <td className="px-4 py-2 text-slate-600">
                          {c.ufs.join(", ") || "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          </>
        )}

        {custos && <SecaoCustos c={custos} />}
      </main>
    </div>
  );
}

const brl = (v: number) =>
  v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

function SecaoCustos({ c }: { c: AdminCustos }) {
  const custoMedio =
    c.por_analise.length > 0
      ? c.por_analise.reduce((s, l) => s + l.custo_brl, 0) / c.por_analise.length
      : 0;
  return (
    <section className="space-y-4">
      <div className="flex items-baseline justify-between">
        <h2 className="text-sm font-semibold text-slate-700">
          Custo real de LLM (medido — tokens de verdade)
        </h2>
        <span className="text-[11px] text-slate-400">
          câmbio US$ {c.usd_brl.toLocaleString("pt-BR")} · {c.n_registros} chamadas
        </span>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <Cartao titulo="Custo total (R$)" valor={c.total_brl} moeda />
        <Cartao titulo="Análises medidas" valor={c.por_analise.length} />
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <p className="text-sm text-slate-500">Custo médio por análise</p>
          <p className="mt-1 text-3xl font-bold tracking-tight text-slate-900">
            {brl(custoMedio)}
          </p>
          <p className="mt-1 text-[11px] text-slate-400">Urbanismo IA + Jurídico</p>
        </div>
      </div>

      {c.avisos.length > 0 && (
        <div className="rounded-lg bg-amber-50 p-3 text-xs text-amber-900">
          {c.avisos.map((a) => (
            <p key={a}>{a}</p>
          ))}
        </div>
      )}

      {/* Uso da plataforma */}
      <div className="grid gap-4 sm:grid-cols-3">
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <p className="text-sm text-slate-500">Regenerações de urbanismo</p>
          <p className="mt-1 text-3xl font-bold tracking-tight text-slate-900">
            {c.total_regeneracoes.toLocaleString("pt-BR")}
          </p>
          <p className="mt-1 text-[11px] text-slate-400">
            média {c.media_regeneracoes_por_analise.toLocaleString("pt-BR")} por análise
          </p>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <p className="text-sm text-slate-500">Matrículas processadas</p>
          <p className="mt-1 text-3xl font-bold tracking-tight text-slate-900">
            {c.total_matriculas.toLocaleString("pt-BR")}
          </p>
          <p className="mt-1 text-[11px] text-slate-400">
            média {c.media_matriculas_por_analise.toLocaleString("pt-BR")} por KMZ/análise
          </p>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <p className="mb-2 text-sm font-semibold text-slate-700">
            Perfil de loteamento mais usado
          </p>
          {c.perfil_uso.length === 0 ? (
            <p className="text-sm text-slate-400">Sem dados ainda.</p>
          ) : (
            <ul className="space-y-1">
              {c.perfil_uso.map((p) => (
                <li key={p.rotulo} className="flex justify-between text-sm">
                  <span className="text-slate-600">{p.rotulo}</span>
                  <span className="font-semibold text-slate-900">{p.n}×</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {/* Custo e uso por cliente */}
      <div className="rounded-2xl border border-slate-200 bg-white shadow-sm">
        <h3 className="border-b border-slate-100 px-4 py-3 text-sm font-semibold text-slate-700">
          Custo e uso por cliente
        </h3>
        {c.por_cliente.length === 0 ? (
          <p className="px-4 py-3 text-sm text-slate-400">Sem medições ainda.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-[11px] uppercase tracking-wide text-slate-400">
                <tr>
                  <th className="px-4 py-2 font-medium">Cliente</th>
                  <th className="px-4 py-2 font-medium">Análises c/ IA</th>
                  <th className="px-4 py-2 font-medium">Regen. urbanismo</th>
                  <th className="px-4 py-2 font-medium">Matrículas</th>
                  <th className="px-4 py-2 text-right font-medium">Custo (R$)</th>
                  <th className="px-4 py-2 text-right font-medium">R$/análise</th>
                </tr>
              </thead>
              <tbody>
                {c.por_cliente.map((cl) => (
                  <tr key={cl.usuario_id} className="border-t border-slate-100">
                    <td className="px-4 py-2 text-slate-700">
                      {cl.email || cl.usuario_id.slice(0, 8)}
                    </td>
                    <td className="px-4 py-2 text-slate-600">{cl.n_analises_ia}</td>
                    <td className="px-4 py-2 text-slate-600">{cl.n_regeneracoes}</td>
                    <td className="px-4 py-2 text-slate-600">{cl.n_matriculas}</td>
                    <td className="px-4 py-2 text-right font-semibold text-slate-900">
                      {brl(cl.custo_brl)}
                    </td>
                    <td className="px-4 py-2 text-right text-slate-500">
                      {brl(cl.n_analises_ia > 0 ? cl.custo_brl / cl.n_analises_ia : 0)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <TabelaCusto titulo="Por dimensão" linhas={c.por_dimensao} />
        <TabelaCusto titulo="Por modelo" linhas={c.por_modelo} />
      </div>

      <TabelaCusto
        titulo="Por análise (Urbanismo IA + Jurídico)"
        linhas={c.por_analise}
        larga
      />
      <TabelaCusto
        titulo="LUOS por município (custo único, amortizado entre análises da cidade)"
        linhas={c.luos_por_municipio}
        larga
      />
    </section>
  );
}

function TabelaCusto({
  titulo,
  linhas,
  larga,
}: {
  titulo: string;
  linhas: { chave: string; chamadas: number; custo_brl: number; custo_usd: number }[];
  larga?: boolean;
}) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white shadow-sm">
      <h3 className="border-b border-slate-100 px-4 py-3 text-sm font-semibold text-slate-700">
        {titulo}
      </h3>
      {linhas.length === 0 ? (
        <p className="px-4 py-3 text-sm text-slate-400">Sem medições ainda.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="text-[11px] uppercase tracking-wide text-slate-400">
              <tr>
                <th className="px-4 py-2 font-medium">{larga ? "Chave" : "Item"}</th>
                <th className="px-4 py-2 font-medium">Chamadas</th>
                <th className="px-4 py-2 text-right font-medium">Custo (R$)</th>
                <th className="px-4 py-2 text-right font-medium">US$</th>
              </tr>
            </thead>
            <tbody>
              {linhas.map((l) => (
                <tr key={l.chave} className="border-t border-slate-100">
                  <td
                    className={`px-4 py-2 text-slate-700 ${larga ? "font-mono text-xs" : ""}`}
                  >
                    {larga ? l.chave : l.chave}
                  </td>
                  <td className="px-4 py-2 text-slate-600">{l.chamadas}</td>
                  <td className="px-4 py-2 text-right font-semibold text-slate-900">
                    {brl(l.custo_brl)}
                  </td>
                  <td className="px-4 py-2 text-right text-slate-500">
                    {l.custo_usd.toLocaleString("pt-BR", { maximumFractionDigits: 3 })}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function Cartao({
  titulo,
  valor,
  moeda,
}: {
  titulo: string;
  valor: number;
  moeda?: boolean;
}) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <p className="text-sm text-slate-500">{titulo}</p>
      <p className="mt-1 text-3xl font-bold tracking-tight text-slate-900">
        {moeda
          ? valor.toLocaleString("pt-BR", { style: "currency", currency: "BRL" })
          : valor.toLocaleString("pt-BR")}
      </p>
    </div>
  );
}

function CartaoDistribuicao({
  titulo,
  dados,
}: {
  titulo: string;
  dados: Record<string, number>;
}) {
  const itens = Object.entries(dados);
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <p className="mb-3 text-sm font-semibold text-slate-700">{titulo}</p>
      {itens.length === 0 ? (
        <p className="text-sm text-slate-400">Sem dados ainda.</p>
      ) : (
        <ul className="space-y-1.5">
          {itens.map(([k, v]) => (
            <li key={k} className="flex items-center justify-between text-sm">
              <span className="text-slate-600">{k}</span>
              <span className="font-semibold text-slate-900">{v}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
