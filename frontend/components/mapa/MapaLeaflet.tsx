"use client";

import "leaflet/dist/leaflet.css";

import { useEffect } from "react";
import { GeoJSON, MapContainer, TileLayer, useMap } from "react-leaflet";
import type { Feature, GeoJsonObject } from "geojson";
import L from "leaflet";
import type { ChaveOverlay } from "@/lib/api";
import { CORES_FAIXA, CORES_OVERLAY, ESTILO_OVERLAY } from "@/components/mapa/overlays";

// O front apenas RENDERIZA o GeoJSON que veio do backend. Nenhuma geo-matemática
// aqui — fitBounds é só enquadramento de tela, não cálculo de viabilidade.
function EnquadrarPoligono({ geojson }: { geojson: GeoJSON.Polygon }) {
  const map = useMap();
  useEffect(() => {
    const layer = L.geoJSON(geojson as GeoJsonObject);
    const bounds = layer.getBounds();
    if (bounds.isValid()) {
      map.fitBounds(bounds, { padding: [24, 24] });
    }
  }, [geojson, map]);
  return null;
}

export default function MapaLeaflet({
  geojson,
  overlays,
  lotesFeatures,
  quadras,
}: {
  geojson: GeoJSON.Polygon;
  overlays?: Partial<Record<ChaveOverlay, GeoJSON.Geometry>>;
  // Fase 9.5 — parcelamento legível: cada lote como Feature (borda própria, cor por score).
  lotesFeatures?: GeoJSON.FeatureCollection | null;
  // Fase 9.7 — quadras como FACES da malha: contorno tracejado por baixo dos lotes.
  quadras?: GeoJSON.FeatureCollection | null;
}) {
  return (
    <MapContainer
      center={[-15.78, -47.93]}
      zoom={4}
      scrollWheelZoom
      style={{ height: "100%", width: "100%" }}
    >
      <TileLayer
        attribution="Tiles &copy; Esri"
        url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
      />

      {/* Fase 9.13 — restrição recortada (≥30%/mata/APP) ao FUNDO e DISCRETA: desenhada ANTES do
          parcelamento (fica por baixo), com fill esmaecido + contorno tracejado dessaturado. O dado
          não muda; só para de competir com o projeto. Rótulo segue na legenda. */}
      {overlays?.urb_restricao &&
        (() => {
          const e = ESTILO_OVERLAY.urb_restricao!;
          return (
            <GeoJSON
              key={`urb_restricao-${JSON.stringify(overlays.urb_restricao)}`}
              data={overlays.urb_restricao as GeoJsonObject}
              style={{ color: e.color, weight: e.weight, fillColor: e.fillColor, fillOpacity: e.fillOpacity, dashArray: e.dashArray }}
            />
          );
        })()}

      {/* Camadas de área (via/verde reservado/remanescente/lazer/institucional) — estilo próprio
          com contraste sobre satélite (Fase 9.6) */}
      {overlays &&
        (Object.keys(overlays) as ChaveOverlay[]).map((chave) => {
          if (chave === "urb_restricao") return null; // já desenhada ao fundo (acima)
          const g = overlays[chave];
          if (!g) return null;
          const cor = CORES_OVERLAY[chave];
          const e = ESTILO_OVERLAY[chave];
          const estilo = e
            ? { color: e.color, weight: e.weight, fillColor: e.fillColor, fillOpacity: e.fillOpacity, dashArray: e.dashArray }
            : { color: cor, weight: 1, fillColor: cor, fillOpacity: 0.3 };
          return (
            <GeoJSON key={`${chave}-${JSON.stringify(g)}`} data={g as GeoJsonObject} style={estilo} />
          );
        })}

      {/* Fase 9.7 — QUADRAS (faces da malha): contorno por baixo dos lotes, p/ ver os miolos
          que as ruas cercam. Sem preenchimento (os lotes coloridos vêm por cima). */}
      {quadras && quadras.features.length > 0 && (
        <GeoJSON
          key={`quadras-${quadras.features.length}`}
          data={quadras as GeoJsonObject}
          style={{ color: "#334155", weight: 1.5, fill: false, dashArray: "5 4" }}
          onEachFeature={(f, layer) => {
            const p = (f.properties ?? {}) as Record<string, unknown>;
            const area = typeof p.area_m2 === "number" ? Math.round(p.area_m2) : "—";
            layer.bindPopup(`Quadra ${p.quadra_id ?? "—"} · ${area} m²`);
          }}
        />
      )}

      {/* Fase 9.5 — LOTE A LOTE: cada lote com sua borda, cor pela faixa de score (heatmap) */}
      {lotesFeatures && lotesFeatures.features.length > 0 && (
        <GeoJSON
          key={`lotes-${lotesFeatures.features.length}`}
          data={lotesFeatures as GeoJsonObject}
          style={(f?: Feature) => {
            const faixa = (f?.properties?.faixa_score as string) ?? "";
            return {
              color: "#374151", // borda escura por lote → parcelamento legível
              weight: 0.8,
              fillColor: CORES_FAIXA[faixa] ?? "#9ca3af",
              fillOpacity: 0.5,
            };
          }}
          onEachFeature={(f, layer) => {
            const p = (f.properties ?? {}) as Record<string, unknown>;
            const area = typeof p.area_m2 === "number" ? Math.round(p.area_m2) : "—";
            const score = typeof p.score === "number" ? p.score.toFixed(1) : "—";
            layer.bindPopup(
              `Lote ${p.lote_id ?? "—"} · ${area} m² · score ${score} · quadra ${p.quadra_id ?? "—"}`
            );
          }}
        />
      )}

      <GeoJSON
        key={JSON.stringify(geojson)}
        data={geojson as GeoJsonObject}
        style={{ color: "#f59e0b", weight: 2, fill: false }}
      />
      <EnquadrarPoligono geojson={geojson} />
    </MapContainer>
  );
}
