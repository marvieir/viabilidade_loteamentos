"use client";

import { IconDownload, IconMap, IconPlay, IconPlus } from "@/components/Icons";
import type { Analise } from "@/lib/api";

const ROTULO_COBERTURA: Record<string, string> = {
  BASE_FEDERAL: "Base Federal",
  PARCIAL_UF: "Parcial (UF)",
  COMPLETA: "Completa",
};

export function TopBar({
  analise,
  onNova,
  onAnalisarTudo,
  analisando,
  onLaudo,
  gerandoLaudo,
}: {
  analise: Analise | null;
  onNova: () => void;
  onAnalisarTudo: () => void;
  analisando?: boolean;
  onLaudo?: () => void;
  gerandoLaudo?: boolean;
}) {
  const jur = analise?.jurisdicao;
  const local =
    jur?.municipio && jur?.uf
      ? `${jur.municipio} / ${jur.uf}`
      : jur?.uf || "Jurisdição federal";

  return (
    <header className="sticky top-0 z-[1100] flex h-16 items-center justify-between border-b border-slate-200 bg-white/90 px-4 backdrop-blur sm:px-5">
      <div className="flex items-center gap-3">
        <div className="grid h-9 w-9 place-items-center rounded-xl bg-gradient-to-br from-indigo-600 to-violet-600 text-white shadow-sm">
          <IconMap width={20} height={20} />
        </div>
        <div className="leading-tight">
          <p className="text-sm font-bold">Pré-Viabilidade de Loteamento</p>
          <p className="hidden text-[11px] text-slate-500 sm:block">
            Triagem determinística · cada número com proveniência
          </p>
        </div>
      </div>

      <div className="flex items-center gap-2">
        {analise && (
          <>
            <div className="hidden items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-1.5 lg:flex">
              <span className="text-sm font-semibold">{local}</span>
              <span className="h-3.5 w-px bg-slate-300" />
              <span className="text-sm text-slate-600">
                {analise.geometria.area_ha.toLocaleString("pt-BR")} ha
              </span>
              <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-medium text-amber-800">
                {ROTULO_COBERTURA[analise.jurisdicao.cobertura] ?? "—"}
              </span>
            </div>
            <button
              type="button"
              onClick={onAnalisarTudo}
              disabled={analisando}
              className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
            >
              <IconPlay width={15} height={15} />
              {analisando ? "Analisando…" : "Analisar tudo"}
            </button>
            {onLaudo && (
              <button
                type="button"
                onClick={onLaudo}
                disabled={gerandoLaudo}
                title="Gera o laudo de triagem em PDF (composição das dimensões já analisadas)"
                className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
              >
                <IconDownload width={15} height={15} />
                {gerandoLaudo ? "Gerando…" : "Gerar laudo (PDF)"}
              </button>
            )}
          </>
        )}
        <button
          type="button"
          onClick={onNova}
          className="inline-flex items-center gap-1.5 rounded-xl bg-slate-900 px-3.5 py-2 text-sm font-medium text-white hover:bg-slate-800"
        >
          <IconPlus width={15} height={15} />
          Nova análise
        </button>
      </div>
    </header>
  );
}
