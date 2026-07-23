"use client";

// Fase UX-2 — estado vazio ORIENTADO (spec: docs/fase-ux-onboarding.md). Antes da primeira
// execução, cada card responde as três perguntas do usuário novo: o que eu ganho, o que eu
// preciso, quanto demora. Pesquisa (NN/g): estado vazio com orientação + ação melhora a
// conclusão de tarefa em 30–45%. Só apresentação — nenhuma regra de negócio aqui.

export function EstadoVazio({
  entrega,
  precisa,
  tempo,
  className = "",
}: {
  entrega: string; // o que a análise devolve, em linguagem de usuário
  precisa: string; // insumos necessários ("Nada além da gleba" quando é 1 clique)
  tempo?: string; // expectativa honesta de duração
  className?: string;
}) {
  return (
    <div
      className={`rounded-xl border border-dashed border-slate-200 bg-slate-50/60 p-4 ${className}`}
    >
      <dl className="space-y-2 text-sm">
        <div className="flex gap-2">
          <dt className="shrink-0 font-semibold text-slate-700">Você recebe:</dt>
          <dd className="text-slate-600">{entrega}</dd>
        </div>
        <div className="flex gap-2">
          <dt className="shrink-0 font-semibold text-slate-700">Precisa de:</dt>
          <dd className="text-slate-600">{precisa}</dd>
        </div>
        {tempo && (
          <div className="flex gap-2">
            <dt className="shrink-0 font-semibold text-slate-700">Leva:</dt>
            <dd className="text-slate-600">{tempo}</dd>
          </div>
        )}
      </dl>
    </div>
  );
}
