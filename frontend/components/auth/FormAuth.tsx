"use client";

// Fase 12 — formulário compartilhado de login/cadastro. Split-screen de produto:
// painel de marca (proposta de valor) + formulário. Só transporta dados — nenhuma
// regra de negócio no front.

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/components/auth/AuthProvider";
import { IconMap } from "@/components/Icons";

const VALOR = [
  {
    t: "Triagem determinística",
    d: "Ambiental, declividade, aproveitamento, urbanismo e financeiro — mesma gleba, mesmo resultado, sempre.",
  },
  {
    t: "Cada número com proveniência",
    d: "Fonte legal, perfil municipal e data de referência acompanham todo valor calculado.",
  },
  {
    t: "Do KMZ ao laudo",
    d: "Envie o polígono da gleba e exporte a análise em PDF ou Excel para o seu cliente.",
  },
];

export function FormAuth({ modo }: { modo: "login" | "registrar" }) {
  const router = useRouter();
  const { entrar, cadastrar } = useAuth();
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [nome, setNome] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  const cadastro = modo === "registrar";

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErro(null);
    if (cadastro && senha.length < 8) {
      setErro("A senha precisa de pelo menos 8 caracteres.");
      return;
    }
    setEnviando(true);
    try {
      if (cadastro) await cadastrar(email, senha, nome);
      else await entrar(email, senha);
      router.push("/app");
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Falha na autenticação.");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <main className="grid min-h-screen lg:grid-cols-2">
      {/* Painel de marca — a primeira impressão do produto (desktop) */}
      <aside className="relative hidden flex-col justify-between overflow-hidden bg-gradient-to-br from-indigo-700 via-indigo-600 to-violet-600 p-10 text-white lg:flex">
        <div className="pointer-events-none absolute -right-24 -top-24 h-96 w-96 rounded-full bg-white/10 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-32 -left-16 h-80 w-80 rounded-full bg-violet-400/20 blur-3xl" />

        <div className="relative flex items-center gap-3">
          <div className="grid h-10 w-10 place-items-center rounded-xl bg-white/15 shadow-sm backdrop-blur">
            <IconMap width={22} height={22} />
          </div>
          <p className="text-sm font-bold tracking-tight">
            Pré-Viabilidade <span className="font-medium text-indigo-200">· Loteamento</span>
          </p>
        </div>

        <div className="relative max-w-md">
          <h2 className="text-3xl font-bold leading-tight tracking-tight">
            A triagem da gleba antes da due diligence.
          </h2>
          <ul className="mt-8 space-y-5">
            {VALOR.map((v) => (
              <li key={v.t} className="flex gap-3">
                <svg
                  width="18"
                  height="18"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2.5"
                  className="mt-0.5 shrink-0 text-emerald-300"
                >
                  <path d="M20 6L9 17l-5-5" />
                </svg>
                <div>
                  <p className="text-sm font-semibold">{v.t}</p>
                  <p className="mt-0.5 text-[13px] leading-snug text-indigo-100/90">{v.d}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>

        <p className="relative text-[11px] text-indigo-200/80">
          Ferramenta de pré-viabilidade/triagem — não decide aprovação municipal.
        </p>
      </aside>

      {/* Formulário */}
      <section className="grid place-items-center px-4 py-12 sm:py-16">
        <div className="w-full max-w-sm">
          {/* Marca no mobile (o painel esquerdo some) */}
          <div className="mb-8 flex items-center justify-center gap-2.5 lg:hidden">
            <div className="grid h-10 w-10 place-items-center rounded-xl bg-gradient-to-br from-indigo-600 to-violet-600 text-white shadow-sm">
              <IconMap width={22} height={22} />
            </div>
            <p className="text-sm font-bold tracking-tight">
              Pré-Viabilidade <span className="font-medium text-slate-400">· Loteamento</span>
            </p>
          </div>

          <h1 className="text-2xl font-bold tracking-tight">
            {cadastro ? "Criar sua conta" : "Bem-vindo de volta"}
          </h1>
          <p className="mt-1.5 text-sm text-slate-500">
            {cadastro
              ? "Comece a analisar glebas em minutos — salve e reabra suas análises."
              : "Entre para acessar suas análises de pré-viabilidade."}
          </p>

          <form onSubmit={onSubmit} className="mt-8 space-y-4">
            {cadastro && (
              <Campo
                rotulo="Nome (opcional)"
                type="text"
                value={nome}
                onChange={setNome}
                placeholder="Seu nome"
                autoComplete="name"
              />
            )}
            <Campo
              rotulo="E-mail"
              type="email"
              value={email}
              onChange={setEmail}
              placeholder="voce@exemplo.com"
              autoComplete="email"
              required
            />
            <Campo
              rotulo="Senha"
              type="password"
              value={senha}
              onChange={setSenha}
              placeholder={cadastro ? "mínimo 8 caracteres" : "sua senha"}
              autoComplete={cadastro ? "new-password" : "current-password"}
              required
            />

            {erro && (
              <p className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
                {erro}
              </p>
            )}

            <button
              type="submit"
              disabled={enviando}
              className="h-10 w-full rounded-lg bg-gradient-to-br from-indigo-600 to-violet-600 px-4 text-sm font-semibold text-white shadow-sm transition hover:opacity-95 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500/40 focus-visible:ring-offset-2 disabled:opacity-60"
            >
              {enviando ? "Aguarde…" : cadastro ? "Criar conta" : "Entrar"}
            </button>
          </form>

          <p className="mt-6 text-center text-sm text-slate-500">
            {cadastro ? (
              <>
                Já tem conta?{" "}
                <Link href="/login" className="font-semibold text-indigo-600 hover:underline">
                  Entrar
                </Link>
              </>
            ) : (
              <>
                Não tem conta?{" "}
                <Link href="/registrar" className="font-semibold text-indigo-600 hover:underline">
                  Criar conta
                </Link>
              </>
            )}
          </p>
        </div>
      </section>
    </main>
  );
}

function Campo({
  rotulo,
  value,
  onChange,
  ...rest
}: {
  rotulo: string;
  value: string;
  onChange: (v: string) => void;
} & Omit<React.InputHTMLAttributes<HTMLInputElement>, "value" | "onChange">) {
  return (
    <label className="block">
      <span className="mb-1 block text-sm font-medium text-slate-700">{rotulo}</span>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="h-10 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm shadow-sm outline-none transition-colors placeholder:text-slate-400 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100"
        {...rest}
      />
    </label>
  );
}
