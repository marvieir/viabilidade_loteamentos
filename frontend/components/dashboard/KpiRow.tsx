"use client";

import type {
  Ambiental,
  Analise,
  Aproveitamento,
  Declividade,
  Vegetacao,
} from "@/lib/api";

const ha = (m2: number) =>
  (m2 / 10000).toLocaleString("pt-BR", { maximumFractionDigits: 2 });

export function KpiRow({
  analise,
  aprov,
  amb,
  verde,
  decliv,
}: {
  analise: Analise;
  aprov: Aproveitamento | null;
  amb: Ambiental | null;
  verde: Vegetacao | null;
  decliv: Declividade | null;
}) {
  // Aproveitável: prioriza o cenário com diretriz (headline). Só renderiza JSON do backend.
  const comDiretriz = aprov?.cenario_diretriz ?? null;
  const aprovM2 = comDiretriz
    ? comDiretriz.area_aproveitavel_m2
    : aprov?.area_aproveitavel_m2 ?? null;
  const aprovPct = comDiretriz
    ? comDiretriz.pct_sobre_total
    : aprov?.pct_sobre_total ?? null;
  const lotes = comDiretriz ? comDiretriz.n_lotes : aprov?.n_lotes_teto ?? null;

  // Restrições críticas: alertas ambientais + vedação de declividade + verde em APP/UC.
  const nAlertas = amb?.alertas.filter((a) => a.severidade === "ALERTA").length ?? 0;
  const temDecliv = !!decliv?.flag_vedacao;
  const temVerdeDuro = (verde?.severidade?.restricao_dura.area_m2 ?? 0) > 0;
  const analisado = !!amb || !!decliv || !!verde;
  const nRestricoes = nAlertas + (temDecliv ? 1 : 0) + (temVerdeDuro ? 1 : 0);

  return (
    <section className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
      <Stat
        rotulo="Área total"
        valor={analise.geometria.area_ha.toLocaleString("pt-BR")}
        unidade="ha"
        sub={`${analise.geometria.area_m2.toLocaleString("pt-BR", { maximumFractionDigits: 0 })} m² · perímetro ${analise.geometria.perimetro_m.toLocaleString("pt-BR", { maximumFractionDigits: 0 })} m`}
      />
      <Stat
        tom="emerald"
        rotulo={comDiretriz ? "Aproveitável (com diretriz)" : "Aproveitável (teto físico)"}
        valor={aprovM2 != null ? ha(aprovM2) : "—"}
        unidade={aprovM2 != null ? "ha" : ""}
        sub={
          aprovM2 != null
            ? `${aprovPct != null ? (aprovPct * 100).toLocaleString("pt-BR", { maximumFractionDigits: 1 }) + "% da gleba" : ""}${comDiretriz ? " · doação descontada" : ""}`
            : "rode o Aproveitamento"
        }
      />
      <Stat
        tom="indigo"
        rotulo="Lotes"
        valor={lotes != null ? String(lotes) : "—"}
        sub={
          lotes != null
            ? comDiretriz
              ? `lote legal ${comDiretriz.lote_min_m2_legal.toLocaleString("pt-BR")} m² + doação`
              : "teto físico (sem doação)"
            : "rode o Aproveitamento"
        }
      />
      <Stat
        tom={nRestricoes > 0 ? "rose" : analisado ? "emerald" : "slate"}
        rotulo="Restrições críticas"
        valor={analisado ? String(nRestricoes) : "—"}
        sub={
          analisado
            ? nRestricoes > 0
              ? [
                  nAlertas ? `${nAlertas} ambiental` : "",
                  temDecliv ? "declividade ≥30%" : "",
                  temVerdeDuro ? "verde APP/UC" : "",
                ]
                  .filter(Boolean)
                  .join(" · ")
              : "nenhuma incidente"
            : "rode Ambiental/Declividade"
        }
      />
    </section>
  );
}

const TONS = {
  slate: "border-slate-200 bg-white text-slate-900",
  emerald: "border-emerald-200 bg-emerald-50 text-emerald-900",
  indigo: "border-indigo-200 bg-indigo-50 text-indigo-900",
  rose: "border-rose-200 bg-rose-50 text-rose-900",
} as const;

const TONS_ROTULO = {
  slate: "text-slate-500",
  emerald: "text-emerald-700",
  indigo: "text-indigo-700",
  rose: "text-rose-700",
} as const;

function Stat({
  rotulo,
  valor,
  unidade,
  sub,
  tom = "slate",
}: {
  rotulo: string;
  valor: string;
  unidade?: string;
  sub?: string;
  tom?: keyof typeof TONS;
}) {
  return (
    <div className={`rounded-2xl border p-4 shadow-sm ${TONS[tom]}`}>
      <p className={`text-xs font-medium ${TONS_ROTULO[tom]}`}>{rotulo}</p>
      <p className="mt-1 text-2xl font-bold tracking-tight">
        {valor}
        {unidade ? (
          <span className="text-base font-semibold opacity-50"> {unidade}</span>
        ) : null}
      </p>
      {sub ? <p className="mt-1 text-[11px] opacity-70">{sub}</p> : null}
    </div>
  );
}
