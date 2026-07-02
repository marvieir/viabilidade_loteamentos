"use client";

import { useEffect, useState } from "react";
import { StatusChip } from "@/components/ui/status";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { buscarLocalizacao, type Localizacao } from "@/lib/api";

/* Fase 6 — Localização: enriquecimento socioeconômico IBGE (INFORMATIVO, §1-A).
   O front SÓ renderiza o JSON do backend (§2): nenhum número é calculado/reformatado
   aqui — exibe os pares *_fmt, as razões UF/Brasil e as leituras prontas. Não decide
   viabilidade nem é análise de mercado. */

export function CardLocalizacao({
  analiseId,
  onData,
  sinal,
  inicial,
}: {
  analiseId: string;
  onData?: (d: Localizacao | null) => void;
  sinal?: number;
  inicial?: Localizacao | null; // snapshot salvo — reidrata sem reprocessar
}) {
  const [data, setData] = useState<Localizacao | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(false);

  async function carregar() {
    setCarregando(true);
    setErro(null);
    try {
      const r = await buscarLocalizacao(analiseId);
      setData(r);
      onData?.(r);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Falha ao carregar.");
    } finally {
      setCarregando(false);
    }
  }

  // Reidrata do snapshot salvo ("Abrir análise"): contexto anterior sem reprocessar.
  useEffect(() => {
    if (inicial && !data) {
      setData(inicial);
      onData?.(inicial);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [inicial]);

  useEffect(() => {
    if (sinal) carregar();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sinal]);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex flex-wrap items-center gap-2">
          <span>Localização</span>
          <StatusChip className="ml-auto" estado={data ? "ok" : "pendente"} />
        </CardTitle>
        <CardDescription>
          Contexto socioeconômico do município (IBGE — Censo 2022/2010, PIB dos Municípios;
          déficit da FJP quando disponível). Enriquecimento{" "}
          <span className="font-medium">informativo</span>: não entra em nenhum cálculo de
          viabilidade e não é análise de mercado. Cada número com fonte e ano.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <Button onClick={carregar} disabled={carregando}>
          {carregando ? "Carregando…" : "Carregar localização"}
        </Button>

        {erro && (
          <p className="rounded-lg bg-rose-50 p-3 text-sm text-rose-800">{erro}</p>
        )}

        {data && !data.avaliada && (
          <div className="rounded-lg bg-amber-50 p-3 text-xs text-amber-900">
            {data.avisos.map((a) => (
              <p key={a}>{a}</p>
            ))}
          </div>
        )}

        {data && data.avaliada && data.cobertura === "INDISPONIVEL" && (
          <div className="rounded-lg bg-amber-50 p-3 text-xs text-amber-900">
            {data.avisos.map((a) => (
              <p key={a}>{a}</p>
            ))}
          </div>
        )}

        {data && data.avaliada && data.cobertura !== "INDISPONIVEL" && (
          <>
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold text-slate-900">
                {data.municipio.nome}
                {data.municipio.uf ? `/${data.municipio.uf}` : ""}
              </span>
              <BadgeCobertura cobertura={data.cobertura} />
            </div>

            <BlocoPopulacao loc={data} />
            <BlocoRenda loc={data} />
            <BlocoHabitacao loc={data} />
            <BlocoFaixaEtaria loc={data} />

            <p className="text-xs text-slate-500">{data.proveniencia}</p>
            {data.avisos.map((a) => (
              <p key={a} className="text-xs text-slate-400">
                {a}
              </p>
            ))}
          </>
        )}
      </CardContent>
    </Card>
  );
}

function BadgeCobertura({ cobertura }: { cobertura: string }) {
  const cor =
    cobertura === "COMPLETA"
      ? "bg-emerald-50 text-emerald-700 border-emerald-200"
      : "bg-amber-50 text-amber-700 border-amber-200";
  const rotulo = cobertura === "COMPLETA" ? "4 indicadores" : "parcial";
  return (
    <span className={`rounded-full border px-2 py-0.5 text-xs font-medium ${cor}`}>
      {rotulo}
    </span>
  );
}

function Bloco({
  titulo,
  fonte,
  children,
  indisponivel,
  aviso,
}: {
  titulo: string;
  fonte?: string | null;
  children?: React.ReactNode;
  indisponivel?: boolean;
  aviso?: string | null;
}) {
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
      <div className="flex items-center justify-between gap-2">
        <p className="text-sm font-semibold text-slate-800">{titulo}</p>
        {fonte && (
          <span className="rounded bg-white px-1.5 py-0.5 text-[10px] text-slate-500">
            {fonte}
          </span>
        )}
      </div>
      {indisponivel ? (
        <p className="mt-1 text-xs text-slate-400">
          {aviso ?? "Indisponível na fonte para este município."}
        </p>
      ) : (
        <div className="mt-2">{children}</div>
      )}
    </div>
  );
}

function Metrica({ rotulo, valor }: { rotulo: string; valor: string }) {
  return (
    <div>
      <p className="text-xs text-slate-500">{rotulo}</p>
      <p className="text-base font-semibold text-slate-900">{valor}</p>
    </div>
  );
}

function BlocoPopulacao({ loc }: { loc: Localizacao }) {
  const p = loc.populacao;
  return (
    <Bloco titulo="População" fonte={p.fonte} indisponivel={!p.disponivel} aviso={p.aviso}>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <Metrica rotulo="Censo 2022" valor={p.censo_2022_fmt ?? "—"} />
        <Metrica rotulo="Densidade" valor={p.densidade_fmt ?? "—"} />
        <Metrica
          rotulo="Crescimento 2010→2022"
          valor={
            p.crescimento_total_fmt
              ? `${p.crescimento_total_fmt} (${p.crescimento_aa_fmt}/ano)`
              : "—"
          }
        />
      </div>
      {p.leitura && <p className="mt-2 text-xs text-slate-600">{p.leitura}</p>}
    </Bloco>
  );
}

function BlocoRenda({ loc }: { loc: Localizacao }) {
  const r = loc.renda;
  return (
    <Bloco titulo="Renda — PIB per capita" fonte={r.fonte} indisponivel={!r.disponivel} aviso={r.aviso}>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <Metrica rotulo={`PIB per capita${r.ano ? ` (${r.ano})` : ""}`} valor={r.pib_per_capita_fmt ?? "—"} />
        {r.vs_uf_fmt && <Metrica rotulo="vs. estado" valor={r.vs_uf_fmt} />}
        {r.vs_brasil_fmt && <Metrica rotulo="vs. Brasil" valor={r.vs_brasil_fmt} />}
      </div>
      {r.leitura && <p className="mt-2 text-xs text-slate-600">{r.leitura}</p>}
    </Bloco>
  );
}

function BlocoHabitacao({ loc }: { loc: Localizacao }) {
  const h = loc.habitacao;
  return (
    <Bloco titulo="Habitação" fonte={h.fonte} indisponivel={!h.disponivel} aviso={undefined}>
      {h.deficit ? (
        <Metrica
          rotulo={`Déficit habitacional (${h.deficit.fonte} ${h.deficit.ano})`}
          valor={`${h.deficit.valor_fmt} domicílios`}
        />
      ) : h.fallback_estoque ? (
        <>
          <div className="grid grid-cols-2 gap-3">
            <Metrica
              rotulo="Domicílios ocupados"
              valor={h.fallback_estoque.domicilios_ocupados_fmt}
            />
            <Metrica
              rotulo="Moradores/domicílio"
              valor={h.fallback_estoque.moradores_por_domicilio_fmt}
            />
          </div>
          {h.aviso && (
            <p className="mt-2 rounded bg-amber-50 p-2 text-xs text-amber-800">{h.aviso}</p>
          )}
        </>
      ) : null}
    </Bloco>
  );
}

function BlocoFaixaEtaria({ loc }: { loc: Localizacao }) {
  const f = loc.faixa_etaria;
  const cores = ["bg-indigo-400", "bg-sky-400", "bg-emerald-400", "bg-amber-400"];
  return (
    <Bloco titulo="Faixa etária" fonte={f.fonte} indisponivel={!f.disponivel} aviso={f.aviso}>
      {/* Barra empilhada — largura proporcional ao pct vindo do backend (sem cálculo aqui). */}
      <div className="flex h-5 w-full overflow-hidden rounded">
        {f.grupos.map((g, i) => (
          <div
            key={g.faixa}
            className={cores[i % cores.length]}
            style={{ width: `${g.pct * 100}%` }}
            title={`${g.faixa}: ${g.pct_fmt}`}
          />
        ))}
      </div>
      <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-4">
        {f.grupos.map((g, i) => (
          <div key={g.faixa} className="flex items-center gap-1.5">
            <span className={`h-2.5 w-2.5 rounded-sm ${cores[i % cores.length]}`} />
            <span className="text-xs text-slate-600">
              {g.faixa}: <span className="font-medium text-slate-900">{g.pct_fmt}</span>
            </span>
          </div>
        ))}
      </div>
    </Bloco>
  );
}
