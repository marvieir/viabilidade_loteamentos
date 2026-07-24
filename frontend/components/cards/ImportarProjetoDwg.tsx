"use client";

// Fase URB-IMPORT, IMP-3 (docs/fase-urb-import.md) — wizard de 3 passos para carregar um
// projeto de loteamento PRONTO (DWG/DXF): Arquivo → Camadas → Conferência. O front só
// renderiza o que o backend devolve (inventário, proposta, auditoria, pendências) — nenhum
// número é calculado ou formatado aqui (§regra 2).

import { useState } from "react";
import dynamic from "next/dynamic";
import {
  confirmarImportacaoDwg,
  importarProjetoDwg,
  type ChaveOverlay,
  type InventarioImportacao,
  type PapelCamada,
  type PropostaImportada,
} from "@/lib/api";

const MapaLeaflet = dynamic(() => import("@/components/mapa/MapaLeaflet"), {
  ssr: false,
  loading: () => (
    <div className="flex h-full items-center justify-center text-sm text-slate-400">
      Carregando mapa…
    </div>
  ),
});

const PAPEIS: { v: PapelCamada; r: string }[] = [
  { v: "lote", r: "Lotes" },
  { v: "via", r: "Vias / guias" },
  { v: "verde", r: "Área verde" },
  { v: "institucional", r: "Institucional" },
  { v: "ignorar", r: "Ignorar" },
];

const ROTULO_PENDENCIA: Record<string, string> = {
  rotulo_sem_lote: "rótulo de área sem lote fechado",
  lote_sem_rotulo: "lote fechado sem rótulo de área",
};

function overlaysDe(p: PropostaImportada): Partial<Record<ChaveOverlay, GeoJSON.Geometry>> {
  const o: Partial<Record<ChaveOverlay, GeoJSON.Geometry>> = {};
  if (p.geometria.areas_verdes) o.urb_verde = p.geometria.areas_verdes;
  if (p.geometria.institucional) o.urb_institucional = p.geometria.institucional;
  return o;
}

// Painel de conferência/resultado — usado no passo 3 do wizard E na proposta já salva.
export function PainelImportado({
  proposta,
  glebaGeojson,
}: {
  proposta: PropostaImportada;
  glebaGeojson: GeoJSON.Polygon;
}) {
  const r = proposta.auditoria.resumo;
  return (
    <div className="space-y-3">
      <div className="overflow-hidden rounded-xl border border-slate-200">
        <div className="flex items-center justify-between bg-slate-50 px-3 py-1.5">
          <span className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
            Projeto importado — {proposta.arquivo}
          </span>
          <span className="rounded-full bg-indigo-100 px-2 py-0.5 text-[10px] font-semibold text-indigo-700">
            importada
          </span>
        </div>
        <div className="h-[440px] w-full">
          <MapaLeaflet
            geojson={glebaGeojson}
            overlays={overlaysDe(proposta)}
            lotesFeatures={proposta.geometria.lotes_features}
            quadras={null}
            lazerFeatures={null}
          />
        </div>
      </div>

      {/* Encaixe */}
      <p className="rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-600">
        Encaixe na gleba:{" "}
        {proposta.encaixe.metodo === "utm"
          ? `automático — arquivo georreferenciado (UTM, EPSG ${proposta.encaixe.epsg}).`
          : `ajuste automático ao contorno (best-fit${
              proposta.encaixe.score != null ? `, aderência ${proposta.encaixe.score}` : ""
            }) — confira visualmente no mapa acima.`}
      </p>
      {proposta.encaixe.aviso && (
        <p className="rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-900">
          {proposta.encaixe.aviso}
        </p>
      )}

      {/* Auditoria medido × declarado */}
      <div className="rounded-xl border border-slate-200 p-3">
        <p className="text-sm font-semibold text-slate-800">
          Auditoria: área medida × área declarada no CAD
        </p>
        <p className="mt-1 text-xs text-slate-600">
          {r.lotes_medidos} lote(s) fechados ({r.com_rotulo} com rótulo de área)
          {r.dif_mediana_fmt ? ` · diferença mediana ${r.dif_mediana_fmt}` : ""}
          {r.acima_2pct > 0 ? ` · ${r.acima_2pct} lote(s) com diferença acima de 2%` : ""}
        </p>
        {proposta.auditoria.lotes.length > 0 && (
          <div className="mt-2 max-h-56 overflow-y-auto">
            <table className="w-full text-xs">
              <thead className="text-left text-slate-500">
                <tr>
                  <th className="py-1 pr-2">Lote</th>
                  <th className="py-1 pr-2">Medida (m²)</th>
                  <th className="py-1 pr-2">Declarada (m²)</th>
                  <th className="py-1">Dif.</th>
                </tr>
              </thead>
              <tbody>
                {proposta.auditoria.lotes.map((l) => (
                  <tr key={l.id} className="border-t border-slate-100">
                    <td className="py-1 pr-2 font-medium">{l.id}</td>
                    <td className="py-1 pr-2 tabular-nums">{l.area_medida_fmt}</td>
                    <td className="py-1 pr-2 tabular-nums">{l.area_declarada_fmt ?? "—"}</td>
                    <td
                      className={`py-1 tabular-nums ${
                        (l.dif_pct ?? 0) > 0.02 ? "font-semibold text-amber-700" : ""
                      }`}
                    >
                      {l.dif_fmt ?? "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Pendências */}
      {proposta.pendencias.length > 0 && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
          <p className="font-semibold">
            Pendências ({proposta.pendencias.length}) — nada aqui vira lote automaticamente:
          </p>
          <ul className="mt-1 list-disc pl-4">
            {proposta.pendencias.slice(0, 12).map((p, i) => (
              <li key={i}>
                {ROTULO_PENDENCIA[p.tipo]}
                {p.area_fmt ? ` (${p.area_fmt} m²)` : ""}
              </li>
            ))}
            {proposta.pendencias.length > 12 && (
              <li>… e mais {proposta.pendencias.length - 12}.</li>
            )}
          </ul>
        </div>
      )}

      <p className="text-[11px] text-slate-400">{proposta.proveniencia}</p>
      {proposta.avisos.map((a, i) => (
        <p key={i} className="rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-500">
          {a}
        </p>
      ))}
    </div>
  );
}

export function ImportarProjetoDwg({
  analiseId,
  glebaGeojson,
  onSalvo,
  onFechar,
}: {
  analiseId: string;
  glebaGeojson: GeoJSON.Polygon;
  onSalvo: (p: PropostaImportada) => void;
  onFechar: () => void;
}) {
  const [inv, setInv] = useState<InventarioImportacao | null>(null);
  const [mapeamento, setMapeamento] = useState<Record<string, PapelCamada>>({});
  const [preview, setPreview] = useState<PropostaImportada | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);

  async function enviarArquivo(arquivo: File) {
    setOcupado(true);
    setErro(null);
    try {
      const i = await importarProjetoDwg(analiseId, arquivo);
      setInv(i);
      setMapeamento(Object.fromEntries(i.camadas.map((c) => [c.nome, c.sugestao])));
      setPreview(null);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Falha ao ler o arquivo.");
    } finally {
      setOcupado(false);
    }
  }

  async function conferir(salvar: boolean) {
    if (!inv) return;
    setOcupado(true);
    setErro(null);
    try {
      const p = await confirmarImportacaoDwg(analiseId, inv.importacao_id, mapeamento, salvar);
      if (salvar) {
        onSalvo(p);
      } else {
        setPreview(p);
      }
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Falha ao processar o projeto.");
    } finally {
      setOcupado(false);
    }
  }

  const etapa = preview ? 3 : inv ? 2 : 1;

  return (
    <div className="space-y-3 rounded-xl border border-indigo-200 bg-indigo-50/40 p-4">
      <div className="flex items-center justify-between">
        <p className="text-sm font-semibold text-slate-800">
          Carregar projeto pronto (DWG/DXF) — passo {etapa} de 3
        </p>
        <button
          type="button"
          onClick={onFechar}
          className="rounded-md px-2 py-0.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
          aria-label="Fechar"
        >
          ✕
        </button>
      </div>

      {etapa === 1 && (
        <div className="space-y-2">
          <p className="text-xs text-slate-600">
            Envie a planta do loteamento (DWG ou DXF). Nós lemos as camadas, você confirma o
            que é lote/via/verde, e o projeto vira uma proposta com quadro de áreas real e
            auditoria das áreas declaradas.
          </p>
          <label className="inline-flex cursor-pointer items-center rounded-lg bg-gradient-to-br from-indigo-600 to-violet-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:opacity-95">
            {ocupado ? "Lendo o arquivo…" : "Escolher arquivo DWG/DXF"}
            <input
              type="file"
              accept=".dwg,.dxf"
              className="hidden"
              disabled={ocupado}
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) enviarArquivo(f);
                e.target.value = "";
              }}
            />
          </label>
        </div>
      )}

      {etapa === 2 && inv && (
        <div className="space-y-2">
          <p className="text-xs text-slate-600">
            <strong>{inv.arquivo}</strong> ({inv.formato}). Confirme o papel de cada camada —
            pré-marcamos pela leitura do desenho:
          </p>
          {inv.avisos.map((a, i) => (
            <p key={i} className="rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-900">
              {a}
            </p>
          ))}
          <div className="max-h-64 overflow-y-auto rounded-lg border border-slate-200 bg-white">
            <table className="w-full text-xs">
              <thead className="text-left text-slate-500">
                <tr>
                  <th className="px-2 py-1.5">Camada</th>
                  <th className="px-2 py-1.5">Conteúdo</th>
                  <th className="px-2 py-1.5">Rótulos de área</th>
                  <th className="px-2 py-1.5">Papel</th>
                </tr>
              </thead>
              <tbody>
                {inv.camadas.map((c) => (
                  <tr key={c.nome} className="border-t border-slate-100">
                    <td className="px-2 py-1 font-medium">{c.nome}</td>
                    <td className="px-2 py-1 text-slate-500">
                      {Object.entries(c.entidades)
                        .slice(0, 3)
                        .map(([t, n]) => `${t}:${n}`)
                        .join(" · ")}
                    </td>
                    <td className="px-2 py-1 tabular-nums">{c.rotulos_area || "—"}</td>
                    <td className="px-2 py-1">
                      <select
                        value={mapeamento[c.nome] ?? "ignorar"}
                        onChange={(e) =>
                          setMapeamento((m) => ({
                            ...m,
                            [c.nome]: e.target.value as PapelCamada,
                          }))
                        }
                        className="rounded-md border border-slate-300 bg-white px-1.5 py-0.5 text-xs"
                      >
                        {PAPEIS.map((p) => (
                          <option key={p.v} value={p.v}>
                            {p.r}
                          </option>
                        ))}
                      </select>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              disabled={ocupado}
              onClick={() => conferir(false)}
              className="rounded-lg bg-gradient-to-br from-indigo-600 to-violet-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:opacity-95 disabled:opacity-60"
            >
              {ocupado ? "Processando…" : "Ver conferência"}
            </button>
            <button
              type="button"
              disabled={ocupado}
              onClick={() => setInv(null)}
              className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm text-slate-600 hover:bg-slate-50"
            >
              Trocar arquivo
            </button>
          </div>
        </div>
      )}

      {etapa === 3 && preview && (
        <div className="space-y-3">
          <PainelImportado proposta={preview} glebaGeojson={glebaGeojson} />
          <div className="flex gap-2">
            <button
              type="button"
              disabled={ocupado}
              onClick={() => conferir(true)}
              className="rounded-lg bg-gradient-to-br from-emerald-600 to-teal-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:opacity-95 disabled:opacity-60"
            >
              {ocupado ? "Salvando…" : "Salvar como proposta"}
            </button>
            <button
              type="button"
              disabled={ocupado}
              onClick={() => setPreview(null)}
              className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm text-slate-600 hover:bg-slate-50"
            >
              Voltar às camadas
            </button>
          </div>
        </div>
      )}

      {erro && (
        <p className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
          {erro}
        </p>
      )}
    </div>
  );
}
