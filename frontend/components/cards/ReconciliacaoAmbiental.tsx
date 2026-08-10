"use client";

// AMB-EXC — Vistoria de campo e reconciliação (mockups aprovados 08/08).
// O front SÓ renderiza o que o backend mandou (§2): manchas, vereditos, régua e resumo
// vêm prontos com proveniência; aqui não há nenhum cálculo.

import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  buscarManchasAmbientais,
  registrarLaudoAmbiental,
  type AjusteLaudo,
  type ManchaAmb,
  type ManchasAmbientais,
  type ReconciliacaoResumo,
} from "@/lib/api";

const m2 = (v: number) =>
  v.toLocaleString("pt-BR", { maximumFractionDigits: 0 }) + " m²";

const PILL: Record<ManchaAmb["concordancia"], { cls: string; rotulo: string }> = {
  mata_alta_confianca: { cls: "bg-emerald-100 text-emerald-800", rotulo: "MATA — alta confiança" },
  mata_provavel: { cls: "bg-emerald-50 text-emerald-700", rotulo: "Mata provável" },
  divergem: { cls: "bg-rose-100 text-rose-800", rotulo: "DIVERGEM — vistoriar" },
  campestre_provavel: { cls: "bg-lime-100 text-lime-800", rotulo: "Campo nativo provável" },
  dados_insuficientes: { cls: "bg-slate-100 text-slate-600", rotulo: "Dados insuficientes — vistoriar" },
};

const ESTAGIOS = [
  { v: "", r: "— sem ajuste —" },
  { v: "primaria", r: "Primária" },
  { v: "sec_avancado", r: "Secundária — avançado" },
  { v: "sec_medio", r: "Secundária — médio" },
  { v: "sec_inicial", r: "Secundária — inicial" },
  { v: "nao_nativa", r: "Não é vegetação nativa" },
];
const FORMACOES = [
  { v: "", r: "— sem ajuste —" },
  { v: "florestal", r: "Nativa florestal" },
  { v: "campestre", r: "Nativa campestre (campo)" },
  { v: "nao_nativa", r: "Não é vegetação nativa" },
];

export function ReconciliacaoAmbiental({ analiseId }: { analiseId: string }) {
  const [dados, setDados] = useState<ManchasAmbientais | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(false);
  const [formAberto, setFormAberto] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [resumo, setResumo] = useState<ReconciliacaoResumo | null>(null);

  // formulário do laudo
  const [responsavel, setResponsavel] = useState("");
  const [registro, setRegistro] = useState("");
  const [dataVistoria, setDataVistoria] = useState("");
  const [perimetroPre, setPerimetroPre] = useState<string>("nao_sei");
  const [perimetroFonte, setPerimetroFonte] = useState("");
  const [escolhas, setEscolhas] = useState<Record<string, string>>({});
  const [arquivo, setArquivo] = useState<File | null>(null);
  const [restrTipo, setRestrTipo] = useState("banhado");
  const [restrGeo, setRestrGeo] = useState<File | null>(null);

  async function carregar() {
    setCarregando(true);
    setErro(null);
    try {
      const r = await buscarManchasAmbientais(analiseId);
      setDados(r);
      setResumo(r.reconciliacao_vigente ?? null);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Falha ao carregar.");
    } finally {
      setCarregando(false);
    }
  }

  async function aplicar() {
    if (!dados) return;
    setEnviando(true);
    setErro(null);
    try {
      const ehMA = dados.regime?.codigo === "mata_atlantica";
      const ajustes: AjusteLaudo[] = [];
      for (const m of dados.manchas) {
        const v = escolhas[m.mancha_id];
        if (!v) continue;
        ajustes.push(
          ehMA
            ? { acao: "estagio", mancha_id: m.mancha_id, assinatura: m.assinatura, estagio: v }
            : { acao: "formacao", mancha_id: m.mancha_id, assinatura: m.assinatura, formacao: v }
        );
      }
      if (restrGeo) {
        const texto = await restrGeo.text();
        const gj = JSON.parse(texto) as Record<string, unknown>; // só parse de arquivo — sem geo-matemática
        const geom = (gj.type === "FeatureCollection"
          ? (gj.features as Array<{ geometry: unknown }> | undefined)?.[0]?.geometry
          : gj.type === "Feature"
            ? (gj as { geometry?: unknown }).geometry
            : gj) as Record<string, unknown> | undefined;
        if (geom) ajustes.push({ acao: "nova_restricao", tipo_restricao: restrTipo, geojson: geom });
      }
      if (ajustes.length === 0) {
        setErro("Nenhum ajuste selecionado — enquadre ao menos uma mancha ou anexe um achado de campo.");
        return;
      }
      const r = await registrarLaudoAmbiental(
        analiseId,
        {
          responsavel,
          registro,
          data_vistoria: dataVistoria,
          perimetro_urbano_pre_lei: perimetroPre === "nao_sei" ? null : perimetroPre === "sim",
          perimetro_urbano_fonte: perimetroFonte,
          ajustes,
        },
        arquivo
      );
      setResumo(r);
      setFormAberto(false);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Falha ao aplicar o laudo.");
    } finally {
      setEnviando(false);
    }
  }

  const gate = dados?.gate;

  return (
    <div className="mt-4 rounded-xl border border-slate-200 p-4">
      <div className="flex flex-wrap items-center gap-2">
        <h4 className="text-sm font-extrabold text-slate-900">
          Vistoria de campo — segunda opinião e laudo
        </h4>
        <span className="rounded-full bg-[#1d1252] px-2.5 py-0.5 text-[10px] font-extrabold uppercase tracking-wide text-white">
          Planos pagos
        </span>
        {!dados && (
          <Button size="sm" variant="secondary" className="ml-auto" onClick={carregar} disabled={carregando}>
            {carregando ? "Carregando…" : "Carregar manchas"}
          </Button>
        )}
      </div>
      <p className="mt-1 text-xs text-slate-500">
        Cruza cada mancha de vegetação &quot;a verificar&quot; com fontes independentes e recebe o laudo do
        engenheiro ambiental — que declara os fatos; a consequência legal é aplicada pelo motor, citando o
        dispositivo. A autorização de supressão é sempre do órgão competente.
      </p>

      {erro && <p className="mt-3 rounded-lg bg-rose-50 p-3 text-sm text-rose-800">{erro}</p>}

      {gate?.status === "bloqueado" && (
        <div className="mt-3 rounded-lg bg-slate-50 p-4 text-sm text-slate-700">
          Recurso de plano pago — a prévia gratuita encerrou.{" "}
          <a className="font-bold text-[#ff914d] underline" href="/planos-mvp">Conhecer os planos</a>
        </div>
      )}
      {gate?.status === "previa" && (
        <p className="mt-3 rounded-lg bg-amber-50 p-2.5 text-xs text-amber-900">
          Prévia gratuita: {gate.dias_restantes} dia(s) restante(s).
        </p>
      )}

      {dados && dados.regime && gate?.status !== "bloqueado" && (
        <>
          <div className="mt-3 grid gap-2 sm:grid-cols-3">
            <div className="rounded-lg bg-slate-50 p-2.5">
              <div className="text-[10px] font-bold uppercase text-slate-500">Regime da gleba</div>
              <div className="text-xs font-bold text-slate-900">{dados.regime.rotulo}</div>
            </div>
            <div className="rounded-lg bg-slate-50 p-2.5 sm:col-span-2">
              <div className="text-[10px] font-bold uppercase text-slate-500">
                Rito · cobertura {dados.regime.cobertura}
              </div>
              <div className="text-[11px] text-slate-700">{dados.regime.rito}</div>
            </div>
          </div>

          {dados.manchas.length === 0 ? (
            <p className="mt-3 text-sm text-slate-500">Nenhuma mancha de vegetação a verificar.</p>
          ) : (
            <div className="mt-3 overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b text-left text-[10px] uppercase tracking-wide text-slate-500">
                    <th className="py-1.5 pr-2">Mancha</th>
                    <th className="py-1.5 pr-2">Área</th>
                    <th className="py-1.5 pr-2">O que as fontes dizem</th>
                    <th className="py-1.5 pr-2">Concordância</th>
                    {formAberto && <th className="py-1.5">Laudo diz</th>}
                  </tr>
                </thead>
                <tbody>
                  {dados.manchas.map((m) => (
                    <tr key={m.mancha_id} className="border-b border-dashed border-slate-100 align-top">
                      <td className="py-2 pr-2 font-mono font-bold">{m.mancha_id}</td>
                      <td className="py-2 pr-2 font-mono">{m2(m.area_m2)}</td>
                      <td className="py-2 pr-2 text-slate-600">
                        {m.leituras.map((le) => (
                          <span key={le.fonte} className="mr-2 inline-block">
                            <b className="text-slate-800">{le.fonte}:</b> {le.valor}
                            {le.detalhe ? ` (${le.detalhe})` : ""}
                          </span>
                        ))}
                      </td>
                      <td className="py-2 pr-2">
                        <span className={`inline-block rounded-full px-2 py-0.5 text-[10px] font-extrabold ${PILL[m.concordancia].cls}`}>
                          {PILL[m.concordancia].rotulo}
                        </span>
                        <div className="mt-1 max-w-[220px] text-[10px] text-slate-500">{m.motivo}</div>
                      </td>
                      {formAberto && (
                        <td className="py-2">
                          <select
                            className="rounded-md border border-slate-300 p-1 text-xs"
                            value={escolhas[m.mancha_id] ?? ""}
                            onChange={(e) =>
                              setEscolhas((s) => ({ ...s, [m.mancha_id]: e.target.value }))
                            }
                          >
                            {(dados.regime?.codigo === "mata_atlantica" ? ESTAGIOS : FORMACOES).map(
                              (o) => (
                                <option key={o.v} value={o.v}>{o.r}</option>
                              )
                            )}
                          </select>
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {!formAberto && dados.manchas.length > 0 && (
            <Button size="sm" className="mt-3" onClick={() => setFormAberto(true)}>
              Registrar laudo de vistoria
            </Button>
          )}

          {formAberto && (
            <div className="mt-4 space-y-3 rounded-lg border border-dashed border-[#ff914d] bg-orange-50/30 p-3">
              <div className="grid gap-2 sm:grid-cols-3">
                <label className="text-xs">
                  <span className="font-bold text-slate-600">Responsável técnico *</span>
                  <input className="mt-1 w-full rounded-md border border-slate-300 p-1.5"
                         value={responsavel} onChange={(e) => setResponsavel(e.target.value)} />
                </label>
                <label className="text-xs">
                  <span className="font-bold text-slate-600">Registro/ART (opcional)</span>
                  <input className="mt-1 w-full rounded-md border border-slate-300 p-1.5"
                         value={registro} onChange={(e) => setRegistro(e.target.value)} />
                </label>
                <label className="text-xs">
                  <span className="font-bold text-slate-600">Data da vistoria *</span>
                  <input type="date" className="mt-1 w-full rounded-md border border-slate-300 p-1.5"
                         value={dataVistoria} onChange={(e) => setDataVistoria(e.target.value)} />
                </label>
              </div>
              {dados.regime.codigo === "mata_atlantica" && (
                <div className="grid gap-2 sm:grid-cols-2">
                  <label className="text-xs">
                    <span className="font-bold text-slate-600">Perímetro urbano aprovado até 22/12/2006?</span>
                    <select className="mt-1 w-full rounded-md border border-slate-300 p-1.5"
                            value={perimetroPre} onChange={(e) => setPerimetroPre(e.target.value)}>
                      <option value="nao_sei">Não sei (aplica a leitura mais conservadora)</option>
                      <option value="sim">Sim (antes da Lei da Mata Atlântica)</option>
                      <option value="nao">Não (depois)</option>
                    </select>
                  </label>
                  <label className="text-xs">
                    <span className="font-bold text-slate-600">Fonte (lei municipal)</span>
                    <input className="mt-1 w-full rounded-md border border-slate-300 p-1.5"
                           placeholder="ex.: Lei municipal 2.140/98"
                           value={perimetroFonte} onChange={(e) => setPerimetroFonte(e.target.value)} />
                  </label>
                </div>
              )}
              <div className="grid gap-2 sm:grid-cols-3">
                <label className="text-xs sm:col-span-1">
                  <span className="font-bold text-slate-600">Arquivo do laudo (PDF)</span>
                  <input type="file" accept="application/pdf" className="mt-1 w-full text-xs"
                         onChange={(e) => setArquivo(e.target.files?.[0] ?? null)} />
                </label>
                <label className="text-xs">
                  <span className="font-bold text-slate-600">Achado de campo (opcional)</span>
                  <select className="mt-1 w-full rounded-md border border-slate-300 p-1.5"
                          value={restrTipo} onChange={(e) => setRestrTipo(e.target.value)}>
                    <option value="banhado">Banhado / área úmida</option>
                    <option value="nascente">Nascente</option>
                    <option value="app_curso_dagua">APP de curso d&apos;água</option>
                    <option value="outro">Outra restrição</option>
                  </select>
                </label>
                <label className="text-xs">
                  <span className="font-bold text-slate-600">Polígono do achado (GeoJSON)</span>
                  <input type="file" accept=".json,.geojson,application/geo+json" className="mt-1 w-full text-xs"
                         onChange={(e) => setRestrGeo(e.target.files?.[0] ?? null)} />
                </label>
              </div>
              <div className="flex items-center justify-between gap-3">
                <p className="text-[10px] text-slate-500">
                  O enquadramento por mancha está na coluna &quot;Laudo diz&quot; da tabela acima. Cada ajuste
                  grava proveniência (laudo, responsável, data, dispositivo).
                </p>
                <div className="flex gap-2">
                  <Button size="sm" variant="secondary" onClick={() => setFormAberto(false)}>Cancelar</Button>
                  <Button size="sm" onClick={aplicar}
                          disabled={enviando || !responsavel.trim() || !dataVistoria}>
                    {enviando ? "Aplicando…" : "Aplicar reconciliação e recalcular"}
                  </Button>
                </div>
              </div>
            </div>
          )}
        </>
      )}

      {resumo && (
        <div className="mt-4 rounded-lg border border-emerald-200 bg-emerald-50/40 p-3">
          <div className="text-xs font-extrabold text-emerald-900">
            Reconciliação aplicada (versão {resumo.versao}) — base {resumo.saldo_m2 >= 0 ? "+" : ""}
            {m2(resumo.saldo_m2)}
            {resumo.saldo_otimista_m2 > 0 && (
              <span className="ml-2 font-bold text-amber-700">
                · cenário otimista +{m2(resumo.saldo_otimista_m2)} (se o órgão autorizar)
              </span>
            )}
          </div>
          <table className="mt-2 w-full text-[11px]">
            <thead>
              <tr className="border-b text-left text-[9px] uppercase text-slate-500">
                <th className="py-1 pr-2">Item</th><th className="py-1 pr-2">Decisão</th>
                <th className="py-1 pr-2">Consequência (motor)</th><th className="py-1">Efeito</th>
              </tr>
            </thead>
            <tbody>
              {resumo.itens.map((i) => (
                <tr key={i.item_id} className="border-b border-dashed border-emerald-100 align-top">
                  <td className="py-1.5 pr-2 font-mono font-bold">{i.item_id}</td>
                  <td className="py-1.5 pr-2">{i.decisao}</td>
                  <td className="py-1.5 pr-2 text-slate-600">{i.leitura} <i className="text-slate-400">({i.base_legal})</i></td>
                  <td className="py-1.5 font-mono font-bold">
                    {i.efeito_m2 !== 0 ? (
                      <span className={i.efeito_m2 > 0 ? "text-emerald-700" : "text-rose-700"}>
                        {i.efeito_m2 > 0 ? "+" : ""}{m2(i.efeito_m2)}
                      </span>
                    ) : i.efeito_otimista_m2 > 0 ? (
                      <span className="text-amber-700">+{m2(i.efeito_otimista_m2)} só no otimista</span>
                    ) : (
                      <span className="text-slate-400">0 (segue restrita)</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {resumo.avisos.length > 0 && (
            <ul className="mt-2 list-disc pl-4 text-[10px] text-amber-800">
              {resumo.avisos.map((a, i) => <li key={i}>{a}</li>)}
            </ul>
          )}
          <p className="mt-2 rounded bg-amber-50 p-2 text-[10px] text-amber-900">{resumo.leitura}</p>
          <p className="mt-2 text-[11px] font-bold text-slate-700">
            Próximo passo: reexecute as abas (aproveitamento/urbanismo) — os números passam a usar a
            área reconciliada. No Urbanismo, clique em &quot;Regenerar&quot;.
          </p>
        </div>
      )}
    </div>
  );
}
