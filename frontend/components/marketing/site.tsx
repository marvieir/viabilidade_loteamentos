// Marketing — casca comum das páginas públicas (home e páginas de vendas).
// Copy vem dos blueprints em docs/marketing/ (Light Copy: sem travessão, sem exclamação).
// Paleta editorial-imobiliária: verde-floresta profundo + creme + terracota de detalhe.

import Link from "next/link";

// Link do CTA secundário "Agendar demonstração online". Configurável por env no build
// (NEXT_PUBLIC_LINK_DEMO); e-mail definido pelo operador em 21/07/2026.
export const LINK_DEMO =
  process.env.NEXT_PUBLIC_LINK_DEMO ??
  "mailto:marco.rodrigues.vieira@gmail.com?subject=Demonstra%C3%A7%C3%A3o%20online%20Viabilidade%20homeeye";

export const CORES = {
  tinta: "#1c2a24",
  florestaProfunda: "#16241f",
  floresta: "#1b4332",
  musgo: "#40695a",
  papel: "#f7f3ea",
  papel2: "#efe8d9",
  cremeBotao: "#e9dfc4",
  terracota: "#b25b38",
} as const;

export function BotoesCta({ escuro = false }: { escuro?: boolean }) {
  return (
    <div className="flex flex-col items-center gap-3 sm:flex-row sm:justify-center">
      <Link
        href="/registrar"
        className={`inline-flex h-12 items-center justify-center rounded-xl px-7 text-base font-semibold shadow-lg transition ${
          escuro
            ? "bg-[#e9dfc4] text-[#16241f] shadow-black/30 hover:bg-[#f3ecd8]"
            : "bg-[#1b4332] text-[#f3ecd8] shadow-[#1b4332]/25 hover:bg-[#16382a]"
        }`}
      >
        Criar conta grátis
      </Link>
      <a
        href={LINK_DEMO}
        className={`inline-flex h-12 items-center justify-center rounded-xl border px-7 text-base font-semibold transition ${
          escuro
            ? "border-[#4a6557] text-[#e6e0cd] hover:bg-[#22362d]"
            : "border-[#c4bba4] text-[#3c4a42] hover:bg-[#efe8d9]"
        }`}
      >
        Agendar demonstração online
      </a>
    </div>
  );
}

export function HeaderSite() {
  return (
    <header className="sticky top-0 z-20 border-b border-[#2c4a3b] bg-[#16241f]/95 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-3 px-4 sm:px-5">
        <Link href="/" className="flex shrink-0 items-baseline gap-1.5">
          <span className="text-lg font-extrabold tracking-tight text-[#f3ecd8]">homeeye</span>
          <span className="font-display text-sm font-medium italic text-[#9cc0ab]">
            Viabilidade
          </span>
        </Link>
        <nav className="hidden items-center gap-6 text-sm text-[#c9d4c9] md:flex">
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
            className="hidden text-sm font-medium text-[#c9d4c9] transition hover:text-white sm:block"
          >
            Entrar
          </Link>
          <Link
            href="/registrar"
            className="inline-flex h-9 items-center whitespace-nowrap rounded-lg bg-[#e9dfc4] px-3 text-sm font-semibold text-[#16241f] transition hover:bg-[#f3ecd8] sm:px-4"
          >
            Criar conta grátis
          </Link>
          {/* Menu mobile: <details> NATIVO — abre/fecha sem JavaScript (progressive enhancement) */}
          <details className="relative md:hidden">
            <summary
              aria-label="Abrir menu"
              className="flex h-9 w-9 cursor-pointer list-none items-center justify-center rounded-lg border border-[#3b5748] text-[#e6e0cd] transition hover:bg-[#22362d] [&::-webkit-details-marker]:hidden"
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
            <nav className="absolute right-0 top-11 w-56 rounded-xl border border-[#2c4a3b] bg-[#16241f] p-2 shadow-xl shadow-black/40">
              <a
                href="/#como-funciona"
                className="block rounded-lg px-3 py-2.5 text-sm text-[#c9d4c9] transition hover:bg-[#22362d] hover:text-white"
              >
                Como funciona
              </a>
              <a
                href="/#para-quem"
                className="block rounded-lg px-3 py-2.5 text-sm text-[#c9d4c9] transition hover:bg-[#22362d] hover:text-white"
              >
                Para quem é
              </a>
              <Link
                href="/loteadores"
                className="block rounded-lg px-3 py-2.5 text-sm text-[#c9d4c9] transition hover:bg-[#22362d] hover:text-white"
              >
                Para loteadores
              </Link>
              <div className="my-1 h-px bg-[#2c4a3b]" />
              <Link
                href="/login"
                className="block rounded-lg px-3 py-2.5 text-sm font-medium text-[#e6e0cd] transition hover:bg-[#22362d] hover:text-white"
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
    <p className="mx-auto max-w-3xl px-5 text-center text-xs leading-relaxed text-[#7d786a]">
      A Viabilidade homeeye é pré-análise de triagem. Aprovação é da prefeitura, medição oficial
      é do agrimensor, parecer jurídico é do advogado. O relatório aponta exatamente o que checar
      com cada um.
    </p>
  );
}

export function FooterSite() {
  return (
    <footer className="border-t border-[#ddd5c2] bg-[#f3efe4] py-10">
      <div className="mx-auto max-w-4xl space-y-4 px-5 text-center">
        <p className="text-xs leading-relaxed text-[#7d786a]">
          A Viabilidade homeeye é uma plataforma de pré-análise de viabilidade (triagem). Não
          aprova parcelamento, não substitui profissionais habilitados nem decisão municipal.
          Ausência de achado não significa ausência de problema; consulte o relatório para a
          cobertura de cada análise.
        </p>
        <p className="text-xs text-[#9a937f]">
          <a href={LINK_DEMO} className="transition hover:text-[#5a5546]">
            Contato
          </a>{" "}
          · Termos · Privacidade (LGPD)
        </p>
      </div>
    </footer>
  );
}
