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
  buscarDeclividade,
  type ChaveOverlay,
  type Declividade,
} from "@/lib/api";

const ha = (v: number) =>
  (v / 10000).toLocaleString("pt-BR", { maximumFractionDigits: 2 }) + " ha";
const pctBR = (v: number) =>
  (v * 100).toLocaleString("pt-BR", { maximumFractionDigits: 1 }) + "%";

type OverlaysDecliv = Partial<Record<ChaveOverlay, GeoJSON.Geometry>>;
const ehGeom = (g: unknown): g is GeoJSON.Geometry =>
  !!g && typeof g === "object" && "type" in (g as object);

const ROTULO_FAIXA: Record<string, string> = {
  suave: "Suave",
  media: "Média",
  alta: "Alta",
};

export function CardDeclividade({
  analiseId,
  onOverlaysDecliv,
  onData,
  sinal,
}: {
  analiseId: string;
  onOverlaysDecliv?: (o: OverlaysDecliv) => void;
  onData?: (d: Declividade) => void;
  sinal?: number;
}) {
  const [data, setData] = useState<Declividade | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(false);

  async function analisar() {
    setCarregando(true);
    setErro(null);
    try {
      const r = await buscarDeclividade(analiseId);
      setData(r);
      onData?.(r);
      // Empurra a mancha vedada (≥30%) pro mapa. Só renderiza — geometria veio do backend.
      const ov: OverlaysDecliv = {};
      if (r.flag_vedacao && ehGeom(r.flag_vedacao.geojson))
        ov.declividade_vedada = r.flag_vedacao.geojson;
      onOverlaysDecliv?.(ov);
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
        <CardTitle>Declividade</CardTitle>
        <CardDescription>
          Declividade do terreno a partir do DEM (Copernicus GLO-30, sem chave). Faixas
          suave/média/alta e a <span className="font-medium">vedação legal ≥30%</span>{" "}
          (Lei 6.766/79), que entra na área não-aproveitável. Triagem orientativa — não
          substitui levantamento topográfico. Cálculo no backend, com proveniência.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <Button onClick={analisar} disabled={carregando}>
          {carregando ? "Analisando…" : "Analisar declividade"}
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
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <Metrica
                titulo="Declividade média"
                valor={
                  data.declividade_media_pct != null
                    ? `${data.declividade_media_pct.toLocaleString("pt-BR")}%`
                    : "—"
                }
              />
              {data.faixas.map((f) => (
                <Metrica
                  key={f.classe}
                  titulo={`${ROTULO_FAIXA[f.classe]} (${f.limite})`}
                  valor={pctBR(f.pct)}
                  sub={ha(f.area_m2)}
                  destaque={f.classe === "alta" ? "alta" : undefined}
                />
              ))}
            </div>

            {/* Flag legal ≥30% — vedação de parcelamento */}
            {data.flag_vedacao ? (
              <div className="rounded-lg border border-rose-200 bg-rose-50 p-3">
                <p className="text-sm font-semibold text-rose-900">
                  ⛔ Declividade ≥30% — vedação de parcelamento ·{" "}
                  {ha(data.flag_vedacao.area_m2)} (
                  {pctBR(data.flag_vedacao.pct_da_gleba)} da gleba)
                </p>
                <p className="mt-1 text-xs text-rose-800">
                  {data.flag_vedacao.base_legal} — {data.flag_vedacao.ressalva}
                </p>
                <p className="mt-1 text-xs text-rose-600">
                  Mancha em vermelho no mapa; entra na área não-aproveitável.
                </p>
              </div>
            ) : (
              <p className="rounded-lg bg-emerald-50 p-3 text-xs text-emerald-800">
                Sem área com declividade ≥30% — nenhuma vedação da Lei 6.766 incidente.
              </p>
            )}

            {data.proveniencia && (
              <p className="text-xs text-slate-500">{data.proveniencia}</p>
            )}
            {data.avisos.map((a) => (
              <p key={a} className="text-xs text-slate-400">
                {a}
              </p>
            ))}
          </>
        )}
      </CardContent>
    </Card>
  );
}

function Metrica({
  titulo,
  valor,
  sub,
  destaque,
}: {
  titulo: string;
  valor: string;
  sub?: string;
  destaque?: "alta";
}) {
  return (
    <div
      className={`rounded-lg border p-3 ${
        destaque === "alta"
          ? "border-rose-200 bg-rose-50"
          : "border-slate-200 bg-slate-50"
      }`}
    >
      <p className="text-xs text-slate-500">{titulo}</p>
      <p className="text-base font-semibold text-slate-900">{valor}</p>
      {sub && <p className="text-xs text-slate-400">{sub}</p>}
    </div>
  );
}
