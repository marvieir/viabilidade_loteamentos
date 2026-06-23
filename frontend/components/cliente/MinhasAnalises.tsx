"use client";

// Fase 12.2 — lista (cards) das análises salvas do cliente. Carregar reidrata a gleba
// e devolve o objeto Analise (mesmo shape do upload), que a home recoloca na tela.

import { useCallback, useEffect, useState } from "react";
import {
  carregarAnalise,
  excluirAnalise,
  listarSalvas,
  type AnaliseResumo,
} from "@/lib/salvas";
import type { Analise } from "@/lib/api";

export function MinhasAnalises({
  onCarregar,
  recarregar,
}: {
  onCarregar: (a: Analise, salvaId: string) => void;
  recarregar?: number; // muda o valor → força refetch (ex.: após salvar)
}) {
  const [itens, setItens] = useState<AnaliseResumo[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState<string | null>(null);
  const [ocupadoId, setOcupadoId] = useState<string | null>(null);

  const buscar = useCallback(async () => {
    setCarregando(true);
    setErro(null);
    try {
      setItens(await listarSalvas());
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Falha ao listar.");
    } finally {
      setCarregando(false);
    }
  }, []);

  useEffect(() => {
    buscar();
  }, [buscar, recarregar]);

  async function abrir(id: string) {
    setOcupadoId(id);
    try {
      const analise = await carregarAnalise(id);
      onCarregar(analise, id);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Falha ao carregar.");
    } finally {
      setOcupadoId(null);
    }
  }

  async function remover(id: string, titulo: string) {
    if (!confirm(`Excluir a análise "${titulo}"? Esta ação não pode ser desfeita.`)) return;
    setOcupadoId(id);
    try {
      await excluirAnalise(id);
      setItens((xs) => xs.filter((x) => x.id !== id));
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Falha ao excluir.");
    } finally {
      setOcupadoId(null);
    }
  }

  if (carregando) {
    return <p className="text-sm text-slate-500">Carregando suas análises…</p>;
  }
  if (erro) {
    return <p className="text-sm text-rose-600">{erro}</p>;
  }
  if (itens.length === 0) {
    return (
      <p className="text-sm text-slate-500">
        Você ainda não salvou nenhuma análise. Envie um KMZ acima e use “Salvar análise”.
      </p>
    );
  }

  return (
    <ul className="grid gap-3 sm:grid-cols-2">
      {itens.map((a) => (
        <li
          key={a.id}
          className="rounded-xl border border-slate-200 bg-white p-4 text-left shadow-sm"
        >
          <p className="truncate font-semibold text-slate-800" title={a.titulo}>
            {a.titulo}
          </p>
          <p className="mt-0.5 text-sm text-slate-500">
            {[a.cidade, a.uf].filter(Boolean).join(" / ") || "Jurisdição não informada"}
            {a.area_ha != null && (
              <> · {a.area_ha.toLocaleString("pt-BR")} ha</>
            )}
          </p>
          <p className="mt-1 text-[11px] text-slate-400">
            Atualizada em {new Date(a.atualizada_em).toLocaleString("pt-BR")}
          </p>
          <div className="mt-3 flex gap-2">
            <button
              type="button"
              onClick={() => abrir(a.id)}
              disabled={ocupadoId === a.id}
              className="rounded-lg bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
            >
              {ocupadoId === a.id ? "Abrindo…" : "Abrir"}
            </button>
            <button
              type="button"
              onClick={() => remover(a.id, a.titulo)}
              disabled={ocupadoId === a.id}
              className="rounded-lg border border-slate-200 px-3 py-1.5 text-sm font-medium text-rose-600 hover:bg-rose-50 disabled:opacity-50"
            >
              Excluir
            </button>
          </div>
        </li>
      ))}
    </ul>
  );
}
