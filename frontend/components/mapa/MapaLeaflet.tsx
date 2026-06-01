"use client";

import "leaflet/dist/leaflet.css";

import { useEffect } from "react";
import { GeoJSON, MapContainer, TileLayer, useMap } from "react-leaflet";
import type { GeoJsonObject } from "geojson";
import L from "leaflet";
import type { ChaveOverlay } from "@/lib/api";
import { CORES_OVERLAY } from "@/components/cards/CardAmbiental";

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
}: {
  geojson: GeoJSON.Polygon;
  overlays?: Partial<Record<ChaveOverlay, GeoJSON.Geometry>>;
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

      {overlays &&
        (Object.keys(overlays) as ChaveOverlay[]).map((chave) => {
          const g = overlays[chave];
          if (!g) return null;
          const cor = CORES_OVERLAY[chave];
          return (
            <GeoJSON
              key={`${chave}-${JSON.stringify(g)}`}
              data={g as GeoJsonObject}
              style={{ color: cor, weight: 1, fillColor: cor, fillOpacity: 0.25 }}
            />
          );
        })}

      <GeoJSON
        key={JSON.stringify(geojson)}
        data={geojson as GeoJsonObject}
        style={{ color: "#f59e0b", weight: 2, fillOpacity: 0.15 }}
      />
      <EnquadrarPoligono geojson={geojson} />
    </MapContainer>
  );
}
