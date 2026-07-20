"use client";

// "Esqueci minha senha" — pede o e-mail e mostra SEMPRE a mesma confirmação (a resposta
// do backend não revela se a conta existe). O link de redefinição chega por e-mail.

import { useState } from "react";
import Link from "next/link";
import { esqueciSenha } from "@/lib/auth";

export default function EsqueciPage() {
  const [email, setEmail] = useState("");
  const [mensagem, setMensagem] = useState<string | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErro(null);
    setEnviando(true);
    try {
      setMensagem(await esqueciSenha(email));
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Falha ao pedir a redefinição.");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <main className="grid min-h-screen place-items-center bg-slate-50 px-4">
      <div className="w-full max-w-sm rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">
        <h1 className="text-xl font-bold tracking-tight">Esqueci minha senha</h1>
        <p className="mt-1.5 text-sm text-slate-500">
          Informe o e-mail da sua conta. Enviaremos um link para criar uma senha nova.
        </p>

        {mensagem ? (
          <div className="mt-6 space-y-4">
            <p className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
              {mensagem}
            </p>
            <Link
              href="/login"
              className="block text-center text-sm font-semibold text-indigo-600 hover:underline"
            >
              Voltar para o login
            </Link>
          </div>
        ) : (
          <form onSubmit={onSubmit} className="mt-6 space-y-4">
            <label className="block">
              <span className="mb-1 block text-sm font-medium text-slate-700">E-mail</span>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="voce@exemplo.com"
                autoComplete="email"
                required
                className="h-10 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm shadow-sm outline-none transition-colors placeholder:text-slate-400 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100"
              />
            </label>

            {erro && (
              <p className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
                {erro}
              </p>
            )}

            <button
              type="submit"
              disabled={enviando}
              className="h-10 w-full rounded-lg bg-gradient-to-br from-indigo-600 to-violet-600 px-4 text-sm font-semibold text-white shadow-sm transition hover:opacity-95 disabled:opacity-60"
            >
              {enviando ? "Enviando…" : "Enviar link de redefinição"}
            </button>

            <p className="text-center text-sm text-slate-500">
              Lembrou a senha?{" "}
              <Link href="/login" className="font-semibold text-indigo-600 hover:underline">
                Entrar
              </Link>
            </p>
          </form>
        )}
      </div>
    </main>
  );
}
