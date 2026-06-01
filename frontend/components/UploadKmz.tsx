"use client";

import { useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { criarAnalise, type Analise } from "@/lib/api";

export function UploadKmz({
  onAnalise,
}: {
  onAnalise: (a: Analise) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [carregando, setCarregando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  async function enviar(file: File) {
    setCarregando(true);
    setErro(null);
    try {
      const analise = await criarAnalise(file);
      onAnalise(analise);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Falha ao processar o KMZ.");
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
    </div>
  );
}
