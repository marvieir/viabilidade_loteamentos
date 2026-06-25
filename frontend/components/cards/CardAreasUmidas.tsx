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
  buscarAreasUmidas,
  type AreasUmidas,
  type ChaveOverlay,
} from "@/lib/api";

const m2 = (v: number) =>
  v.toLocaleString("pt-BR", { maximumFractionDigits: 2 }) + " m²";
const ha = (v: number) =>
  (v / 10000).toLocaleString("pt-BR", { maximumFractionDigits: 2 }) + " ha";

type OverlaysUmidas = Partial<Record<ChaveOverlay, GeoJSON.Geometry>>;
const ehGeom = (g: unknown): g is GeoJSON.Geometry =>
  !!g && typeof g === "object" && "type" in (g as object);

export function CardAreasUmidas({
  analiseId,
  onOverlaysUmidas,
  onData,
  sinal,
}: {
  analiseId: string;
  onOverlaysUmidas?: (o: OverlaysUmidas) => void;
  onData?: (d: AreasUmidas) => void;
  sinal?: number;
}) {
  const [data, setData] = useState<AreasUmidas | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(false);

  async function analisar() {
    setCarregando(true);
    setErro(null);
    try {
      const r = await buscarAreasUmidas(analiseId);
      setData(r);
      onData?.(r);
      // Só renderiza a mancha que veio do backend — front não recalcula geometria.
      const ov: OverlaysUmidas = {};
      if (ehGeom(r.geojson_umidas)) ov.areas_umidas = r.geojson_umidas;
      onOverlaysUmidas?.(ov);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Falha ao analisar.");
    } finally {
      setCarregando(false);
    }
  }

  useEffect(() => {
    if (sinal) analisar();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sinal]);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Áreas úmidas / alagadas</CardTitle>
        <CardDescription>
          Identifica área úmida/alagável (campo alagado, brejo, banhado, várzea) sobre a
          gleba — restrição não-edificável candidata (APP, Código Florestal art. 4º). Triagem
          por sensoriamento remoto, não laudo: a delimitação e o enquadramento de APP são do
          engenheiro ambiental. Cálculo no backend, com proveniência.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <Button onClick={analisar} disabled={carregando}>
          {carregando ? "Analisando…" : "Analisar áreas úmidas"}
        </Button>

        {erro && (
          <p className="rounded-lg bg-rose-50 p-3 text-sm text-rose-800">{erro}</p>
        )}

        {data && !data.consultada && (
          <div className="rounded-lg bg-amber-50 p-3 text-xs text-amber-900">
            {data.avisos.length > 0 ? (
              data.avisos.map((a) => <p key={a}>{a}</p>)
            ) : (
              <p>Áreas úmidas não consultadas (fonte de dados não configurada).</p>
            )}
          </div>
        )}

        {data && data.consultada && (
          <>
            <div className="grid grid-cols-2 gap-3">
              <Metrica titulo="Total da gleba" valor={ha(data.area_total_m2)} />
              <Metrica
                titulo="Área úmida/alagável"
                valor={data.area_umida_m2 != null ? ha(data.area_umida_m2) : "—"}
                destaque
              />
            </div>

            {data.area_umida_m2 != null && data.area_umida_m2 > 0 ? (
              <p className="text-sm text-slate-700">
                <span className="font-semibold text-teal-700">
                  {(data.pct_da_gleba ?? 0).toLocaleString("pt-BR")}%
                </span>{" "}
                da gleba é área úmida/alagável —{" "}
                {data.area_umida_m2 != null ? m2(data.area_umida_m2) : "—"}. Tratar como
                não-edificável candidata (APP) até verificação do engenheiro ambiental.
              </p>
            ) : (
              <p className="text-sm text-slate-700">
                Nenhuma área úmida/alagável detectada na gleba pela fonte consultada.
              </p>
            )}

            {data.proveniencia && (
              <p className="text-xs text-slate-500">
                {data.proveniencia.fonte}
                {data.proveniencia.data_referencia
                  ? ` · ${data.proveniencia.data_referencia}`
                  : ""}
                {data.proveniencia.classes.length > 0
                  ? ` · classes ${data.proveniencia.classes.join("/")}`
                  : ""}{" "}
                — {data.proveniencia.base_legal}. {data.proveniencia.ressalva}
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
  destaque?: boolean;
}) {
  return (
    <div
      className={`rounded-lg border p-3 ${
        destaque ? "border-teal-200 bg-teal-50" : "border-slate-200 bg-slate-50"
      }`}
    >
      <p className="text-xs text-slate-500">{titulo}</p>
      <p className="text-base font-semibold text-slate-900">{valor}</p>
    </div>
  );
}
