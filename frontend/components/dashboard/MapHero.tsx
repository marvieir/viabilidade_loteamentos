"use client";

import dynamic from "next/dynamic";
import { IconLayers } from "@/components/Icons";
import { CORES_OVERLAY, ROTULO_OVERLAY } from "@/components/mapa/overlays";
import type { Analise, ChaveOverlay } from "@/lib/api";

const MapaLeaflet = dynamic(() => import("@/components/mapa/MapaLeaflet"), {
  ssr: false,
  loading: () => (
    <div className="flex h-full items-center justify-center text-sm text-slate-400">
      Carregando mapa…
    </div>
  ),
});

type Overlays = Partial<Record<ChaveOverlay, GeoJSON.Geometry>>;

const ROTULO_ROTA: Record<string, string> = {
  POLYGON_DIRETO: "polígono do arquivo",
  POLYGON_REPARADO: "polígono corrigido (auto-interseção)",
  LINHA_FECHAVEL: "linha fechada automaticamente",
};

export function MapHero({
  analise,
  overlays,
  ocultos,
  onToggle,
  badge,
}: {
  analise: Analise;
  overlays: Overlays;
  ocultos: Set<ChaveOverlay>;
  onToggle: (k: ChaveOverlay) => void;
  badge?: React.ReactNode;
}) {
  const chaves = Object.keys(overlays) as ChaveOverlay[];
  const visiveis: Overlays = {};
  chaves.forEach((k) => {
    if (!ocultos.has(k)) visiveis[k] = overlays[k];
  });
  const reparado = analise.origem_geometria.rota === "POLYGON_REPARADO";

  return (
    <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
      <div className="relative">
        <div className="h-[380px] w-full">
          <MapaLeaflet geojson={analise.geometria.geojson} overlays={visiveis} />
        </div>

        {chaves.length > 0 && (
          <div className="absolute right-3 top-3 z-[500] w-56 rounded-xl border border-slate-200 bg-white/95 p-3 shadow-lg backdrop-blur">
            <p className="mb-2 flex items-center gap-1.5 text-xs font-semibold text-slate-700">
              <IconLayers width={14} height={14} /> Camadas
            </p>
            <div className="space-y-1">
              {chaves.map((k) => (
                <label
                  key={k}
                  className="flex cursor-pointer items-center gap-2 text-xs text-slate-600"
                >
                  <input
                    type="checkbox"
                    checked={!ocultos.has(k)}
                    onChange={() => onToggle(k)}
                    className="accent-slate-900"
                  />
                  <span
                    className="inline-block h-2.5 w-2.5 rounded-sm"
                    style={{ backgroundColor: CORES_OVERLAY[k] }}
                  />
                  {ROTULO_OVERLAY[k]}
                </label>
              ))}
            </div>
          </div>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-2 border-t border-slate-200 px-4 py-3 text-xs">
        <span
          className={`rounded-full px-2 py-0.5 font-medium ${
            reparado ? "bg-amber-100 text-amber-800" : "bg-emerald-100 text-emerald-800"
          }`}
        >
          {ROTULO_ROTA[analise.origem_geometria.rota] ?? "geometria"}
        </span>
        {badge}
        <span className="ml-auto text-slate-400">
          {analise.geometria.perimetro_m.toLocaleString("pt-BR", {
            maximumFractionDigits: 0,
          })}{" "}
          m de perímetro
        </span>
      </div>
    </section>
  );
}
