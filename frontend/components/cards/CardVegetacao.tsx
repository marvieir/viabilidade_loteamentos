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
import { buscarVegetacao, type Vegetacao } from "@/lib/api";

const m2 = (v: number) =>
  v.toLocaleString("pt-BR", { maximumFractionDigits: 2 }) + " m²";
const ha = (v: number) =>
  (v / 10000).toLocaleString("pt-BR", { maximumFractionDigits: 2 }) + " ha";

export function CardVegetacao({
  analiseId,
  onOverlayVerde,
}: {
  analiseId: string;
  onOverlayVerde?: (g: GeoJSON.Geometry | null) => void;
}) {
  const [data, setData] = useState<Vegetacao | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(false);

  async function analisar() {
    setCarregando(true);
    setErro(null);
    try {
      const r = await buscarVegetacao(analiseId);
      setData(r);
      // Empurra a mancha verde pro mapa (só renderiza; a geometria veio do backend).
      const g = r.geojson_verde;
      onOverlayVerde?.(g && "type" in g ? (g as GeoJSON.Geometry) : null);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Falha ao analisar.");
    } finally {
      setCarregando(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Área verde</CardTitle>
        <CardDescription>
          Identifica a cobertura vegetal da gleba e a desconta da área aproveitável.
          Triagem conservadora — não classifica mata nativa/removível (isso é laudo de
          engenheiro ambiental). Cálculo no backend, com proveniência.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <Button onClick={analisar} disabled={carregando}>
          {carregando ? "Analisando…" : "Analisar área verde"}
        </Button>

        {erro && (
          <p className="rounded-lg bg-rose-50 p-3 text-sm text-rose-800">{erro}</p>
        )}

        {data && !data.consultada && (
          <div className="rounded-lg bg-amber-50 p-3 text-xs text-amber-900">
            {data.avisos.map((a) => (
              <p key={a}>{a}</p>
            ))}
          </div>
        )}

        {data && data.consultada && (
          <>
            <div className="grid grid-cols-3 gap-3">
              <Metrica titulo="Total" valor={ha(data.area_total_m2)} />
              <Metrica
                titulo="Verde (descontado)"
                valor={data.area_verde_m2 != null ? ha(data.area_verde_m2) : "—"}
                destaque="verde"
              />
              <Metrica
                titulo="Líquida (aproveitável base)"
                valor={data.area_liquida_m2 != null ? ha(data.area_liquida_m2) : "—"}
              />
            </div>

            {data.percentual_verde != null && (
              <p className="text-sm text-slate-700">
                <span className="font-semibold text-emerald-700">
                  {data.percentual_verde.toLocaleString("pt-BR")}%
                </span>{" "}
                da gleba é cobertura vegetal —{" "}
                {data.area_verde_m2 != null ? m2(data.area_verde_m2) : "—"} removidos do
                aproveitável.
              </p>
            )}

            {data.proveniencia && (
              <p className="text-xs text-slate-500">
                {data.proveniencia.fonte}
                {data.proveniencia.data_referencia
                  ? ` · ${data.proveniencia.data_referencia}`
                  : ""}{" "}
                — {data.proveniencia.ressalva}
              </p>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}

function Metrica({
  titulo,
  valor,
  destaque,
}: {
  titulo: string;
  valor: string;
  destaque?: "verde";
}) {
  return (
    <div
      className={`rounded-lg border p-3 ${
        destaque === "verde"
          ? "border-emerald-200 bg-emerald-50"
          : "border-slate-200 bg-slate-50"
      }`}
    >
      <p className="text-xs text-slate-500">{titulo}</p>
      <p className="text-base font-semibold text-slate-900">{valor}</p>
    </div>
  );
}
