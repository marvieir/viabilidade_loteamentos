"use client";

// Formulário da entrevista de validação do MVP (roteiro do plano de marketing §8 + blocos
// acordados em 05/08). O ENTREVISTADOR preenche durante a conversa, com a /planos-mvp
// aberta na tela do cliente no bloco de preço. Exige login com papel admin (o backend
// também barra; aqui é UX). Nada de cálculo aqui: o resumo agregado vem do backend.

import { useState } from "react";
import Link from "next/link";
import { RequireAuth } from "@/components/auth/RequireAuth";
import { useAuth } from "@/components/auth/AuthProvider";
import {
  CANAIS,
  COTA_COBRE,
  DESCONTO_FUNDADOR,
  ENTREVISTADORES,
  ESCOLHAS,
  FAIXAS_GLEBAS_ANO,
  FUNCIONALIDADES,
  PERFIS,
  REACOES,
  salvarEntrevista,
  type EntrevistaIn,
} from "@/lib/entrevistas";

const VAZIA: EntrevistaIn = {
  nome: "",
  perfil: "",
  canal: "",
  entrevistador: "",
  ultima_gleba: "",
  glebas_ano: "",
  confianca: "",
  sumisse_amanha: "",
  mais_gostou: [],
  capacidade_nova: "",
  dificuldades: "",
  sentiu_falta: "",
  pagaria_manter: [],
  preco_caro: "",
  preco_barato: "",
  reacao_pacote5: "",
  reacao_semestral: "",
  reacao_anual: "",
  escolha: "",
  travou_motivo: "",
  cota_cobre: "",
  desconto_fundador: "",
  indicacoes: "",
  observacoes: "",
};

export default function PaginaEntrevista() {
  return (
    <RequireAuth>
      <Entrevista />
    </RequireAuth>
  );
}

function Bloco({ titulo, children }: { titulo: string; children: React.ReactNode }) {
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <h2 className="text-sm font-bold uppercase tracking-wider text-slate-500">{titulo}</h2>
      <div className="mt-4 space-y-5">{children}</div>
    </section>
  );
}

function Rotulo({ children }: { children: React.ReactNode }) {
  return <p className="mb-2 text-sm font-medium text-slate-700">{children}</p>;
}

function Chips({
  opcoes,
  valor,
  aoMudar,
}: {
  opcoes: string[];
  valor: string;
  aoMudar: (v: string) => void;
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {opcoes.map((o) => (
        <button
          key={o}
          type="button"
          onClick={() => aoMudar(valor === o ? "" : o)}
          className={`rounded-full border px-3.5 py-1.5 text-sm transition ${
            valor === o
              ? "border-slate-900 bg-slate-900 font-semibold text-white"
              : "border-slate-300 bg-white text-slate-700 hover:border-slate-500"
          }`}
        >
          {o}
        </button>
      ))}
    </div>
  );
}

function ChipsMulti({
  opcoes,
  valor,
  aoMudar,
}: {
  opcoes: string[];
  valor: string[];
  aoMudar: (v: string[]) => void;
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {opcoes.map((o) => {
        const ativo = valor.includes(o);
        return (
          <button
            key={o}
            type="button"
            onClick={() => aoMudar(ativo ? valor.filter((v) => v !== o) : [...valor, o])}
            className={`rounded-full border px-3.5 py-1.5 text-sm transition ${
              ativo
                ? "border-slate-900 bg-slate-900 font-semibold text-white"
                : "border-slate-300 bg-white text-slate-700 hover:border-slate-500"
            }`}
          >
            {ativo ? "✓ " : ""}
            {o}
          </button>
        );
      })}
    </div>
  );
}

function Texto({
  valor,
  aoMudar,
  placeholder,
  linhas = 3,
}: {
  valor: string;
  aoMudar: (v: string) => void;
  placeholder?: string;
  linhas?: number;
}) {
  return (
    <textarea
      value={valor}
      onChange={(e) => aoMudar(e.target.value)}
      placeholder={placeholder}
      rows={linhas}
      className="w-full rounded-xl border border-slate-300 px-3.5 py-2.5 text-sm text-slate-800 outline-none transition focus:border-slate-600"
    />
  );
}

function Entrevista() {
  const { usuario } = useAuth();
  const [dados, setDados] = useState<EntrevistaIn>(VAZIA);
  const [salvando, setSalvando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [salvouNome, setSalvouNome] = useState<string | null>(null);

  const ehAdmin = usuario?.papel === "admin";
  const m = <K extends keyof EntrevistaIn>(k: K) => (v: EntrevistaIn[K]) =>
    setDados((d) => ({ ...d, [k]: v }));

  if (!ehAdmin) {
    return (
      <main className="grid min-h-screen place-items-center bg-slate-50 px-4">
        <div className="max-w-sm rounded-2xl border border-slate-200 bg-white p-8 text-center shadow-sm">
          <h1 className="text-lg font-bold">Acesso restrito</h1>
          <p className="mt-2 text-sm text-slate-500">
            As entrevistas do MVP são exclusivas do administrador.
          </p>
        </div>
      </main>
    );
  }

  async function enviar() {
    setSalvando(true);
    setErro(null);
    try {
      await salvarEntrevista(dados);
      setSalvouNome(dados.nome || "sem nome");
      setDados(VAZIA);
      window.scrollTo({ top: 0 });
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Falha ao salvar.");
    } finally {
      setSalvando(false);
    }
  }

  return (
    <main className="min-h-screen bg-slate-50 pb-16">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-3xl flex-wrap items-center justify-between gap-3 px-5 py-4">
          <div>
            <h1 className="text-lg font-bold text-slate-900">Entrevista de validação do MVP</h1>
            <p className="text-xs text-slate-500">
              Preencha durante a conversa. No bloco de preço, abra a{" "}
              <a href="/planos-mvp" target="_blank" className="underline underline-offset-2">
                /planos-mvp
              </a>{" "}
              na tela do cliente.
            </p>
          </div>
          <Link
            href="/entrevista-mvp/resumo"
            className="rounded-lg border border-slate-300 px-3.5 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-500"
          >
            Ver resumo das respostas
          </Link>
        </div>
      </header>

      <div className="mx-auto mt-6 max-w-3xl space-y-5 px-5">
        {salvouNome && (
          <div className="flex items-center justify-between rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
            <span>Entrevista de “{salvouNome}” salva. O formulário está limpo para a próxima.</span>
            <button onClick={() => setSalvouNome(null)} className="font-semibold">
              ✕
            </button>
          </div>
        )}

        <Bloco titulo="A · Identificação">
          <div>
            <Rotulo>Nome / empresa</Rotulo>
            <input
              value={dados.nome}
              onChange={(e) => m("nome")(e.target.value)}
              className="w-full rounded-xl border border-slate-300 px-3.5 py-2.5 text-sm outline-none transition focus:border-slate-600"
              placeholder="Quem está do outro lado"
            />
          </div>
          <div>
            <Rotulo>Perfil</Rotulo>
            <Chips opcoes={PERFIS} valor={dados.perfil} aoMudar={m("perfil")} />
          </div>
          <div>
            <Rotulo>Canal de origem</Rotulo>
            <Chips opcoes={CANAIS} valor={dados.canal} aoMudar={m("canal")} />
          </div>
          <div>
            <Rotulo>Entrevistador</Rotulo>
            <Chips opcoes={ENTREVISTADORES} valor={dados.entrevistador} aoMudar={m("entrevistador")} />
          </div>
        </Bloco>

        <Bloco titulo="B · Contexto e dor">
          <div>
            <Rotulo>
              “Me conta a última gleba que você avaliou sem a plataforma: o que fez, quanto
              custou, quanto demorou?”
            </Rotulo>
            <Texto valor={dados.ultima_gleba} aoMudar={m("ultima_gleba")} />
          </div>
          <div>
            <Rotulo>Quantas glebas você avalia por ano?</Rotulo>
            <Chips opcoes={FAIXAS_GLEBAS_ANO} valor={dados.glebas_ano} aoMudar={m("glebas_ano")} />
          </div>
          <div>
            <Rotulo>
              “O que a plataforma te disse que você não sabia? Em qual análise mais confiou, em
              qual menos?”
            </Rotulo>
            <Texto valor={dados.confianca} aoMudar={m("confianca")} />
          </div>
          <div>
            <Rotulo>“Se a plataforma sumisse amanhã, o que faria falta primeiro?”</Rotulo>
            <Texto valor={dados.sumisse_amanha} aoMudar={m("sumisse_amanha")} linhas={2} />
          </div>
        </Bloco>

        <Bloco titulo="C · Produto">
          <div>
            <Rotulo>Quais funcionalidades você mais gostou? (marque as citadas)</Rotulo>
            <ChipsMulti opcoes={FUNCIONALIDADES} valor={dados.mais_gostou} aoMudar={m("mais_gostou")} />
          </div>
          <div>
            <Rotulo>
              “O que você passou a conseguir que não conseguia antes da plataforma?”
            </Rotulo>
            <Texto valor={dados.capacidade_nova} aoMudar={m("capacidade_nova")} linhas={2} />
          </div>
          <div>
            <Rotulo>“Quais as principais dificuldades que encontrou usando a plataforma?”</Rotulo>
            <Texto valor={dados.dificuldades} aoMudar={m("dificuldades")} linhas={2} />
          </div>
          <div>
            <Rotulo>“Quais funcionalidades você sentiu falta?”</Rotulo>
            <Texto valor={dados.sentiu_falta} aoMudar={m("sentiu_falta")} linhas={2} />
          </div>
        </Bloco>

        <Bloco titulo="D · Valor">
          <div>
            <Rotulo>“Quais dessas você pagaria para manter?”</Rotulo>
            <ChipsMulti
              opcoes={FUNCIONALIDADES}
              valor={dados.pagaria_manter}
              aoMudar={m("pagaria_manter")}
            />
          </div>
        </Bloco>

        <Bloco titulo="E · Preço (abra a /planos-mvp na tela do cliente)">
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <Rotulo>“A partir de que preço isso fica caro?”</Rotulo>
              <input
                value={dados.preco_caro}
                onChange={(e) => m("preco_caro")(e.target.value)}
                className="w-full rounded-xl border border-slate-300 px-3.5 py-2.5 text-sm outline-none transition focus:border-slate-600"
                placeholder="R$ …"
              />
            </div>
            <div>
              <Rotulo>“A que preço fica barato a ponto de desconfiar?”</Rotulo>
              <input
                value={dados.preco_barato}
                onChange={(e) => m("preco_barato")(e.target.value)}
                className="w-full rounded-xl border border-slate-300 px-3.5 py-2.5 text-sm outline-none transition focus:border-slate-600"
                placeholder="R$ …"
              />
            </div>
          </div>
          <div>
            <Rotulo>Reação ao Pacote 5 glebas (R$ 597 ou 3× R$ 199)</Rotulo>
            <Chips opcoes={REACOES} valor={dados.reacao_pacote5} aoMudar={m("reacao_pacote5")} />
          </div>
          <div>
            <Rotulo>Reação à Semestral (R$ 1.194 em 6× R$ 199, 12 glebas)</Rotulo>
            <Chips opcoes={REACOES} valor={dados.reacao_semestral} aoMudar={m("reacao_semestral")} />
          </div>
          <div>
            <Rotulo>Reação à Anual (R$ 2.148 em 12× R$ 179, 30 glebas)</Rotulo>
            <Chips opcoes={REACOES} valor={dados.reacao_anual} aoMudar={m("reacao_anual")} />
          </div>
          <div>
            <Rotulo>“Se fosse contratar hoje, qual você escolheria?”</Rotulo>
            <Chips opcoes={ESCOLHAS} valor={dados.escolha} aoMudar={m("escolha")} />
          </div>
          <div>
            <Rotulo>Se travou ou não escolheu: o que travou?</Rotulo>
            <Texto valor={dados.travou_motivo} aoMudar={m("travou_motivo")} linhas={2} />
          </div>
          <div>
            <Rotulo>A cota (12 no semestre / 30 no ano) cobre o volume dele?</Rotulo>
            <Chips opcoes={COTA_COBRE} valor={dados.cota_cobre} aoMudar={m("cota_cobre")} />
          </div>
        </Bloco>

        <Bloco titulo="F · Fechamento">
          <div>
            <Rotulo>
              Toparia o desconto de fundador (50% no 1º ano) em troca de caso publicável,
              depoimento e 1 feedback por mês?
            </Rotulo>
            <Chips
              opcoes={DESCONTO_FUNDADOR}
              valor={dados.desconto_fundador}
              aoMudar={m("desconto_fundador")}
            />
          </div>
          <div>
            <Rotulo>“Quem mais você conhece que deveria usar isso?” (mirar 2 indicações)</Rotulo>
            <Texto valor={dados.indicacoes} aoMudar={m("indicacoes")} linhas={2} />
          </div>
          <div>
            <Rotulo>Observações do entrevistador</Rotulo>
            <Texto valor={dados.observacoes} aoMudar={m("observacoes")} />
          </div>
        </Bloco>

        {erro && (
          <p className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {erro}
          </p>
        )}

        <button
          onClick={enviar}
          disabled={salvando}
          className="w-full rounded-xl bg-slate-900 py-3.5 text-base font-semibold text-white transition hover:bg-slate-700 disabled:opacity-50"
        >
          {salvando ? "Salvando…" : "Salvar entrevista"}
        </button>
      </div>
    </main>
  );
}
