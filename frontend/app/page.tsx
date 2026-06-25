"use client";

import { useState } from "react";
import { UploadKmz } from "@/components/UploadKmz";
import { RequireAuth } from "@/components/auth/RequireAuth";
import { MinhasAnalises } from "@/components/cliente/MinhasAnalises";
import { salvarAnalise, atualizarAnalise } from "@/lib/salvas";
import { BadgeCobertura } from "@/components/BadgeCobertura";
import { TopBar } from "@/components/shell/TopBar";
import { Sidebar } from "@/components/shell/Sidebar";
import { SECOES, type Secao } from "@/components/shell/secoes";
import { KpiRow } from "@/components/dashboard/KpiRow";
import { MapHero } from "@/components/dashboard/MapHero";
import { VisaoGeral } from "@/components/dashboard/VisaoGeral";
import { CardAproveitamento } from "@/components/cards/CardAproveitamento";
import { CardUrbanismo } from "@/components/cards/CardUrbanismo";
import { CardPerfilLuos } from "@/components/cards/CardPerfilLuos";
import { CardAmbiental } from "@/components/cards/CardAmbiental";
import { CardVegetacao } from "@/components/cards/CardVegetacao";
import { CardAreasUmidas } from "@/components/cards/CardAreasUmidas";
import { CardDeclividade } from "@/components/cards/CardDeclividade";
import { CardJuridico } from "@/components/cards/CardJuridico";
import { CardConformidade } from "@/components/cards/CardConformidade";
import { CardFinanceira } from "@/components/cards/CardFinanceira";
import { CardEconomica } from "@/components/cards/CardEconomica";
import { CardLocalizacao } from "@/components/cards/CardLocalizacao";
import { IconMap } from "@/components/Icons";
import { gerarLaudo } from "@/lib/api";
import type {
  Ambiental,
  Analise,
  Aproveitamento,
  ChaveOverlay,
  Declividade,
  Economica,
  Financeira,
  JuridicoDocumental,
  Localizacao,
  PerfilMunicipal,
  Vegetacao,
} from "@/lib/api";

type Overlays = Partial<Record<ChaveOverlay, GeoJSON.Geometry>>;

export default function Home() {
  const [analise, setAnalise] = useState<Analise | null>(null);
  const [secao, setSecao] = useState<Secao>("visao");

  // Overlays por origem (cada card alimenta o seu); o mapa-herói mostra a união.
  const [overlaysAmb, setOverlaysAmb] = useState<Overlays>({});
  const [overlaysVerde, setOverlaysVerde] = useState<Overlays>({});
  const [overlaysUmidas, setOverlaysUmidas] = useState<Overlays>({});
  const [overlaysDecliv, setOverlaysDecliv] = useState<Overlays>({});
  const [ocultos, setOcultos] = useState<Set<ChaveOverlay>>(new Set());

  // Dados consolidados para KPIs / visão geral (cada card reporta via onData).
  const [perfil, setPerfil] = useState<PerfilMunicipal | null>(null);
  const [dadosAmb, setDadosAmb] = useState<Ambiental | null>(null);
  const [dadosVerde, setDadosVerde] = useState<Vegetacao | null>(null);
  const [dadosDecliv, setDadosDecliv] = useState<Declividade | null>(null);
  const [dadosAprov, setDadosAprov] = useState<Aproveitamento | null>(null);
  const [dadosJuridico, setDadosJuridico] = useState<JuridicoDocumental | null>(null);
  const [dadosFinanceira, setDadosFinanceira] = useState<Financeira | null>(null);
  const [dadosEconomica, setDadosEconomica] = useState<Economica | null>(null);
  const [dadosLocalizacao, setDadosLocalizacao] = useState<Localizacao | null>(null);

  // "Analisar tudo": incrementa um sinal que cada card observa para disparar a análise.
  const [sinal, setSinal] = useState(0);
  const [gerandoLaudo, setGerandoLaudo] = useState(false);
  // Fase 12.2 — "Minhas análises": id da análise salva carregada (PUT vs POST) + salvando.
  const [salvaId, setSalvaId] = useState<string | null>(null);
  const [salvando, setSalvando] = useState(false);
  const [recarregarSalvas, setRecarregarSalvas] = useState(0);
  // #3 — progresso por seção: cada card reporta "analisando"/"ok"/"erro"; o botão e a sidebar leem.
  const [statusSec, setStatusSec] = useState<Record<string, "analisando" | "ok" | "erro">>({});
  const SECOES_ANALISE = [
    "ambiental", "verde", "declividade", "aproveitamento",
    "juridico", "financeira", "localizacao",
  ] as const;
  const marcar = (sec: string) => (st: "analisando" | "ok" | "erro") =>
    setStatusSec((m) => ({ ...m, [sec]: st }));
  const analisandoTudo = Object.values(statusSec).some((s) => s === "analisando");
  function analisarTudo() {
    setStatusSec(Object.fromEntries(SECOES_ANALISE.map((s) => [s, "analisando"])));
    setSinal((s) => s + 1);
    setTimeout(() => setStatusSec((m) => Object.fromEntries(
      Object.entries(m).map(([k, v]) => [k, v === "analisando" ? "ok" : v]))), 60000);
  }

  const overlays: Overlays = { ...overlaysAmb, ...overlaysVerde, ...overlaysUmidas, ...overlaysDecliv };

  // Fase 7 — laudo PDF: repassa os JSONs que os cards já receberam (front não recalcula).
  async function onLaudo() {
    if (!analise) return;
    setGerandoLaudo(true);
    try {
      const dims = {
        aproveitamento: dadosAprov,
        ambiental: dadosAmb,
        vegetacao: dadosVerde,
        declividade: dadosDecliv,
        juridico: dadosJuridico,
        financeira: dadosFinanceira,
        economica: dadosEconomica,
        localizacao: dadosLocalizacao,
      };
      const blob = await gerarLaudo(analise.analise_id, dims);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `laudo_${analise.analise_id.slice(0, 8)}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (e) {
      alert(e instanceof Error ? e.message : "Falha ao gerar o laudo.");
    } finally {
      setGerandoLaudo(false);
    }
  }

  // Snapshot dos resultados que os cards já receberam (o backend só guarda JSON).
  function snapshotResultados() {
    return {
      aproveitamento: dadosAprov,
      ambiental: dadosAmb,
      vegetacao: dadosVerde,
      declividade: dadosDecliv,
      juridico: dadosJuridico,
      financeira: dadosFinanceira,
      economica: dadosEconomica,
      localizacao: dadosLocalizacao,
    } as Record<string, unknown>;
  }

  // Fase 12.2 — salvar a análise corrente (POST) ou atualizar a carregada (PUT).
  async function onSalvar() {
    if (!analise) return;
    const padrao =
      analise.jurisdicao.municipio ?? `Análise ${new Date().toLocaleDateString("pt-BR")}`;
    const titulo = window.prompt("Título da análise:", padrao);
    if (titulo === null) return; // cancelou
    setSalvando(true);
    try {
      const payload = {
        titulo: titulo.trim() || padrao,
        gleba_geojson: analise.geometria.geojson,
        cidade: analise.jurisdicao.municipio,
        uf: analise.jurisdicao.uf,
        area_ha: analise.geometria.area_ha,
        resultados: snapshotResultados(),
      };
      const salva = salvaId
        ? await atualizarAnalise(salvaId, payload)
        : await salvarAnalise(payload);
      setSalvaId(salva.id);
      setRecarregarSalvas((n) => n + 1);
      alert(salvaId ? "Análise atualizada." : "Análise salva em “Minhas análises”.");
    } catch (e) {
      alert(e instanceof Error ? e.message : "Falha ao salvar a análise.");
    } finally {
      setSalvando(false);
    }
  }

  // Carrega uma análise salva (reidratada no backend) e a recoloca na tela.
  function onCarregarSalva(a: Analise, idSalva: string) {
    onAnalise(a);
    setSalvaId(idSalva);
  }

  function onAnalise(a: Analise | null) {
    setAnalise(a);
    setSalvaId(null);
    setSecao("visao");
    setOverlaysAmb({});
    setOverlaysVerde({});
    setOverlaysUmidas({});
    setOverlaysDecliv({});
    setOcultos(new Set());
    setPerfil(null);
    setDadosAmb(null);
    setDadosVerde(null);
    setDadosDecliv(null);
    setDadosAprov(null);
    setDadosJuridico(null);
    setDadosFinanceira(null);
    setDadosEconomica(null);
    setDadosLocalizacao(null);
    setSinal(0);
    setStatusSec({});
  }

  function toggleOculto(k: ChaveOverlay) {
    setOcultos((prev) => {
      const next = new Set(prev);
      next.has(k) ? next.delete(k) : next.add(k);
      return next;
    });
  }

  const nAlertas =
    dadosAmb?.alertas.filter((a) => a.severidade === "ALERTA").length ?? 0;

  return (
    <RequireAuth>
    <div className="min-h-screen">
      <TopBar
        analise={analise}
        onNova={() => onAnalise(null)}
        onAnalisarTudo={analisarTudo}
        analisando={analisandoTudo}
        onLaudo={onLaudo}
        gerandoLaudo={gerandoLaudo}
        onSalvar={onSalvar}
        salvando={salvando}
        jaSalva={salvaId !== null}
      />

      {!analise ? (
        <UploadHero onAnalise={onAnalise} onCarregar={onCarregarSalva} recarregar={recarregarSalvas} />
      ) : (
        <div className="flex">
          <Sidebar
            secao={secao}
            onSecao={setSecao}
            alertas={nAlertas}
            perfilConfirmado={perfil?.status === "confirmado"}
            statusSec={statusSec}
          />

          <main className="mx-auto w-full max-w-6xl space-y-5 p-4 sm:p-5">
            {analise.agrupamento && (
              <div className="rounded-xl border border-indigo-200 bg-indigo-50 p-3 text-sm text-indigo-900">
                <p className="font-semibold">
                  Projeto unificado — {analise.agrupamento.n_glebas} glebas contíguas
                </p>
                <p className="text-indigo-800">
                  {analise.agrupamento.proveniencia}. Área da união:{" "}
                  {analise.geometria.area_ha.toLocaleString("pt-BR")} ha (sem dupla
                  contagem). Arquivos: {analise.agrupamento.arquivos.join(", ")}.
                </p>
              </div>
            )}
            <KpiRow
              analise={analise}
              aprov={dadosAprov}
              amb={dadosAmb}
              verde={dadosVerde}
              decliv={dadosDecliv}
              juridico={dadosJuridico}
            />

            <MapHero
              analise={analise}
              overlays={overlays}
              ocultos={ocultos}
              onToggle={toggleOculto}
              badge={
                <BadgeCobertura
                  jurisdicao={analise.jurisdicao}
                  analiseId={analise.analise_id}
                  onJurisdicao={(j) =>
                    setAnalise((prev) => (prev ? { ...prev, jurisdicao: j } : prev))
                  }
                />
              }
            />

            {/* Navegação por seção no mobile (a sidebar cobre o desktop) */}
            <div className="-mx-4 flex gap-1 overflow-x-auto px-4 md:hidden">
              {SECOES.map(({ id, rotulo }) => (
                <button
                  key={id}
                  type="button"
                  onClick={() => setSecao(id)}
                  className={`shrink-0 rounded-lg px-3 py-1.5 text-sm font-medium ${
                    secao === id
                      ? "bg-slate-900 text-white"
                      : "bg-white text-slate-600"
                  }`}
                >
                  {rotulo}
                </button>
              ))}
            </div>

            {/* Painéis: todos montados (estado preservado); só o ativo é exibido. */}
            <div className={secao === "visao" ? "" : "hidden"}>
              <VisaoGeral
                analise={analise}
                amb={dadosAmb}
                verde={dadosVerde}
                decliv={dadosDecliv}
                aprov={dadosAprov}
                onIr={setSecao}
              />
            </div>
            <div className={secao === "ambiental" ? "space-y-4" : "hidden"}>
              <CardAmbiental
                analiseId={analise.analise_id}
                onOverlays={setOverlaysAmb}
                onData={(d) => { setDadosAmb(d); marcar("ambiental")("ok"); }}
                sinal={sinal}
              />
              <CardAreasUmidas
                analiseId={analise.analise_id}
                onOverlaysUmidas={setOverlaysUmidas}
                sinal={sinal}
              />
            </div>
            <div className={secao === "verde" ? "" : "hidden"}>
              <CardVegetacao
                analiseId={analise.analise_id}
                onOverlaysVerde={setOverlaysVerde}
                onData={(d) => { setDadosVerde(d); marcar("verde")("ok"); }}
                sinal={sinal}
              />
            </div>
            <div className={secao === "declividade" ? "" : "hidden"}>
              <CardDeclividade
                analiseId={analise.analise_id}
                onOverlaysDecliv={setOverlaysDecliv}
                onData={(d) => { setDadosDecliv(d); marcar("declividade")("ok"); }}
                sinal={sinal}
              />
            </div>
            <div className={secao === "aproveitamento" ? "" : "hidden"}>
              <CardAproveitamento
                analiseId={analise.analise_id}
                perfil={perfil}
                onData={(d) => { setDadosAprov(d); marcar("aproveitamento")("ok"); }}
                sinal={sinal}
              />
            </div>
            <div className={secao === "urbanismo" ? "" : "hidden"}>
              <CardUrbanismo
                analiseId={analise.analise_id}
                glebaGeojson={analise.geometria.geojson}
                perfil={perfil}
                declividade={dadosDecliv}
              />
            </div>
            <div className={secao === "conformidade" ? "" : "hidden"}>
              <CardConformidade
                analiseId={analise.analise_id}
                perfil={perfil}
                sinal={sinal}
              />
            </div>
            <div className={secao === "juridico" ? "" : "hidden"}>
              <CardJuridico
                analiseId={analise.analise_id}
                onData={(d) => { setDadosJuridico(d); marcar("juridico")("ok"); }}
                sinal={sinal}
              />
            </div>
            <div className={secao === "financeira" ? "" : "hidden"}>
              <CardFinanceira
                analiseId={analise.analise_id}
                aprov={dadosAprov}
                onData={(d) => { setDadosFinanceira(d); marcar("financeira")("ok"); }}
                sinal={sinal}
                econ={dadosEconomica}
              />
            </div>
            <div className={secao === "economica" ? "" : "hidden"}>
              <CardEconomica
                analiseId={analise.analise_id}
                onData={setDadosEconomica}
              />
            </div>
            <div className={secao === "localizacao" ? "" : "hidden"}>
              <CardLocalizacao
                analiseId={analise.analise_id}
                onData={(d) => { setDadosLocalizacao(d); marcar("localizacao")("ok"); }}
                sinal={sinal}
              />
            </div>
            <div className={secao === "luos" ? "" : "hidden"}>
              <CardPerfilLuos
                codIbge={analise.jurisdicao.cod_ibge}
                municipio={analise.jurisdicao.municipio}
                uf={analise.jurisdicao.uf}
                onConfirmado={setPerfil}
              />
            </div>
          </main>
        </div>
      )}
    </div>
    </RequireAuth>
  );
}

function UploadHero({
  onAnalise,
  onCarregar,
  recarregar,
}: {
  onAnalise: (a: Analise) => void;
  onCarregar: (a: Analise, salvaId: string) => void;
  recarregar: number;
}) {
  return (
    <main className="mx-auto grid max-w-3xl gap-8 px-4 py-16 sm:py-24">
      <div className="w-full rounded-2xl border border-slate-200 bg-white p-8 text-center shadow-sm">
        <div className="mx-auto grid h-14 w-14 place-items-center rounded-2xl bg-gradient-to-br from-indigo-600 to-violet-600 text-white shadow-sm">
          <IconMap width={28} height={28} />
        </div>
        <h1 className="mt-5 text-2xl font-bold tracking-tight">
          Pré-Viabilidade de Loteamento
        </h1>
        <p className="mx-auto mt-2 max-w-md text-sm text-slate-500">
          Envie o KMZ da gleba para uma triagem determinística: geometria, ambiental,
          área verde, declividade e aproveitamento — cada número com proveniência. Não
          decide aprovação municipal.
        </p>
        <div className="mt-6 flex justify-center">
          <UploadKmz onAnalise={onAnalise} />
        </div>
      </div>

      <section className="w-full">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">
          Minhas análises
        </h2>
        <MinhasAnalises onCarregar={onCarregar} recarregar={recarregar} />
      </section>
    </main>
  );
}
