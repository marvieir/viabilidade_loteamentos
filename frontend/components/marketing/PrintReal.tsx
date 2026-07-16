"use client";

// Marketing — imagem de print REAL da plataforma (regra do blueprint: mockup inventado é
// proibido). Enquanto o arquivo não existe em /public/marketing/, degrada para um quadro
// neutro com a legenda, sem imagem quebrada.

import { useState } from "react";

export function PrintReal({
  src,
  alt,
  legenda,
  className = "",
}: {
  src: string;
  alt: string;
  legenda?: string;
  className?: string;
}) {
  const [erro, setErro] = useState(false);

  if (erro) {
    return (
      <figure
        className={`grid min-h-[220px] place-items-center rounded-xl border border-dashed border-slate-300 bg-slate-50 p-6 text-center ${className}`}
      >
        <figcaption className="text-sm text-slate-500">
          <span className="mb-1 block text-2xl">🗺️</span>
          {legenda ?? alt}
          <span className="mt-1 block text-[11px] text-slate-400">
            print real da plataforma (em captura)
          </span>
        </figcaption>
      </figure>
    );
  }

  return (
    <figure className={className}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={src}
        alt={alt}
        onError={() => setErro(true)}
        className="w-full rounded-xl border border-slate-200 shadow-lg"
      />
      {legenda && (
        <figcaption className="mt-2 text-center text-xs text-slate-500">{legenda}</figcaption>
      )}
    </figure>
  );
}
