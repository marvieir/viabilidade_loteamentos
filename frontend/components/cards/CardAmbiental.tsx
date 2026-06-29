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
  buscarAmbiental,
  type AlertaAmbiental,
  type Ambiental,
  type ChaveOverlay,
} from "@/lib/api";

const m2 = (v: number) =>
  v.toLocaleString("pt-BR", { maximumFractionDigits: 2 }) + " m²";

export function CardAmbiental({
  analiseId,
  onOverlays,
  onData,
  sinal,
}: {
  analiseId: string;
  onOverlays?: (
    overlays: Partial<Record<ChaveOverlay, GeoJSON.Geometry>>
  ) => void;
  onData?: (d: Ambiental) => void;
  sinal?: number; // "Analisar tudo": dispara a análise quando muda
}) {
  const [data, setData] = useState<Ambiental | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(false);

  async function analisar() {
    setCarregando(true);
    setErro(null);
    try {
      const r = await buscarAmbiental(analiseId);
      setData(r);
      onData?.(r);
      // Empurra todos os overlays; a visibilidade é controlada no painel do mapa-herói.
      onOverlays?.(r.geojson_overlays);
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

            {data.bacia_hidrografica?.consultado &&
              (data.bacia_hidrografica.regiao_hidrografica ||
                data.bacia_hidrografica.bacia ||
                data.bacia_hidrografica.sub_bacia) && (
                <div className="rounded-lg border border-sky-200 bg-sky-50/60 p-3 text-sm">
                  <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Bacia hidrográfica
                  </p>
                  <div className="flex flex-wrap gap-x-4 gap-y-1">
                    {data.bacia_hidrografica.regiao_hidrografica && (
                      <span>
                        Região:{" "}
                        <span className="font-medium">
                          {data.bacia_hidrografica.regiao_hidrografica}
                        </span>
                      </span>
                    )}
                    {data.bacia_hidrografica.bacia && (
                      <span>
                        Bacia:{" "}
                        <span className="font-medium">
                          {data.bacia_hidrografica.bacia}
                        </span>
                      </span>
                    )}
                    {data.bacia_hidrografica.sub_bacia && (
                      <span>
                        Sub-bacia:{" "}
                        <span className="font-medium">
                          {data.bacia_hidrografica.sub_bacia}
                        </span>
                      </span>
                    )}
                  </div>
                  {data.bacia_hidrografica.fonte && (
                    <p className="mt-1 text-xs text-slate-400">
                      {data.bacia_hidrografica.fonte}
                    </p>
                  )}
                </div>
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
