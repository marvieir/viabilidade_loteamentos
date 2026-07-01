"use client";

// Fase 12.2 — workspace "Minhas análises": grid de cards com MINIATURA da gleba (silhueta
// vinda do backend — o front só desenha os pontos, §2), busca, skeleton e empty-state.
// Carregar reidrata a gleba e devolve o objeto Analise (mesmo shape do upload).

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  carregarAnalise,
  excluirAnalise,
  listarSalvas,
  type AnaliseResumo,
} from "@/lib/salvas";
import type { Analise } from "@/lib/api";
import { Button } from "@/components/ui/button";

function dataRelativa(iso: string): string {
  const dias = Math.floor((Date.now() - new Date(iso).getTime()) / 86_400_000);
  if (dias <= 0) return "hoje";
  if (dias === 1) return "ontem";
  if (dias < 30) return `há ${dias} dias`;
  return new Date(iso).toLocaleDateString("pt-BR");
}

/* Miniatura da gleba: desenha os anéis normalizados (0..100) que o backend mandou. */
function ThumbGleba({ aneis }: { aneis?: number[][][] | null }) {
  if (!aneis || aneis.length === 0) {
    return (
      <div className="grid h-16 w-16 shrink-0 place-items-center rounded-lg bg-slate-100 text-slate-300">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
          <path d="M9 20l-5.4-2.7a1 1 0 01-.6-.9V4.6a1 1 0 011.4-.9L9 6l6-2 5.4 2.7a1 1 0 01.6.9v11.8a1 1 0 01-1.4.9L15 18l-6 2z" />
        </svg>
      </div>
    );
  }
  const d = aneis
    .map((anel) => "M" + anel.map(([x, y]) => `${x},${y}`).join(" L") + " Z")
    .join(" ");
  return (
    <div className="grid h-16 w-16 shrink-0 place-items-center rounded-lg border border-indigo-100 bg-indigo-50/60">
      <svg viewBox="0 0 100 100" className="h-14 w-14">
        <path
          d={d}
          fill="rgba(79,70,229,0.14)"
          stroke="#4f46e5"
          strokeWidth="2.5"
          strokeLinejoin="round"
          fillRule="evenodd"
        />
      </svg>
    </div>
  );
}

function Skeleton() {
  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
      {[0, 1, 2].map((i) => (
        <div key={i} className="flex animate-pulse gap-3 rounded-xl border border-slate-200 bg-white p-4">
          <div className="h-16 w-16 rounded-lg bg-slate-100" />
          <div className="flex-1 space-y-2 py-1">
            <div className="h-3.5 w-2/3 rounded bg-slate-100" />
            <div className="h-3 w-1/2 rounded bg-slate-100" />
            <div className="h-3 w-1/3 rounded bg-slate-100" />
          </div>
        </div>
      ))}
    </div>
  );
}

export function MinhasAnalises({
  onCarregar,
  recarregar,
}: {
  onCarregar: (a: Analise, salvaId: string) => void;
  recarregar?: number; // muda o valor → força refetch (ex.: após salvar)
}) {
  const [itens, setItens] = useState<AnaliseResumo[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState<string | null>(null);
  const [ocupadoId, setOcupadoId] = useState<string | null>(null);
  const [busca, setBusca] = useState("");

  const buscar = useCallback(async () => {
    setCarregando(true);
    setErro(null);
    try {
      setItens(await listarSalvas());
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Falha ao listar.");
    } finally {
      setCarregando(false);
    }
  }, []);

  useEffect(() => {
    buscar();
  }, [buscar, recarregar]);

  const filtrados = useMemo(() => {
    const q = busca.trim().toLowerCase();
    if (!q) return itens;
    return itens.filter((a) =>
      `${a.titulo} ${a.cidade ?? ""} ${a.uf ?? ""}`.toLowerCase().includes(q)
    );
  }, [itens, busca]);

  async function abrir(id: string) {
    setOcupadoId(id);
    try {
      const analise = await carregarAnalise(id);
      onCarregar(analise, id);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Falha ao carregar.");
    } finally {
      setOcupadoId(null);
    }
  }

  async function remover(id: string, titulo: string) {
    if (!confirm(`Excluir a análise "${titulo}"? Esta ação não pode ser desfeita.`)) return;
    setOcupadoId(id);
    try {
      await excluirAnalise(id);
      setItens((xs) => xs.filter((x) => x.id !== id));
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Falha ao excluir.");
    } finally {
      setOcupadoId(null);
    }
  }

  return (
    <div className="space-y-3">
      {/* Toolbar: título + contagem + busca */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-500">
          Minhas análises
          {!carregando && (
            <span className="ml-2 rounded-full bg-slate-200/80 px-2 py-0.5 text-[11px] font-semibold text-slate-600">
              {itens.length}
            </span>
          )}
        </h2>
        {itens.length > 3 && (
          <input
            value={busca}
            onChange={(e) => setBusca(e.target.value)}
            placeholder="Buscar por título ou cidade…"
            className="h-9 w-64 rounded-lg border border-slate-200 bg-white px-3 text-sm placeholder:text-slate-400 focus:border-indigo-300 focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
          />
        )}
      </div>

      {erro && (
        <p className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{erro}</p>
      )}

      {carregando ? (
        <Skeleton />
      ) : itens.length === 0 ? (
        <div className="grid place-items-center rounded-xl border border-dashed border-slate-300 bg-white/60 px-6 py-12 text-center">
          <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" strokeWidth="1.5">
            <path d="M9 20l-5.4-2.7a1 1 0 01-.6-.9V4.6a1 1 0 011.4-.9L9 6l6-2 5.4 2.7a1 1 0 01.6.9v11.8a1 1 0 01-1.4.9L15 18l-6 2z" />
          </svg>
          <p className="mt-3 text-sm font-medium text-slate-700">Nenhuma análise salva ainda</p>
          <p className="mt-1 max-w-xs text-xs text-slate-500">
            Envie o KMZ de uma gleba acima e clique em “Salvar” para guardá-la aqui — com
            urbanismo, jurídico e financeiro preservados.
          </p>
        </div>
      ) : filtrados.length === 0 ? (
        <p className="px-1 text-sm text-slate-500">Nada encontrado para “{busca}”.</p>
      ) : (
        <ul className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {filtrados.map((a) => (
            <li key={a.id}>
              <div
                role="button"
                tabIndex={0}
                onClick={() => ocupadoId === null && abrir(a.id)}
                onKeyDown={(e) => e.key === "Enter" && ocupadoId === null && abrir(a.id)}
                className={`group flex h-full cursor-pointer gap-3 rounded-xl border bg-white p-4 text-left shadow-sm transition-all ${
                  ocupadoId === a.id
                    ? "border-indigo-300 opacity-70"
                    : "border-slate-200 hover:-translate-y-0.5 hover:border-indigo-300 hover:shadow-md"
                }`}
              >
                <ThumbGleba aneis={a.silhueta} />
                <div className="flex min-w-0 flex-1 flex-col">
                  <p className="truncate font-semibold text-slate-800" title={a.titulo}>
                    {a.titulo}
                  </p>
                  <p className="mt-0.5 truncate text-[13px] text-slate-500">
                    {[a.cidade, a.uf].filter(Boolean).join(" / ") || "Jurisdição não informada"}
                    {a.area_ha != null && (
                      <span className="font-medium text-slate-600">
                        {" "}· {a.area_ha.toLocaleString("pt-BR")} ha
                      </span>
                    )}
                  </p>
                  <p className="mt-0.5 text-[11px] text-slate-400" title={new Date(a.atualizada_em).toLocaleString("pt-BR")}>
                    Atualizada {dataRelativa(a.atualizada_em)}
                  </p>
                  <div className="mt-auto flex items-center gap-2 pt-2.5">
                    <Button
                      size="sm"
                      onClick={(e) => {
                        e.stopPropagation();
                        abrir(a.id);
                      }}
                      disabled={ocupadoId !== null}
                    >
                      {ocupadoId === a.id ? "Abrindo…" : "Abrir"}
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      className="text-slate-400 hover:bg-rose-50 hover:text-rose-600"
                      onClick={(e) => {
                        e.stopPropagation();
                        remover(a.id, a.titulo);
                      }}
                      disabled={ocupadoId !== null}
                    >
                      Excluir
                    </Button>
                  </div>
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
