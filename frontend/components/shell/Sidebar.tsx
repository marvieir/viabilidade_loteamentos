"use client";

import { SECOES, type Secao } from "@/components/shell/secoes";

export function Sidebar({
  secao,
  onSecao,
  alertas,
  perfilConfirmado,
}: {
  secao: Secao;
  onSecao: (s: Secao) => void;
  alertas?: number; // badge no item Ambiental
  perfilConfirmado?: boolean;
}) {
  return (
    <aside className="sticky top-16 hidden h-[calc(100vh-4rem)] w-60 shrink-0 border-r border-slate-200 bg-white p-3 md:block">
      <p className="px-3 pb-2 pt-1 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
        Análise
      </p>
      <nav className="space-y-1 text-sm">
        {SECOES.map(({ id, rotulo, Icone }) => {
          const ativo = secao === id;
          return (
            <button
              key={id}
              type="button"
              onClick={() => onSecao(id)}
              className={`flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left transition-colors ${
                ativo
                  ? "bg-slate-900 font-medium text-white"
                  : "text-slate-600 hover:bg-slate-100"
              }`}
            >
              <Icone className={ativo ? "text-white" : "text-slate-400"} width={17} height={17} />
              <span className="truncate">{rotulo}</span>
              {id === "ambiental" && alertas ? (
                <span className="ml-auto rounded-full bg-rose-100 px-1.5 text-[11px] font-semibold text-rose-700">
                  {alertas}
                </span>
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
