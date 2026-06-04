"use client";

import { useState } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  buscarAmbiental,
  type AlertaAmbiental,
  type Ambiental,
  type ChaveOverlay,
} from "@/lib/api";

// Cores das camadas no mapa (também usadas na legenda do card).
export const CORES_OVERLAY: Record<ChaveOverlay, string> = {
  app: "#3b82f6",
  faixa_nao_edificavel: "#06b6d4",
  app_massa_dagua: "#0ea5e9",
  uc: "#16a34a",
  mineracao: "#d97706",
  linhas_transmissao: "#a855f7",
};

const ROTULO_OVERLAY: Record<ChaveOverlay, string> = {
  app: "APP (hidrografia)",
  faixa_nao_edificavel: "Faixa não-edificável (15 m)",
  app_massa_dagua: "APP de massa d'água (lago/represa)",
  uc: "Unidade de conservação",
  mineracao: "Mineração (ANM)",
  linhas_transmissao: "Faixa de servidão (LT/ANEEL)",
};

const m2 = (v: number) =>
  v.toLocaleString("pt-BR", { maximumFractionDigits: 2 }) + " m²";

export function CardAmbiental({
  analiseId,
  onOverlays,
}: {
  analiseId: string;
  onOverlays?: (
    overlays: Partial<Record<ChaveOverlay, GeoJSON.Geometry>>
  ) => void;
}) {
  const [data, setData] = useState<Ambiental | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(false);
  const [visiveis, setVisiveis] = useState<Set<ChaveOverlay>>(new Set());

  function aplicarVisiveis(
    overlays: Partial<Record<ChaveOverlay, GeoJSON.Geometry>>,
    sel: Set<ChaveOverlay>
  ) {
    const filtrado: Partial<Record<ChaveOverlay, GeoJSON.Geometry>> = {};
    (Object.keys(overlays) as ChaveOverlay[]).forEach((k) => {
      if (sel.has(k)) filtrado[k] = overlays[k];
    });
    onOverlays?.(filtrado);
  }

  async function analisar() {
    setCarregando(true);
    setErro(null);
    try {
      const r = await buscarAmbiental(analiseId);
      setData(r);
      const todas = new Set(
        Object.keys(r.geojson_overlays) as ChaveOverlay[]
      );
      setVisiveis(todas);
      aplicarVisiveis(r.geojson_overlays, todas);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Falha ao analisar.");
    } finally {
      setCarregando(false);
    }
  }

  function toggle(k: ChaveOverlay) {
    if (!data) return;
    const sel = new Set(visiveis);
    sel.has(k) ? sel.delete(k) : sel.add(k);
    setVisiveis(sel);
    aplicarVisiveis(data.geojson_overlays, sel);
  }

  const chavesOverlay = data
    ? (Object.keys(data.geojson_overlays) as ChaveOverlay[])
    : [];

  return (
    <Card>
      <CardHeader>
        <CardTitle>Ambiental</CardTitle>
        <CardDescription>
          Overlays vetoriais (hidrografia/APP, unidades de conservação, mineração)
          por interseção espacial. Cálculo no backend; cada alerta traz a fonte e a
          data. Triagem informativa, não decide aprovação.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <Button onClick={analisar} disabled={carregando}>
          {carregando ? "Analisando…" : "Analisar ambiental"}
        </Button>

        {erro && (
          <p className="rounded-lg bg-rose-50 p-3 text-sm text-rose-800">{erro}</p>
        )}

        {data && (
          <>
            {chavesOverlay.length > 0 && (
              <div className="flex flex-wrap gap-3 text-xs">
                {chavesOverlay.map((k) => (
                  <label key={k} className="flex items-center gap-1.5 text-slate-600">
                    <input
                      type="checkbox"
                      checked={visiveis.has(k)}
                      onChange={() => toggle(k)}
                    />
                    <span
                      className="inline-block h-3 w-3 rounded-sm"
                      style={{ backgroundColor: CORES_OVERLAY[k] }}
                    />
                    {ROTULO_OVERLAY[k]}
                  </label>
                ))}
              </div>
            )}

            {data.sem_alertas ? (
              <p className="rounded-lg bg-emerald-50 p-3 text-sm text-emerald-800">
                Nenhuma sobreposição ambiental encontrada nas camadas consultadas.
              </p>
            ) : (
              <ul className="space-y-2">
                {data.alertas.map((a, i) => (
                  <AlertaItem key={`${a.tipo}-${i}`} a={a} />
                ))}
              </ul>
            )}

            {(data.camadas_consultadas.length > 0 ||
              data.camadas_indisponiveis.length > 0) && (
              <p className="text-xs text-slate-500">
                {data.camadas_consultadas.length > 0 && (
                  <>Camadas consultadas: {data.camadas_consultadas.join(", ")}. </>
                )}
                {data.camadas_indisponiveis.length > 0 && (
                  <span className="text-amber-700">
                    Indisponíveis: {data.camadas_indisponiveis.join(", ")}.
                  </span>
                )}
              </p>
            )}

            {data.avisos.length > 0 && (
              <div className="rounded-lg bg-amber-50 p-3 text-xs text-amber-900">
                {data.avisos.map((a) => (
                  <p key={a}>{a}</p>
                ))}
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}

function AlertaItem({ a }: { a: AlertaAmbiental }) {
  const alerta = a.severidade === "ALERTA";
  return (
    <li
      className={`rounded-lg border p-3 text-sm ${
        alerta
          ? "border-rose-200 bg-rose-50"
          : "border-slate-200 bg-slate-50"
      }`}
    >
      <div className="flex items-center gap-2">
        <span
          className={`rounded-full px-2 py-0.5 text-xs font-medium ${
            alerta ? "bg-rose-200 text-rose-900" : "bg-slate-200 text-slate-700"
          }`}
        >
          {a.severidade}
        </span>
        <span className="font-medium text-slate-900">{a.tipo}</span>
        {a.area_afetada_m2 != null && (
          <span className="text-xs text-slate-500">
            · {m2(a.area_afetada_m2)} na gleba
          </span>
        )}
      </div>
      <p className="mt-1 text-slate-700">{a.detalhe}</p>
      <p className="mt-1 text-xs text-slate-500">
        {a.proveniencia.camada}
        {a.proveniencia.data_referencia
          ? ` · ${a.proveniencia.data_referencia}`
          : ""}{" "}
        — {a.proveniencia.ressalva}
      </p>
    </li>
  );
}
