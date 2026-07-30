"use client";

// Mapa do laudo de EXEMPLO público — só EMBALA o GeoJSON que o backend publicou (§regra 2).
import dynamic from "next/dynamic";
import type { ChaveOverlay } from "@/lib/api";
import { CORES_OVERLAY, ROTULO_OVERLAY } from "@/components/mapa/overlays";

const MapaLeaflet = dynamic(() => import("@/components/mapa/MapaLeaflet"), {
  ssr: false,
  loading: () => (
    <div className="flex h-full items-center justify-center text-sm text-papel-tinta3">
      Carregando mapa…
    </div>
  ),
});

export function MapaExemplo({
  gleba,
  geometria,
  overlaysCrus,
}: {
  gleba: GeoJSON.Polygon;
  geometria: Record<string, unknown> | null;
  /** Camadas prontas (mapa ambiental): já vêm chaveadas por ChaveOverlay do backend. */
  overlaysCrus?: Record<string, GeoJSON.Geometry> | null;
}) {
  const g = (geometria ?? {}) as Record<string, GeoJSON.Geometry | undefined>;
  const overlays: Partial<Record<ChaveOverlay, GeoJSON.Geometry>> =
    (overlaysCrus as Partial<Record<ChaveOverlay, GeoJSON.Geometry>>) ?? {};
  if (g.areas_verdes) overlays.urb_verde = g.areas_verdes;
  if (g.institucional) overlays.urb_institucional = g.institucional;
  if (g.sistema_lazer) overlays.urb_lazer = g.sistema_lazer;
  if (g.arruamento) overlays.urb_arruamento = g.arruamento;
  const lotes = (geometria as { lotes_features?: GeoJSON.FeatureCollection } | null)
    ?.lotes_features ?? null;
  const presentes = Object.keys(overlays) as ChaveOverlay[];
  return (
    <div>
    <div className="h-[420px] w-full overflow-hidden rounded-xl border border-papel-linha">
      <MapaLeaflet
        geojson={gleba}
        overlays={overlays}
        lotesFeatures={lotes}
        quadras={null}
        lazerFeatures={null}
      />
    </div>
    {presentes.length > 0 && (
      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1.5 rounded-lg border border-papel-linha bg-white/60 px-3 py-2 text-[12px] text-papel-tinta2">
        <b className="text-papel-tinta">Camadas:</b>
        {presentes.map((k) => (
          <span key={k} className="inline-flex items-center gap-1.5">
            <span className="inline-block h-2.5 w-3 rounded-sm"
                  style={{ background: CORES_OVERLAY[k] ?? "#999" }} />
            {ROTULO_OVERLAY[k] ?? k}
          </span>
        ))}
      </div>
    )}
    </div>
  );
}
