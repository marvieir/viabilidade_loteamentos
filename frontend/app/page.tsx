"use client";

import { useState } from "react";
import dynamic from "next/dynamic";
import { UploadKmz } from "@/components/UploadKmz";
import { BadgeCobertura } from "@/components/BadgeCobertura";
import { CardAproveitamento } from "@/components/cards/CardAproveitamento";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import type { Analise } from "@/lib/api";

// Leaflet só roda no cliente.
const MapaLeaflet = dynamic(() => import("@/components/mapa/MapaLeaflet"), {
  ssr: false,
  loading: () => (
    <div className="flex h-full items-center justify-center text-sm text-slate-400">
      Carregando mapa…
    </div>
  ),
});

const m2 = (v: number) =>
  v.toLocaleString("pt-BR", { maximumFractionDigits: 2 }) + " m²";

export default function Home() {
  const [analise, setAnalise] = useState<Analise | null>(null);

  return (
    <main className="mx-auto max-w-5xl space-y-6 p-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-bold">Pré-Viabilidade de Loteamento</h1>
        <p className="text-sm text-slate-500">
          Triagem determinística a partir do KMZ da gleba. Todo número vem do
          backend, com proveniência. Não decide aprovação municipal.
        </p>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>1 · KMZ da gleba</CardTitle>
        </CardHeader>
        <CardContent>
          <UploadKmz onAnalise={setAnalise} />
        </CardContent>
      </Card>

      {analise && (
        <>
          <Card>
            <CardHeader>
              <CardTitle>2 · Geometria e jurisdição</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="h-80 overflow-hidden rounded-lg border border-slate-200">
                <MapaLeaflet geojson={analise.geometria.geojson} />
              </div>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                <Metrica titulo="Área" valor={m2(analise.geometria.area_m2)} />
                <Metrica
                  titulo="Área (ha)"
                  valor={`${analise.geometria.area_ha.toLocaleString("pt-BR")} ha`}
                />
                <Metrica
                  titulo="Perímetro"
                  valor={`${analise.geometria.perimetro_m.toLocaleString("pt-BR")} m`}
                />
              </div>
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <span className="rounded-full bg-emerald-100 px-2 py-0.5 font-medium text-emerald-800">
                  {analise.origem_geometria.rota === "POLYGON_DIRETO"
                    ? "polígono do arquivo"
                    : "linha fechada automaticamente"}
                </span>
                <span className="text-slate-500">
                  {analise.origem_geometria.descricao}
                </span>
              </div>
              <BadgeCobertura jurisdicao={analise.jurisdicao} />
              {analise.avisos.length > 0 && (
                <div className="rounded-lg bg-sky-50 p-3 text-xs text-sky-900">
                  {analise.avisos.map((a) => (
                    <p key={a}>{a}</p>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          <CardAproveitamento analiseId={analise.analise_id} />
        </>
      )}
    </main>
  );
}

function Metrica({ titulo, valor }: { titulo: string; valor: string }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
      <p className="text-xs text-slate-500">{titulo}</p>
      <p className="text-base font-semibold text-slate-900">{valor}</p>
    </div>
  );
}
