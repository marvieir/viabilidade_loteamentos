"use client";

// Redefinição de senha — a página que o link do e-mail abre (?token=...). O token é de
// uso único e expira; erro do backend já vem com a instrução de pedir um link novo.

import { Suspense, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { redefinirSenha } from "@/lib/auth";

export default function RedefinirPage() {
  // useSearchParams exige um limite de Suspense para o prerender estático.
  return (
    <Suspense fallback={null}>
      <FormRedefinir />
    </Suspense>
  );
}

function FormRedefinir() {
  const token = useSearchParams().get("token") ?? "";
  const [senha, setSenha] = useState("");
  const [confirma, setConfirma] = useState("");
  const [mensagem, setMensagem] = useState<string | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErro(null);
    if (senha.length < 8) {
      setErro("A senha precisa de pelo menos 8 caracteres.");
      return;
    }
    if (senha !== confirma) {
      setErro("As duas senhas não conferem.");
      return;
    }
    setEnviando(true);
    try {
      setMensagem(await redefinirSenha(token, senha));
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Falha ao redefinir a senha.");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <main className="grid min-h-screen place-items-center bg-slate-50 px-4">
      <div className="w-full max-w-sm rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">
        <h1 className="text-xl font-bold tracking-tight">Criar senha nova</h1>

        {!token ? (
          <div className="mt-4 space-y-4">
            <p className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
              Este endereço não tem um código de redefinição. Abra o link exatamente como
              veio no e-mail, ou peça um link novo.
            </p>
            <Link
              href="/esqueci"
              className="block text-center text-sm font-semibold text-indigo-600 hover:underline"
            >
              Pedir um link novo
            </Link>
          </div>
        ) : mensagem ? (
          <div className="mt-4 space-y-4">
            <p className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
              {mensagem}
            </p>
            <Link
              href="/login"
              className="block h-10 rounded-lg bg-gradient-to-br from-indigo-600 to-violet-600 px-4 text-center text-sm font-semibold leading-10 text-white shadow-sm transition hover:opacity-95"
            >
              Ir para o login
            </Link>
          </div>
        ) : (
          <form onSubmit={onSubmit} className="mt-6 space-y-4">
            <Campo
              rotulo="Senha nova"
              value={senha}
              onChange={setSenha}
              placeholder="mínimo 8 caracteres"
            />
            <Campo
              rotulo="Repita a senha nova"
              value={confirma}
              onChange={setConfirma}
              placeholder="a mesma senha"
            />

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
              {enviando ? "Salvando…" : "Salvar senha nova"}
            </button>
          </form>
        )}
      </div>
    </main>
  );
}

function Campo({
  rotulo,
  value,
  onChange,
  placeholder,
}: {
  rotulo: string;
  value: string;
  onChange: (v: string) => void;
  placeholder: string;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-sm font-medium text-slate-700">{rotulo}</span>
      <input
        type="password"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        autoComplete="new-password"
        required
        className="h-10 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm shadow-sm outline-none transition-colors placeholder:text-slate-400 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100"
      />
    </label>
  );
}
