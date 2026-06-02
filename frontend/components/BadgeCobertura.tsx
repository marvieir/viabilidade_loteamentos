"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import {
  buscarMunicipios,
  corrigirMunicipio,
  type Jurisdicao,
  type MunicipioRef,
} from "@/lib/api";

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
  const [busca, setBusca] = useState("");
  const [resultados, setResultados] = useState<MunicipioRef[]>([]);
  const [buscando, setBuscando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(false);

  // Autocomplete por nome (debounce 250 ms). A busca é offline, na malha local.
  useEffect(() => {
    const termo = busca.trim();
    if (!editando || termo.length < 2) {
      setResultados([]);
      return;
    }
    let vivo = true;
    setBuscando(true);
    const t = setTimeout(async () => {
      try {
        const r = await buscarMunicipios(termo);
        if (vivo) setResultados(r);
      } catch {
        if (vivo) setResultados([]);
      } finally {
        if (vivo) setBuscando(false);
      }
    }, 250);
    return () => {
      vivo = false;
      clearTimeout(t);
    };
  }, [busca, editando]);

  async function aplicar(codIbge: string) {
    setCarregando(true);
    setErro(null);
    try {
      const j = await corrigirMunicipio(analiseId, codIbge);
      onJurisdicao(j);
      setEditando(false);
      setBusca("");
      setResultados([]);
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
        <div className="space-y-1 rounded-lg bg-slate-50 p-3">
          <label className="flex flex-col gap-1 text-xs text-slate-600">
            Buscar município por nome
            <input
              autoFocus
              value={busca}
              onChange={(e) => setBusca(e.target.value)}
              placeholder="ex.: São Roque"
              className="rounded-lg border border-slate-300 px-2 py-1 text-sm text-slate-900"
            />
          </label>
          {busca.trim().length >= 2 && (
            <div className="max-h-48 overflow-auto rounded-lg border border-slate-200 bg-white">
              {buscando && (
                <p className="px-3 py-2 text-xs text-slate-400">Buscando…</p>
              )}
              {!buscando && resultados.length === 0 && (
                <p className="px-3 py-2 text-xs text-slate-400">
                  Nenhum município encontrado (a malha municipal pode não estar
                  carregada).
                </p>
              )}
              {resultados.map((m) => (
                <button
                  key={m.cod_ibge}
                  type="button"
                  disabled={carregando}
                  onClick={() => aplicar(m.cod_ibge)}
                  className="block w-full px-3 py-1.5 text-left text-sm text-slate-800 hover:bg-sky-50 disabled:opacity-50"
                >
                  {m.municipio} <span className="text-slate-400">/ {m.uf}</span>
                </button>
              ))}
            </div>
          )}
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
