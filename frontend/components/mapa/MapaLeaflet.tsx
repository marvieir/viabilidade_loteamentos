"use client";

import "leaflet/dist/leaflet.css";

import { useEffect } from "react";
import { CircleMarker, GeoJSON, MapContainer, TileLayer, useMap, useMapEvents } from "react-leaflet";
import type { Feature, GeoJsonObject } from "geojson";
import L from "leaflet";
import type { ChaveOverlay } from "@/lib/api";
import { CORES_FAIXA, CORES_FINA, CORES_OVERLAY, CORES_QUINTIL, ESTILO_OVERLAY } from "@/components/mapa/overlays";

// O front apenas RENDERIZA o GeoJSON que veio do backend. Nenhuma geo-matemática
// aqui — fitBounds/invalidateSize são só enquadramento de tela, não cálculo de viabilidade.
//
// Leaflet mede o container UMA vez no mount. Se naquele instante ele estava oculto
// (display:none, ex.: seção em aba não-ativa) ou se a altura muda depois (botão
// "Expandir mapa"), o mapa não recalcula sozinho — só o tile inicial carrega e o resto
// fica CINZA, com a vista presa no zoom inicial. Este helper recalcula o tamanho E
// re-enquadra o polígono no mount e a cada redimensionamento do container.
function AjustarEEnquadrar({ geojson }: { geojson: GeoJSON.Polygon }) {
  const map = useMap();
  useEffect(() => {
    const ajustar = () => {
      map.invalidateSize();
      const bounds = L.geoJSON(geojson as GeoJsonObject).getBounds();
      if (bounds.isValid()) {
        map.fitBounds(bounds, { padding: [24, 24] });
      }
    };
    // Primeiro ajuste após o layout assentar (container já com tamanho real).
    const t = setTimeout(ajustar, 0);
    const ro = new ResizeObserver(ajustar);
    ro.observe(map.getContainer());
    return () => {
      clearTimeout(t);
      ro.disconnect();
    };
  }, [geojson, map]);
  return null;
}

// Captura o clique do usuário (ex.: marcar o ponto de acesso) — só repassa a coordenada;
// nenhuma geo-matemática aqui (§2).
function CapturaClique({ aoClicar }: { aoClicar: (p: { lat: number; lng: number }) => void }) {
  useMapEvents({ click: (e) => aoClicar(e.latlng) });
  return null;
}

export default function MapaLeaflet({
  geojson,
  overlays,
  lotesFeatures,
  quadras,
  lazerFeatures,
  aoClicar,
  marcador,
}: {
  geojson: GeoJSON.Polygon;
  overlays?: Partial<Record<ChaveOverlay, GeoJSON.Geometry>>;
  // Fase 9.5 — parcelamento legível: cada lote como Feature (borda própria, cor por score).
  lotesFeatures?: GeoJSON.FeatureCollection | null;
  // Fase 9.7 — quadras como FACES da malha: contorno tracejado por baixo dos lotes.
  quadras?: GeoJSON.FeatureCollection | null;
  // Fase U2 — lazer rotulado: sub-parcelas do hub + praças de bolso (tooltip por rótulo).
  lazerFeatures?: GeoJSON.FeatureCollection | null;
  // Modo "marcar no mapa": callback de clique + marcador [lat, lng] do ponto escolhido.
  aoClicar?: (p: { lat: number; lng: number }) => void;
  marcador?: [number, number] | null;
}) {
  return (
    <MapContainer
      center={[-15.78, -47.93]}
      zoom={4}
      scrollWheelZoom
      style={{ height: "100%", width: "100%", cursor: aoClicar ? "crosshair" : undefined }}
    >
      <TileLayer
        attribution="Tiles &copy; Esri"
        url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
      />

      {/* Fase 10.2 — não-edificável (≥30%/mata/APP) = BOSQUE/área verde PRESERVADA: desenhada ANTES
          do parcelamento (fica ao fundo), em verde-mata visível com textura pontilhada. Não é mais um
          vazio com satélite vazando ("buraco"); lê como amenidade preservada. Rótulo na legenda. */}
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

      {/* Declividade (faixas): FeatureCollection pintada POR FEIÇÃO (cada uma tem properties.classe
          → cor verde→vermelho). Camada ligável separada da mancha legal ≥30%. */}
      {overlays?.declividade_faixas && (
        <GeoJSON
          key={`declividade_faixas-${JSON.stringify(overlays.declividade_faixas)}`}
          data={overlays.declividade_faixas as GeoJsonObject}
          style={(f?: Feature) => {
            const classe = (f?.properties?.classe as string) ?? "";
            const cor = CORES_FINA[classe] ?? "#9ca3af";
            return { color: cor, weight: 0.5, fillColor: cor, fillOpacity: 0.55 };
          }}
        />
      )}

      {/* Camadas de área (via/verde reservado/remanescente/lazer/institucional) — estilo próprio
          com contraste sobre satélite (Fase 9.6) */}
      {overlays &&
        (Object.keys(overlays) as ChaveOverlay[]).map((chave) => {
          if (chave === "urb_restricao") return null; // já desenhada ao fundo (acima)
          if (chave === "declividade_faixas") return null; // desenhada por feição (acima)
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

      {/* Fase U2 — LAZER ROTULADO: sub-parcelas do hub (piscina/quadra/salão…) e praças de
          bolso, com tooltip do backend (rótulo + área formatada). Desenhado sobre a mancha
          do sistema de lazer (overlay urb_lazer) para detalhar o programa. */}
      {lazerFeatures && lazerFeatures.features.length > 0 && (
        <GeoJSON
          key={`lazer-${lazerFeatures.features.length}`}
          data={lazerFeatures as GeoJsonObject}
          style={(f?: Feature) => {
            const tipo = (f?.properties?.tipo as string) ?? "hub";
            return tipo === "praca"
              ? { color: "#15803d", weight: 1.5, fillColor: "#22c55e", fillOpacity: 0.45 }
              : { color: "#0f766e", weight: 1, fillColor: "#2dd4bf", fillOpacity: 0.4, dashArray: "3 3" };
          }}
          onEachFeature={(f, layer) => {
            const p = (f.properties ?? {}) as Record<string, unknown>;
            const area = typeof p.area_fmt === "string" ? ` · ${p.area_fmt} m²` : "";
            layer.bindTooltip(`${p.rotulo ?? "Lazer"}${area}`, { sticky: true });
          }}
        />
      )}

      {/* Fase 9.5 — LOTE A LOTE: cada lote com sua borda, cor pela faixa de score (heatmap) */}
      {lotesFeatures && lotesFeatures.features.length > 0 && (
        <GeoJSON
          key={`lotes-${lotesFeatures.features.length}`}
          data={lotesFeatures as GeoJsonObject}
          style={(f?: Feature) => {
            // U1 — cor primária = QUINTIL de valorização relativo (backend); snapshot antigo
            // sem quintil cai na faixa absoluta de score (compat).
            const quintil = f?.properties?.quintil_valor as number | undefined;
            const faixa = (f?.properties?.faixa_score as string) ?? "";
            return {
              color: "#374151", // borda escura por lote → parcelamento legível
              weight: 0.8,
              fillColor:
                (quintil != null ? CORES_QUINTIL[quintil] : CORES_FAIXA[faixa]) ?? "#9ca3af",
              fillOpacity: 0.5,
            };
          }}
          onEachFeature={(f, layer) => {
            const p = (f.properties ?? {}) as Record<string, unknown>;
            const area = typeof p.area_m2 === "number" ? Math.round(p.area_m2) : "—";
            const score = typeof p.score === "number" ? p.score.toFixed(1) : "—";
            // Fase 11.13 — declividade média do lote (amostrada do DEM no backend; orientativa,
            // DSM 30 m). Só exibe se houver DEM; sem dado, omite a parcela (não inventa).
            const decliv =
              typeof p.declividade_pct === "number" ? ` · decliv. ${p.declividade_pct}%` : "";
            // Fase U1 — score v2: multiplicador posicional + fatores (o backend calculou; só exibe).
            const mult =
              typeof p.multiplicador === "number"
                ? ` · valor ×${p.multiplicador.toFixed(2)}`
                : "";
            const NOMES_FATOR: Record<string, string> = {
              verde: "verde", agua: "água", lazer: "lazer", culdesac: "bolsão",
              privacidade: "privacidade", orientacao: "orientação", sossego: "sossego",
            };
            const fatores =
              p.fatores && typeof p.fatores === "object"
                ? Object.entries(p.fatores as Record<string, number>)
                    .map(([k, v]) => `${NOMES_FATOR[k] ?? k} ${v.toFixed(2)}`)
                    .join(" · ")
                : "";
            layer.bindPopup(
              `Lote ${p.lote_id ?? "—"} · ${area} m² · score ${score} · quadra ${p.quadra_id ?? "—"}${decliv}${mult}` +
                (fatores ? `<br/><span style="font-size:11px;color:#6b7280">${fatores}</span>` : "")
            );
          }}
        />
      )}

      <GeoJSON
        key={JSON.stringify(geojson)}
        data={geojson as GeoJsonObject}
        style={{ color: "#f59e0b", weight: 2, fill: false }}
      />
      <AjustarEEnquadrar geojson={geojson} />
      {aoClicar && <CapturaClique aoClicar={aoClicar} />}
      {marcador && (
        <>
          {/* ALVO do operador (acesso marcado) — estilo distinto do disco rosa do pórtico */}
          <CircleMarker
          center={marcador}
          radius={11}
          pathOptions={{ color: "#312e81", fillColor: "#ffffff", fillOpacity: 0.85, weight: 3, dashArray: "5 4" }}
        />
          <CircleMarker
            center={marcador}
            radius={3}
            pathOptions={{ color: "#312e81", fillColor: "#4f46e5", fillOpacity: 1, weight: 2 }}
          />
        </>
      )}
    </MapContainer>
  );
}
