"use client";

// Fase 12 — formulário compartilhado de login/cadastro. Visual alinhado ao Hero da
// home (card branco, gradiente índigo). Só transporta dados — nenhuma regra de negócio.

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/components/auth/AuthProvider";
import { IconMap } from "@/components/Icons";

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
      router.push("/");
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Falha na autenticação.");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <main className="mx-auto grid max-w-md place-items-center px-4 py-16 sm:py-24">
      <div className="w-full rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">
        <div className="mx-auto grid h-14 w-14 place-items-center rounded-2xl bg-gradient-to-br from-indigo-600 to-violet-600 text-white shadow-sm">
          <IconMap width={28} height={28} />
        </div>
        <h1 className="mt-5 text-center text-2xl font-bold tracking-tight">
          {cadastro ? "Criar conta" : "Entrar"}
        </h1>
        <p className="mx-auto mt-2 max-w-xs text-center text-sm text-slate-500">
          {cadastro
            ? "Cadastre-se para salvar e reabrir suas análises de pré-viabilidade."
            : "Acesse suas análises de pré-viabilidade de loteamento."}
        </p>

        <form onSubmit={onSubmit} className="mt-6 space-y-4">
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
            <p className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{erro}</p>
          )}

          <button
            type="submit"
            disabled={enviando}
            className="w-full rounded-lg bg-gradient-to-br from-indigo-600 to-violet-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:opacity-95 disabled:opacity-60"
          >
            {enviando ? "Aguarde…" : cadastro ? "Criar conta" : "Entrar"}
          </button>
        </form>

        <p className="mt-5 text-center text-sm text-slate-500">
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
        className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100"
        {...rest}
      />
    </label>
  );
}
