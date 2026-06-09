"use client";

import { useState } from "react";
import { UploadKmz } from "@/components/UploadKmz";
import { BadgeCobertura } from "@/components/BadgeCobertura";
import { TopBar } from "@/components/shell/TopBar";
import { Sidebar } from "@/components/shell/Sidebar";
import { SECOES, type Secao } from "@/components/shell/secoes";
import { KpiRow } from "@/components/dashboard/KpiRow";
import { MapHero } from "@/components/dashboard/MapHero";
import { VisaoGeral } from "@/components/dashboard/VisaoGeral";
import { CardAproveitamento } from "@/components/cards/CardAproveitamento";
import { CardPerfilLuos } from "@/components/cards/CardPerfilLuos";
import { CardAmbiental } from "@/components/cards/CardAmbiental";
import { CardVegetacao } from "@/components/cards/CardVegetacao";
import { CardDeclividade } from "@/components/cards/CardDeclividade";
import { CardJuridico } from "@/components/cards/CardJuridico";
import { IconMap } from "@/components/Icons";
import type {
  Ambiental,
  Analise,
  Aproveitamento,
  ChaveOverlay,
  Declividade,
  JuridicoDocumental,
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
  const [overlaysDecliv, setOverlaysDecliv] = useState<Overlays>({});
  const [ocultos, setOcultos] = useState<Set<ChaveOverlay>>(new Set());

  // Dados consolidados para KPIs / visão geral (cada card reporta via onData).
  const [perfil, setPerfil] = useState<PerfilMunicipal | null>(null);
  const [dadosAmb, setDadosAmb] = useState<Ambiental | null>(null);
  const [dadosVerde, setDadosVerde] = useState<Vegetacao | null>(null);
  const [dadosDecliv, setDadosDecliv] = useState<Declividade | null>(null);
  const [dadosAprov, setDadosAprov] = useState<Aproveitamento | null>(null);
  const [dadosJuridico, setDadosJuridico] = useState<JuridicoDocumental | null>(null);

  // "Analisar tudo": incrementa um sinal que cada card observa para disparar a análise.
  const [sinal, setSinal] = useState(0);

  const overlays: Overlays = { ...overlaysAmb, ...overlaysVerde, ...overlaysDecliv };

  function onAnalise(a: Analise | null) {
    setAnalise(a);
    setSecao("visao");
    setOverlaysAmb({});
    setOverlaysVerde({});
    setOverlaysDecliv({});
    setOcultos(new Set());
    setPerfil(null);
    setDadosAmb(null);
    setDadosVerde(null);
    setDadosDecliv(null);
    setDadosAprov(null);
    setDadosJuridico(null);
    setSinal(0);
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
    <div className="min-h-screen">
      <TopBar
        analise={analise}
        onNova={() => onAnalise(null)}
        onAnalisarTudo={() => setSinal((s) => s + 1)}
      />

      {!analise ? (
        <UploadHero onAnalise={onAnalise} />
      ) : (
        <div className="flex">
          <Sidebar
            secao={secao}
            onSecao={setSecao}
            alertas={nAlertas}
            perfilConfirmado={perfil?.status === "confirmado"}
          />

          <main className="mx-auto w-full max-w-6xl space-y-5 p-4 sm:p-5">
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
            <div className={secao === "ambiental" ? "" : "hidden"}>
              <CardAmbiental
                analiseId={analise.analise_id}
                onOverlays={setOverlaysAmb}
                onData={setDadosAmb}
                sinal={sinal}
              />
            </div>
            <div className={secao === "verde" ? "" : "hidden"}>
              <CardVegetacao
                analiseId={analise.analise_id}
                onOverlaysVerde={setOverlaysVerde}
                onData={setDadosVerde}
                sinal={sinal}
              />
            </div>
            <div className={secao === "declividade" ? "" : "hidden"}>
              <CardDeclividade
                analiseId={analise.analise_id}
                onOverlaysDecliv={setOverlaysDecliv}
                onData={setDadosDecliv}
                sinal={sinal}
              />
            </div>
            <div className={secao === "aproveitamento" ? "" : "hidden"}>
              <CardAproveitamento
                analiseId={analise.analise_id}
                perfil={perfil}
                onData={setDadosAprov}
                sinal={sinal}
              />
            </div>
            <div className={secao === "juridico" ? "" : "hidden"}>
              <CardJuridico
                analiseId={analise.analise_id}
                onData={setDadosJuridico}
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
  );
}

function UploadHero({ onAnalise }: { onAnalise: (a: Analise) => void }) {
  return (
    <main className="mx-auto grid max-w-3xl place-items-center px-4 py-16 sm:py-24">
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
    </main>
  );
}
