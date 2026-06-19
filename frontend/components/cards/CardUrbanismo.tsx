"use client";

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  proporUrbanismo,
  type ChaveOverlay,
  type ConformidadeLegal,
  type ItemFidelidadeArea,
  type PerfilMunicipal,
  type PropostaUrbanistica,
  type PublicoAlvo,
  type TipoLoteamento,
} from "@/lib/api";
import {
  CORES_OVERLAY,
  ESTILO_OVERLAY,
  ROTULO_OVERLAY,
} from "@/components/mapa/overlays";

const MapaLeaflet = dynamic(() => import("@/components/mapa/MapaLeaflet"), {
  ssr: false,
  loading: () => (
    <div className="flex h-full items-center justify-center text-sm text-slate-400">
      Carregando mapa…
    </div>
  ),
});

const TIPOS: { v: TipoLoteamento; r: string }[] = [
  { v: "aberto", r: "Loteamento aberto" },
  { v: "fechado", r: "Loteamento fechado" },
  { v: "condominio_lotes", r: "Condomínio de lotes" },
  { v: "desmembramento", r: "Desmembramento" },
  { v: "loteamento_rural", r: "Loteamento rural" },
];
const PUBLICOS: { v: PublicoAlvo; r: string }[] = [
  { v: "baixa", r: "Baixa renda (densidade alta)" },
  { v: "media", r: "Média renda (equilíbrio)" },
  { v: "alta", r: "Alta renda (exclusividade)" },
];

// Linha do quadro de áreas: rótulo + m² (fmt do backend) + % (fmt do backend).
function LinhaArea({
  rotulo,
  m2,
  pct,
  forte,
}: {
  rotulo: string;
  m2: string;
  pct: string;
  forte?: boolean;
}) {
  return (
    <div
      className={`flex items-center justify-between py-1.5 text-sm ${
        forte ? "font-semibold text-slate-900" : "text-slate-700"
      }`}
    >
      <span>{rotulo}</span>
      <span className="tabular-nums">
        {m2} m² <span className="ml-1 text-slate-400">·</span>{" "}
        <span className="text-slate-500">{pct}</span>
      </span>
    </div>
  );
}

export function CardUrbanismo({
  analiseId,
  glebaGeojson,
  perfil,
  onData,
}: {
  analiseId: string;
  glebaGeojson: GeoJSON.Polygon;
  perfil?: PerfilMunicipal | null;
  onData?: (p: PropostaUrbanistica | null) => void;
}) {
  const zonas = perfil?.zonas.map((z) => z.codigo) ?? [];
  const [tipo, setTipo] = useState<TipoLoteamento>("aberto");
  const [publico, setPublico] = useState<PublicoAlvo>("media");
  const [zona, setZona] = useState<string>("");
  const [proposta, setProposta] = useState<PropostaUrbanistica | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(false);
  const [mapaExpandido, setMapaExpandido] = useState(false); // Fase 9.6 — mapa maior

  useEffect(() => {
    if (!zona && zonas.length > 0) setZona(zonas[0]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [perfil]);

  async function gerar() {
    setCarregando(true);
    setErro(null);
    try {
      const p = await proporUrbanismo(analiseId, tipo, publico, zona || null);
      setProposta(p);
      onData?.(p);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Falha ao gerar o estudo de massa.");
    } finally {
      setCarregando(false);
    }
  }

  // Camadas do layout → overlays do mapa (o front só renderiza o GeoJSON do backend, §2).
  const overlays: Partial<Record<ChaveOverlay, GeoJSON.Geometry>> = {};
  const lotesFeatures = proposta?.geometria.lotes_features ?? null;
  const temFeatures = !!lotesFeatures && lotesFeatures.features.length > 0;
  if (proposta) {
    const g = proposta.geometria;
    if (g.arruamento) overlays.urb_arruamento = g.arruamento;
    // Fase 9.6 — verde SEPARADO: bloco reservado (destaque) × sobra de ponta (discreto).
    if (g.areas_verdes_reservada) overlays.urb_verde_reservada = g.areas_verdes_reservada;
    if (g.areas_verdes_sobra) overlays.urb_verde_sobra = g.areas_verdes_sobra;
    if (!g.areas_verdes_reservada && !g.areas_verdes_sobra && g.areas_verdes)
      overlays.urb_verde = g.areas_verdes; // fallback (backend antigo)
    if (g.sistema_lazer) overlays.urb_lazer = g.sistema_lazer;
    if (g.institucional) overlays.urb_institucional = g.institucional;
    // Fase 9.8 — restrição recortada (mata/declividade/APP): demarcada e rotulada (não "clarão").
    if (g.restricao_recortada) overlays.urb_restricao = g.restricao_recortada;
    // Fase 9.5 — lotes desenhados LOTE A LOTE (FeatureCollection). Sem features → fallback
    // para o polígono fundido (compat com versões antigas do backend).
    if (!temFeatures && g.lotes) overlays.urb_lotes = g.lotes;
  }
  // Camadas presentes (para a legenda do mapa).
  const camadasMapa = Object.keys(overlays) as ChaveOverlay[];

  const q = proposta?.quadro_areas;
  const ind = proposta?.indicadores;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex flex-wrap items-center gap-2">
          Urbanismo — estudo de massa
          <span className="rounded-full bg-amber-200 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-amber-900">
            Esquemático
          </span>
        </CardTitle>
        <CardDescription>
          A IA propõe o <strong>programa</strong> (lote-alvo, viário, % de lazer) sob o
          perfil escolhido; o motor <strong>gera e mede</strong> toda a geometria e todos os
          números — nenhum número vem da IA. É pré-análise de triagem, <strong>não</strong> o
          projeto urbanístico: verificar com urbanista (art. 6º Lei 6.766).
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          <label className="text-sm text-slate-600">Tipo</label>
          <select
            value={tipo}
            onChange={(e) => setTipo(e.target.value as TipoLoteamento)}
            className="rounded-lg border border-slate-200 px-2 py-2 text-sm"
          >
            {TIPOS.map((t) => (
              <option key={t.v} value={t.v}>
                {t.r}
              </option>
            ))}
          </select>
          <label className="text-sm text-slate-600">Público-alvo</label>
          <select
            value={publico}
            onChange={(e) => setPublico(e.target.value as PublicoAlvo)}
            className="rounded-lg border border-slate-200 px-2 py-2 text-sm"
          >
            {PUBLICOS.map((p) => (
              <option key={p.v} value={p.v}>
                {p.r}
              </option>
            ))}
          </select>
          {zonas.length > 0 && (
            <>
              <label className="text-sm text-slate-600">Zona (LUOS)</label>
              <select
                value={zona}
                onChange={(e) => setZona(e.target.value)}
                className="rounded-lg border border-slate-200 px-2 py-2 text-sm"
              >
                {zonas.map((z) => (
                  <option key={z} value={z}>
                    {z}
                  </option>
                ))}
              </select>
            </>
          )}
          <Button onClick={gerar} disabled={carregando}>
            {carregando ? "Gerando…" : "Gerar estudo de massa (IA)"}
          </Button>
        </div>

        {erro && (
          <p className="rounded-lg bg-rose-50 p-3 text-sm text-rose-800">{erro}</p>
        )}

        {/* Diretrizes do município (Fase 9.4) — hierarquia LUOS → mercado → federal */}
        {proposta?.diretrizes && (
          <div
            className={`rounded-xl border p-3 text-sm ${
              proposta.diretrizes.confirmada
                ? "border-emerald-200 bg-emerald-50 text-emerald-900"
                : "border-amber-200 bg-amber-50 text-amber-900"
            }`}
          >
            <p className="font-semibold">Diretrizes — {proposta.diretrizes.fonte}</p>
            <p className="mt-0.5">
              Lote legal de{" "}
              <strong>
                {proposta.diretrizes.piso_lote_efetivo_m2.toLocaleString("pt-BR")} a{" "}
                {proposta.diretrizes.teto_lote_m2.toLocaleString("pt-BR")} m²
              </strong>
              {proposta.diretrizes.doacao_min_pct != null && (
                <>
                  {" "}
                  · doação mínima{" "}
                  {(proposta.diretrizes.doacao_min_pct * 100).toLocaleString("pt-BR")}%
                </>
              )}
              . {proposta.diretrizes.aviso}
            </p>
          </div>
        )}

        {proposta && (
          <>
            {/* Mapa do layout esquemático — full width e maior (Fase 9.6) */}
            <div className="overflow-hidden rounded-xl border border-slate-200">
              <div className="flex items-center justify-between bg-slate-50 px-3 py-1.5">
                <span className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                  Parcelamento esquemático
                </span>
                <button
                  type="button"
                  onClick={() => setMapaExpandido((v) => !v)}
                  className="rounded-md border border-slate-200 bg-white px-2 py-1 text-[11px] text-slate-600 hover:bg-slate-100"
                >
                  {mapaExpandido ? "Recolher mapa" : "Expandir mapa"}
                </button>
              </div>
              <div className={`w-full ${mapaExpandido ? "h-[680px]" : "h-[440px]"}`}>
                <MapaLeaflet
                  geojson={glebaGeojson}
                  overlays={overlays}
                  lotesFeatures={lotesFeatures}
                  quadras={proposta?.geometria.quadras ?? null}
                />
              </div>
              <div className="space-y-1.5 bg-slate-50 px-3 py-2">
                {/* Legenda das camadas de área */}
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[10px] text-slate-600">
                  {camadasMapa
                    .filter((c) => c !== "urb_lotes")
                    .map((c) => (
                      <span key={c} className="inline-flex items-center gap-1">
                        <span
                          className="inline-block h-2.5 w-3 rounded-sm border"
                          style={{
                            backgroundColor: (ESTILO_OVERLAY[c]?.fillColor ?? CORES_OVERLAY[c]) + "cc",
                            borderColor: ESTILO_OVERLAY[c]?.color ?? CORES_OVERLAY[c],
                          }}
                        />
                        {ROTULO_OVERLAY[c]}
                      </span>
                    ))}
                </div>
                {temFeatures && (
                  <div className="flex flex-wrap items-center gap-2 text-[10px] text-slate-500">
                    <span>Cor do lote = score:</span>
                    {[
                      ["0-3", "#2563eb"],
                      ["3-5", "#06b6d4"],
                      ["5-7", "#84cc16"],
                      ["7-9", "#f59e0b"],
                      ["9-10", "#ef4444"],
                    ].map(([faixa, cor]) => (
                      <span key={faixa} className="inline-flex items-center gap-1">
                        <span
                          className="inline-block h-2.5 w-2.5 rounded-sm"
                          style={{ backgroundColor: cor }}
                        />
                        {faixa}
                      </span>
                    ))}
                  </div>
                )}
                {/* Fase 9.7 — diagnóstico da MALHA: viário conexo + institucional qualifica_legal. */}
                {proposta?.geometria.viario_diagnostico && (
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[10px] text-slate-600">
                    {(() => {
                      const vd = proposta.geometria.viario_diagnostico!;
                      const ilhas = vd.ilhas ?? 1;
                      // Fase 9.8 — conexo geral, ou conexo POR ILHA quando a restrição parte a gleba.
                      const ok = vd.conexo || (ilhas > 1 && vd.conexo_por_ilha);
                      const txt = vd.conexo
                        ? "conexo (malha única)"
                        : ilhas > 1 && vd.conexo_por_ilha
                          ? `${ilhas} ilhas conexas (partidas pela restrição)`
                          : `em ${vd.trechos} trechos`;
                      return (
                        <span className="inline-flex items-center gap-1">
                          <span className={`inline-block h-2 w-2 rounded-full ${ok ? "bg-emerald-500" : "bg-amber-500"}`} />
                          Viário {txt}
                          {!!vd.stubs_podados && ` · ${vd.stubs_podados} caco(s) podado(s)`}
                        </span>
                      );
                    })()}
                    {proposta.geometria.institucional_diagnostico && (
                      <span className="inline-flex items-center gap-1">
                        <span
                          className={`inline-block h-2 w-2 rounded-full ${
                            proposta.geometria.institucional_diagnostico.qualifica_legal
                              ? "bg-emerald-500"
                              : "bg-slate-400"
                          }`}
                        />
                        Institucional{" "}
                        {proposta.geometria.institucional_diagnostico.qualifica_legal
                          ? "qualifica (frente/via, ⌀≥10 m)"
                          : "a definir com a Prefeitura"}
                      </span>
                    )}
                    {proposta.geometria.sistema_lazer?.forma === "quadra" && (
                      <span className="inline-flex items-center gap-1">
                        <span className="inline-block h-2 w-2 rounded-full bg-cyan-500" />
                        Lazer formado (frente p/ via)
                      </span>
                    )}
                    {/* Fase 9.9 — traçado sinuoso (curvo, contornando o íngreme). */}
                    {proposta.geometria.viario_diagnostico.eixos_curvos && (
                      <span className="inline-flex items-center gap-1">
                        <span className="inline-block h-2 w-2 rounded-full bg-violet-500" />
                        Traçado sinuoso (curva {proposta.geometria.viario_diagnostico.sinuosidade_media?.toFixed(2)}
                        {proposta.geometria.viario_diagnostico.esqueleto_origem === "llm" ? " · IA" : " · padrão"})
                      </span>
                    )}
                    {/* Fase 9.11 — grade adaptada ao terreno (quarteirão dimensionado por ilha). */}
                    {proposta.geometria.viario_diagnostico.grade_adaptativa && (
                      <span className="inline-flex items-center gap-1">
                        <span className="inline-block h-2 w-2 rounded-full bg-amber-500" />
                        Grade adaptada ao terreno (quarteirão por ilha)
                      </span>
                    )}
                    {/* Fase 9.12 — todo lote com frente para via (definição legal de lote). */}
                    {proposta.geometria.viario_diagnostico.todos_lotes_com_frente_via && (
                      <span className="inline-flex items-center gap-1">
                        <span className="inline-block h-2 w-2 rounded-full bg-emerald-600" />
                        Todo lote com frente para via
                        {typeof proposta.geometria.viario_diagnostico.testada_media_m === "number" &&
                          ` (testada média ${proposta.geometria.viario_diagnostico.testada_media_m.toFixed(1)} m)`}
                      </span>
                    )}
                    {/* Fase 9.14 — traçado inteligente: contorno da restrição + cul-de-sacs. */}
                    {((proposta.geometria.viario_diagnostico.trechos_contornando_restricao ?? 0) > 0 ||
                      (proposta.geometria.viario_diagnostico.culdesacs_bulbo ?? 0) > 0) && (
                      <span className="inline-flex items-center gap-1">
                        <span className="inline-block h-2 w-2 rounded-full bg-sky-600" />
                        Traçado: via contorna a restrição
                        {(proposta.geometria.viario_diagnostico.culdesacs_bulbo ?? 0) > 0 &&
                          `, ${proposta.geometria.viario_diagnostico.culdesacs_bulbo} cul-de-sac(s)`}
                        {(proposta.geometria.viario_diagnostico.lotes_recuperados_de_sobra ?? 0) > 0 &&
                          `, ${proposta.geometria.viario_diagnostico.lotes_recuperados_de_sobra} lote(s) recuperado(s)`}
                      </span>
                    )}
                  </div>
                )}
                <p className="text-[11px] text-slate-500">
                  Traçado ESQUEMÁTICO — vias SINUOSAS a partir dos eixos curvos propostos pela IA,
                  contornando a área não-edificável; quadras são as faces que as ruas cercam. As
                  curvas são aproximadas (não o traçado executivo do urbanista); o valor é o quadro
                  de áreas, não a precisão do desenho. Clique num lote para área/score, ou numa
                  quadra para sua área.
                </p>
              </div>
            </div>

            <div>
              {/* Quadro de áreas */}
              <div className="rounded-xl border border-slate-200 p-4">
                <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">
                  {/* Fase 10 (Parte 1): a área líquida aproveitável é a CANÔNICA (mesma das abas
                      Ambiental/Aproveitamento); cai para o quadro interno se ausente. */}
                  Quadro de áreas (sobre a área líquida{" "}
                  {proposta?.areas_canonicas
                    ? Math.round(proposta.areas_canonicas.area_liquida_aproveitavel_m2).toLocaleString("pt-BR")
                    : q?.area_liquida_fmt}{" "}
                  m²)
                </p>
                {q && (
                  <div className="divide-y divide-slate-100">
                    <LinhaArea
                      rotulo="Vendável (lotes)"
                      m2={q.vendavel.m2_fmt}
                      pct={q.vendavel.pct_fmt}
                      forte
                    />
                    {/* Fase 10 (Parte 2) — verde HONESTO: reserva (verde legítimo) e sobra
                        geométrica em LINHAS SEPARADAS; a sobra nunca é chamada de "área verde". */}
                    {q.area_verde_reserva ? (
                      <LinhaArea
                        rotulo="Área verde de doação/reserva"
                        m2={q.area_verde_reserva.m2_fmt}
                        pct={q.area_verde_reserva.pct_fmt}
                      />
                    ) : (
                      <LinhaArea rotulo="Áreas verdes" m2={q.areas_verdes.m2_fmt} pct={q.areas_verdes.pct_fmt} />
                    )}
                    {q.sobra_geometrica && q.sobra_geometrica.m2 > 0 && (
                      <LinhaArea
                        rotulo="Sobra geométrica ⚠️ (meta: reduzir)"
                        m2={q.sobra_geometrica.m2_fmt}
                        pct={q.sobra_geometrica.pct_fmt}
                      />
                    )}
                    {q.sistema_lazer.m2 > 0 && (
                      <LinhaArea
                        rotulo="Sistema de lazer"
                        m2={q.sistema_lazer.m2_fmt}
                        pct={q.sistema_lazer.pct_fmt}
                      />
                    )}
                    {q.institucional.m2 > 0 && (
                      <LinhaArea
                        rotulo="Institucional"
                        m2={q.institucional.m2_fmt}
                        pct={q.institucional.pct_fmt}
                      />
                    )}
                    <LinhaArea
                      rotulo="Arruamento (viário)"
                      m2={q.arruamento.m2_fmt}
                      pct={q.arruamento.pct_fmt}
                    />
                  </div>
                )}
                {ind && (
                  <div className="mt-3 grid grid-cols-2 gap-2 text-sm">
                    <Kpi rotulo="Nº de lotes" valor={String(ind.n_lotes)} />
                    <Kpi
                      rotulo="Área média"
                      valor={ind.area_media_fmt ? `${ind.area_media_fmt} m²` : "—"}
                    />
                    <Kpi
                      rotulo="Testada média"
                      valor={
                        ind.testada_media_m != null
                          ? `${ind.testada_media_m.toLocaleString("pt-BR")} m`
                          : "—"
                      }
                    />
                    <Kpi
                      rotulo="Profundidade"
                      valor={
                        ind.profundidade_media_m != null
                          ? `${ind.profundidade_media_m.toLocaleString("pt-BR")} m`
                          : "—"
                      }
                    />
                  </div>
                )}
                {/* Fase 9.10 — PONTE: rotula o estudo (geométrico) e cita o teto regulatório.
                    Texto interpolado pelo backend; o front só renderiza. */}
                {proposta?.reconciliacao && (
                  <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-3">
                    <p className="text-[11px] font-semibold uppercase tracking-wide text-amber-700">
                      Estudo de massa × teto regulatório
                    </p>
                    <p className="mt-1 text-xs text-amber-900">{proposta.reconciliacao.leitura}</p>
                    {proposta.reconciliacao.ref_teto_regulatorio && (
                      <p className="mt-1 text-[11px] text-amber-700">
                        Faixa honesta: ~{proposta.reconciliacao.ref_teto_regulatorio.lotes} (teto
                        legal) → ~{proposta.reconciliacao.lotes_estudo} (este estudo).
                      </p>
                    )}
                  </div>
                )}
              </div>
            </div>

            {/* Programa proposto pela IA (proveniência) */}
            <div className="rounded-xl border border-indigo-200 bg-indigo-50 p-3 text-sm text-indigo-900">
              <p className="font-semibold">Programa proposto pela IA ({proposta.programa.origem})</p>
              <p className="text-indigo-800">
                Lote-alvo {proposta.programa.lote_alvo_m2.toLocaleString("pt-BR")} m² ·
                densidade {proposta.programa.densidade} · lazer{" "}
                {(proposta.programa.pct_lazer * 100).toLocaleString("pt-BR")}% · viário{" "}
                {proposta.programa.arquetipo_viario}. {proposta.programa.justificativa}
              </p>
            </div>

            {/* Fidelidade: convergência programa × medido (Fase 9.1) */}
            {proposta.fidelidade && (
              <div className="rounded-xl border border-slate-200 p-4">
                <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Fidelidade — programa × medido
                </p>
                <div className="space-y-2">
                  {proposta.fidelidade.areas.map((a) => (
                    <ConvergeBar key={a.item} a={a} />
                  ))}
                </div>
                <div className="mt-3 flex flex-wrap gap-2 text-xs text-slate-600">
                  <span className="rounded-full bg-slate-100 px-2 py-0.5">
                    Viário: {proposta.fidelidade.viario.arquetipo}
                    {proposta.fidelidade.viario.esqueleto_usado
                      ? " · eixos da IA"
                      : " · grelha"}
                  </span>
                  {proposta.fidelidade.topografia.orientacao_por_declividade && (
                    <span className="rounded-full bg-slate-100 px-2 py-0.5">
                      Quarteirões orientados pela declividade (triagem)
                    </span>
                  )}
                </div>
              </div>
            )}

            {/* Distribuição de tamanhos (Fase 9.3) — o lote emerge da subdivisão da quadra */}
            {proposta.distribuicao_tamanhos &&
              proposta.distribuicao_tamanhos.faixas.length > 0 && (
                <div className="rounded-xl border border-slate-200 p-4">
                  <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Distribuição de tamanhos — o lote é o que a quadra comporta
                  </p>
                  <p className="mb-2 text-sm text-slate-700">
                    Média{" "}
                    <strong>
                      {proposta.distribuicao_tamanhos.media_m2.toLocaleString("pt-BR", {
                        maximumFractionDigits: 0,
                      })}{" "}
                      m²
                    </strong>{" "}
                    · variação{" "}
                    {(proposta.distribuicao_tamanhos.cv * 100).toLocaleString("pt-BR", {
                      maximumFractionDigits: 0,
                    })}
                    % · de{" "}
                    {proposta.distribuicao_tamanhos.min_m2.toLocaleString("pt-BR", {
                      maximumFractionDigits: 0,
                    })}{" "}
                    a{" "}
                    {proposta.distribuicao_tamanhos.max_m2.toLocaleString("pt-BR", {
                      maximumFractionDigits: 0,
                    })}{" "}
                    m²
                  </p>
                  <div className="flex items-end gap-1" style={{ height: 80 }}>
                    {(() => {
                      const fx = proposta.distribuicao_tamanhos!.faixas;
                      const max = Math.max(...fx.map((f) => f.n), 1);
                      return fx.map((f) => (
                        <div
                          key={f.de}
                          className="flex flex-1 flex-col items-center justify-end"
                          title={`${f.de}–${f.ate} m²: ${f.n} lotes`}
                        >
                          <span className="text-[10px] tabular-nums text-slate-400">
                            {f.n}
                          </span>
                          <div
                            className="w-full rounded-t bg-emerald-500"
                            style={{ height: `${Math.round((f.n / max) * 60)}px` }}
                          />
                          <span className="mt-1 text-[9px] tabular-nums text-slate-400">
                            {f.de}
                          </span>
                        </div>
                      ));
                    })()}
                  </div>
                  <p className="mt-2 text-xs text-slate-500">
                    Retalho perdido{" "}
                    {(
                      proposta.distribuicao_tamanhos.retalho_perdido_pct * 100
                    ).toLocaleString("pt-BR", { maximumFractionDigits: 1 })}
                    % · viário{" "}
                    {(proposta.distribuicao_tamanhos.viario_pct * 100).toLocaleString("pt-BR", {
                      maximumFractionDigits: 1,
                    })}
                    % · tamanho e valor desacoplados (posição → R$/m², não tamanho)
                  </p>
                  <p className="mt-1 text-xs text-slate-400">
                    {proposta.distribuicao_tamanhos.fora_da_faixa === 0
                      ? "Todos os lotes dentro da faixa legal (clamp município → federal)."
                      : `${proposta.distribuicao_tamanhos.fora_da_faixa} lote(s) fora da faixa legal — verificar.`}
                    {proposta.distribuicao_tamanhos.lote_alvo_origem
                      ? ` ${proposta.distribuicao_tamanhos.lote_alvo_origem}`
                      : ""}
                  </p>
                </div>
              )}

            {/* Conformidade legal (Fase 9.4) — medido × mínimo do município */}
            {proposta.conformidade_legal.length > 0 && (
              <div className="rounded-xl border border-slate-200 p-4">
                <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Conformidade legal — medido × mínimo do município
                </p>
                <ul className="space-y-1.5">
                  {proposta.conformidade_legal.map((c: ConformidadeLegal) => (
                    <li key={c.item} className="flex items-start gap-2 text-sm">
                      <span
                        className={`mt-0.5 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase ${
                          c.status === "nao_atende"
                            ? "bg-rose-200 text-rose-900"
                            : c.status === "nao_avaliado"
                            ? "bg-slate-200 text-slate-600"
                            : "bg-emerald-100 text-emerald-800"
                        }`}
                      >
                        {c.status.replace(/_/g, " ")}
                      </span>
                      <span className="text-slate-700">{c.leitura}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Heatmap de valorização (qualidade relativa, sem preço) */}
            {proposta.heatmap.score_medio != null && (
              <div className="rounded-xl border border-slate-200 p-4">
                <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Heatmap de score por lote — médio {proposta.heatmap.score_medio} (qualidade
                  relativa; o R$/m² por faixa é seu)
                </p>
                <div className="space-y-1">
                  {proposta.heatmap.faixas.map((f) => (
                    <div key={f.faixa} className="flex items-center gap-2 text-sm">
                      <span className="w-12 text-slate-600">{f.faixa}</span>
                      <div className="h-3 flex-1 overflow-hidden rounded bg-slate-100">
                        <div
                          className="h-full bg-emerald-500"
                          style={{ width: `${Math.round(f.pct * 100)}%` }}
                        />
                      </div>
                      <span className="w-16 text-right tabular-nums text-slate-500">
                        {f.n} lote{f.n > 1 ? "s" : ""}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Conformidade do programa (sinaliza, não decide) */}
            {proposta.conformidade_programa.length > 0 && (
              <ul className="space-y-2">
                {proposta.conformidade_programa.map((c) => (
                  <li
                    key={c.item}
                    className={`rounded-lg border p-3 text-sm ${
                      c.status === "atencao"
                        ? "border-amber-300 bg-amber-50 text-amber-900"
                        : "border-slate-200 bg-slate-50 text-slate-700"
                    }`}
                  >
                    {c.leitura}
                  </li>
                ))}
              </ul>
            )}

            {proposta.esqueleto_ignorado.length > 0 && (
              <div className="rounded-lg bg-slate-50 p-3 text-xs text-slate-500">
                {proposta.esqueleto_ignorado.map((s) => (
                  <p key={s}>• {s}</p>
                ))}
              </div>
            )}

            <p className="text-xs text-slate-500">{proposta.proveniencia}</p>

            <div className="rounded-lg bg-amber-50 p-3 text-xs text-amber-900">
              {proposta.avisos.map((a) => (
                <p key={a}>• {a}</p>
              ))}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}

// Barra de convergência: alvo do programa (marcador) × medido pelo motor.
function ConvergeBar({ a }: { a: ItemFidelidadeArea }) {
  const alvo = a.alvo_pct ?? 0;
  const medido = a.medido_pct ?? 0;
  const cor =
    a.status === "atendido"
      ? "bg-emerald-500"
      : a.status === "degradado"
      ? "bg-amber-500"
      : "bg-indigo-500";
  const esc = (v: number) => `${Math.min(Math.round(v * 100), 100)}%`;
  return (
    <div className="text-sm">
      <div className="flex items-center justify-between text-slate-700">
        <span className="capitalize">{a.item}</span>
        <span className="tabular-nums text-slate-500">
          {(medido * 100).toLocaleString("pt-BR", { maximumFractionDigits: 1 })}% medido ·
          alvo {(alvo * 100).toLocaleString("pt-BR", { maximumFractionDigits: 1 })}%
        </span>
      </div>
      <div className="relative mt-1 h-3 overflow-hidden rounded bg-slate-100">
        <div className={`h-full ${cor}`} style={{ width: esc(medido) }} />
        {/* marcador do alvo do programa */}
        <div
          className="absolute top-0 h-full w-0.5 bg-slate-900"
          style={{ left: esc(alvo) }}
          title="alvo do programa"
        />
      </div>
      {a.leitura && <p className="mt-1 text-xs text-slate-500">{a.leitura}</p>}
    </div>
  );
}

function Kpi({ rotulo, valor }: { rotulo: string; valor: string }) {
  return (
    <div className="rounded-lg bg-slate-50 px-3 py-2">
      <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">
        {rotulo}
      </p>
      <p className="text-base font-bold tabular-nums text-slate-900">{valor}</p>
    </div>
  );
}
