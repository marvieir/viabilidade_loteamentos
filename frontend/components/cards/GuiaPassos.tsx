"use client";

// Fase UX-3 — guia de pré-requisitos (spec: docs/fase-ux-onboarding.md).
// Mesmo desenho do stepper da Financeira, mas guiado por
// ESTADO derivado (não por navegação): cada item mostra se o pré-requisito está pronto,
// pendente ou é opcional — o usuário vê de relance o que falta e o que melhora o
// resultado. Apresentação pura; o estado vem do card (que já conhece seus insumos).

export type EstadoPasso = "ok" | "atencao" | "pendente" | "opcional";

export interface PassoGuia {
  rotulo: string;
  estado: EstadoPasso;
  detalhe?: string; // 1 linha em linguagem de usuário (o que fazer / o que está valendo)
}

const COR_BOLA: Record<EstadoPasso, string> = {
  ok: "bg-emerald-500 text-white",
  atencao: "bg-amber-400 text-white",
  pendente: "border border-slate-200 bg-white text-slate-400",
  opcional: "border border-slate-200 bg-white text-slate-400",
};

export function GuiaPassos({ passos, className = "" }: { passos: PassoGuia[]; className?: string }) {
  return (
    <ol className={`space-y-2 rounded-xl border border-slate-100 bg-slate-50/60 p-3 ${className}`}>
      {passos.map((p, i) => (
        <li key={p.rotulo} className="flex items-start gap-2.5">
          <span
            className={`mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full text-[10px] font-bold ${COR_BOLA[p.estado]}`}
          >
            {p.estado === "ok" ? (
              <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3.5">
                <path d="M20 6L9 17l-5-5" />
              </svg>
            ) : (
              i + 1
            )}
          </span>
          <div className="min-w-0 text-sm leading-snug">
            <span className="font-medium text-slate-700">{p.rotulo}</span>
            {p.estado === "opcional" && (
              <span className="ml-1.5 rounded-full border border-slate-200 bg-white px-1.5 py-0.5 text-[10px] text-slate-400">
                opcional
              </span>
            )}
            {p.detalhe && <p className="text-xs text-slate-500">{p.detalhe}</p>}
          </div>
        </li>
      ))}
    </ol>
  );
}
