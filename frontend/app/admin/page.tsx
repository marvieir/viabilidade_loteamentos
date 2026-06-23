"use client";

// Fase 12.3 — painel admin (cards). Protegido: exige login E papel admin. O backend
// também barra (requer_admin); aqui é só a UX (não confiar só no front para autorizar).

import { useEffect, useState } from "react";
import Link from "next/link";
import { RequireAuth } from "@/components/auth/RequireAuth";
import { useAuth } from "@/components/auth/AuthProvider";
import {
  listarClientes,
  obterMetricas,
  type AdminCliente,
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
        const [m, c] = await Promise.all([obterMetricas(), listarClientes()]);
        setMetricas(m);
        setClientes(c);
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
            href="/"
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
      <header className="sticky top-0 z-10 flex h-16 items-center justify-between border-b border-slate-200 bg-white/90 px-5 backdrop-blur">
        <div>
          <p className="text-sm font-bold">Painel do administrador</p>
          <p className="text-[11px] text-slate-500">{usuario?.email}</p>
        </div>
        <div className="flex items-center gap-2">
          <Link
            href="/"
            className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            App
          </Link>
          <button
            type="button"
            onClick={sair}
            className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
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
      </main>
    </div>
  );
}

function Cartao({ titulo, valor }: { titulo: string; valor: number }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <p className="text-sm text-slate-500">{titulo}</p>
      <p className="mt-1 text-3xl font-bold tracking-tight text-slate-900">
        {valor.toLocaleString("pt-BR")}
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
