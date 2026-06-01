"use client";

import { useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { criarAnalise, IngestaoRecusada, type Analise } from "@/lib/api";

type Recusa = { detalhe: string; orientacao: string };

export function UploadKmz({
  onAnalise,
}: {
  onAnalise: (a: Analise) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [carregando, setCarregando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [recusa, setRecusa] = useState<Recusa | null>(null);

  async function enviar(file: File) {
    setCarregando(true);
    setErro(null);
    setRecusa(null);
    try {
      const analise = await criarAnalise(file);
      onAnalise(analise);
    } catch (e) {
      if (e instanceof IngestaoRecusada) {
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
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) enviar(f);
        }}
      />
      <Button onClick={() => inputRef.current?.click()} disabled={carregando}>
        {carregando ? "Processando…" : "Enviar KMZ da gleba"}
      </Button>
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
    </div>
  );
}
