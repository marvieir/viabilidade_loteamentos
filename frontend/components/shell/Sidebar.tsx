"use client";

import { SECOES, type Secao } from "@/components/shell/secoes";

export function Sidebar({
  secao,
  onSecao,
  alertas,
  perfilConfirmado,
  statusSec,
}: {
  secao: Secao;
  onSecao: (s: Secao) => void;
  alertas?: number; // badge no item Ambiental
  perfilConfirmado?: boolean;
  // #3 — progresso do "Analisar tudo": âmbar pulsando (analisando) → verde (concluído).
  statusSec?: Record<string, "analisando" | "ok" | "erro">;
}) {
  return (
    <aside className="sticky top-16 hidden h-[calc(100vh-4rem)] w-60 shrink-0 border-r border-slate-200 bg-white p-3 md:block">
      <p className="px-3 pb-2 pt-1 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
        Análise
      </p>
      <nav className="space-y-1 text-sm">
        {SECOES.map(({ id, rotulo, Icone, sub }) => {
          const ativo = secao === id;
          return (
            <button
              key={id}
              type="button"
              onClick={() => onSecao(id)}
              className={`flex w-full items-center gap-3 rounded-lg py-2 text-left transition-colors ${
                sub ? "ml-3 border-l border-slate-200 pl-4 pr-3" : "px-3"
              } ${
                ativo
                  ? "bg-slate-900 font-medium text-white"
                  : "text-slate-600 hover:bg-slate-100"
              }`}
            >
              <Icone
                className={ativo ? "text-white" : "text-slate-400"}
                width={sub ? 15 : 17}
                height={sub ? 15 : 17}
              />
              <span className="truncate">{rotulo}</span>
              {id === "ambiental" && alertas ? (
                <span className="ml-auto rounded-full bg-rose-100 px-1.5 text-[11px] font-semibold text-rose-700">
                  {alertas}
                </span>
              ) : null}
              {/* #3 — ponto de progresso: âmbar pulsando = analisando; verde = concluído. */}
              {statusSec?.[id] === "analisando" ? (
                <span className="ml-auto h-2 w-2 shrink-0 animate-pulse rounded-full bg-amber-400" />
              ) : statusSec?.[id] === "ok" ? (
                <span className="ml-auto h-2 w-2 shrink-0 rounded-full bg-emerald-500" />
              ) : statusSec?.[id] === "erro" ? (
                <span className="ml-auto h-2 w-2 shrink-0 rounded-full bg-rose-500" />
              ) : null}
            </button>
          );
        })}
      </nav>

      <div className="mt-6 rounded-xl border border-slate-200 bg-slate-50 p-3">
        <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
          Diretriz municipal
        </p>
        <p className="mt-1 text-xs text-slate-600">
          {perfilConfirmado ? (
            <>
              Perfil LUOS{" "}
              <span className="font-semibold text-emerald-700">confirmado</span> —
              alimentando o cálculo com doação e lote legal.
            </>
          ) : (
            <>
              Sem perfil municipal confirmado. O cálculo usa o teto físico (sem doação)
              até a LUOS ser confirmada.
            </>
          )}
        </p>
      </div>
    </aside>
  );
}
