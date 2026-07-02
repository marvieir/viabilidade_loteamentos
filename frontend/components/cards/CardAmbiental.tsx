"use client";

import { useEffect, useState } from "react";
import { StatusChip } from "@/components/ui/status";
import { Notas } from "@/components/ui/notas";
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
  inicial,
}: {
  analiseId: string;
  onOverlays?: (
    overlays: Partial<Record<ChaveOverlay, GeoJSON.Geometry>>
  ) => void;
  onData?: (d: Ambiental) => void;
  sinal?: number; // "Analisar tudo": dispara a análise quando muda
  inicial?: Ambiental | null; // snapshot salvo — reidrata sem reprocessar
}) {
  const [data, setData] = useState<Ambiental | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(false);

  function adotar(r: Ambiental) {
    setData(r);
    onData?.(r);
    // Empurra todos os overlays; a visibilidade é controlada no painel do mapa-herói.
    onOverlays?.(r.geojson_overlays);
  }

  async function analisar() {
    setCarregando(true);
    setErro(null);
    try {
      adotar(await buscarAmbiental(analiseId));
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

  // Reidrata do snapshot salvo ("Abrir análise"): mostra o resultado anterior sem reprocessar.
  useEffect(() => {
    if (inicial && !data) adotar(inicial);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [inicial]);


  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex flex-wrap items-center gap-2">
          <span>Ambiental</span>
          {data ? (
            (() => {
              const n = data.alertas.filter((a) => a.severidade === "ALERTA").length;
              return n > 0 ? (
                <StatusChip className="ml-auto" estado="alerta" rotulo={`${n} alerta${n > 1 ? "s" : ""}`} />
              ) : (
                <StatusChip className="ml-auto" estado="ok" rotulo="sem incidência" />
              );
            })()
          ) : (
            <StatusChip className="ml-auto" estado="pendente" />
          )}
        </CardTitle>
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

            {data.malha_fundiaria?.consultado && (
              <div className="rounded-lg border border-orange-200 bg-orange-50/60 p-3 text-sm">
                <div className="mb-1 flex items-center justify-between gap-2">
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Malha fundiária (SIGEF/SNCI)
                  </p>
                  {data.malha_fundiaria.cobertura_pct != null && (
                    <span className="rounded-full bg-orange-100 px-2 py-0.5 text-xs font-medium text-orange-900">
                      {data.malha_fundiaria.cobertura_pct.toLocaleString("pt-BR")}% da gleba já
                      parcelada
                    </span>
                  )}
                </div>
                {!data.malha_fundiaria.na_cobertura ? (
                  <p className="rounded bg-amber-50 p-2 text-xs text-amber-900">
                    Gleba fora da cobertura de dados SIGEF carregada — a malha fundiária não foi
                    avaliada nesta UF. Carregue o SIGEF do estado correspondente.
                  </p>
                ) : data.malha_fundiaria.n_parcelas > 0 ? (
                  <>
                    <p className="text-slate-700">
                      {data.malha_fundiaria.n_parcelas}{" "}
                      {data.malha_fundiaria.n_parcelas === 1
                        ? "parcela registrada incide"
                        : "parcelas registradas incidem"}{" "}
                      sobre a gleba.
                    </p>
                    <ul className="mt-2 space-y-1">
                      {data.malha_fundiaria.parcelas.map((p, i) => (
                        <li
                          key={`${p.codigo ?? "parcela"}-${i}`}
                          className="flex flex-wrap items-baseline gap-x-2 text-xs text-slate-600"
                        >
                          <span className="font-medium text-slate-900">
                            {p.codigo ?? "Parcela sem código"}
                          </span>
                          {p.area_ha != null && (
                            <span>
                              ·{" "}
                              {p.area_ha.toLocaleString("pt-BR", {
                                maximumFractionDigits: 2,
                              })}{" "}
                              ha
                            </span>
                          )}
                          {p.situacao && <span>· {p.situacao}</span>}
                          {p.titular && <span>· {p.titular}</span>}
                        </li>
                      ))}
                    </ul>
                  </>
                ) : (
                  <p className="text-slate-700">
                    Nenhuma parcela georreferenciada (SIGEF/SNCI) incide sobre a gleba — área
                    possivelmente ainda não certificada no INCRA.
                  </p>
                )}
                {data.malha_fundiaria.fonte && (
                  <p className="mt-1 text-xs text-slate-400">{data.malha_fundiaria.fonte}</p>
                )}
              </div>
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

            <Notas itens={data.avisos} />
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
