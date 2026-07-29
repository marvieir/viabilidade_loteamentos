// Marketing — casca comum das páginas públicas (home e páginas de vendas).
// Copy vem dos blueprints em docs/marketing/ (Light Copy: sem travessão, sem exclamação).
// Paleta voaz.app (29/07): marinho profundo + creme + laranja de acento. O verde da marca
// NÃO entra aqui — fica reservado para estado no produto (conforme/confirmado).

import Link from "next/link";
import { Logo } from "@/components/marca/Logo";

// Link do CTA secundário "Agendar demonstração online". Configurável por env no build
// (NEXT_PUBLIC_LINK_DEMO); e-mail definido pelo operador em 21/07/2026.
export const LINK_DEMO =
  process.env.NEXT_PUBLIC_LINK_DEMO ??
  "mailto:marco.rodrigues.vieira@gmail.com?subject=Demonstra%C3%A7%C3%A3o%20online%20voaz.app";

export const CORES = {
  tinta: "#1d1252",
  marinhoProfundo: "#170d48",
  marinho: "#241862",
  marinhoClaro: "#4a3f7a",
  papel: "#fbf6f1",
  papel2: "#fff4f4",
  laranja: "#ff914d",
  laranjaEscuro: "#db6b1a",
} as const;

export function BotoesCta({ escuro = false }: { escuro?: boolean }) {
  return (
    <div className="flex flex-col items-center gap-3 sm:flex-row sm:justify-center">
      <Link
        href="/registrar"
        className={`inline-flex h-12 items-center justify-center rounded-xl px-7 text-base font-semibold shadow-lg transition ${
          escuro
            ? "bg-[#ff914d] text-[#170d48] shadow-black/30 hover:bg-[#db6b1a] hover:text-white"
            : "bg-[#ff914d] text-[#170d48] shadow-[#ff914d]/30 hover:bg-[#db6b1a] hover:text-white"
        }`}
      >
        Criar conta grátis
      </Link>
      <a
        href={LINK_DEMO}
        className={`inline-flex h-12 items-center justify-center rounded-xl border px-7 text-base font-semibold transition ${
          escuro
            ? "border-[#4a3f7a] text-[#fdeae4] hover:bg-[#241862]"
            : "border-[#e3d5c8] text-[#4a3f7a] hover:bg-[#fff4f4]"
        }`}
      >
        Agendar demonstração online
      </a>
    </div>
  );
}

export function HeaderSite() {
  return (
    <header className="sticky top-0 z-20 border-b border-[#2e1f7a] bg-[#170d48]/95 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-3 px-4 sm:px-5">
        <Link href="/" className="flex shrink-0 items-center" aria-label="voaz.app — início">
          <Logo tamanho={30} />
        </Link>
        <nav className="hidden items-center gap-6 text-sm text-[#c3b8e8] md:flex">
          <a href="/#como-funciona" className="transition hover:text-white">
            Como funciona
          </a>
          <a href="/#para-quem" className="transition hover:text-white">
            Para quem é
          </a>
          <Link href="/loteadores" className="transition hover:text-white">
            Para loteadores
          </Link>
        </nav>
        <div className="flex shrink-0 items-center gap-2 sm:gap-3">
          {/* No mobile o "Entrar" mora dentro do menu (o header espremia — MKT-5 item 1) */}
          <Link
            href="/login"
            className="hidden text-sm font-medium text-[#c3b8e8] transition hover:text-white sm:block"
          >
            Entrar
          </Link>
          <Link
            href="/registrar"
            className="inline-flex h-9 items-center whitespace-nowrap rounded-lg bg-[#ff914d] px-3 text-sm font-semibold text-[#170d48] transition hover:bg-[#db6b1a] hover:text-white sm:px-4"
          >
            Criar conta grátis
          </Link>
          {/* Menu mobile: <details> NATIVO — abre/fecha sem JavaScript (progressive enhancement) */}
          <details className="relative md:hidden">
            <summary
              aria-label="Abrir menu"
              className="flex h-9 w-9 cursor-pointer list-none items-center justify-center rounded-lg border border-[#2e1f7a] text-[#fdeae4] transition hover:bg-[#241862] [&::-webkit-details-marker]:hidden"
            >
              <svg
                width="18"
                height="18"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
              >
                <path d="M3 6h18M3 12h18M3 18h18" />
              </svg>
            </summary>
            <nav className="absolute right-0 top-11 w-56 rounded-xl border border-[#2e1f7a] bg-[#170d48] p-2 shadow-xl shadow-black/40">
              <a
                href="/#como-funciona"
                className="block rounded-lg px-3 py-2.5 text-sm text-[#c3b8e8] transition hover:bg-[#241862] hover:text-white"
              >
                Como funciona
              </a>
              <a
                href="/#para-quem"
                className="block rounded-lg px-3 py-2.5 text-sm text-[#c3b8e8] transition hover:bg-[#241862] hover:text-white"
              >
                Para quem é
              </a>
              <Link
                href="/loteadores"
                className="block rounded-lg px-3 py-2.5 text-sm text-[#c3b8e8] transition hover:bg-[#241862] hover:text-white"
              >
                Para loteadores
              </Link>
              <div className="my-1 h-px bg-[#2e1f7a]" />
              <Link
                href="/login"
                className="block rounded-lg px-3 py-2.5 text-sm font-medium text-[#fdeae4] transition hover:bg-[#241862] hover:text-white"
              >
                Entrar
              </Link>
            </nav>
          </details>
        </div>
      </div>
    </header>
  );
}

export function FaixaHonestidade() {
  return (
    <p className="mx-auto max-w-3xl px-5 text-center text-xs leading-relaxed text-[#96796a]">
      A voaz.app é pré-análise de triagem. Aprovação é da prefeitura, medição oficial
      é do agrimensor, parecer jurídico é do advogado. O relatório aponta exatamente o que checar
      com cada um.
    </p>
  );
}

export function FooterSite() {
  return (
    <footer className="border-t border-[#e3d5c8] bg-[#fbf6f1] py-10">
      <div className="mx-auto max-w-4xl space-y-4 px-5 text-center">
        <p className="text-xs leading-relaxed text-[#96796a]">
          A voaz.app é uma plataforma de pré-análise de viabilidade (triagem). Não
          aprova parcelamento, não substitui profissionais habilitados nem decisão municipal.
          Ausência de achado não significa ausência de problema; consulte o relatório para a
          cobertura de cada análise.
        </p>
        <p className="text-xs text-[#96796a]">
          <a href={LINK_DEMO} className="transition hover:text-[#5b4a3e]">
            Contato
          </a>{" "}
          · Termos · Privacidade (LGPD)
        </p>
      </div>
    </footer>
  );
}
