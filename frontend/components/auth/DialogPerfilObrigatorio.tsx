"use client";

// Contato obrigatório no 1º login (pedido do operador, 23/07): modal que NÃO fecha até o
// usuário salvar nome + celular. Sem ✕, sem clique-fora, sem Esc — o backend valida
// (PATCH /api/auth/perfil) e o usuário do contexto é atualizado, o que desmonta o modal.

import { useState } from "react";
import { atualizarPerfil } from "@/lib/auth";
import { useAuth } from "@/components/auth/AuthProvider";

export function DialogPerfilObrigatorio() {
  const { usuario, atualizarUsuario } = useAuth();
  const [nome, setNome] = useState(usuario?.nome ?? "");
  const [celular, setCelular] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErro(null);
    setEnviando(true);
    try {
      atualizarUsuario(await atualizarPerfil(nome, celular));
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Falha ao salvar. Tente de novo.");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div className="fixed inset-0 z-[1400] grid place-items-center bg-slate-900/50 px-4">
      <div className="w-full max-w-sm rounded-2xl border border-slate-200 bg-white p-6 shadow-xl">
        <h2 className="text-lg font-bold tracking-tight">Complete seu cadastro</h2>
        <p className="mt-1 text-sm text-slate-600">
          Para continuar, informe seu nome e um celular de contato — usamos para falar com
          você sobre as suas análises.
        </p>

        <form onSubmit={onSubmit} className="mt-4 space-y-4">
          <label className="block">
            <span className="mb-1 block text-sm font-medium text-slate-700">Nome</span>
            <input
              type="text"
              value={nome}
              onChange={(e) => setNome(e.target.value)}
              placeholder="seu nome completo"
              autoComplete="name"
              required
              className="h-10 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm shadow-sm outline-none transition-colors placeholder:text-slate-400 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100"
            />
          </label>
          <label className="block">
            <span className="mb-1 block text-sm font-medium text-slate-700">
              Celular (com DDD)
            </span>
            <input
              type="tel"
              value={celular}
              onChange={(e) => setCelular(e.target.value)}
              placeholder="(24) 99999-8888"
              autoComplete="tel"
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
            {enviando ? "Salvando…" : "Salvar e continuar"}
          </button>
        </form>
      </div>
    </div>
  );
}
