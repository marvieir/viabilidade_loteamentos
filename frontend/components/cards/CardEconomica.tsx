"use client";

import { useEffect, useState } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  calcularEconomica,
  obterEconomica,
  type Economica,
} from "@/lib/api";

/* Fase 5 — Econômica: AVALIA o fluxo da Financeira (VPL/TIR/paybacks/curva VPL×TMA).
   O front só renderiza o JSON do backend (§2): a curva é plotada com os pares que o
   backend mandou; nenhum número é derivado aqui. TMA sem default — placeholder é
   exemplo rotulado. */

export function CardEconomica({
  analiseId,
  onData,
}: {
  analiseId: string;
  onData?: (d: Economica | null) => void;
}) {
  const [tmaPct, setTmaPct] = useState<string>(""); // % a.a. real — vazio = não declarada
  const [dados, setDados] = useState<Economica | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(false);

  // Avaliação persistida (se houver) — recarrega ao trocar de análise.
  useEffect(() => {
    let ativo = true;
    setDados(null);
    setErro(null);
    obterEconomica(analiseId).then((d) => {
      if (!ativo || !d) return;
      setDados(d);
      setTmaPct(String(d.tma.aa_real * 100));
      onData?.(d);
    });
    return () => {
      ativo = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [analiseId]);

  async function calcular() {
    const tma = parseFloat(tmaPct.replace(",", "."));
    if (!Number.isFinite(tma)) {
      setErro("Informe a sua TMA real (% a.a.) — é a premissa que decide a leitura.");
      return;
    }
    setCarregando(true);
    setErro(null);
    try {
      const d = await calcularEconomica(analiseId, tma / 100);
      setDados(d);
      onData?.(d);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Falha ao avaliar.");
    } finally {
      setCarregando(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Econômica — VPL · TIR · payback</CardTitle>
        <CardDescription>
          Avalia o fluxo que a Financeira montou, descontado pela sua TMA{" "}
          <strong>real</strong> (acima do IPCA). Rode a Financeira primeiro; os
          resultados também preenchem o semáforo do dashboard dela.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* TMA — premissa-chave, sem default */}
        <div className="flex flex-wrap items-end gap-3">
          <div className="grow">
            <p className="text-[11px] font-medium text-slate-600">
              TMA real (% a.a.)
            </p>
            <input
              type="text"
              inputMode="decimal"
              value={tmaPct}
              onChange={(e) => setTmaPct(e.target.value)}
              placeholder="ex.: 12 — exemplo, defina a sua pelo seu custo de capital"
              className="w-full rounded-lg border border-slate-200 px-2 py-2 text-sm"
            />
            <p className="mt-0.5 text-[11px] text-slate-400">
              Quanto seu capital precisa render <em>acima do IPCA</em> para o projeto
              valer a pena. Sem default: a leitura depende dela.
            </p>
          </div>
          <Button onClick={calcular} disabled={carregando}>
            {carregando ? "Avaliando…" : "Avaliar fluxo"}
          </Button>
        </div>

        {erro && (
          <p className="rounded-lg bg-rose-50 p-3 text-sm text-rose-800">{erro}</p>
        )}

        {dados && <Resultado d={dados} />}
      </CardContent>
    </Card>
  );
}

const COR: Record<string, string> = {
  favoravel: "bg-emerald-500",
  atencao: "bg-amber-500",
  desfavoravel: "bg-rose-500",
  pendente: "bg-slate-300",
};

function Resultado({ d }: { d: Economica }) {
  return (
    <div className="space-y-4">
      {/* Indicadores */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Kpi
          rotulo={`VPL @ TMA ${d.tma.aa_real_fmt}`}
          valor={d.vpl.valor_fmt}
          tom={d.vpl.valor > 0 ? "emerald" : d.vpl.valor < 0 ? "rose" : "slate"}
        />
        <Kpi
          rotulo="TIR real (a.a.)"
          valor={d.tir.aa_fmt ?? `— (${d.tir.status})`}
          sub={d.tir.mensal != null ? `${(d.tir.mensal * 100).toLocaleString("pt-BR", { maximumFractionDigits: 4 })}% a.m.` : undefined}
        />
        <Kpi
          rotulo="Payback simples / descontado"
          valor={
            d.payback.simples_mes != null
              ? `mês ${d.payback.simples_mes} / ${d.payback.descontado_mes != null ? `mês ${d.payback.descontado_mes}` : "—"}`
              : "não recuperado"
          }
        />
        <Kpi
          rotulo="Exposição descontada · IL"
          valor={d.exposicao_descontada.valor_fmt}
          sub={
            d.indice_lucratividade != null
              ? `IL ${d.indice_lucratividade.toLocaleString("pt-BR", { maximumFractionDigits: 4 })} · mês ${d.exposicao_descontada.mes}`
              : `mês ${d.exposicao_descontada.mes}`
          }
          tom="rose"
        />
      </div>

      {/* Leituras §1-A */}
      <div className="rounded-xl border border-slate-200 p-4">
        <p className="mb-2 text-sm font-semibold text-slate-800">
          Leitura sob as premissas declaradas
        </p>
        <ul className="space-y-1.5">
          {d.leituras.map((l) => (
            <li key={l.chave} className="flex items-start gap-2 text-sm">
              <span className={`mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full ${COR[l.status]}`} />
              <span className="text-slate-700">{l.texto}</span>
            </li>
          ))}
        </ul>
        {(d.tir.avisos.length > 0 || d.payback.avisos.length > 0) && (
          <ul className="mt-2 space-y-1 text-[11px] text-slate-500">
            {[...d.tir.avisos, ...d.payback.avisos].map((a) => (
              <li key={a}>• {a}</li>
            ))}
          </ul>
        )}
      </div>

      {/* Curva VPL × TMA */}
      <CurvaVplTma pontos={d.curva_vpl_tma} tmaAtual={d.tma.aa_real} />

      {/* Convenção + avisos */}
      <div className="rounded-lg bg-slate-50 p-3 text-xs text-slate-600">
        <p className="font-medium">{d.convencao}</p>
        <p className="mt-1 text-slate-400">{d.proveniencia}</p>
      </div>
      <div className="rounded-lg bg-amber-50 p-3 text-xs text-amber-900">
        {d.avisos.map((a) => (
          <p key={a}>• {a}</p>
        ))}
      </div>
    </div>
  );
}

/* Plotagem SVG dos pares (tma_aa, vpl) vindos do backend — só escala visual (pixels),
   nenhum número novo é produzido aqui. */
function CurvaVplTma({
  pontos,
  tmaAtual,
}: {
  pontos: { tma_aa: number; vpl: number; vpl_fmt: string }[];
  tmaAtual: number;
}) {
  const [hover, setHover] = useState<number | null>(null);
  if (pontos.length < 2) return null;
  const W = 640, H = 220, PAD = 10;
  const xs = pontos.map((p) => p.tma_aa);
  const ys = pontos.map((p) => p.vpl);
  const xMin = Math.min(...xs), xMax = Math.max(...xs);
  const yMin = Math.min(...ys, 0), yMax = Math.max(...ys, 0);
  const X = (v: number) => PAD + ((v - xMin) / (xMax - xMin || 1)) * (W - 2 * PAD);
  const Y = (v: number) => H - PAD - ((v - yMin) / (yMax - yMin || 1)) * (H - 2 * PAD);
  const linha = pontos.map((p, i) => `${i === 0 ? "M" : "L"}${X(p.tma_aa)},${Y(p.vpl)}`).join(" ");
  const h = hover != null ? pontos[hover] : null;

  return (
    <div className="rounded-xl border border-slate-200 p-4">
      <p className="text-sm font-semibold text-slate-800">Curva VPL × TMA real</p>
      <p className="mb-2 text-[11px] text-slate-500">
        Onde a curva cruza o zero é a taxa que anula o valor (≈ TIR). Passe o mouse
        para ler os pontos.
      </p>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full"
        onMouseLeave={() => setHover(null)}
        onMouseMove={(e) => {
          const r = e.currentTarget.getBoundingClientRect();
          const fx = ((e.clientX - r.left) / r.width) * W;
          let melhor = 0, dist = Infinity;
          pontos.forEach((p, i) => {
            const dx = Math.abs(X(p.tma_aa) - fx);
            if (dx < dist) { dist = dx; melhor = i; }
          });
          setHover(melhor);
        }}
      >
        {/* linha do zero */}
        <line x1={PAD} x2={W - PAD} y1={Y(0)} y2={Y(0)} stroke="#cbd5e1" strokeDasharray="4 4" />
        {/* marcador da TMA informada */}
        {tmaAtual >= xMin && tmaAtual <= xMax && (
          <line x1={X(tmaAtual)} x2={X(tmaAtual)} y1={PAD} y2={H - PAD} stroke="#6366f1" strokeDasharray="3 3" />
        )}
        <path d={linha} fill="none" stroke="#0f766e" strokeWidth="2.5" />
        {h && (
          <>
            <circle cx={X(h.tma_aa)} cy={Y(h.vpl)} r="4" fill="#0f766e" />
            <text
              x={X(h.tma_aa) < W / 2 ? X(h.tma_aa) + 8 : X(h.tma_aa) - 8}
              y={Math.max(Y(h.vpl) - 10, 14)}
              textAnchor={X(h.tma_aa) < W / 2 ? "start" : "end"}
              className="fill-slate-700 text-[12px] font-medium"
            >
              {(h.tma_aa * 100).toLocaleString("pt-BR", { maximumFractionDigits: 1 })}% a.a. → {h.vpl_fmt}
            </text>
          </>
        )}
      </svg>
      <div className="mt-1 flex justify-between text-[11px] text-slate-400">
        <span>{(xMin * 100).toLocaleString("pt-BR")}% a.a.</span>
        <span className="text-indigo-500">┊ sua TMA</span>
        <span>{(xMax * 100).toLocaleString("pt-BR")}% a.a.</span>
      </div>
    </div>
  );
}

function Kpi({
  rotulo,
  valor,
  sub,
  tom = "slate",
}: {
  rotulo: string;
  valor: string;
  sub?: string;
  tom?: "slate" | "emerald" | "rose";
}) {
  const cores = {
    slate: "border-slate-200 bg-white text-slate-900",
    emerald: "border-emerald-200 bg-emerald-50 text-emerald-900",
    rose: "border-rose-200 bg-rose-50 text-rose-900",
  };
  return (
    <div className={`rounded-xl border p-3 shadow-sm ${cores[tom]}`}>
      <p className="text-[11px] opacity-70">{rotulo}</p>
      <p className="mt-0.5 text-base font-bold tracking-tight">{valor}</p>
      {sub && <p className="text-[11px] opacity-70">{sub}</p>}
    </div>
  );
}
