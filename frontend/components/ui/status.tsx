import * as React from "react";

/* Badge de status no header de cada card de dimensão — o usuário vê de relance o que já
   foi analisado e onde há alerta, sem abrir o card. Ligado ao DADO REAL do card (§2: o
   front só rotula o que o backend devolveu; nenhum status é inferido por cálculo). */

const ESTILOS = {
  pendente: "border-slate-200 bg-slate-50 text-slate-500",
  ok: "border-emerald-200 bg-emerald-50 text-emerald-700",
  atencao: "border-amber-200 bg-amber-50 text-amber-800",
  alerta: "border-rose-200 bg-rose-50 text-rose-700",
} as const;

const ROTULO_PADRAO = {
  pendente: "pendente",
  ok: "analisado",
  atencao: "atenção",
  alerta: "alerta",
} as const;

export function StatusChip({
  estado,
  rotulo,
  className,
}: {
  estado: keyof typeof ESTILOS;
  rotulo?: string;
  className?: string;
}) {
  return (
    <span
      className={`inline-flex shrink-0 items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium ${ESTILOS[estado]} ${className ?? ""}`}
    >
      {estado === "ok" && (
        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
          <path d="M20 6L9 17l-5-5" />
        </svg>
      )}
      {(estado === "alerta" || estado === "atencao") && (
        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
          <path d="M12 9v4m0 4h.01M10.3 3.9L1.8 18a2 2 0 001.7 3h17a2 2 0 001.7-3L13.7 3.9a2 2 0 00-3.4 0z" />
        </svg>
      )}
      {rotulo ?? ROTULO_PADRAO[estado]}
    </span>
  );
}
