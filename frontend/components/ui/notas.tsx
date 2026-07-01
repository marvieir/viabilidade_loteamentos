"use client";

/* Avisos dos cards SEM roubar tela: alertas CRÍTICOS ficam sempre visíveis (âmbar);
   as notas de metodologia/disclaimer (a maioria, e estáticas) ficam colapsadas num
   <details> ("Notas e metodologia (N)"). Progressive disclosure — o essencial primeiro. */

const CRITICO =
  /ATENÇÃO|PÓRTICO|INDISPON|FALHOU|NÃO FOI|NENHUM|LIMITE|REGENERE|CONFIRME O ACESSO|SEM VIA/i;

export function Notas({
  itens,
  titulo = "Notas e metodologia",
}: {
  itens: string[];
  titulo?: string;
}) {
  if (!itens || itens.length === 0) return null;
  const criticos = itens.filter((a) => CRITICO.test(a));
  const notas = itens.filter((a) => !CRITICO.test(a));
  return (
    <div className="space-y-2">
      {criticos.length > 0 && (
        <div className="space-y-1 rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
          {criticos.map((a) => (
            <p key={a}>⚠ {a}</p>
          ))}
        </div>
      )}
      {notas.length > 0 && (
        <details className="group rounded-lg border border-slate-200 bg-slate-50/60">
          <summary className="flex cursor-pointer select-none items-center gap-1.5 px-3 py-2 text-xs font-medium text-slate-500 transition-colors hover:text-slate-700 [&::-webkit-details-marker]:hidden">
            <svg
              width="12"
              height="12"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.5"
              className="transition-transform group-open:rotate-90"
            >
              <path d="M9 6l6 6-6 6" />
            </svg>
            {titulo} ({notas.length})
          </summary>
          <div className="space-y-1 px-3 pb-3 pt-0.5 text-xs leading-relaxed text-slate-500">
            {notas.map((a) => (
              <p key={a}>• {a}</p>
            ))}
          </div>
        </details>
      )}
    </div>
  );
}
