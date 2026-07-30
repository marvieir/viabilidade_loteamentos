// Laudo de exemplo — página PÚBLICA (sem login). Pedido do operador em 29/07: responde
// "o que sai daí?" antes de a pessoa subir a própria gleba, que é a objeção que trava
// conversão. Superfície EDITORIAL (direção B do mockup aprovado): papel, serifa e número em
// monoespaçada — o que vendemos é parecer, e a página se parece com um.
//
// §regra 2: o front NÃO calcula nem reformata. Todo número vem do endpoint /api/exemplo/laudo,
// que roda o mesmo motor determinístico dos clientes sobre a gleba real de São Roque.

import type { Metadata } from "next";
import Link from "next/link";
import { Logo } from "@/components/marca/Logo";
import { FooterSite } from "@/components/marketing/site";

export const metadata: Metadata = {
  title: "voaz.app — laudo de exemplo (gleba real em São Roque/SP)",
  description:
    "Veja um laudo de pré-viabilidade completo antes de enviar a sua gleba: quadro de "
    + "áreas, lotes, régua legal aplicada e a fonte de cada número.",
};

// Revalida de hora em hora: o laudo muda só quando o motor muda.
export const revalidate = 3600;

// Esta página renderiza no SERVIDOR, então a URL da api é a INTERNA da rede do compose —
// "localhost" aqui é o próprio container do web, e foi o que fez a página cair no fallback
// "indisponível" no primeiro teste do operador. Fora do container, cai no endereço público.
const API =
  process.env.API_BASE_INTERNA ??
  process.env.NEXT_PUBLIC_API_BASE ??
  "http://localhost:8700";

type Uso = { m2: number; m2_fmt: string; pct_apo: number; pct_fmt: string };
type Laudo = {
  gleba: {
    rotulo: string; municipio: string; uf: string; cod_ibge: string;
    aproveitavel_m2: number; aproveitavel_ha: number; tipo: string;
  };
  quadro_areas: Record<string, Uso | number | string | null>;
  indicadores: {
    n_lotes: number; area_media_m2: number | null; area_media_fmt: string | null;
    testada_media_m: number | null; profundidade_media_m: number | null;
  };
  diretrizes: {
    cobertura: string; fonte: string; lote_min_zona_m2: number | null;
    piso_lote_efetivo_m2: number; doacao_min_pct: number | null;
    doacao_split: { viario: number | null; verde: number | null;
                    institucional: number | null } | null;
  };
  proveniencia: string;
};

// Ordem e cor de cada linha do quadro — as mesmas cores do mapa do produto, para quem vê o
// laudo e depois o app reconhecer o mesmo código visual.
const LINHAS: { chave: string; rotulo: string; cor: string }[] = [
  { chave: "vendavel", rotulo: "Vendável (lotes)", cor: "#ff914d" },
  { chave: "arruamento", rotulo: "Arruamento", cor: "#7b719e" },
  { chave: "sistema_lazer", rotulo: "Sistema de lazer", cor: "#a2dfbb" },
  { chave: "area_verde_reserva", rotulo: "Área verde de reserva", cor: "#3a806f" },
  { chave: "institucional", rotulo: "Institucional", cor: "#db6b1a" },
  { chave: "sobra_geometrica", rotulo: "Sobra geométrica", cor: "#e3d5c8" },
  { chave: "lamina_dagua", rotulo: "Lâmina d'água", cor: "#8ec5e6" },
];

async function buscarLaudo(): Promise<Laudo | null> {
  try {
    const res = await fetch(`${API}/api/exemplo/laudo`, { next: { revalidate: 3600 } });
    if (!res.ok) return null;
    return (await res.json()) as Laudo;
  } catch {
    return null; // servidor fora do ar → a página degrada com honestidade, não quebra
  }
}

export default async function LaudoExemploPage() {
  const laudo = await buscarLaudo();

  return (
    <div className="min-h-screen bg-papel text-papel-tinta">
      <header className="sticky top-0 z-10 border-b border-papel-linha bg-papel/95 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-4xl items-center justify-between px-5">
          <Link href="/" aria-label="voaz.app — início">
            <Logo tamanho={28} tom="laranja-escuro" />
          </Link>
          <div className="flex items-center gap-3">
            <span className="rounded-full bg-verde/15 px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider text-verde">
              exemplo real
            </span>
            <Link
              href="/registrar"
              className="inline-flex h-9 items-center rounded-lg bg-laranja px-4 text-sm font-bold text-marinho-900 transition hover:bg-laranja-600 hover:text-white"
            >
              Analisar minha gleba
            </Link>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-4xl px-5 pb-16">
        {laudo === null ? (
          <div className="py-24 text-center">
            <h1 className="font-serifa text-2xl">O laudo de exemplo está indisponível agora.</h1>
            <p className="mx-auto mt-3 max-w-md text-sm text-papel-tinta2">
              Não conseguimos falar com o servidor de análise. Tente recarregar em alguns
              minutos — ou crie a sua conta e analise a sua própria gleba.
            </p>
            <Link
              href="/registrar"
              className="mt-6 inline-flex h-11 items-center rounded-lg bg-laranja px-6 text-sm font-bold text-marinho-900 transition hover:bg-laranja-600 hover:text-white"
            >
              Criar conta grátis
            </Link>
          </div>
        ) : (
          <>
            {/* Capa do parecer */}
            <section className="pt-12">
              <div className="flex flex-wrap justify-between gap-3 border-b border-papel-linha pb-3 font-mono text-[11px] uppercase tracking-[0.14em] text-papel-tinta3">
                <span>Laudo de pré-viabilidade</span>
                <span>
                  {laudo.gleba.municipio} / {laudo.gleba.uf} · IBGE {laudo.gleba.cod_ibge}
                </span>
              </div>
              <h1 className="mt-6 font-serifa text-[clamp(28px,5vw,44px)] leading-[1.05]">
                {laudo.gleba.rotulo}
              </h1>
              <p className="mt-4 max-w-[52ch] font-serifa text-lg text-papel-tinta2">
                {laudo.gleba.tipo} · diretriz municipal{" "}
                {laudo.diretrizes.cobertura === "COMPLETA" ? "confirmada" : "não confirmada"}{" "}
                (zona MUE).
              </p>
            </section>

            {/* Achados de capa */}
            <section className="mt-10 grid gap-7 border-t border-papel-linha pt-7 sm:grid-cols-2 lg:grid-cols-4">
              <Achado
                k="Área aproveitável"
                v={`${laudo.gleba.aproveitavel_ha.toLocaleString("pt-BR")} ha`}
                d="gleba menos declividade ≥30%"
              />
              <Achado
                k="Lotes"
                v={String(laudo.indicadores.n_lotes)}
                d={laudo.indicadores.area_media_fmt
                  ? `média de ${laudo.indicadores.area_media_fmt} m²`
                  : "—"}
              />
              <Achado
                k="Área vendável"
                v={usoDe(laudo, "vendavel")?.pct_fmt ?? "—"}
                d={usoDe(laudo, "vendavel")?.m2_fmt
                  ? `${usoDe(laudo, "vendavel")?.m2_fmt} m²`
                  : "—"}
              />
              <Achado
                k="Testada média"
                v={laudo.indicadores.testada_media_m
                  ? `${laudo.indicadores.testada_media_m} m`
                  : "—"}
                d={laudo.indicadores.profundidade_media_m
                  ? `profundidade ${laudo.indicadores.profundidade_media_m} m`
                  : "—"}
              />
            </section>

            {/* Quadro de áreas */}
            <Secao titulo="Quadro de áreas">
              <div className="grid gap-4">
                {LINHAS.map((l) => {
                  const u = usoDe(laudo, l.chave);
                  if (!u || !u.m2) return null;
                  return (
                    <div key={l.chave}>
                      <div className="h-2.5 w-full overflow-hidden rounded-sm bg-papel-linha">
                        <div
                          className="h-full"
                          style={{
                            width: `${Math.min(100, u.pct_apo * 100)}%`,
                            background: l.cor,
                          }}
                        />
                      </div>
                      <div className="mt-1.5 flex items-baseline justify-between gap-3 text-sm">
                        <span className="text-papel-tinta2">{l.rotulo}</span>
                        <span className="flex gap-4 font-mono tabular-nums">
                          <b className="font-semibold">{u.m2_fmt} m²</b>
                          <b className="w-14 text-right font-semibold">{u.pct_fmt}</b>
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </Secao>

            {/* Régua legal */}
            <Secao titulo="Régua legal aplicada">
              <Linha
                rotulo="Lote mínimo da zona"
                nota="diretriz municipal confirmada por humano antes de entrar no cálculo"
                valor={laudo.diretrizes.lote_min_zona_m2
                  ? `${laudo.diretrizes.lote_min_zona_m2.toLocaleString("pt-BR")} m²`
                  : "não fixado"}
                estado={laudo.diretrizes.cobertura === "COMPLETA" ? "ok" : "atencao"}
                estadoRotulo={laudo.diretrizes.cobertura.toLowerCase()}
              />
              {laudo.diretrizes.doacao_min_pct != null && (
                <Linha
                  rotulo="Doação ao município"
                  nota={
                    laudo.diretrizes.doacao_split
                      ? `viário ${pct(laudo.diretrizes.doacao_split.viario)} · verde ${pct(
                          laudo.diretrizes.doacao_split.verde,
                        )} · institucional ${pct(laudo.diretrizes.doacao_split.institucional)}`
                      : "repartição não detalhada na diretriz"
                  }
                  valor={pct(laudo.diretrizes.doacao_min_pct)}
                  estado="ok"
                  estadoRotulo="confirmada"
                />
              )}
              <Linha
                rotulo="Piso legal federal"
                nota="Lei 6.766/79, art. 4º, II — vale sempre que o município não fixa mais"
                valor="125 m²"
                estado="atencao"
                estadoRotulo="retaguarda"
              />
            </Secao>

            {/* Proveniência + chamada */}
            <section className="mt-12 rounded-xl bg-papel-escuro p-6">
              <p className="font-serifa text-[15px] leading-relaxed text-papel-tinta2">
                {laudo.proveniencia}
              </p>
              <div className="mt-5 flex flex-wrap items-center gap-3">
                <Link
                  href="/registrar"
                  className="inline-flex h-12 items-center rounded-lg bg-laranja px-6 text-sm font-bold text-marinho-900 transition hover:bg-laranja-600 hover:text-white"
                >
                  Analisar minha gleba agora
                </Link>
                <Link
                  href="/"
                  className="inline-flex h-12 items-center rounded-lg border border-papel-linha px-6 text-sm font-semibold transition hover:bg-papel"
                >
                  Como funciona
                </Link>
              </div>
            </section>
          </>
        )}
      </main>

      <FooterSite />
    </div>
  );
}

function usoDe(l: Laudo, chave: string): Uso | null {
  const v = l.quadro_areas[chave];
  return v && typeof v === "object" && "m2_fmt" in v ? (v as Uso) : null;
}

// A diretriz vem em FRAÇÃO do backend; aqui só trocamos a casa decimal por texto — não é
// cálculo de negócio, é apresentação de percentual (§regra 2 continua valendo p/ áreas).
function pct(f: number | null | undefined): string {
  return f == null ? "—" : `${(f * 100).toLocaleString("pt-BR")}%`;
}

function Achado({ k, v, d }: { k: string; v: string; d: string }) {
  return (
    <div>
      <p className="font-mono text-[10.5px] uppercase tracking-[0.13em] text-papel-tinta3">{k}</p>
      <p className="mt-1 font-mono text-[29px] font-semibold tabular-nums leading-none">{v}</p>
      <p className="mt-1.5 text-[12.5px] text-papel-tinta2">{d}</p>
    </div>
  );
}

function Secao({ titulo, children }: { titulo: string; children: React.ReactNode }) {
  return (
    <section className="mt-10 border-t border-papel-linha pt-7">
      <h2 className="mb-5 text-[12px] font-bold uppercase tracking-[0.14em] text-laranja-600">
        {titulo}
      </h2>
      {children}
    </section>
  );
}

function Linha({
  rotulo, nota, valor, estado, estadoRotulo,
}: {
  rotulo: string; nota: string; valor: string;
  estado: "ok" | "atencao"; estadoRotulo: string;
}) {
  return (
    <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 border-b border-papel-linha py-3">
      <span className="text-sm">
        {rotulo}
        <span className="mt-0.5 block font-serifa text-[11.5px] italic text-papel-tinta3">
          {nota}
        </span>
      </span>
      <span className="flex items-center gap-3">
        <b className="font-mono text-[15px] font-semibold tabular-nums">{valor}</b>
        <span
          className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ${
            estado === "ok"
              ? "bg-verde/15 text-verde"
              : "bg-laranja-600/15 text-laranja-700"
          }`}
        >
          {estadoRotulo}
        </span>
      </span>
    </div>
  );
}
