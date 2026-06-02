"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { corrigirMunicipio, type Jurisdicao } from "@/lib/api";

const rotulo: Record<string, string> = {
  BASE_FEDERAL: "Cobertura: Base Federal",
  PARCIAL_UF: "Cobertura: Parcial (UF)",
  COMPLETA: "Cobertura: Completa",
};

const variante: Record<string, "warning" | "info" | "success"> = {
  BASE_FEDERAL: "warning",
  PARCIAL_UF: "info",
  COMPLETA: "success",
};

export function BadgeCobertura({
  jurisdicao,
  analiseId,
  onJurisdicao,
}: {
  jurisdicao: Jurisdicao;
  analiseId: string;
  onJurisdicao: (j: Jurisdicao) => void;
}) {
  const {
    cobertura,
    nao_considerado,
    municipio,
    uf,
    origem,
    cruza_divisa,
    municipios_candidatos,
  } = jurisdicao;

  const [editando, setEditando] = useState(false);
  const [cod, setCod] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(false);

  async function aplicar(codIbge: string) {
    setCarregando(true);
    setErro(null);
    try {
      const j = await corrigirMunicipio(analiseId, codIbge);
      onJurisdicao(j);
      setEditando(false);
      setCod("");
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Falha ao corrigir município.");
    } finally {
      setCarregando(false);
    }
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant={variante[cobertura]}>{rotulo[cobertura]}</Badge>
        <span className="text-sm text-slate-600">
          {municipio
            ? `${municipio}${uf ? ` / ${uf}` : ""}`
            : "Município não resolvido"}
        </span>
        <span
          className={`rounded-full px-2 py-0.5 text-xs font-medium ${
            origem === "informado"
              ? "bg-sky-100 text-sky-800"
              : "bg-slate-100 text-slate-600"
          }`}
        >
          {origem === "informado" ? "informado" : "detectado"}
        </span>
        <button
          type="button"
          onClick={() => setEditando((v) => !v)}
          className="text-xs font-medium text-sky-700 underline-offset-2 hover:underline"
        >
          corrigir município
        </button>
      </div>

      {cruza_divisa && municipios_candidatos.length > 0 && (
        <div className="rounded-lg bg-amber-50 p-3 text-xs text-amber-900">
          <p className="mb-1 font-medium">
            A gleba cruza a divisa de {municipios_candidatos.length} municípios.
            Confirme qual rege a análise:
          </p>
          <div className="flex flex-wrap gap-2">
            {municipios_candidatos.map((m) => (
              <button
                key={m.cod_ibge}
                type="button"
                disabled={carregando}
                onClick={() => aplicar(m.cod_ibge)}
                className="rounded-md border border-amber-300 bg-white px-2 py-1 font-medium hover:bg-amber-100 disabled:opacity-50"
              >
                {m.municipio} / {m.uf}
              </button>
            ))}
          </div>
        </div>
      )}

      {editando && (
        <div className="flex flex-wrap items-end gap-2 rounded-lg bg-slate-50 p-3">
          <label className="flex flex-col gap-1 text-xs text-slate-600">
            Código IBGE do município
            <input
              value={cod}
              onChange={(e) => setCod(e.target.value)}
              placeholder="ex.: 3506607"
              className="rounded-lg border border-slate-300 px-2 py-1 text-sm text-slate-900"
            />
          </label>
          <Button
            onClick={() => aplicar(cod.trim())}
            disabled={carregando || cod.trim().length === 0}
            className="px-3 py-1"
          >
            {carregando ? "Aplicando…" : "Aplicar"}
          </Button>
        </div>
      )}

      {erro && <p className="text-xs text-rose-700">{erro}</p>}

      {nao_considerado.length > 0 && (
        <div className="rounded-lg bg-amber-50 p-3 text-xs text-amber-900">
          <p className="mb-1 font-medium">Não considerado nesta análise:</p>
          <ul className="list-disc space-y-0.5 pl-4">
            {nao_considerado.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
