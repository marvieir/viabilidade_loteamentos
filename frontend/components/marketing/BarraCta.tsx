"use client";

// Marketing — barra de CTA fixa que aparece depois que o leitor passa do hero (um único
// objetivo de conversão sempre à mão, sem atrapalhar a leitura).

import Link from "next/link";
import { useEffect, useState } from "react";

export function BarraCta({ texto }: { texto: string }) {
  const [visivel, setVisivel] = useState(false);

  useEffect(() => {
    const onScroll = () => setVisivel(window.scrollY > 850);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <div
      className={`fixed inset-x-0 bottom-0 z-30 transition-transform duration-300 ${
        visivel ? "translate-y-0" : "translate-y-full"
      }`}
    >
      <div className="border-t border-[#2e1f7a] bg-[#170d48]/95 px-4 py-3 backdrop-blur">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-4">
          <p className="hidden text-sm text-[#d8d2c0] sm:block">{texto}</p>
          <div className="flex w-full items-center justify-center gap-3 sm:w-auto">
            <Link
              href="/registrar"
              className="inline-flex h-10 items-center rounded-lg bg-[#ff914d] px-5 text-sm font-semibold text-[#170d48] transition hover:bg-[#fff4f4]"
            >
              Criar conta grátis
            </Link>
            <span className="text-xs text-[#9287c4]">1 gleba/mês grátis</span>
          </div>
        </div>
      </div>
    </div>
  );
}
