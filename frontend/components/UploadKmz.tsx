"use client";

import { useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  criarAnalise,
  GrupoRecusado,
  IngestaoRecusada,
  type Analise,
} from "@/lib/api";

type Recusa = { detalhe: string; orientacao: string };
type RecusaGrupo = { erro: string; detalhe: string; arquivos: string[] };

const TITULO_GRUPO: Record<string, string> = {
  GLEBAS_NAO_CONTIGUAS: "Glebas não contíguas",
  GLEBAS_SOBREPOSTAS: "Glebas se sobrepõem",
  MUNICIPIOS_DIFERENTES: "Glebas em municípios diferentes",
};

export function UploadKmz({
  onAnalise,
}: {
  onAnalise: (a: Analise) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [carregando, setCarregando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [recusa, setRecusa] = useState<Recusa | null>(null);
  const [recusaGrupo, setRecusaGrupo] = useState<RecusaGrupo | null>(null);

  async function enviar(files: File[]) {
    setCarregando(true);
    setErro(null);
    setRecusa(null);
    setRecusaGrupo(null);
    try {
      const analise = await criarAnalise(files);
      onAnalise(analise);
    } catch (e) {
      if (e instanceof GrupoRecusado) {
        setRecusaGrupo({ erro: e.erro, detalhe: e.detalhe, arquivos: e.arquivos });
      } else if (e instanceof IngestaoRecusada) {
        // Topografia/CAD: mensagem diagnóstica clara, sem stack trace.
        setRecusa({ detalhe: e.diagnostico.detalhe, orientacao: e.orientacao });
      } else {
        setErro(e instanceof Error ? e.message : "Falha ao processar o arquivo.");
      }
    } finally {
      setCarregando(false);
    }
  }

  return (
    <div className="space-y-2">
      <input
        ref={inputRef}
        type="file"
        accept=".kmz,.kml"
        multiple
        className="hidden"
        onChange={(e) => {
          const fs = Array.from(e.target.files ?? []);
          if (fs.length) enviar(fs);
          e.target.value = ""; // permite re-selecionar os mesmos arquivos
        }}
      />
      <Button onClick={() => inputRef.current?.click()} disabled={carregando}>
        {carregando ? "Processando…" : "Enviar KMZ da gleba"}
      </Button>
      <p className="text-xs text-slate-500">
        1 arquivo = uma gleba. Selecione <strong>2 ou mais KMZ vizinhos</strong> para
        analisá-los como um projeto único (união geométrica).
      </p>
      {erro && (
        <p className="rounded-lg bg-rose-50 p-3 text-sm text-rose-800">{erro}</p>
      )}
      {recusa && (
        <div className="space-y-1 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm">
          <p className="font-medium text-amber-900">
            Arquivo de topografia/CAD — não foi possível ler um perímetro.
          </p>
          <p className="text-amber-800">{recusa.detalhe}</p>
          <p className="text-amber-700">{recusa.orientacao}</p>
        </div>
      )}
      {recusaGrupo && (
        <div className="space-y-1 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm">
          <p className="font-medium text-amber-900">
            {TITULO_GRUPO[recusaGrupo.erro] ?? "Não foi possível agrupar as glebas"}
          </p>
          <p className="text-amber-800">{recusaGrupo.detalhe}</p>
          {recusaGrupo.arquivos.length > 0 && (
            <p className="text-amber-700">
              Arquivos: {recusaGrupo.arquivos.join(", ")}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
