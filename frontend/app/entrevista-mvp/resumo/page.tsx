"use client";

// Consolidação das entrevistas do MVP — renderiza os AGREGADOS que o backend calcula
// (/api/entrevistas/resumo) e a lista individual (/api/entrevistas). O front não soma
// nada: só barras e tabelas sobre o JSON recebido. Admin-only nas duas pontas.

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { RequireAuth } from "@/components/auth/RequireAuth";
import { useAuth } from "@/components/auth/AuthProvider";
import {
  ESCOLHAS,
  REACOES,
  excluirEntrevista,
  listarEntrevistas,
  obterResumoEntrevistas,
  type Contagem,
  type Entrevista,
  type EntrevistaResumo,
  type TextoEntrevista,
} from "@/lib/entrevistas";

export default function PaginaResumo() {
  return (
    <RequireAuth>
      <Resumo />
    </RequireAuth>
  );
}

function Cartao({ titulo, children }: { titulo: string; children: React.ReactNode }) {
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <h2 className="text-sm font-bold uppercase tracking-wider text-slate-500">{titulo}</h2>
      <div className="mt-4">{children}</div>
    </section>
  );
}

function Barras({ dados }: { dados: Contagem[] }) {
  if (!dados.length) return <p className="text-sm text-slate-400">Sem respostas ainda.</p>;
  const maior = Math.max(...dados.map((d) => d.n));
  return (
    <ul className="space-y-2.5">
      {dados.map((d) => (
        <li key={d.rotulo}>
          <div className="flex items-baseline justify-between gap-3 text-sm">
            <span className="text-slate-700">{d.rotulo}</span>
            <span className="font-semibold text-slate-900">{d.n}</span>
          </div>
          <div className="mt-1 h-2 rounded-full bg-slate-100">
            <div
              className="h-2 rounded-full bg-slate-800"
              style={{ width: `${(d.n / maior) * 100}%` }}
            />
          </div>
        </li>
      ))}
    </ul>
  );
}

function Citacoes({ itens }: { itens: TextoEntrevista[] }) {
  if (!itens.length) return <p className="text-sm text-slate-400">Sem respostas ainda.</p>;
  return (
    <ul className="space-y-3">
      {itens.map((t, i) => (
        <li key={i} className="rounded-xl border border-slate-100 bg-slate-50 px-4 py-3">
          <p className="text-sm text-slate-800">“{t.texto}”</p>
          <p className="mt-1 text-xs text-slate-500">
            {t.nome || "sem nome"}
            {t.perfil ? ` · ${t.perfil}` : ""}
          </p>
        </li>
      ))}
    </ul>
  );
}

function CampoLido({ rotulo, valor }: { rotulo: string; valor: string | string[] }) {
  const texto = Array.isArray(valor) ? valor.join(", ") : valor;
  if (!texto) return null;
  return (
    <div>
      <dt className="text-xs font-semibold uppercase tracking-wide text-slate-400">{rotulo}</dt>
      <dd className="mt-0.5 whitespace-pre-wrap text-sm text-slate-800">{texto}</dd>
    </div>
  );
}

function Resumo() {
  const { usuario } = useAuth();
  const [resumo, setResumo] = useState<EntrevistaResumo | null>(null);
  const [lista, setLista] = useState<Entrevista[]>([]);
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(true);

  const ehAdmin = usuario?.papel === "admin";

  const carregar = useCallback(async () => {
    setCarregando(true);
    setErro(null);
    try {
      const [r, l] = await Promise.all([obterResumoEntrevistas(), listarEntrevistas()]);
      setResumo(r);
      setLista(l);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Falha ao carregar.");
    } finally {
      setCarregando(false);
    }
  }, []);

  useEffect(() => {
    if (ehAdmin) void carregar();
    else setCarregando(false);
  }, [ehAdmin, carregar]);

  async function excluir(e: Entrevista) {
    if (!window.confirm(`Excluir a entrevista de "${e.nome || "sem nome"}"?`)) return;
    try {
      await excluirEntrevista(e.id);
      await carregar();
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Falha ao excluir.");
    }
  }

  if (!ehAdmin) {
    return (
      <main className="grid min-h-screen place-items-center bg-slate-50 px-4">
        <div className="max-w-sm rounded-2xl border border-slate-200 bg-white p-8 text-center shadow-sm">
          <h1 className="text-lg font-bold">Acesso restrito</h1>
          <p className="mt-2 text-sm text-slate-500">
            O resumo das entrevistas é exclusivo do administrador.
          </p>
        </div>
      </main>
    );
  }

  const perfisComEscolha = Object.keys(resumo?.escolha_por_perfil ?? {});

  return (
    <main className="min-h-screen bg-slate-50 pb-16">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-3 px-5 py-4">
          <div>
            <h1 className="text-lg font-bold text-slate-900">
              Entrevistas do MVP · consolidação
            </h1>
            <p className="text-xs text-slate-500">
              {resumo ? `${resumo.total} entrevista(s) registrada(s)` : "…"}
            </p>
          </div>
          <div className="flex gap-2">
            <button
              onClick={carregar}
              className="rounded-lg border border-slate-300 px-3.5 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-500"
            >
              Atualizar
            </button>
            <Link
              href="/entrevista-mvp"
              className="rounded-lg bg-slate-900 px-3.5 py-2 text-sm font-semibold text-white transition hover:bg-slate-700"
            >
              Nova entrevista
            </Link>
          </div>
        </div>
      </header>

      <div className="mx-auto mt-6 max-w-5xl space-y-5 px-5">
        {erro && (
          <p className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {erro}
          </p>
        )}
        {carregando && <p className="text-sm text-slate-500">Carregando…</p>}

        {resumo && !carregando && (
          <>
            <div className="grid gap-5 md:grid-cols-2">
              <Cartao titulo="Qual plano escolheria hoje (a escolha é o dado)">
                <Barras dados={resumo.escolhas} />
              </Cartao>
              <Cartao titulo="Perfil dos entrevistados">
                <Barras dados={resumo.por_perfil} />
              </Cartao>
              <Cartao titulo="Glebas avaliadas por ano">
                <Barras dados={resumo.por_glebas_ano} />
              </Cartao>
              <Cartao titulo="A cota (12/30) cobre o volume?">
                <Barras dados={resumo.cota_cobre} />
              </Cartao>
            </div>

            <Cartao titulo="Escolha de plano por perfil">
              {perfisComEscolha.length === 0 ? (
                <p className="text-sm text-slate-400">Sem respostas ainda.</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[560px] text-sm">
                    <thead>
                      <tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-400">
                        <th className="py-2 pr-4">Perfil</th>
                        {ESCOLHAS.map((e) => (
                          <th key={e} className="px-3 py-2 text-center">
                            {e}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {perfisComEscolha.map((p) => (
                        <tr key={p} className="border-b border-slate-100 last:border-0">
                          <td className="py-2.5 pr-4 font-medium text-slate-800">{p}</td>
                          {ESCOLHAS.map((e) => {
                            const n = resumo.escolha_por_perfil[p]?.[e] ?? 0;
                            return (
                              <td
                                key={e}
                                className={`px-3 py-2.5 text-center ${
                                  n ? "font-bold text-slate-900" : "text-slate-300"
                                }`}
                              >
                                {n || "·"}
                              </td>
                            );
                          })}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Cartao>

            <Cartao titulo="Reação aos planos pagos">
              <div className="grid gap-5 sm:grid-cols-3">
                {Object.entries(resumo.reacoes).map(([plano, contagens]) => (
                  <div key={plano}>
                    <p className="mb-2 text-sm font-semibold text-slate-800">{plano}</p>
                    <Barras
                      dados={REACOES.map((r) => ({ rotulo: r, n: contagens[r] ?? 0 })).filter(
                        (d) => d.n > 0,
                      )}
                    />
                  </div>
                ))}
              </div>
            </Cartao>

            <div className="grid gap-5 md:grid-cols-2">
              <Cartao titulo="Funcionalidades que mais gostou">
                <Barras dados={resumo.mais_gostou} />
              </Cartao>
              <Cartao titulo="Pagaria para manter">
                <Barras dados={resumo.pagaria_manter} />
              </Cartao>
            </div>

            <Cartao titulo="Calibragem de preço (caro a partir de · barato a ponto de desconfiar)">
              {resumo.precos.length === 0 ? (
                <p className="text-sm text-slate-400">Sem respostas ainda.</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[480px] text-sm">
                    <thead>
                      <tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-400">
                        <th className="py-2 pr-4">Entrevistado</th>
                        <th className="px-3 py-2">Perfil</th>
                        <th className="px-3 py-2">Fica caro</th>
                        <th className="px-3 py-2">Barato demais</th>
                      </tr>
                    </thead>
                    <tbody>
                      {resumo.precos.map((p, i) => (
                        <tr key={i} className="border-b border-slate-100 last:border-0">
                          <td className="py-2.5 pr-4 font-medium text-slate-800">
                            {p.nome || "sem nome"}
                          </td>
                          <td className="px-3 py-2.5 text-slate-600">{p.perfil}</td>
                          <td className="px-3 py-2.5 text-slate-800">{p.caro}</td>
                          <td className="px-3 py-2.5 text-slate-800">{p.barato}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Cartao>

            <div className="grid gap-5 md:grid-cols-2">
              <Cartao titulo="O que travou (hipótese do Pacote 5)">
                <Citacoes itens={resumo.travas} />
              </Cartao>
              <Cartao titulo="Desconto de fundador">
                <Barras dados={resumo.desconto_fundador} />
              </Cartao>
              <Cartao titulo="Funcionalidades que sentiram falta">
                <Citacoes itens={resumo.sentiu_falta} />
              </Cartao>
              <Cartao titulo="Dificuldades no uso">
                <Citacoes itens={resumo.dificuldades} />
              </Cartao>
            </div>

            <Cartao titulo="O que passaram a conseguir (ouro para copy)">
              <Citacoes itens={resumo.capacidades} />
            </Cartao>

            <Cartao titulo={`Respostas individuais (${lista.length})`}>
              {lista.length === 0 ? (
                <p className="text-sm text-slate-400">Nenhuma entrevista registrada.</p>
              ) : (
                <div className="space-y-3">
                  {lista.map((e) => (
                    <details
                      key={e.id}
                      className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3"
                    >
                      <summary className="cursor-pointer list-none text-sm font-semibold text-slate-800 marker:hidden">
                        {e.nome || "sem nome"}
                        <span className="ml-2 font-normal text-slate-500">
                          {e.perfil}
                          {e.escolha ? ` · escolheu: ${e.escolha}` : ""} ·{" "}
                          {new Date(e.ts).toLocaleDateString("pt-BR")}
                        </span>
                      </summary>
                      <dl className="mt-3 space-y-2.5 border-t border-slate-200 pt-3">
                        <CampoLido rotulo="Canal" valor={e.canal} />
                        <CampoLido rotulo="Entrevistador" valor={e.entrevistador} />
                        <CampoLido rotulo="Última gleba sem a plataforma" valor={e.ultima_gleba} />
                        <CampoLido rotulo="Glebas por ano" valor={e.glebas_ano} />
                        <CampoLido rotulo="Confiança nas análises" valor={e.confianca} />
                        <CampoLido rotulo="Se sumisse amanhã" valor={e.sumisse_amanha} />
                        <CampoLido rotulo="Mais gostou" valor={e.mais_gostou} />
                        <CampoLido rotulo="Passou a conseguir" valor={e.capacidade_nova} />
                        <CampoLido rotulo="Dificuldades" valor={e.dificuldades} />
                        <CampoLido rotulo="Sentiu falta" valor={e.sentiu_falta} />
                        <CampoLido rotulo="Pagaria para manter" valor={e.pagaria_manter} />
                        <CampoLido rotulo="Fica caro a partir de" valor={e.preco_caro} />
                        <CampoLido rotulo="Barato a ponto de desconfiar" valor={e.preco_barato} />
                        <CampoLido rotulo="Reação Pacote 5" valor={e.reacao_pacote5} />
                        <CampoLido rotulo="Reação Semestral" valor={e.reacao_semestral} />
                        <CampoLido rotulo="Reação Anual" valor={e.reacao_anual} />
                        <CampoLido rotulo="O que travou" valor={e.travou_motivo} />
                        <CampoLido rotulo="Cota cobre o volume" valor={e.cota_cobre} />
                        <CampoLido rotulo="Desconto de fundador" valor={e.desconto_fundador} />
                        <CampoLido rotulo="Indicações" valor={e.indicacoes} />
                        <CampoLido rotulo="Observações" valor={e.observacoes} />
                      </dl>
                      <button
                        onClick={() => excluir(e)}
                        className="mt-3 text-xs font-medium text-red-600 underline-offset-2 hover:underline"
                      >
                        Excluir este registro
                      </button>
                    </details>
                  ))}
                </div>
              )}
            </Cartao>
          </>
        )}
      </div>
    </main>
  );
}
