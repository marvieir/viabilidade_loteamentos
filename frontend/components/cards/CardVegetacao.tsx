"use client";

import { useEffect, useState } from "react";
import { StatusChip } from "@/components/ui/status";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  buscarVegetacao,
  type ChaveOverlay,
  type Vegetacao,
} from "@/lib/api";

const m2 = (v: number) =>
  v.toLocaleString("pt-BR", { maximumFractionDigits: 2 }) + " m²";
const ha = (v: number) =>
  (v / 10000).toLocaleString("pt-BR", { maximumFractionDigits: 2 }) + " ha";
const pctBR = (v: number) =>
  (v * 100).toLocaleString("pt-BR", { maximumFractionDigits: 1 }) + "%";

type OverlaysVerde = Partial<Record<ChaveOverlay, GeoJSON.Geometry>>;
const ehGeom = (g: unknown): g is GeoJSON.Geometry =>
  !!g && typeof g === "object" && "type" in (g as object);

export function CardVegetacao({
  analiseId,
  onOverlaysVerde,
  onData,
  sinal,
}: {
  analiseId: string;
  onOverlaysVerde?: (o: OverlaysVerde) => void;
  onData?: (d: Vegetacao) => void;
  sinal?: number;
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
      onData?.(r);
      // Empurra a(s) mancha(s) pro mapa. Com severidade: dois baldes (dura/a verificar);
      // sem severidade: o verde total. Só renderiza — a geometria veio do backend.
      const ov: OverlaysVerde = {};
      if (r.severidade) {
        if (ehGeom(r.severidade.restricao_dura.geojson))
          ov.verde_dura = r.severidade.restricao_dura.geojson;
        if (ehGeom(r.severidade.a_verificar.geojson))
          ov.verde_verificar = r.severidade.a_verificar.geojson;
      } else if (ehGeom(r.geojson_verde)) {
        ov.verde = r.geojson_verde;
      }
      onOverlaysVerde?.(ov);
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
        <CardTitle className="flex flex-wrap items-center gap-2">
          <span>Área verde</span>
          {data ? (
            (data.severidade?.restricao_dura.area_m2 ?? 0) > 0 ? (
              <StatusChip className="ml-auto" estado="atencao" rotulo="restrição dura" />
            ) : (
              <StatusChip className="ml-auto" estado="ok" />
            )
          ) : (
            <StatusChip className="ml-auto" estado="pendente" />
          )}
        </CardTitle>
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
              {/* Fase 10 (Parte 1): "Parcial" = gleba − só vegetação (NÃO é a líquida). A LÍQUIDA
                  aproveitável é a canônica (gleba − veg − declividade − APP), igual nas outras abas. */}
              <Metrica
                titulo="Parcial (só vegetação)"
                valor={data.area_parcial_veg_m2 != null ? ha(data.area_parcial_veg_m2) : "—"}
              />
            </div>

            {data.bioma?.consultado && data.bioma.dominante && (
              <div className="rounded-lg border border-emerald-200 bg-emerald-50/60 p-3 text-sm">
                <span className="font-medium">Bioma:</span>{" "}
                <span className="font-semibold text-emerald-800">
                  {data.bioma.dominante}
                </span>
                {data.bioma.biomas.length > 1 && (
                  <span className="text-slate-600">
                    {" "}
                    ·{" "}
                    {data.bioma.biomas
                      .map((b) => `${b.nome} ${pctBR(b.pct)}`)
                      .join(" · ")}
                  </span>
                )}
                {data.bioma.fonte && (
                  <span className="block text-xs text-slate-400">{data.bioma.fonte}</span>
                )}
              </div>
            )}

            {data.areas_canonicas != null && (
              <p className="text-sm text-slate-700">
                Área líquida aproveitável (canônica, gleba − vegetação − declividade − APP):{" "}
                <span className="font-semibold text-slate-900">
                  {ha(data.areas_canonicas.area_liquida_aproveitavel_m2)}
                </span>{" "}
                — o mesmo número nas abas Aproveitamento e Urbanismo.
              </p>
            )}

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

            {/* Fase 2.3 — severidade do verde */}
            {data.severidade && (
              <div className="space-y-2 rounded-lg border border-slate-200 p-3">
                <p className="text-sm font-medium text-slate-800">
                  Severidade do verde
                </p>
                <div className="grid grid-cols-2 gap-3">
                  <div className="rounded-lg border border-rose-200 bg-rose-50 p-2">
                    <p className="text-xs text-rose-700">
                      🔴 Restrição dura (APP/UC)
                    </p>
                    <p className="text-sm font-semibold text-rose-900">
                      {ha(data.severidade.restricao_dura.area_m2)} (
                      {pctBR(data.severidade.restricao_dura.pct_do_verde)})
                    </p>
                    {data.severidade.restricao_dura.fontes.length > 0 && (
                      <p className="text-xs text-rose-600">
                        {data.severidade.restricao_dura.fontes.join(", ")}
                      </p>
                    )}
                  </div>
                  <div className="rounded-lg border border-yellow-200 bg-yellow-50 p-2">
                    <p className="text-xs text-yellow-700">🟡 A verificar</p>
                    <p className="text-sm font-semibold text-yellow-900">
                      {ha(data.severidade.a_verificar.area_m2)} (
                      {pctBR(data.severidade.a_verificar.pct_do_verde)})
                    </p>
                    <p className="text-xs text-yellow-700">
                      potencial desbloqueável:{" "}
                      {ha(data.severidade.potencial_desbloqueavel_m2)}
                    </p>
                  </div>
                </div>
                <p className="text-xs text-slate-500">
                  {data.severidade.ressalva}
                </p>
              </div>
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
