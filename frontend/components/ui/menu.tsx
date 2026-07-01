"use client";

import * as React from "react";

/* Dropdown leve (sem dependências): fecha em clique-fora e Escape. Usado para
   consolidar ações secundárias da toolbar (Exportar ▾, menu do usuário) —
   princípio de 2026: menos botões soltos, ações agrupadas por intenção. */

export function Menu({
  botao,
  children,
  alinhar = "right",
}: {
  botao: React.ReactNode;
  children: React.ReactNode;
  alinhar?: "left" | "right";
}) {
  const [aberto, setAberto] = React.useState(false);
  const ref = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    if (!aberto) return;
    function fora(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setAberto(false);
    }
    function esc(e: KeyboardEvent) {
      if (e.key === "Escape") setAberto(false);
    }
    document.addEventListener("mousedown", fora);
    document.addEventListener("keydown", esc);
    return () => {
      document.removeEventListener("mousedown", fora);
      document.removeEventListener("keydown", esc);
    };
  }, [aberto]);

  return (
    <div ref={ref} className="relative">
      <div onClick={() => setAberto((v) => !v)}>{botao}</div>
      {aberto && (
        <div
          className={`absolute top-full z-[1200] mt-1.5 min-w-[13rem] overflow-hidden rounded-xl border border-slate-200 bg-white py-1 shadow-lg ${
            alinhar === "right" ? "right-0" : "left-0"
          }`}
          onClick={() => setAberto(false)}
        >
          {children}
        </div>
      )}
    </div>
  );
}

export function MenuItem({
  onClick,
  disabled,
  children,
  destaque,
}: {
  onClick?: () => void;
  disabled?: boolean;
  children: React.ReactNode;
  destaque?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`flex w-full items-center gap-2 px-3 py-2 text-left text-sm transition-colors ${
        destaque ? "text-rose-600 hover:bg-rose-50" : "text-slate-700 hover:bg-slate-50"
      } disabled:pointer-events-none disabled:opacity-50`}
    >
      {children}
    </button>
  );
}

export function MenuLabel({ children }: { children: React.ReactNode }) {
  return (
    <p className="truncate px-3 pb-1 pt-2 text-[11px] font-medium uppercase tracking-wide text-slate-400">
      {children}
    </p>
  );
}

export function MenuDivisor() {
  return <div className="my-1 h-px bg-slate-100" />;
}
