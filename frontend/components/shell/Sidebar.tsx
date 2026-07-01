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
    <aside className="sticky top-14 hidden h-[calc(100vh-3.5rem)] w-56 shrink-0 flex-col border-r border-slate-200 bg-white md:flex">
      <nav className="flex-1 space-y-0.5 overflow-y-auto px-2.5 py-3 text-sm">
        <p className="px-2.5 pb-1.5 text-[10px] font-semibold uppercase tracking-widest text-slate-400">
          Análise
        </p>
        {SECOES.map(({ id, rotulo, Icone, sub }) => {
          const ativo = secao === id;
          return (
            <button
              key={id}
              type="button"
              onClick={() => onSecao(id)}
              className={`group relative flex w-full items-center gap-2.5 rounded-lg py-1.5 text-left transition-colors ${
                sub ? "ml-3 w-[calc(100%-0.75rem)] pl-3 pr-2" : "px-2.5"
              } ${
                ativo
                  ? "bg-indigo-50 font-medium text-indigo-700"
                  : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
              }`}
            >
              {/* barra de acento do item ativo (padrão de produto profissional) */}
              {ativo && (
                <span className="absolute -left-0.5 top-1/2 h-4 w-0.5 -translate-y-1/2 rounded-full bg-indigo-600" />
              )}
              <Icone
                className={ativo ? "text-indigo-600" : "text-slate-400 group-hover:text-slate-500"}
                width={sub ? 14 : 16}
                height={sub ? 14 : 16}
              />
              <span className="truncate">{rotulo}</span>
              {id === "ambiental" && alertas ? (
                <span className="ml-auto rounded-full bg-rose-100 px-1.5 text-[10px] font-semibold leading-4 text-rose-700">
                  {alertas}
                </span>
              ) : null}
              {/* progresso: âmbar pulsando = analisando; verde = concluído. */}
              {statusSec?.[id] === "analisando" ? (
                <span className="ml-auto h-1.5 w-1.5 shrink-0 animate-pulse rounded-full bg-amber-400" />
              ) : statusSec?.[id] === "ok" ? (
                <span className="ml-auto h-1.5 w-1.5 shrink-0 rounded-full bg-emerald-500" />
              ) : statusSec?.[id] === "erro" ? (
                <span className="ml-auto h-1.5 w-1.5 shrink-0 rounded-full bg-rose-500" />
              ) : null}
            </button>
          );
        })}
      </nav>

      <div className="border-t border-slate-100 p-3">
        <div className="rounded-lg bg-slate-50 p-2.5">
          <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-400">
            Diretriz municipal
          </p>
          <p className="mt-1 text-[11px] leading-snug text-slate-600">
            {perfilConfirmado ? (
              <>
                Perfil LUOS{" "}
                <span className="font-semibold text-emerald-700">confirmado</span> —
                alimentando doação e lote legal.
              </>
            ) : (
              <>
                Sem perfil confirmado — o cálculo usa o teto físico até a LUOS ser
                confirmada.
              </>
            )}
          </p>
        </div>
      </div>
    </aside>
  );
}
