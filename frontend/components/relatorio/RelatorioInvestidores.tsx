"use client";

/* LAUDO-INV — relatório detalhado para investidores (fase-laudo-inv.md, aprovada 16/08).
   Renderiza o JSON do backend em páginas A4 imprimíveis (o navegador salva o PDF).
   §2 inegociável: NENHUM número é calculado aqui — só desenho (projeção de exibição dos
   GeoJSON e escala visual dos gráficos); todo rótulo numérico vem *_fmt do backend.
   Gate bloqueado → só a mensagem de plano pago (decisão do operador, 16/08). */

import type { RelatorioInv } from "@/lib/api";
import { CORES_FAIXA, CORES_QUINTIL } from "@/components/mapa/overlays";

/* eslint-disable @typescript-eslint/no-explicit-any */
type GJ = any;

// ---------- projeção de EXIBIÇÃO (equiretangular local) — desenho, não medida ----------
function coletarPosicoes(g: GJ, out: number[][]) {
  if (!g) return;
  if (Array.isArray(g) && typeof g[0] === "number") { out.push(g as number[]); return; }
  if (Array.isArray(g)) { g.forEach((x) => coletarPosicoes(x, out)); return; }
  if (g.type === "FeatureCollection") g.features?.forEach((f: GJ) => coletarPosicoes(f, out));
  else if (g.type === "Feature") coletarPosicoes(g.geometry, out);
  else if (g.coordinates) coletarPosicoes(g.coordinates, out);
}

function useProjecao(camadas: GJ[], w: number, h: number) {
  const pos: number[][] = [];
  camadas.forEach((c) => coletarPosicoes(c, pos));
  if (!pos.length) return null;
  const lons = pos.map((p) => p[0]);
  const lats = pos.map((p) => p[1]);
  const minLon = Math.min(...lons), maxLon = Math.max(...lons);
  const minLat = Math.min(...lats), maxLat = Math.max(...lats);
  const kx = Math.cos(((minLat + maxLat) / 2) * (Math.PI / 180));
  const dx = (maxLon - minLon) * kx || 1e-9;
  const dy = maxLat - minLat || 1e-9;
  const esc = Math.min((w - 16) / dx, (h - 16) / dy);
  return (lon: number, lat: number): [number, number] => [
    8 + (lon - minLon) * kx * esc,
    8 + (maxLat - lat) * esc,
  ];
}

function aneisDe(geom: GJ): number[][][] {
  if (!geom) return [];
  if (geom.type === "Polygon") return [geom.coordinates[0]];
  if (geom.type === "MultiPolygon") return geom.coordinates.map((p: GJ) => p[0]);
  if (geom.type === "Feature") return aneisDe(geom.geometry);
  if (geom.type === "FeatureCollection")
    return geom.features?.flatMap((f: GJ) => aneisDe(f)) ?? [];
  return [];
}

function pathDe(aneis: number[][][], proj: (a: number, b: number) => [number, number]) {
  return aneis
    .map((anel) => "M " + anel.map(([lo, la]) => proj(lo, la).map((v) => v.toFixed(1)).join(",")).join(" L ") + " Z")
    .join(" ");
}

function corDoLote(props: GJ): string {
  const q = props?.quintil_valor;
  if (q != null && CORES_QUINTIL[q]) return CORES_QUINTIL[q];
  const f = props?.faixa_score;
  if (f != null && CORES_FAIXA[f]) return CORES_FAIXA[f];
  return "#ffedd5";
}

function PlantaSvg({ geo, gleba, heat, altura = 430 }: {
  geo: Record<string, GJ>; gleba: GJ | null; heat: boolean; altura?: number;
}) {
  const W = 660;
  const lotesFC = geo?.lotes_features;
  const camadasBbox = [gleba, lotesFC, geo?.arruamento, geo?.areas_verdes,
    geo?.verde_remanescente, geo?.institucional, geo?.agua].filter(Boolean);
  const proj = useProjecao(camadasBbox, W, altura);
  if (!proj) return <p className="text-xs text-slate-400">Sem geometria para desenhar.</p>;
  const P = (g: GJ) => pathDe(aneisDe(g), proj);
  return (
    <svg viewBox={`0 0 ${W} ${altura}`} className="w-full rounded border border-slate-200 bg-white">
      {gleba && <path d={P(gleba)} fill="#fafaf9" stroke="#0f172a" strokeWidth="2" strokeDasharray="7 4" />}
      {geo?.arruamento && <path d={P(geo.arruamento)} fill="#e2e8f0" stroke="#94a3b8" strokeWidth="0.6" />}
      {geo?.areas_verdes && <path d={P(geo.areas_verdes)} fill="#bbf7d0" stroke="#16a34a" strokeWidth="0.7" fillOpacity="0.9" />}
      {geo?.verde_remanescente && <path d={P(geo.verde_remanescente)} fill="#a7f3d0" stroke="#059669" strokeWidth="0.7" fillOpacity="0.8" />}
      {geo?.sistema_lazer && <path d={P(geo.sistema_lazer)} fill="#99f6e4" stroke="#0d9488" strokeWidth="0.7" />}
      {geo?.institucional && <path d={P(geo.institucional)} fill="#ddd6fe" stroke="#7c3aed" strokeWidth="0.7" />}
      {geo?.agua && <path d={P(geo.agua)} fill="#bae6fd" stroke="#0284c7" strokeWidth="0.7" />}
      {lotesFC?.features?.map((f: GJ, i: number) => (
        <path key={f.properties?.lote_id ?? i} d={P(f)}
          fill={heat ? corDoLote(f.properties) : "#ffedd5"}
          fillOpacity={heat ? 0.85 : 1}
          stroke={heat ? "#374151" : "#9a3412"} strokeWidth="0.5" />
      ))}
      {geo?.portico && <path d={P(geo.portico)} fill="#1d1252" stroke="#1d1252" />}
    </svg>
  );
}

// ---------- gráficos (escala VISUAL; rótulos são *_fmt do backend) ----------
function FluxoAnualSvg({ linhas }: { linhas: { ano: number; entradas: number; saidas: number; acumulado: number; acumulado_fmt: string }[] }) {
  if (!linhas?.length) return null;
  const W = 640, H = 200, y0 = 150;
  const maxV = Math.max(...linhas.map((l) => Math.max(l.entradas, l.saidas)), 1);
  const maxA = Math.max(...linhas.map((l) => Math.abs(l.acumulado)), 1);
  const passo = (W - 60) / linhas.length;
  const pontos = linhas.map((l, i) => `${(46 + i * passo + passo / 2).toFixed(0)},${(y0 - (l.acumulado / maxA) * 55).toFixed(0)}`);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full">
      <line x1="40" y1={y0} x2={W - 8} y2={y0} stroke="#94a3b8" />
      {linhas.map((l, i) => {
        const bx = 46 + i * passo;
        const he = (l.entradas / maxV) * 90, hs = (l.saidas / maxV) * 90;
        return (
          <g key={l.ano}>
            <rect x={bx} y={y0 - he} width={passo * 0.28} height={he} fill="#34d399" />
            <rect x={bx + passo * 0.32} y={y0 - hs} width={passo * 0.28} height={hs} fill="#fda4af" />
            <text x={bx + passo / 2} y={y0 + 16} fontSize="10" fill="#64748b" textAnchor="middle">ano {l.ano}</text>
          </g>
        );
      })}
      <polyline points={pontos.join(" ")} fill="none" stroke="#1d1252" strokeWidth="2.2" />
      {pontos.map((p) => {
        const [x, y] = p.split(",");
        return <circle key={p} cx={x} cy={y} r="2.6" fill="#1d1252" />;
      })}
    </svg>
  );
}

function CurvaVplSvg({ pontos }: { pontos: { tma_aa: number; vpl: number; vpl_fmt: string }[] }) {
  if (!pontos?.length) return null;
  const W = 640, H = 180;
  const vs = pontos.map((p) => p.vpl);
  const minV = Math.min(...vs, 0), maxV = Math.max(...vs, 0);
  const y = (v: number) => 14 + ((maxV - v) / (maxV - minV || 1)) * (H - 50);
  const x = (i: number) => 40 + (i / (pontos.length - 1 || 1)) * (W - 60);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full">
      <line x1="36" y1={y(0)} x2={W - 8} y2={y(0)} stroke="#94a3b8" />
      <polyline points={pontos.map((p, i) => `${x(i).toFixed(0)},${y(p.vpl).toFixed(0)}`).join(" ")} fill="none" stroke="#ff914d" strokeWidth="2.2" />
      <text x="40" y="12" fontSize="10" fill="#64748b">VPL</text>
      <text x={W - 10} y={y(0) + 14} fontSize="10" fill="#64748b" textAnchor="end">TMA ({pontos[0]?.tma_aa != null ? `${(pontos[0].tma_aa * 100).toFixed(0)}%` : ""}–{pontos.at(-1)?.tma_aa != null ? `${((pontos.at(-1)!.tma_aa) * 100).toFixed(0)}%` : ""} a.a.)</text>
    </svg>
  );
}

// ---------- blocos de layout ----------
const LUZ_COR: Record<string, string> = {
  favoravel: "#10b981", atencao: "#f59e0b", restricao: "#ef4444",
  informativa: "#64748b", nao_analisada: "#cbd5e1",
};
const LUZ_ROTULO: Record<string, string> = {
  favoravel: "FAVORÁVEL", atencao: "ATENÇÃO", restricao: "RESTRIÇÃO",
  informativa: "INFORMATIVA", nao_analisada: "NÃO ANALISADA",
};

function Pagina({ rodape, num, children }: { rodape: string; num: string; children: React.ReactNode }) {
  return (
    <div className="rel-pg relative mx-auto mb-5 min-h-[1160px] w-[900px] bg-white px-12 pb-16 pt-10 shadow-md">
      {children}
      <div className="absolute bottom-4 left-12 right-12 flex justify-between border-t border-slate-200 pt-1.5 text-[9px] text-slate-400">
        <span>voaz.app · {rodape}</span><span>{num}</span>
      </div>
    </div>
  );
}

function Titulo({ children }: { children: React.ReactNode }) {
  return <h2 className="mb-3 border-l-4 border-laranja-500 pl-2.5 text-[16px] font-extrabold text-marinho-900">{children}</h2>;
}

function TabelaItens({ itens }: { itens: { rotulo: string; valor: string; proveniencia: string | null }[] }) {
  return (
    <table className="w-full text-[11px]">
      <tbody>
        {itens.map((it) => (
          <tr key={it.rotulo} className="border-b border-dashed border-slate-100">
            <td className="py-1 pr-2 font-semibold text-marinho-900">{it.rotulo}</td>
            <td className="py-1 text-right font-mono text-slate-700">{it.valor}</td>
            <td className="py-1 pl-3 text-[9.5px] italic text-slate-400">{it.proveniencia ?? ""}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

// ---------- componente principal ----------
export function RelatorioInvestidores({ rel, glebaGeojson, onFechar }: {
  rel: RelatorioInv;
  glebaGeojson: GJ | null;
  onFechar: () => void;
}) {
  if (rel.gate.status === "bloqueado") {
    return (
      <div className="fixed inset-0 z-[100] grid place-items-center bg-slate-900/50 p-4" onClick={onFechar}>
        <div className="max-w-md rounded-xl bg-white p-6 shadow-xl" onClick={(e) => e.stopPropagation()}>
          <p className="text-base font-bold text-marinho-900">🔒 Relatório para investidores</p>
          <p className="mt-2 text-sm text-slate-600">
            Este relatório detalhado — planta do estudo, mapa de valorização lote a lote,
            resultados financeiros e jurídicos — está disponível <b>apenas nos planos pagos</b>.
          </p>
          <p className="mt-1 text-xs text-slate-400">{rel.gate.motivo}</p>
          <div className="mt-4 flex justify-end gap-2">
            <button className="rounded-lg px-3 py-2 text-sm text-slate-600 hover:bg-slate-100" onClick={onFechar}>Fechar</button>
            <a className="rounded-lg bg-laranja-500 px-3 py-2 text-sm font-semibold text-white hover:bg-laranja-600" href="/planos-mvp">Conhecer os planos</a>
          </div>
        </div>
      </div>
    );
  }

  const geo = rel.urbanismo_snapshot?.geometria ?? null;
  const quadro = rel.urbanismo_snapshot?.quadro_areas ?? null;
  const ind = rel.urbanismo_snapshot?.indicadores ?? null;
  const heatmap = rel.urbanismo_snapshot?.heatmap ?? null;
  const fin = rel.financeira_snapshot?.resultado ?? null;
  const eco = rel.economica_snapshot?.resultado ?? null;

  const linhasQuadro: [string, string][] = [
    ["vendavel", "Lotes (vendável)"], ["arruamento", "Sistema viário"],
    ["area_verde_reserva", "Verde (reserva)"], ["sistema_lazer", "Sistema de lazer"],
    ["institucional", "Institucional"], ["verde_remanescente", "Verde remanescente"],
    ["sobra_geometrica", "Sobra técnica"], ["lamina_dagua", "Lâmina d'água"],
  ];

  return (
    <div className="rel-root fixed inset-0 z-[100] overflow-y-auto bg-slate-300/95 py-5">
      {/* barra de ações — some na impressão */}
      <div className="rel-acoes sticky top-0 z-10 mx-auto mb-4 flex w-[900px] items-center justify-between rounded-lg bg-marinho-900 px-4 py-2.5 text-white shadow-lg">
        <p className="text-sm font-semibold">Relatório para investidores — pré-visualização</p>
        <div className="flex gap-2">
          <button onClick={() => window.print()} className="rounded-lg bg-laranja-500 px-3 py-1.5 text-sm font-semibold hover:bg-laranja-600">Salvar PDF</button>
          <button onClick={onFechar} className="rounded-lg bg-white/10 px-3 py-1.5 text-sm hover:bg-white/20">Fechar</button>
        </div>
      </div>

      {/* CAPA + SUMÁRIO */}
      <Pagina rodape={rel.rodape} num="capa">
        <div className="flex items-baseline justify-between">
          <span className="text-sm font-extrabold tracking-wide text-laranja-500">voaz.app</span>
          <span className="text-[10px] text-slate-400">relatório do estudo · {rel.data_geracao}</span>
        </div>
        <div className="mt-14">
          <p className="text-[11px] font-bold uppercase tracking-widest text-laranja-600">Relatório de pré-análise — apresentação a investidores</p>
          <h1 className="mt-1 text-3xl font-extrabold text-marinho-900">{rel.titulo}</h1>
          <p className="mt-3 text-[13px] leading-7 text-slate-600">
            {String(rel.identificacao?.municipio ?? "—")}/{String(rel.identificacao?.uf ?? "—")} ·
            área bruta <b>{String(rel.identificacao?.area_ha ?? "—")} ha</b> (medida geodésica) ·
            régua legal: cobertura {String(rel.identificacao?.cobertura ?? "—")}
            {rel.preparado_por && <><br />Preparado por <b>{rel.preparado_por}</b></>}
          </p>
        </div>
        <div className="mt-5 rounded-lg border-2 border-amber-300 bg-amber-50 p-3.5 text-[11.5px] font-medium text-amber-900">{rel.ressalva_capa}</div>

        <div className="mt-7">
          <Titulo>Sumário executivo</Titulo>
          <div className="grid grid-cols-4 gap-2.5">
            {rel.kpis.map((k) => (
              <div key={k.rotulo} className="rounded-lg border border-slate-200 p-2.5">
                <p className="text-[9px] font-bold uppercase tracking-wide text-slate-500">{k.rotulo}</p>
                <p className="font-mono text-[15px] font-extrabold text-marinho-900">{k.valor}</p>
                {k.proveniencia && <p className="text-[9px] text-slate-400">{k.proveniencia}</p>}
              </div>
            ))}
          </div>
          <div className="mt-4 space-y-1.5">
            {rel.semaforo.map((s) => (
              <div key={s.dimensao} className="grid grid-cols-[14px_150px_110px_1fr] items-center gap-2.5 text-[11.5px]">
                <span className="h-3 w-3 rounded-sm" style={{ background: LUZ_COR[s.luz] ?? "#cbd5e1" }} />
                <b className="text-marinho-900">{s.dimensao}</b>
                <span className="font-extrabold" style={{ color: LUZ_COR[s.luz] }}>{LUZ_ROTULO[s.luz] ?? s.luz}</span>
                <span className="text-slate-500">{s.justificativa}</span>
              </div>
            ))}
          </div>
          {rel.nao_analisadas.length > 0 && (
            <p className="mt-3 text-[10px] text-slate-400">
              Não analisadas nesta sessão: {rel.nao_analisadas.join(" · ")} — ausência de análise não significa ausência do problema.
            </p>
          )}
        </div>
      </Pagina>

      {/* SEÇÕES EXECUTIVAS (mesma composição do laudo, com detalhes) */}
      <Pagina rodape={rel.rodape} num="dimensões">
        <Titulo>Dimensões analisadas — detalhe</Titulo>
        <div className="space-y-5">
          {rel.secoes.map((s) => (
            <div key={s.chave}>
              <div className="mb-1 flex items-center gap-2">
                <span className="h-2.5 w-2.5 rounded-sm" style={{ background: LUZ_COR[s.luz] ?? "#cbd5e1" }} />
                <h3 className="text-[13px] font-bold text-marinho-900">{s.titulo}</h3>
                {!s.analisada && <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[9px] font-bold uppercase text-slate-500">não analisada</span>}
              </div>
              {s.itens.length > 0 && <TabelaItens itens={s.itens} />}
              {s.avisos.length > 0 && (
                <ul className="mt-1 list-disc pl-5 text-[9.5px] text-slate-400">
                  {s.avisos.map((a) => <li key={a}>{a}</li>)}
                </ul>
              )}
            </div>
          ))}
        </div>
      </Pagina>

      {/* URBANISMO — planta + quadro */}
      {geo && (
        <Pagina rodape={rel.rodape} num="urbanismo">
          <Titulo>Urbanismo — estudo de massa <span className="ml-1 rounded-full bg-amber-100 px-2 py-0.5 text-[9px] font-bold uppercase text-amber-800">esquemático</span></Titulo>
          <p className="mb-2 text-[10.5px] text-slate-500">Estudo de TRIAGEM gerado e medido pelo motor determinístico — não substitui o projeto urbanístico (art. 6º, Lei 6.766/79).</p>
          <PlantaSvg geo={geo} gleba={glebaGeojson} heat={false} />
          <div className="mt-3 grid grid-cols-2 gap-5">
            <div>
              <h3 className="mb-1 text-[12px] font-bold text-slate-700">Quadro de áreas</h3>
              <table className="w-full text-[11px]">
                <tbody>
                  {linhasQuadro.map(([k, rotulo]) => {
                    const v = quadro?.[k];
                    if (!v?.m2_fmt) return null;
                    return (
                      <tr key={k} className="border-b border-dashed border-slate-100">
                        <td className="py-1 font-semibold text-marinho-900">{rotulo}</td>
                        <td className="py-1 text-right font-mono">{v.m2_fmt}</td>
                        <td className="py-1 text-right font-mono text-slate-500">{v.pct_fmt}</td>
                      </tr>
                    );
                  })}
                  {quadro?.area_liquida_fmt && (
                    <tr className="border-t-2 border-slate-200 font-extrabold">
                      <td className="py-1">Área líquida do estudo</td>
                      <td className="py-1 text-right font-mono">{quadro.area_liquida_fmt}</td>
                      <td />
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
            <div>
              <h3 className="mb-1 text-[12px] font-bold text-slate-700">Indicadores</h3>
              <table className="w-full text-[11px]">
                <tbody>
                  {ind?.n_lotes != null && <tr className="border-b border-dashed border-slate-100"><td className="py-1 font-semibold">Lotes</td><td className="py-1 text-right font-mono">{ind.n_lotes}{ind.area_media_fmt ? ` · média ${ind.area_media_fmt}` : ""}</td></tr>}
                  {ind?.testada_media_m != null && <tr className="border-b border-dashed border-slate-100"><td className="py-1 font-semibold">Testada média</td><td className="py-1 text-right font-mono">{ind.testada_media_m} m</td></tr>}
                  {ind?.comprimento_vias_m != null && <tr className="border-b border-dashed border-slate-100"><td className="py-1 font-semibold">Vias</td><td className="py-1 text-right font-mono">{Math.round(ind.comprimento_vias_m).toLocaleString("pt-BR")} m</td></tr>}
                  {rel.urbanismo_snapshot?.versao != null && <tr><td className="py-1 font-semibold">Versão do estudo</td><td className="py-1 text-right font-mono">v{rel.urbanismo_snapshot.versao}</td></tr>}
                </tbody>
              </table>
              {rel.urbanismo_snapshot?.proveniencia && (
                <p className="mt-2 text-[9.5px] italic text-slate-400">{String(rel.urbanismo_snapshot.proveniencia)}</p>
              )}
            </div>
          </div>
        </Pagina>
      )}

      {/* VALORIZAÇÃO — mapa de calor */}
      {geo?.lotes_features?.features?.length > 0 && (
        <Pagina rodape={rel.rodape} num="valorização">
          <Titulo>Valorização lote a lote <span className="ml-1 rounded-full bg-amber-100 px-2 py-0.5 text-[9px] font-bold uppercase text-amber-800">régua relativa do estudo</span></Titulo>
          <p className="mb-2 text-[10.5px] text-slate-500">Score POSICIONAL de cada lote no traçado (mesma régua do aplicativo) — comparação relativa entre os lotes do estudo, não avaliação de mercado. Orienta tabela de preços e ordem de lançamento.</p>
          <PlantaSvg geo={geo} gleba={glebaGeojson} heat />
          <div className="mt-2 flex flex-wrap gap-3 text-[10px] text-slate-600">
            {Object.entries(CORES_QUINTIL).map(([q, cor]) => (
              <span key={q}><i className="mr-1 inline-block h-2.5 w-2.5 rounded-sm align-[-1px]" style={{ background: cor }} />quintil {q}</span>
            ))}
          </div>
          {heatmap?.faixas?.length > 0 && (
            <div className="mt-3 max-w-sm">
              <h3 className="mb-1 text-[12px] font-bold text-slate-700">Distribuição por faixa de score</h3>
              <table className="w-full text-[11px]"><tbody>
                {heatmap.faixas.map((f: GJ) => (
                  <tr key={f.faixa} className="border-b border-dashed border-slate-100">
                    <td className="py-1 font-semibold">{f.faixa}</td>
                    <td className="py-1 text-right font-mono">{f.n} lotes</td>
                  </tr>
                ))}
              </tbody></table>
              {heatmap.proveniencia && <p className="mt-1 text-[9.5px] italic text-slate-400">{heatmap.proveniencia}</p>}
            </div>
          )}
        </Pagina>
      )}

      {/* FINANCEIRO + ECONÔMICA */}
      {fin && (
        <Pagina rodape={rel.rodape} num="financeiro">
          <Titulo>Financeiro e Econômica <span className="ml-1 rounded-full bg-amber-100 px-2 py-0.5 text-[9px] font-bold uppercase text-amber-800">sob as premissas declaradas</span></Titulo>
          {fin.fluxo_resumo_anual?.length > 0 && (
            <>
              <h3 className="mb-1 text-[12px] font-bold text-slate-700">Fluxo de caixa anual</h3>
              <FluxoAnualSvg linhas={fin.fluxo_resumo_anual} />
              <p className="mb-3 text-[10px] text-slate-500">■ entradas · ■ saídas · ─ acumulado (escala visual; valores na tabela de blocos abaixo)</p>
            </>
          )}
          <div className="grid grid-cols-2 gap-5">
            <div>
              <h3 className="mb-1 text-[12px] font-bold text-slate-700">Blocos de custo (com proveniência)</h3>
              <table className="w-full text-[10.5px]"><tbody>
                {fin.blocos.map((b) => (
                  <tr key={b.bloco} className="border-b border-dashed border-slate-100">
                    <td className="py-1 font-semibold text-marinho-900">{b.bloco}</td>
                    <td className="py-1 text-right font-mono">{b.total_fmt}</td>
                  </tr>
                ))}
              </tbody></table>
              {fin.cenarios && fin.cenarios.length > 0 && (
                <>
                  <h3 className="mb-1 mt-3 text-[12px] font-bold text-slate-700">Cenários de venda</h3>
                  <table className="w-full text-[10.5px]"><tbody>
                    {fin.cenarios.map((c) => (
                      <tr key={c.nome} className="border-b border-dashed border-slate-100">
                        <td className={`py-1 ${c.ativo ? "font-extrabold" : "font-semibold"}`}>{c.nome} · {c.duracao_meses}m</td>
                        <td className="py-1 text-right font-mono">{c.resultado_nominal_fmt}</td>
                        <td className="py-1 text-right font-mono text-rose-700">{c.exposicao_maxima.valor_fmt}</td>
                      </tr>
                    ))}
                  </tbody></table>
                </>
              )}
            </div>
            <div>
              {eco && (
                <>
                  <h3 className="mb-1 text-[12px] font-bold text-slate-700">Econômica (TMA {eco.tma?.aa_real_fmt})</h3>
                  <table className="w-full text-[10.5px]"><tbody>
                    <tr className="border-b border-dashed border-slate-100"><td className="py-1 font-semibold">VPL</td><td className="py-1 text-right font-mono">{eco.vpl?.valor_fmt}</td></tr>
                    <tr className="border-b border-dashed border-slate-100"><td className="py-1 font-semibold">TIR real a.a.</td><td className="py-1 text-right font-mono">{eco.tir?.aa_fmt ?? `— (${eco.tir?.status})`}</td></tr>
                    <tr className="border-b border-dashed border-slate-100"><td className="py-1 font-semibold">Payback simples / descontado</td><td className="py-1 text-right font-mono">{eco.payback?.simples_mes ?? "—"} / {eco.payback?.descontado_mes ?? "—"} meses</td></tr>
                    {eco.mtir_aa_fmt && <tr className="border-b border-dashed border-slate-100"><td className="py-1 font-semibold">MTIR a.a.</td><td className="py-1 text-right font-mono">{eco.mtir_aa_fmt}</td></tr>}
                  </tbody></table>
                  {eco.curva_vpl_tma?.length > 0 && (
                    <>
                      <h3 className="mb-1 mt-3 text-[12px] font-bold text-slate-700">Curva VPL × TMA</h3>
                      <CurvaVplSvg pontos={eco.curva_vpl_tma} />
                    </>
                  )}
                </>
              )}
              {fin.comparativo_tributario?.leitura && (
                <p className="mt-3 rounded border border-slate-200 bg-slate-50 p-2 text-[10px] text-slate-600">
                  <b>Tributário (LC 214/2025):</b> {fin.comparativo_tributario.leitura}
                </p>
              )}
            </div>
          </div>
        </Pagina>
      )}

      {/* PREMISSAS, FONTES E AVISOS */}
      <Pagina rodape={rel.rodape} num="premissas e fontes">
        <Titulo>Premissas, fontes e avisos</Titulo>
        {fin && (
          <>
            <h3 className="mb-1 text-[12px] font-bold text-slate-700">Proveniência dos blocos financeiros</h3>
            <table className="w-full text-[10px]"><tbody>
              {fin.blocos.map((b) => (
                <tr key={b.bloco} className="border-b border-dashed border-slate-100">
                  <td className="py-1 font-semibold text-marinho-900">{b.bloco}</td>
                  <td className="py-1 pl-3 text-slate-500">{b.proveniencia}</td>
                </tr>
              ))}
            </tbody></table>
          </>
        )}
        <h3 className="mb-1 mt-4 text-[12px] font-bold text-slate-700">Fontes por dimensão</h3>
        <table className="w-full text-[10px]"><tbody>
          {rel.proveniencia_consolidada.map((p) => (
            <tr key={p.dimensao} className="border-b border-dashed border-slate-100">
              <td className="py-1 font-semibold text-marinho-900">{p.dimensao}</td>
              <td className="py-1 pl-3 text-slate-500">{p.fonte}</td>
            </tr>
          ))}
        </tbody></table>
        <h3 className="mb-1 mt-4 text-[12px] font-bold text-slate-700">Avisos</h3>
        <ul className="list-disc space-y-0.5 pl-5 text-[10px] text-slate-500">
          {rel.avisos.map((a) => <li key={a}>{a}</li>)}
          {rel.secoes.flatMap((s) => s.avisos).map((a, i) => <li key={`${i}-${a.slice(0, 24)}`}>{a}</li>)}
        </ul>
      </Pagina>

      {/* impressão: só o relatório, uma página A4 por bloco */}
      <style>{`
        @media print {
          body * { visibility: hidden; }
          .rel-root, .rel-root * { visibility: visible; }
          .rel-acoes, .rel-acoes * { display: none !important; }
          .rel-root { position: absolute !important; inset: 0 !important; overflow: visible !important; background: #fff !important; padding: 0 !important; }
          .rel-pg { width: auto !important; min-height: 0 !important; margin: 0 !important; box-shadow: none !important; page-break-after: always; }
        }
        @page { size: A4; margin: 11mm; }
      `}</style>
    </div>
  );
}
