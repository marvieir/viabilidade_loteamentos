"use client";

// Fase UX-1 — Trilha da Análise (spec: docs/fase-ux-onboarding.md). Barra compacta com o
// progresso + painel expansível com os 6 passos. O ESTADO vem pronto do backend
// (GET /analises/{id}/trilha) — aqui só se renderiza e navega (regra inegociável).
// Trilha SUGERIDA: nada trava; o painel abre sozinho nas 2 primeiras análises da conta
// (contador local, heurística de interface).

import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/auth";
import type { Secao } from "@/components/shell/secoes";

interface TrilhaPasso {
  id: string;
  titulo: string;
  estado: "concluido" | "disponivel" | "atencao" | "pendente";
  motivo: string;
  cobertura?: string | null;
}

interface Trilha {
  passo_atual: string;
  passos: TrilhaPasso[];
}

// Para onde cada passo leva no workspace (navegação por seção).
const SECAO_DO_PASSO: Record<string, Secao> = {
  gleba: "visao",
  diretrizes: "luos",
  ambiental: "ambiental",
  urbanismo: "urbanismo",
  juridico: "juridico",
  financeira: "financeira",
};

const COR_BOLINHA: Record<TrilhaPasso["estado"], string> = {
  concluido: "bg-emerald-500",
  disponivel: "bg-indigo-400",
  atencao: "bg-amber-400",
  pendente: "bg-slate-300",
};

const ROTULO_ESTADO: Record<TrilhaPasso["estado"], string> = {
  concluido: "Concluído",
  disponivel: "Disponível",
  atencao: "Atenção",
  pendente: "Falta insumo",
};

const COR_ETIQUETA: Record<TrilhaPasso["estado"], string> = {
  concluido: "bg-emerald-50 text-emerald-700 border-emerald-200",
  disponivel: "bg-indigo-50 text-indigo-700 border-indigo-200",
  atencao: "bg-amber-50 text-amber-800 border-amber-200",
  pendente: "bg-slate-50 text-slate-500 border-slate-200",
};

function abrirAutomatico(): boolean {
  try {
    const n = Number(localStorage.getItem("trilha_analises_vistas") ?? "0");
    if (n < 2) {
      localStorage.setItem("trilha_analises_vistas", String(n + 1));
      return true;
    }
  } catch {
    /* storage indisponível → não abre sozinho */
  }
  return false;
}

export function TrilhaAnalise({
  analiseId,
  sinal,
  onIr,
}: {
  analiseId: string;
  sinal: number; // muda quando "Analisar tudo" roda → refetch
  onIr: (secao: Secao) => void;
}) {
  const [trilha, setTrilha] = useState<Trilha | null>(null);
  const [aberto, setAberto] = useState(false);

  const carregar = useCallback(async () => {
    try {
      const r = await apiFetch(`/api/analises/${analiseId}/trilha`);
      if (r.ok) setTrilha(await r.json());
    } catch {
      /* trilha é orientação — falha de rede não pode quebrar o workspace */
    }
  }, [analiseId]);

  useEffect(() => {
    carregar();
  }, [carregar, sinal]);

  // Abre sozinho só nas 2 primeiras análises (decisão da spec) — uma vez por análise.
  useEffect(() => {
    if (abrirAutomatico()) setAberto(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [analiseId]);

  if (!trilha) return null;

  const idx = trilha.passos.findIndex((p) => p.id === trilha.passo_atual);
  const concluidos = trilha.passos.filter((p) => p.estado === "concluido").length;
  const atual = trilha.passos[idx >= 0 ? idx : 0];
  const completa = concluidos === trilha.passos.length;

  return (
    <div className="rounded-xl border border-slate-200 bg-white shadow-sm">
      {/* Barra compacta — sempre visível; clique expande */}
      <button
        type="button"
        onClick={() => {
          setAberto((v) => !v);
          if (!aberto) carregar(); // painel abrindo → estado fresco
        }}
        className="flex w-full items-center justify-between gap-3 px-4 py-2.5 text-left"
      >
        <div className="flex min-w-0 items-center gap-3">
          <span className="shrink-0 text-sm font-semibold text-slate-700">
            Trilha da análise
          </span>
          <span className="hidden truncate text-sm text-slate-500 sm:block">
            {completa
              ? "todos os passos concluídos"
              : `próximo: ${atual.titulo.toLowerCase()}`}
          </span>
        </div>
        <div className="flex shrink-0 items-center gap-3">
          <div className="flex items-center gap-1.5">
            {trilha.passos.map((p) => (
              <span
                key={p.id}
                title={`${p.titulo} — ${ROTULO_ESTADO[p.estado]}`}
                className={`h-2.5 w-2.5 rounded-full ${COR_BOLINHA[p.estado]}`}
              />
            ))}
          </div>
          <span className="text-xs font-medium text-slate-500">
            {concluidos}/{trilha.passos.length}
          </span>
          <svg
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.5"
            className={`text-slate-400 transition-transform ${aberto ? "rotate-180" : ""}`}
          >
            <path d="M6 9l6 6 6-6" />
          </svg>
        </div>
      </button>

      {/* Painel expandido — os 6 passos com estado, motivo e ação */}
      {aberto && (
        <ol className="space-y-1 border-t border-slate-100 p-3">
          {trilha.passos.map((p, i) => {
            const ativo = p.id === trilha.passo_atual;
            return (
              <li
                key={p.id}
                className={`flex items-start gap-3 rounded-lg p-2.5 ${
                  ativo ? "bg-indigo-50/60" : ""
                }`}
              >
                <span
                  className={`mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-full text-[11px] font-bold ${
                    p.estado === "concluido"
                      ? "bg-emerald-500 text-white"
                      : `border ${COR_ETIQUETA[p.estado]}`
                  }`}
                >
                  {p.estado === "concluido" ? "✓" : i + 1}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="text-sm font-semibold text-slate-800">{p.titulo}</p>
                    <span
                      className={`rounded-full border px-2 py-0.5 text-[10px] font-medium ${COR_ETIQUETA[p.estado]}`}
                    >
                      {ROTULO_ESTADO[p.estado]}
                    </span>
                  </div>
                  <p className="mt-0.5 text-xs leading-relaxed text-slate-500">{p.motivo}</p>
                </div>
                {p.estado !== "concluido" && SECAO_DO_PASSO[p.id] && (
                  <button
                    type="button"
                    onClick={() => onIr(SECAO_DO_PASSO[p.id])}
                    className="shrink-0 rounded-lg border border-slate-200 px-2.5 py-1 text-xs font-semibold text-slate-600 transition-colors hover:bg-slate-50"
                  >
                    Abrir
                  </button>
                )}
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}
