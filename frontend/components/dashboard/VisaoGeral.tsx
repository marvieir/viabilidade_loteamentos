"use client";

import { SECOES, type Secao } from "@/components/shell/secoes";
import type {
  Ambiental,
  Analise,
  Aproveitamento,
  Declividade,
  Vegetacao,
} from "@/lib/api";

export function VisaoGeral({
  analise,
  amb,
  verde,
  decliv,
  aprov,
  onIr,
}: {
  analise: Analise;
  amb: Ambiental | null;
  verde: Vegetacao | null;
  decliv: Declividade | null;
  aprov: Aproveitamento | null;
  onIr: (s: Secao) => void;
}) {
  const status: Record<string, { feito: boolean; resumo: string }> = {
    ambiental: {
      feito: !!amb,
      resumo: amb
        ? amb.sem_alertas
          ? "Sem sobreposições"
          : `${amb.alertas.length} alerta(s)`
        : "Não analisado",
    },
    verde: {
      feito: !!verde,
      resumo: verde
        ? verde.consultada
          ? `${verde.percentual_verde?.toLocaleString("pt-BR") ?? "—"}% de cobertura`
          : "Indisponível"
        : "Não analisado",
    },
    declividade: {
      feito: !!decliv,
      resumo: decliv
        ? decliv.consultada
          ? `média ${decliv.declividade_media_pct?.toLocaleString("pt-BR") ?? "—"}%`
          : "Indisponível"
        : "Não analisado",
    },
    aproveitamento: {
      feito: !!aprov,
      resumo: aprov
        ? aprov.cenario_diretriz
          ? `${aprov.cenario_diretriz.n_lotes} lotes (com diretriz)`
          : `${aprov.n_lotes_teto ?? "—"} lotes (teto físico)`
        : "Não analisado",
    },
  };

  return (
    <div className="space-y-4">
      <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="text-lg font-semibold">Visão geral da gleba</h2>
        <p className="mt-1 text-sm text-slate-500">
          Triagem determinística a partir do KMZ. Abra cada dimensão na navegação ou use
          <span className="font-medium text-slate-700"> Analisar tudo</span> no topo. Todo
          número vem do backend, com proveniência — esta ferramenta não decide aprovação
          municipal.
        </p>

        <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
          {SECOES.filter((s) => s.id in status).map(({ id, rotulo, Icone }) => {
            const st = status[id];
            return (
              <button
                key={id}
                type="button"
                onClick={() => onIr(id)}
                className="flex items-center gap-3 rounded-xl border border-slate-200 bg-slate-50 p-3 text-left transition-colors hover:bg-slate-100"
              >
                <span
                  className={`grid h-9 w-9 place-items-center rounded-lg ${
                    st.feito ? "bg-emerald-100 text-emerald-700" : "bg-slate-200 text-slate-500"
                  }`}
                >
                  <Icone width={18} height={18} />
                </span>
                <span className="min-w-0">
                  <span className="block text-sm font-medium text-slate-800">{rotulo}</span>
                  <span className="block truncate text-xs text-slate-500">{st.resumo}</span>
                </span>
                <span
                  className={`ml-auto rounded-full px-2 py-0.5 text-[11px] font-medium ${
                    st.feito
                      ? "bg-emerald-100 text-emerald-700"
                      : "bg-slate-200 text-slate-500"
                  }`}
                >
                  {st.feito ? "✓" : "pendente"}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {(analise.avisos.length > 0 || analise.jurisdicao.nao_considerado.length > 0) && (
        <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-xs text-amber-900">
          <p className="mb-1 font-semibold">Avisos e limites desta análise</p>
          <ul className="list-inside list-disc space-y-0.5">
            {analise.avisos.map((a) => (
              <li key={a}>{a}</li>
            ))}
            {analise.jurisdicao.nao_considerado.map((a) => (
              <li key={a}>{a}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
