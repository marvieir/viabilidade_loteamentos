"use client";

import { useEffect, useState } from "react";
import { StatusChip } from "@/components/ui/status";
import { Notas } from "@/components/ui/notas";
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
  listarUrbanismo,
  materializarVariante,
  valorPosicionalUrbanismo,
  type ChaveOverlay,
  type ConformidadeLegal,
  type Declividade,
  type ItemFidelidadeArea,
  type PerfilMunicipal,
  type PropostaUrbanistica,
  type PublicoAlvo,
  type TipoLoteamento,
  type ValorPosicional,
} from "@/lib/api";
import {
  CORES_OVERLAY,
  CORES_QUINTIL,
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

// Fase U1 — rótulos pt-BR dos fatores do score v2 (chaves vêm do backend).
const ROTULO_FATOR: Record<string, string> = {
  verde: "verde",
  agua: "água",
  lazer: "lazer",
  culdesac: "bolsão (cul-de-sac)",
  privacidade: "privacidade",
  orientacao: "orientação solar",
  sossego: "sossego",
};

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
  declividade,
}: {
  analiseId: string;
  glebaGeojson: GeoJSON.Polygon;
  perfil?: PerfilMunicipal | null;
  onData?: (p: PropostaUrbanistica | null) => void;
  declividade?: Declividade | null; // Fase 11.12 — vocação do terreno (topografia → perfil sugerido)
}) {
  const zonas = perfil?.zonas.map((z) => z.codigo) ?? [];
  const [tipo, setTipo] = useState<TipoLoteamento>("aberto");
  const [publico, setPublico] = useState<PublicoAlvo>("media");
  const [zona, setZona] = useState<string>("");
  const [loteMax, setLoteMax] = useState<string>(""); // Fase 11.8 — teto de lote (m²); vazio = perfil
  const [criarLago, setCriarLago] = useState(false); // Fase U3 — lago no ponto baixo do DEM
  const [proposta, setProposta] = useState<PropostaUrbanistica | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(false);
  const [mapaExpandido, setMapaExpandido] = useState(false); // Fase 9.6 — mapa maior
  // Acesso marcado pelo operador no mapa ([lat, lng]) — âncora DEFINITIVA do pórtico
  // (prioridade sobre o OSM; zona rural tem via mal mapeada). Persiste entre regenerações.
  const [acessoPonto, setAcessoPonto] = useState<[number, number] | null>(null);
  const [marcandoAcesso, setMarcandoAcesso] = useState(false);
  // Fase U4 — troca de variante (materializada no backend, sem IA e fora do cap).
  const [varianteCarregando, setVarianteCarregando] = useState<string | null>(null);
  // Fase U1 — valor posicional: preço médio do OPERADOR × multiplicador do score v2 (backend).
  const [valorBase, setValorBase] = useState<"por_lote" | "por_m2">("por_lote");
  const [valorPreco, setValorPreco] = useState<string>("");
  const [valor, setValor] = useState<ValorPosicional | null>(null);
  const [valorErro, setValorErro] = useState<string | null>(null);
  const [valorCarregando, setValorCarregando] = useState(false);

  useEffect(() => {
    if (!zona && zonas.length > 0) setZona(zonas[0]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [perfil]);

  // Ao abrir a análise, recarrega o ÚLTIMO layout já gerado (snapshot salvo no backend) —
  // SEM chamar a IA. Só o botão "Regenerar" consome token. Evita refazer à toa (economia real).
  useEffect(() => {
    let vivo = true;
    (async () => {
      try {
        const lista = await listarUrbanismo(analiseId);
        if (vivo && lista.length > 0) {
          const ultima = lista[lista.length - 1];
          setProposta(ultima);
          onData?.(ultima);
        }
      } catch {
        /* sem snapshot salvo → começa vazio, sem erro */
      }
    })();
    return () => {
      vivo = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [analiseId]);

  async function gerar() {
    setCarregando(true);
    setErro(null);
    try {
      const loteMaxNum = loteMax.trim() ? Number(loteMax) : null;
      const p = await proporUrbanismo(
        analiseId, tipo, publico, zona || null, undefined,
        loteMaxNum && loteMaxNum > 0 ? loteMaxNum : null,
        acessoPonto ? [acessoPonto[1], acessoPonto[0]] : null,
        criarLago
      );
      setProposta(p);
      onData?.(p);
      setValor(null); // valor posicional era da proposta anterior — recalcular sob demanda
      setValorErro(null);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Falha ao gerar o estudo de massa.");
    } finally {
      setCarregando(false);
    }
  }

  // Fase U4 — abre uma variante alternativa: o backend REMATERIALIZA a geometria a partir do
  // programa salvo (zero IA, fora do cap) e devolve a proposta completa; o front só troca.
  async function abrirVariante(varianteId: string) {
    setVarianteCarregando(varianteId);
    setErro(null);
    try {
      const p = await materializarVariante(analiseId, varianteId);
      setProposta(p);
      onData?.(p);
      setValor(null);
      setValorErro(null);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Falha ao abrir a variante.");
    } finally {
      setVarianteCarregando(null);
    }
  }

  // Fase U1 — cruza o preço médio do operador com o multiplicador posicional salvo na
  // proposta (endpoint /urbanismo/valor: sem LLM, fora do cap). O front só exibe o retorno.
  async function calcularValor() {
    const preco = Number(valorPreco.replace(",", "."));
    if (!preco || preco <= 0) {
      setValorErro("Informe um preço médio maior que zero.");
      return;
    }
    setValorCarregando(true);
    setValorErro(null);
    try {
      const v = await valorPosicionalUrbanismo(
        analiseId,
        valorBase === "por_lote" ? { preco_lote_medio: preco } : { preco_m2_medio: preco },
        proposta?.versao ?? null
      );
      setValor(v);
    } catch (e) {
      setValorErro(e instanceof Error ? e.message : "Falha ao calcular o valor posicional.");
    } finally {
      setValorCarregando(false);
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
    if (g.portico) overlays.urb_portico = g.portico; // Fase 11.3 — marcador da entrada/portaria
    if (g.agua) overlays.urb_agua = g.agua; // U3 — lago/espelho d'água criado
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

  // Fase 11.12 — VOCAÇÃO do terreno pela topografia: a app sugere o perfil (e avisa se o escolhido
  // não combina). Heurística sobre a declividade já calculada (média + fração ≥30%).
  const decMedia = declividade?.declividade_media_pct ?? null;
  const ved30 = declividade?.flag_vedacao?.pct_da_gleba ?? 0;
  let vocacao: { perfil: PublicoAlvo; texto: string } | null = null;
  if (decMedia != null) {
    const m = decMedia.toFixed(0);
    const v = ved30 >= 0.05 ? `, ${(ved30 * 100).toFixed(0)}% em ≥30%` : "";
    if (decMedia >= 15 || ved30 >= 0.12) {
      vocacao = {
        perfil: "alta",
        texto: `Terreno de serra (declividade média ${m}%${v}) → vocação ALTA RENDA: lotes amplos, baixa densidade e valor de paisagem. Baixa renda densa renderia pouco aqui.`,
      };
    } else if (decMedia < 8 && ved30 < 0.05) {
      vocacao = {
        perfil: "baixa",
        texto: `Terreno plano (declividade média ${m}%) → viável para todos os perfis; baixa/média renda densa rende bem.`,
      };
    } else {
      vocacao = {
        perfil: "media",
        texto: `Relevo moderado (declividade média ${m}%${v}) → vocação média/alta renda.`,
      };
    }
  }
  const vocacaoConflita =
    vocacao != null && vocacao.perfil !== publico &&
    !(vocacao.perfil === "media" && publico === "alta");

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex flex-wrap items-center gap-2">
          Urbanismo — estudo de massa
          <span className="rounded-full bg-amber-200 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-amber-900">
            Esquemático
          </span>
          {proposta ? (
            <StatusChip className="ml-auto" estado="ok" rotulo={`gerado · v${proposta.versao}`} />
          ) : (
            <StatusChip className="ml-auto" estado="pendente" />
          )}
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
          <label className="text-sm text-slate-600">Lote máx. (m²)</label>
          <input
            type="number"
            min={0}
            step={50}
            value={loteMax}
            onChange={(e) => setLoteMax(e.target.value)}
            placeholder="perfil"
            title="Tamanho máximo de lote recomendado (m²). Vazio = padrão do perfil. Nunca abaixo do piso legal."
            className="w-24 rounded-lg border border-slate-200 px-2 py-2 text-sm"
          />
          <label
            className="flex items-center gap-1.5 text-sm text-slate-600"
            title="Sintetiza um lago paisagístico no ponto baixo do terreno (DEM) com orla-parque — amenidade valorizadora (pesquisa §1). Sem DEM, degrada com aviso."
          >
            <input
              type="checkbox"
              checked={criarLago}
              onChange={(e) => setCriarLago(e.target.checked)}
              className="h-4 w-4 rounded border-slate-300"
            />
            Criar lago 💧
          </label>
          <Button onClick={gerar} disabled={carregando}>
            {carregando
              ? "Gerando…"
              : proposta
              ? "Regenerar (consome IA)"
              : "Gerar estudo de massa (IA)"}
          </Button>
        </div>
        {proposta && !carregando && (
          <p className="-mt-1 text-[11px] text-slate-400">
            Layout carregado do último salvo — não consumiu IA. Clique em “Regenerar” só se quiser
            um novo traçado (aí sim consome).
          </p>
        )}
        {acessoPonto && (
          <p className="-mt-1 text-[11px] font-medium text-emerald-700">
            📍 Acesso marcado no mapa — na próxima geração o pórtico será ancorado nesse ponto
            (independe do OSM).
          </p>
        )}

        {/* Fase 11.12 — VOCAÇÃO do terreno: a app sugere o perfil pela topografia e avisa conflito. */}
        {vocacao && (
          <p
            className={`rounded-lg p-2.5 text-sm ${
              vocacaoConflita
                ? "bg-amber-50 text-amber-800"
                : "bg-sky-50 text-sky-800"
            }`}
          >
            {vocacaoConflita ? "⚠️ " : "🧭 "}
            {vocacao.texto}
            {vocacaoConflita && (
              <>
                {" "}
                Você selecionou <strong>{publico === "baixa" ? "baixa renda" : publico === "media" ? "média renda" : "alta renda"}</strong>
                {" "}— considere ajustar o público-alvo à vocação do terreno.
              </>
            )}
          </p>
        )}

        {/* Fase 11.11 — VALIDAÇÃO: o app corrige o usuário. Lote máx. perto do piso da zona =
            janela apertada → sobra. Avisa (não bloqueia). O piso vem do estudo já gerado. */}
        {(() => {
          const piso = proposta?.diretrizes?.piso_lote_efetivo_m2;
          const lm = Number(loteMax);
          if (!loteMax.trim() || !piso || !(lm > 0) || lm >= piso * 1.4) return null;
          const rec = Math.ceil((piso * 1.5) / 50) * 50;
          return (
            <p className="rounded-lg bg-amber-50 p-2.5 text-sm text-amber-800">
              ⚠️ Faixa de lote apertada [{piso.toLocaleString("pt-BR")}–
              {lm.toLocaleString("pt-BR")} m²] — perto do piso legal da zona, tende a gerar muita{" "}
              <strong>sobra geométrica</strong>. Recomendado: lote máx. ≥{" "}
              <strong>{rec.toLocaleString("pt-BR")} m²</strong> (ou deixe vazio para o padrão seguro).
            </p>
          );
        })()}

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
                <div className="flex items-center gap-1.5">
                  <button
                    type="button"
                    onClick={() => {
                      if (acessoPonto && !marcandoAcesso) {
                        setAcessoPonto(null); // limpar
                      } else {
                        setMarcandoAcesso((v) => !v);
                      }
                    }}
                    className={`rounded-md border px-2 py-1 text-[11px] transition-colors ${
                      marcandoAcesso
                        ? "border-pink-300 bg-pink-50 text-pink-700"
                        : acessoPonto
                          ? "border-emerald-300 bg-emerald-50 text-emerald-700 hover:bg-emerald-100"
                          : "border-slate-200 bg-white text-slate-600 hover:bg-slate-100"
                    }`}
                    title="Marque no mapa onde é o acesso real do terreno — o pórtico será ancorado nele (prioridade sobre o OSM)."
                  >
                    {marcandoAcesso
                      ? "Clique no mapa onde é o acesso…"
                      : acessoPonto
                        ? "✓ Acesso marcado — limpar"
                        : "📍 Marcar acesso"}
                  </button>
                  <button
                    type="button"
                    onClick={() => setMapaExpandido((v) => !v)}
                    className="rounded-md border border-slate-200 bg-white px-2 py-1 text-[11px] text-slate-600 hover:bg-slate-100"
                  >
                    {mapaExpandido ? "Recolher mapa" : "Expandir mapa"}
                  </button>
                </div>
              </div>
              <div className={`w-full ${mapaExpandido ? "h-[680px]" : "h-[440px]"}`}>
                <MapaLeaflet
                  geojson={glebaGeojson}
                  overlays={overlays}
                  lotesFeatures={lotesFeatures}
                  quadras={proposta?.geometria.quadras ?? null}
                  lazerFeatures={proposta?.geometria.sistema_lazer_features ?? null}
                  aoClicar={
                    marcandoAcesso
                      ? (p) => {
                          setAcessoPonto([p.lat, p.lng]);
                          setMarcandoAcesso(false);
                        }
                      : undefined
                  }
                  marcador={acessoPonto}
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
                    <span>Cor do lote = valorização relativa (quintis):</span>
                    {([1, 2, 3, 4, 5] as const).map((q) => (
                      <span key={q} className="inline-flex items-center gap-1">
                        <span
                          className="inline-block h-2.5 w-2.5 rounded-sm"
                          style={{ backgroundColor: CORES_QUINTIL[q] }}
                        />
                        {q === 1 ? "menos valorizados" : q === 5 ? "mais valorizados" : `Q${q}`}
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
                    {/* Fase 10 (Parte 3) — loteamento único: a travessia ligou as porções. */}
                    {proposta.geometria.viario_diagnostico.conexao?.loteamento_conexo &&
                      (proposta.geometria.viario_diagnostico.conexao?.porcoes_detectadas ?? 0) > 1 && (
                        <span className="inline-flex items-center gap-1">
                          <span className="inline-block h-2 w-2 rounded-full bg-indigo-600" />
                          Loteamento único — porções ligadas pela travessia
                          {proposta.geometria.viario_diagnostico.conexao?.travessia?.modelo === "diagonal_minimax" &&
                            " (via diagonal)"}
                          {typeof proposta.geometria.viario_diagnostico.conexao?.travessia?.greide_medido_pct === "number" &&
                            ` (greide ~${proposta.geometria.viario_diagnostico.conexao.travessia.greide_medido_pct}%${
                              proposta.geometria.viario_diagnostico.conexao.travessia.greide_indeterminado ? ", confirmar com topografia" : ""
                            })`}
                        </span>
                      )}
                    {/* Fase 10.3 — a via de conexão cruza a faixa ≥30% (veda LOTE, não via): exige laudo. */}
                    {proposta.geometria.viario_diagnostico.conexao?.travessia?.exigencia_geotecnica && (
                      <span className="inline-flex items-start gap-1 text-amber-700">
                        <span className="mt-1 inline-block h-2 w-2 shrink-0 rounded-full bg-amber-600" />
                        <span>
                          Via de conexão cruza declividade ≥30% em corte/aterro — exige projeto
                          geométrico e laudo geotécnico (art. 3º Lei 6.766). Nenhum lote na faixa
                          ≥30%; só a via a atravessa.
                        </span>
                      </span>
                    )}
                    {/* Fase 10 (Parte 4) — alto padrão: uma portaria, institucional na entrada. */}
                    {(proposta.geometria.viario_diagnostico.alto_padrao?.porticos ?? 0) > 0 && (
                      <span className="inline-flex items-center gap-1">
                        <span className="inline-block h-2 w-2 rounded-full bg-amber-700" />
                        {proposta.geometria.viario_diagnostico.alto_padrao?.porticos === 1
                          ? "Uma portaria/pórtico na entrada"
                          : `${proposta.geometria.viario_diagnostico.alto_padrao?.porticos} pórticos`}
                        {proposta.geometria.viario_diagnostico.alto_padrao?.institucional_na_entrada &&
                          " · institucional na entrada"}
                        {proposta.geometria.viario_diagnostico.alto_padrao?.arborizacao_viaria &&
                          " · arborização viária"}
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
                    {q.lamina_dagua && q.lamina_dagua.m2 > 0 && (
                      <LinhaArea
                        rotulo="Lâmina d'água (lago criado) 💧"
                        m2={q.lamina_dagua.m2_fmt}
                        pct={q.lamina_dagua.pct_fmt}
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

            {/* Fase U4 — VARIANTES do otimizador: K estratégias geradas com UMA proposta de IA;
                a função de valor escolheu; abrir alternativa não chama IA nem consome o cap. */}
            {(proposta.variantes ?? []).length > 1 && (
              <div className="rounded-xl border border-slate-200 p-4">
                <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Variantes do estudo (otimizador U4 — abrir alternativa não gasta gerações)
                </p>
                <div className="flex flex-wrap gap-2">
                  {(proposta.variantes ?? []).map((v) => {
                    const ativa = v.escolhida;
                    return (
                      <button
                        key={v.variante_id}
                        onClick={() => !v.escolhida && abrirVariante(v.variante_id)}
                        disabled={varianteCarregando !== null}
                        className={`rounded-lg border px-3 py-2 text-left text-xs transition ${
                          ativa
                            ? "border-indigo-300 bg-indigo-50 text-indigo-900"
                            : "border-slate-200 bg-white text-slate-700 hover:border-slate-300"
                        }`}
                        title={
                          v.escolhida
                            ? "variante escolhida pela função de valor"
                            : "abrir esta variante (geometria pura — sem custo de IA)"
                        }
                      >
                        <span className="font-semibold">
                          {varianteCarregando === v.variante_id ? "Abrindo… " : ""}
                          {v.rotulo}
                          {v.escolhida ? " ★" : ""}
                        </span>
                        <span className="mt-0.5 block text-[11px] text-slate-500">
                          {v.n_lotes} lotes · valor {v.valor_indice ?? "—"}
                          {v.score_medio != null ? ` · score ${v.score_medio}` : ""}
                        </span>
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Fase U2 — PROGRAMA DE LAZER: hub rotulado + praças de bolso + cobertura 400 m.
                Tudo medido pelo backend; o front só exibe (§2). */}
            {proposta.geometria.lazer_diagnostico &&
              (proposta.geometria.lazer_diagnostico.programa_hub?.length ||
                (proposta.geometria.lazer_diagnostico.n_pracas ?? 0) > 0) && (
                <div className="rounded-xl border border-slate-200 p-4">
                  <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Programa de lazer (U2 — hub + praças de bolso)
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {(proposta.geometria.lazer_diagnostico.programa_hub ?? []).map((a) => (
                      <span
                        key={a.rotulo}
                        className="rounded-full bg-teal-50 px-2 py-0.5 text-[11px] text-teal-800"
                        title="sub-parcela do hub (dimensão típica de mercado — verificar com urbanista)"
                      >
                        {a.rotulo}
                        {a.area_fmt ? ` · ${a.area_fmt} m²` : ""}
                      </span>
                    ))}
                    {(proposta.geometria.lazer_diagnostico.n_pracas ?? 0) > 0 && (
                      <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] text-emerald-800">
                        {proposta.geometria.lazer_diagnostico.n_pracas} praça(s) de bolso
                      </span>
                    )}
                    {proposta.geometria.lazer_diagnostico.cobertura_400m_fmt && (
                      <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] text-slate-700">
                        {proposta.geometria.lazer_diagnostico.cobertura_400m_fmt} dos lotes a
                        ≤400 m do lazer
                      </span>
                    )}
                  </div>
                  {((proposta.geometria.lazer_diagnostico.nao_coube ?? []).length > 0 ||
                    (proposta.geometria.lazer_diagnostico.amenidades_fora_do_hub ?? [])
                      .length > 0) && (
                    <ul className="mt-2 space-y-0.5 text-[11px] text-slate-500">
                      {(proposta.geometria.lazer_diagnostico.nao_coube ?? []).map((r) => (
                        <li key={r}>• não coube no hub: {r}</li>
                      ))}
                      {(proposta.geometria.lazer_diagnostico.amenidades_fora_do_hub ?? []).map(
                        (r) => (
                          <li key={r}>• {r}</li>
                        )
                      )}
                    </ul>
                  )}
                </div>
              )}

            {/* Heatmap de valorização — score v2 (U1): fatores rotulados + pesos do perfil */}
            {proposta.heatmap.score_medio != null && (
              <div className="rounded-xl border border-slate-200 p-4">
                <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Score de valor por lote — médio {proposta.heatmap.score_medio}
                  {proposta.heatmap.versao_score === 2 && proposta.heatmap.perfil
                    ? ` (pesos do perfil "${proposta.heatmap.perfil}")`
                    : " (qualidade relativa; o R$/m² por faixa é seu)"}
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
                {proposta.heatmap.versao_score === 2 && proposta.heatmap.pesos && (
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    {Object.entries(proposta.heatmap.pesos).map(([f, w]) => (
                      <span
                        key={f}
                        className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] text-slate-600"
                        title="peso do fator no score (perfil do público-alvo)"
                      >
                        {ROTULO_FATOR[f] ?? f} ×{w}
                      </span>
                    ))}
                    {(proposta.heatmap.fatores_ausentes ?? []).map((f) => (
                      <span
                        key={f}
                        className="rounded-full border border-dashed border-slate-300 px-2 py-0.5 text-[11px] text-slate-400"
                        title="fator sem camada neste layout — fora da média (não vale zero)"
                      >
                        {ROTULO_FATOR[f] ?? f}: ausente
                      </span>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Fase U1 — VALOR POSICIONAL: preço médio do operador × multiplicador (média 1,0).
                Todo número vem do backend (/urbanismo/valor); o front não calcula nada. */}
            {proposta.heatmap.versao_score === 2 && (
              <div className="rounded-xl border border-slate-200 p-4">
                <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Valor posicional (seu preço médio × posição do lote)
                </p>
                <div className="flex flex-wrap items-center gap-2">
                  <select
                    value={valorBase}
                    onChange={(e) => setValorBase(e.target.value as "por_lote" | "por_m2")}
                    className="h-9 rounded-lg border border-slate-300 bg-white px-2 text-sm"
                  >
                    <option value="por_lote">R$ por lote (médio)</option>
                    <option value="por_m2">R$ por m² (médio)</option>
                  </select>
                  <input
                    type="number"
                    min="0"
                    inputMode="decimal"
                    placeholder={valorBase === "por_lote" ? "ex.: 100000" : "ex.: 350"}
                    value={valorPreco}
                    onChange={(e) => setValorPreco(e.target.value)}
                    className="h-9 w-36 rounded-lg border border-slate-300 px-2 text-sm tabular-nums"
                  />
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={calcularValor}
                    disabled={valorCarregando}
                  >
                    {valorCarregando ? "Calculando…" : "Calcular valor"}
                  </Button>
                </div>
                {valorErro && <p className="mt-2 text-sm text-red-600">{valorErro}</p>}
                {valor && (
                  <div className="mt-3 space-y-2">
                    <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                      <div className="rounded-lg bg-slate-50 p-2">
                        <p className="text-[11px] text-slate-500">VGV posicional</p>
                        <p className="text-sm font-semibold tabular-nums text-slate-900">
                          {valor.vgv_fmt}
                        </p>
                      </div>
                      <div className="rounded-lg bg-slate-50 p-2">
                        <p className="text-[11px] text-slate-500">Preço médio</p>
                        <p className="text-sm font-semibold tabular-nums text-slate-900">
                          {valor.preco_medio_fmt}
                        </p>
                      </div>
                      {valor.lote_max && (
                        <div className="rounded-lg bg-emerald-50 p-2">
                          <p className="text-[11px] text-emerald-700">
                            Mais valorizado · {valor.lote_max.lote_id}
                          </p>
                          <p className="text-sm font-semibold tabular-nums text-emerald-900">
                            {valor.lote_max.preco_fmt}
                          </p>
                        </div>
                      )}
                      {valor.lote_min && (
                        <div className="rounded-lg bg-amber-50 p-2">
                          <p className="text-[11px] text-amber-700">
                            Menos valorizado · {valor.lote_min.lote_id}
                          </p>
                          <p className="text-sm font-semibold tabular-nums text-amber-900">
                            {valor.lote_min.preco_fmt}
                          </p>
                        </div>
                      )}
                    </div>
                    <p className="text-xs text-slate-500">{valor.proveniencia}</p>
                    <Notas itens={valor.avisos} />
                  </div>
                )}
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

            <Notas itens={proposta.avisos} />
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
