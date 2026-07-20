"use client";

// Troca de senha do usuário LOGADO (menu do avatar). Conta nascida pelo Google não tem
// senha atual — o campo some e a primeira senha é definida direto (contrato do backend).

import { useState } from "react";
import { trocarSenha } from "@/lib/auth";

export function DialogTrocarSenha({ onFechar }: { onFechar: () => void }) {
  const [senhaAtual, setSenhaAtual] = useState("");
  const [senhaNova, setSenhaNova] = useState("");
  const [confirma, setConfirma] = useState("");
  const [mensagem, setMensagem] = useState<string | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErro(null);
    if (senhaNova.length < 8) {
      setErro("A senha nova precisa de pelo menos 8 caracteres.");
      return;
    }
    if (senhaNova !== confirma) {
      setErro("As duas senhas novas não conferem.");
      return;
    }
    setEnviando(true);
    try {
      setMensagem(await trocarSenha(senhaAtual || undefined, senhaNova));
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Falha ao trocar a senha.");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-[1300] grid place-items-center bg-slate-900/40 px-4"
      onClick={onFechar}
    >
      <div
        className="w-full max-w-sm rounded-2xl border border-slate-200 bg-white p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4">
          <h2 className="text-lg font-bold tracking-tight">Alterar senha</h2>
          <button
            type="button"
            onClick={onFechar}
            className="rounded-md px-2 py-0.5 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600"
            aria-label="Fechar"
          >
            ✕
          </button>
        </div>

        {mensagem ? (
          <div className="mt-4 space-y-4">
            <p className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
              {mensagem} Sua sessão atual continua ativa; as outras serão desconectadas.
            </p>
            <button
              type="button"
              onClick={onFechar}
              className="h-10 w-full rounded-lg bg-gradient-to-br from-indigo-600 to-violet-600 px-4 text-sm font-semibold text-white shadow-sm transition hover:opacity-95"
            >
              Fechar
            </button>
          </div>
        ) : (
          <form onSubmit={onSubmit} className="mt-4 space-y-4">
            <Campo
              rotulo="Senha atual (deixe em branco se sua conta entra só com o Google)"
              value={senhaAtual}
              onChange={setSenhaAtual}
              placeholder="sua senha atual"
              autoComplete="current-password"
              required={false}
            />
            <Campo
              rotulo="Senha nova"
              value={senhaNova}
              onChange={setSenhaNova}
              placeholder="mínimo 8 caracteres"
              autoComplete="new-password"
            />
            <Campo
              rotulo="Repita a senha nova"
              value={confirma}
              onChange={setConfirma}
              placeholder="a mesma senha"
              autoComplete="new-password"
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
    </div>
  );
}

function Campo({
  rotulo,
  value,
  onChange,
  placeholder,
  autoComplete,
  required = true,
}: {
  rotulo: string;
  value: string;
  onChange: (v: string) => void;
  placeholder: string;
  autoComplete: string;
  required?: boolean;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-sm font-medium text-slate-700">{rotulo}</span>
      <input
        type="password"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        autoComplete={autoComplete}
        required={required}
        className="h-10 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm shadow-sm outline-none transition-colors placeholder:text-slate-400 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100"
      />
    </label>
  );
}
