// Marketing — casca comum das páginas públicas (home e páginas de vendas).
// Copy vem dos blueprints em docs/marketing/ (Light Copy: sem travessão, sem exclamação).

import Link from "next/link";

// Link do CTA secundário "Agendar demonstração online". Configurável por env no build
// (NEXT_PUBLIC_LINK_DEMO); o fallback de e-mail é provisório até o operador definir o canal.
export const LINK_DEMO =
  process.env.NEXT_PUBLIC_LINK_DEMO ??
  "mailto:contato@homeeye.com.br?subject=Demonstra%C3%A7%C3%A3o%20online%20Viabilidade%20homeeye";

export function BotoesCta({ escuro = false }: { escuro?: boolean }) {
  return (
    <div className="flex flex-col items-center gap-3 sm:flex-row sm:justify-center">
      <Link
        href="/registrar"
        className="inline-flex h-12 items-center justify-center rounded-xl bg-emerald-500 px-7 text-base font-semibold text-white shadow-lg shadow-emerald-500/25 transition hover:bg-emerald-400"
      >
        Criar conta grátis
      </Link>
      <a
        href={LINK_DEMO}
        className={`inline-flex h-12 items-center justify-center rounded-xl border px-7 text-base font-semibold transition ${
          escuro
            ? "border-slate-500 text-slate-100 hover:bg-slate-700"
            : "border-slate-300 text-slate-700 hover:bg-slate-100"
        }`}
      >
        Agendar demonstração online
      </a>
    </div>
  );
}

export function HeaderSite() {
  return (
    <header className="sticky top-0 z-20 border-b border-slate-800 bg-slate-900/95 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-5">
        <Link href="/" className="flex items-baseline gap-1.5">
          <span className="text-lg font-extrabold tracking-tight text-white">homeeye</span>
          <span className="text-sm font-medium text-emerald-400">Viabilidade</span>
        </Link>
        <nav className="hidden items-center gap-6 text-sm text-slate-300 md:flex">
          <a href="/#como-funciona" className="hover:text-white">
            Como funciona
          </a>
          <a href="/#para-quem" className="hover:text-white">
            Para quem é
          </a>
          <Link href="/loteadores" className="hover:text-white">
            Para loteadores
          </Link>
        </nav>
        <div className="flex items-center gap-3">
          <Link href="/login" className="text-sm font-medium text-slate-300 hover:text-white">
            Entrar
          </Link>
          <Link
            href="/registrar"
            className="inline-flex h-9 items-center rounded-lg bg-emerald-500 px-4 text-sm font-semibold text-white transition hover:bg-emerald-400"
          >
            Criar conta grátis
          </Link>
        </div>
      </div>
    </header>
  );
}

export function FaixaHonestidade() {
  return (
    <p className="mx-auto max-w-3xl px-5 text-center text-xs leading-relaxed text-slate-500">
      A Viabilidade homeeye é pré-análise de triagem. Aprovação é da prefeitura, medição oficial
      é do agrimensor, parecer jurídico é do advogado. O relatório aponta exatamente o que checar
      com cada um.
    </p>
  );
}

export function FooterSite() {
  return (
    <footer className="border-t border-slate-200 bg-slate-50 py-10">
      <div className="mx-auto max-w-4xl space-y-4 px-5 text-center">
        <p className="text-xs leading-relaxed text-slate-500">
          A Viabilidade homeeye é uma plataforma de pré-análise de viabilidade (triagem). Não
          aprova parcelamento, não substitui profissionais habilitados nem decisão municipal.
          Ausência de achado não significa ausência de problema; consulte o relatório para a
          cobertura de cada análise.
        </p>
        <p className="text-xs text-slate-400">
          <a href={LINK_DEMO} className="hover:text-slate-600">
            Contato
          </a>{" "}
          · Termos · Privacidade (LGPD)
        </p>
      </div>
    </footer>
  );
}
