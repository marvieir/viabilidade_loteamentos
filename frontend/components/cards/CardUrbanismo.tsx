"use client";

import { useState } from "react";
import dynamic from "next/dynamic";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  proporUrbanismo,
  type ChaveOverlay,
  type PropostaUrbanistica,
  type PublicoAlvo,
  type TipoLoteamento,
} from "@/lib/api";

const MapaLeaflet = dynamic(() => import("@/components/mapa/MapaLeaflet"), {
  ssr: false,
  loading: () => (
    <div className="flex h-full items-center justify-center text-sm text-slate-400">
      Carregando mapa…
    </div>
  ),
});

const TIPOS: { v: TipoLoteamento; r: string }[] = [
  { v: "aberto", r: "Loteamento aberto" },
  { v: "fechado", r: "Loteamento fechado" },
  { v: "condominio_lotes", r: "Condomínio de lotes" },
  { v: "desmembramento", r: "Desmembramento" },
  { v: "loteamento_rural", r: "Loteamento rural" },
];
const PUBLICOS: { v: PublicoAlvo; r: string }[] = [
  { v: "baixa", r: "Baixa renda (densidade alta)" },
  { v: "media", r: "Média renda (equilíbrio)" },
  { v: "alta", r: "Alta renda (exclusividade)" },
];

// Linha do quadro de áreas: rótulo + m² (fmt do backend) + % (fmt do backend).
function LinhaArea({
  rotulo,
  m2,
  pct,
  forte,
}: {
  rotulo: string;
  m2: string;
  pct: string;
  forte?: boolean;
}) {
  return (
    <div
      className={`flex items-center justify-between py-1.5 text-sm ${
        forte ? "font-semibold text-slate-900" : "text-slate-700"
      }`}
    >
      <span>{rotulo}</span>
      <span className="tabular-nums">
        {m2} m² <span className="ml-1 text-slate-400">·</span>{" "}
        <span className="text-slate-500">{pct}</span>
      </span>
    </div>
  );
}

export function CardUrbanismo({
  analiseId,
  glebaGeojson,
  onData,
}: {
  analiseId: string;
  glebaGeojson: GeoJSON.Polygon;
  onData?: (p: PropostaUrbanistica | null) => void;
}) {
  const [tipo, setTipo] = useState<TipoLoteamento>("aberto");
  const [publico, setPublico] = useState<PublicoAlvo>("media");
  const [proposta, setProposta] = useState<PropostaUrbanistica | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(false);

  async function gerar() {
    setCarregando(true);
    setErro(null);
    try {
      const p = await proporUrbanismo(analiseId, tipo, publico);
      setProposta(p);
      onData?.(p);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Falha ao gerar o estudo de massa.");
    } finally {
      setCarregando(false);
    }
  }

  // Camadas do layout → overlays do mapa (o front só renderiza o GeoJSON do backend, §2).
  const overlays: Partial<Record<ChaveOverlay, GeoJSON.Geometry>> = {};
  if (proposta) {
    const g = proposta.geometria;
    if (g.arruamento) overlays.urb_arruamento = g.arruamento;
    if (g.areas_verdes) overlays.urb_verde = g.areas_verdes;
    if (g.sistema_lazer) overlays.urb_lazer = g.sistema_lazer;
    if (g.institucional) overlays.urb_institucional = g.institucional;
    if (g.lotes) overlays.urb_lotes = g.lotes; // por cima
  }

  const q = proposta?.quadro_areas;
  const ind = proposta?.indicadores;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex flex-wrap items-center gap-2">
          Urbanismo — estudo de massa
          <span className="rounded-full bg-amber-200 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-amber-900">
            Esquemático
          </span>
        </CardTitle>
        <CardDescription>
          A IA propõe o <strong>programa</strong> (lote-alvo, viário, % de lazer) sob o
          perfil escolhido; o motor <strong>gera e mede</strong> toda a geometria e todos os
          números — nenhum número vem da IA. É pré-análise de triagem, <strong>não</strong> o
          projeto urbanístico: verificar com urbanista (art. 6º Lei 6.766).
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          <label className="text-sm text-slate-600">Tipo</label>
          <select
            value={tipo}
            onChange={(e) => setTipo(e.target.value as TipoLoteamento)}
            className="rounded-lg border border-slate-200 px-2 py-2 text-sm"
          >
            {TIPOS.map((t) => (
              <option key={t.v} value={t.v}>
                {t.r}
              </option>
            ))}
          </select>
          <label className="text-sm text-slate-600">Público-alvo</label>
          <select
            value={publico}
            onChange={(e) => setPublico(e.target.value as PublicoAlvo)}
            className="rounded-lg border border-slate-200 px-2 py-2 text-sm"
          >
            {PUBLICOS.map((p) => (
              <option key={p.v} value={p.v}>
                {p.r}
              </option>
            ))}
          </select>
          <Button onClick={gerar} disabled={carregando}>
            {carregando ? "Gerando…" : "Gerar estudo de massa (IA)"}
          </Button>
        </div>

        {erro && (
          <p className="rounded-lg bg-rose-50 p-3 text-sm text-rose-800">{erro}</p>
        )}

        {proposta && (
          <>
            <div className="grid gap-4 lg:grid-cols-2">
              {/* Mapa do layout esquemático */}
              <div className="overflow-hidden rounded-xl border border-slate-200">
                <div className="h-[300px] w-full">
                  <MapaLeaflet geojson={glebaGeojson} overlays={overlays} />
                </div>
                <p className="bg-slate-50 px-3 py-1.5 text-[11px] text-slate-500">
                  Traçado ESQUEMÁTICO — eixos de via aproximados; o valor é o quadro de
                  áreas, não a precisão do desenho.
                </p>
              </div>

              {/* Quadro de áreas */}
              <div className="rounded-xl border border-slate-200 p-4">
                <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Quadro de áreas (sobre a área líquida {q?.area_liquida_fmt} m²)
                </p>
                {q && (
                  <div className="divide-y divide-slate-100">
                    <LinhaArea
                      rotulo="Vendável (lotes)"
                      m2={q.vendavel.m2_fmt}
                      pct={q.vendavel.pct_fmt}
                      forte
                    />
                    <LinhaArea
                      rotulo="Áreas verdes"
                      m2={q.areas_verdes.m2_fmt}
                      pct={q.areas_verdes.pct_fmt}
                    />
                    {q.sistema_lazer.m2 > 0 && (
                      <LinhaArea
                        rotulo="Sistema de lazer"
                        m2={q.sistema_lazer.m2_fmt}
                        pct={q.sistema_lazer.pct_fmt}
                      />
                    )}
                    {q.institucional.m2 > 0 && (
                      <LinhaArea
                        rotulo="Institucional"
                        m2={q.institucional.m2_fmt}
                        pct={q.institucional.pct_fmt}
                      />
                    )}
                    <LinhaArea
                      rotulo="Arruamento (viário)"
                      m2={q.arruamento.m2_fmt}
                      pct={q.arruamento.pct_fmt}
                    />
                  </div>
                )}
                {ind && (
                  <div className="mt-3 grid grid-cols-2 gap-2 text-sm">
                    <Kpi rotulo="Nº de lotes" valor={String(ind.n_lotes)} />
                    <Kpi
                      rotulo="Área média"
                      valor={ind.area_media_fmt ? `${ind.area_media_fmt} m²` : "—"}
                    />
                    <Kpi
                      rotulo="Testada média"
                      valor={
                        ind.testada_media_m != null
                          ? `${ind.testada_media_m.toLocaleString("pt-BR")} m`
                          : "—"
                      }
                    />
                    <Kpi
                      rotulo="Profundidade"
                      valor={
                        ind.profundidade_media_m != null
                          ? `${ind.profundidade_media_m.toLocaleString("pt-BR")} m`
                          : "—"
                      }
                    />
                  </div>
                )}
              </div>
            </div>

            {/* Programa proposto pela IA (proveniência) */}
            <div className="rounded-xl border border-indigo-200 bg-indigo-50 p-3 text-sm text-indigo-900">
              <p className="font-semibold">Programa proposto pela IA ({proposta.programa.origem})</p>
              <p className="text-indigo-800">
                Lote-alvo {proposta.programa.lote_alvo_m2.toLocaleString("pt-BR")} m² ·
                densidade {proposta.programa.densidade} · lazer{" "}
                {(proposta.programa.pct_lazer * 100).toLocaleString("pt-BR")}% · viário{" "}
                {proposta.programa.arquetipo_viario}. {proposta.programa.justificativa}
              </p>
            </div>

            {/* Heatmap de valorização (qualidade relativa, sem preço) */}
            {proposta.heatmap.score_medio != null && (
              <div className="rounded-xl border border-slate-200 p-4">
                <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Heatmap de score por lote — médio {proposta.heatmap.score_medio} (qualidade
                  relativa; o R$/m² por faixa é seu)
                </p>
                <div className="space-y-1">
                  {proposta.heatmap.faixas.map((f) => (
                    <div key={f.faixa} className="flex items-center gap-2 text-sm">
                      <span className="w-12 text-slate-600">{f.faixa}</span>
                      <div className="h-3 flex-1 overflow-hidden rounded bg-slate-100">
                        <div
                          className="h-full bg-emerald-500"
                          style={{ width: `${Math.round(f.pct * 100)}%` }}
                        />
                      </div>
                      <span className="w-16 text-right tabular-nums text-slate-500">
                        {f.n} lote{f.n > 1 ? "s" : ""}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Conformidade do programa (sinaliza, não decide) */}
            {proposta.conformidade_programa.length > 0 && (
              <ul className="space-y-2">
                {proposta.conformidade_programa.map((c) => (
                  <li
                    key={c.item}
                    className={`rounded-lg border p-3 text-sm ${
                      c.status === "atencao"
                        ? "border-amber-300 bg-amber-50 text-amber-900"
                        : "border-slate-200 bg-slate-50 text-slate-700"
                    }`}
                  >
                    {c.leitura}
                  </li>
                ))}
              </ul>
            )}

            {proposta.esqueleto_ignorado.length > 0 && (
              <div className="rounded-lg bg-slate-50 p-3 text-xs text-slate-500">
                {proposta.esqueleto_ignorado.map((s) => (
                  <p key={s}>• {s}</p>
                ))}
              </div>
            )}

            <p className="text-xs text-slate-500">{proposta.proveniencia}</p>

            <div className="rounded-lg bg-amber-50 p-3 text-xs text-amber-900">
              {proposta.avisos.map((a) => (
                <p key={a}>• {a}</p>
              ))}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}

function Kpi({ rotulo, valor }: { rotulo: string; valor: string }) {
  return (
    <div className="rounded-lg bg-slate-50 px-3 py-2">
      <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">
        {rotulo}
      </p>
      <p className="text-base font-bold tabular-nums text-slate-900">{valor}</p>
    </div>
  );
}
