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
  buscarConformidade,
  type Conformidade,
  type PerfilMunicipal,
  type StatusConformidade,
} from "@/lib/api";

const CHIP: Record<StatusConformidade, { rotulo: string; classe: string }> = {
  considerado: {
    rotulo: "no cálculo",
    classe: "bg-emerald-100 text-emerald-800",
  },
  exigencia_projeto: {
    rotulo: "exigência de projeto",
    classe: "bg-indigo-100 text-indigo-800",
  },
  atencao: { rotulo: "atenção", classe: "bg-amber-200 text-amber-900" },
  nao_extraido: { rotulo: "não avaliado", classe: "bg-slate-200 text-slate-600" },
};

export function CardConformidade({
  analiseId,
  perfil,
  sinal,
}: {
  analiseId: string;
  perfil?: PerfilMunicipal | null;
  sinal?: number;
}) {
  const zonas = perfil?.zonas.map((z) => z.codigo) ?? [];
  const [zona, setZona] = useState<string>("");
  const [modalidade, setModalidade] = useState<string>("");
  const [data, setData] = useState<Conformidade | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(false);

  // Pré-seleciona a única/primeira zona do perfil confirmado (edição livre depois).
  useEffect(() => {
    if (!zona && zonas.length > 0) setZona(zonas[0]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [perfil]);

  const modalidades = perfil?.zonas.find((z) => z.codigo === zona)
    ? Object.keys(perfil!.zonas.find((z) => z.codigo === zona)!.modalidades)
    : [];

  async function avaliar(z = zona, m = modalidade) {
    setCarregando(true);
    setErro(null);
    try {
      const r = await buscarConformidade(analiseId, z || null, m || null);
      setData(r);
      // Sem zona informada, o backend devolve as disponíveis — aproveita p/ o seletor.
      if (!z && r.zonas_disponiveis.length > 0) setZona(r.zonas_disponiveis[0]);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Falha ao avaliar.");
    } finally {
      setCarregando(false);
    }
  }

  useEffect(() => {
    if (sinal) avaliar();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sinal]);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex flex-wrap items-center gap-2">
          <span>Conformidade urbanística</span>
          {data && data.avaliada ? (
            (() => {
              const n = data.itens.filter((i) => i.status === "atencao").length;
              return n > 0 ? (
                <StatusChip className="ml-auto" estado="atencao" rotulo={`${n} ponto${n > 1 ? "s" : ""} de atenção`} />
              ) : (
                <StatusChip className="ml-auto" estado="ok" />
              );
            })()
          ) : (
            <StatusChip className="ml-auto" estado="pendente" />
          )}
        </CardTitle>
        <CardDescription>
          Confronta a gleba com os índices da LUOS extraídos e confirmados (Fase 1.8) que
          não entram no número — frente mínima, CA, taxa de ocupação, repartição da doação.
          Checklist de triagem com proveniência por artigo; não altera o aproveitável.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          <Button onClick={() => avaliar()} disabled={carregando}>
            {carregando ? "Avaliando…" : "Avaliar conformidade"}
          </Button>
          <span className="text-slate-300">·</span>
          <label className="text-sm text-slate-600">Zona</label>
          <select
            value={zona}
            onChange={(e) => setZona(e.target.value)}
            className="rounded-lg border border-slate-200 px-2 py-2 text-sm"
          >
            <option value="">—</option>
            {(zonas.length ? zonas : data?.zonas_disponiveis ?? []).map((z) => (
              <option key={z} value={z}>
                {z}
              </option>
            ))}
          </select>
          {modalidades.length > 0 && (
            <>
              <label className="text-sm text-slate-600">Modalidade</label>
              <select
                value={modalidade}
                onChange={(e) => setModalidade(e.target.value)}
                className="rounded-lg border border-slate-200 px-2 py-2 text-sm"
              >
                <option value="">geral</option>
                {modalidades.map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </select>
            </>
          )}
        </div>

        {erro && (
          <p className="rounded-lg bg-rose-50 p-3 text-sm text-rose-800">{erro}</p>
        )}

        {data && !data.avaliada && data.motivo && (
          <p className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
            {data.motivo}
          </p>
        )}

        {data?.avaliada && (
          <>
            <ul className="space-y-2">
              {data.itens.map((i) => {
                const chip = CHIP[i.status];
                const apagado = i.status === "nao_extraido";
                return (
                  <li
                    key={i.parametro}
                    className={`rounded-lg border p-3 text-sm ${
                      i.status === "atencao"
                        ? "border-amber-300 bg-amber-50"
                        : "border-slate-200 bg-slate-50"
                    } ${apagado ? "opacity-60" : ""}`}
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-medium text-slate-900">{i.rotulo}</span>
                      {i.valor && (
                        <span className="text-slate-600">{i.valor}</span>
                      )}
                      <span
                        className={`rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase ${chip.classe}`}
                      >
                        {chip.rotulo}
                      </span>
                    </div>
                    <p className="mt-1 text-slate-700">{i.leitura}</p>
                    {i.proveniencia && (
                      <p className="mt-1 text-xs text-slate-500">{i.proveniencia}</p>
                    )}
                  </li>
                );
              })}
            </ul>

            {data.proveniencia && (
              <p className="text-xs text-slate-500">{data.proveniencia}</p>
            )}
          </>
        )}

        {data && data.avisos.length > 0 && (
          <div className="rounded-lg bg-amber-50 p-3 text-xs text-amber-900">
            {data.avisos.map((a) => (
              <p key={a}>• {a}</p>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
