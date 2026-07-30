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
import { MapaExemplo } from "@/components/marketing/MapaExemplo";

export const metadata: Metadata = {
  title: "voaz.app — laudo de exemplo (gleba real em São Roque/SP)",
  description:
    "Veja um laudo de pré-viabilidade completo antes de enviar a sua gleba: quadro de "
    + "áreas, lotes, régua legal aplicada e a fonte de cada número.",
};

// ISR de 60 s (30/07): a página sempre-dinâmica re-serializava MBs de GeoJSON a cada
// visita — o botão levava ~10 s. Com 60 s de cache o caminho feliz é instantâneo e o pior
// caso (fallback de erro congelado) dura 1 minuto, não 1 hora como na 1ª versão.
export const revalidate = 60;

// Esta página renderiza no SERVIDOR, então a URL da api é a INTERNA da rede do compose —
// "localhost" aqui é o próprio container do web, e foi o que fez a página cair no fallback
// "indisponível" no primeiro teste do operador. Fora do container, cai no endereço público.
const API =
  process.env.API_BASE_INTERNA ??
  process.env.NEXT_PUBLIC_API_BASE ??
  "http://localhost:8700";

type Completo = {
  tipo: "completo";
  titulo: string;
  publicado_em: string;
  identificacao: Record<string, string | number | null>;
  ressalva: string;
  semaforo: { dimensao: string; luz: string; justificativa: string }[];
  secoes: { chave: string; titulo: string; analisada: boolean; luz: string;
            itens: { rotulo: string; valor: string; proveniencia?: string | null }[];
            avisos: string[] }[];
  juridico: { criticos: number; moderados: number; sem_impacto: number;
              n_documentos: number; luz: string };
  ambiental_geo?: Record<string, GeoJSON.Geometry> | null;
  urbanismo: { geometria: Record<string, unknown> | null;
               quadro_areas: Record<string, Uso | number | string | null> | null };
  gleba_geojson: GeoJSON.Polygon | null;
  proveniencia: string;
};

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
    const res = await fetch(`${API}/api/exemplo/laudo`, { next: { revalidate: 60 } });
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
        ) : (laudo as unknown as Completo).tipo === "completo" ? (
          <LaudoCompleto laudo={laudo as unknown as Completo} />
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

const LUZ_ROTULO: Record<string, { r: string; cls: string }> = {
  favoravel: { r: "favorável", cls: "bg-verde/15 text-verde" },
  atencao: { r: "atenção", cls: "bg-laranja-600/15 text-laranja-700" },
  restricao: { r: "restrição", cls: "bg-red-100 text-red-700" },
  informativa: { r: "informativa", cls: "bg-papel-escuro text-papel-tinta2" },
  nao_analisada: { r: "não analisada", cls: "bg-papel-escuro text-papel-tinta3" },
};

function Luz({ luz }: { luz: string }) {
  const m = LUZ_ROTULO[luz] ?? LUZ_ROTULO.nao_analisada;
  return (
    <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ${m.cls}`}>
      {m.r}
    </span>
  );
}

function LaudoCompleto({ laudo }: { laudo: Completo }) {
  const ident = laudo.identificacao;
  return (
    <>
      <section className="pt-12">
        <div className="flex flex-wrap justify-between gap-3 border-b border-papel-linha pb-3 font-mono text-[11px] uppercase tracking-[0.14em] text-papel-tinta3">
          <span>Análise real · publicada em {laudo.publicado_em}</span>
          <span>{String(ident.municipio ?? "")} / {String(ident.uf ?? "")}</span>
        </div>
        <h1 className="mt-6 font-serifa text-[clamp(26px,4.5vw,42px)] leading-[1.05]">
          {laudo.titulo}
        </h1>
        <p className="mt-3 max-w-[62ch] text-sm text-papel-tinta2">{laudo.ressalva}</p>
      </section>

      {/* Semáforo por dimensão */}
      <section className="mt-8 grid gap-3 sm:grid-cols-2">
        {laudo.semaforo.map((l) => (
          <div key={l.dimensao}
               className="flex items-start justify-between gap-3 rounded-lg border border-papel-linha bg-white/50 px-4 py-3">
            <div>
              <p className="text-sm font-semibold">{l.dimensao}</p>
              <p className="mt-0.5 text-[12px] text-papel-tinta2">{l.justificativa}</p>
            </div>
            <Luz luz={l.luz} />
          </div>
        ))}
      </section>

      {/* Mapa AMBIENTAL: as camadas de restrição sobre a gleba */}
      {laudo.gleba_geojson && laudo.ambiental_geo &&
        Object.keys(laudo.ambiental_geo).length > 0 && (
        <Secao titulo="Análise ambiental no mapa">
          <MapaExemplo gleba={laudo.gleba_geojson} geometria={null}
                       overlaysCrus={laudo.ambiental_geo} />
          <p className="mt-2 text-[12px] text-papel-tinta3">
            Mineração (ANM), Reserva Legal (CAR), domínio da Mata Atlântica, verde a
            verificar e declividade — as mesmas camadas, com as mesmas cores, que o
            usuário vê dentro da plataforma.
          </p>
        </Secao>
      )}

      {/* Mapa da gleba com o urbanismo */}
      {laudo.gleba_geojson && (
        <Secao titulo="A gleba e o estudo urbanístico">
          <MapaExemplo gleba={laudo.gleba_geojson} geometria={laudo.urbanismo.geometria} />
        </Secao>
      )}

      {/* Quadro de áreas do urbanismo */}
      {laudo.urbanismo.quadro_areas && (
        <Secao titulo="Quadro de áreas">
          <div className="grid gap-4">
            {LINHAS.map((l) => {
              const q = laudo.urbanismo.quadro_areas![l.chave];
              const u = q && typeof q === "object" && "m2_fmt" in q ? (q as Uso) : null;
              if (!u || !u.m2) return null;
              return (
                <div key={l.chave}>
                  <div className="h-2.5 w-full overflow-hidden rounded-sm bg-papel-linha">
                    <div className="h-full"
                         style={{ width: `${Math.min(100, u.pct_apo * 100)}%`, background: l.cor }} />
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
      )}

      {/* Jurídico: SÓ contagens por severidade (decisão do operador — nenhum detalhe) */}
      <Secao titulo="Análise jurídica dos documentos">
        <div className="grid gap-4 sm:grid-cols-3">
          <ContagemJuridica n={laudo.juridico.criticos} rotulo="itens que podem ser críticos"
                            cor="text-red-700" />
          <ContagemJuridica n={laudo.juridico.moderados} rotulo="itens de impacto moderado"
                            cor="text-laranja-700" />
          <ContagemJuridica n={laudo.juridico.sem_impacto} rotulo="itens sem impacto no loteamento"
                            cor="text-verde" />
        </div>
        <p className="mt-4 text-[12.5px] text-papel-tinta3">
          {laudo.juridico.n_documentos} documento(s) analisados. Os detalhes de cada achado —
          e a citação do ato que o sustenta — aparecem na análise completa, dentro da
          plataforma. Aqui, por respeito aos dados do proprietário, só as contagens.
        </p>
      </Secao>

      {/* Demais dimensões, como o laudo PDF as monta */}
      {laudo.secoes.filter((s) => s.analisada && s.chave !== "identificacao").map((s) => (
        <Secao key={s.chave} titulo={s.titulo}>
          <div className="mb-3"><Luz luz={s.luz} /></div>
          {s.itens.map((it) => (
            <div key={it.rotulo}
                 className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 border-b border-papel-linha py-2.5 text-sm">
              <span>
                {it.rotulo}
                {it.proveniencia && (
                  <span className="mt-0.5 block font-serifa text-[11.5px] italic text-papel-tinta3">
                    {it.proveniencia}
                  </span>
                )}
              </span>
              <b className="font-mono text-[14px] font-semibold tabular-nums">{it.valor}</b>
            </div>
          ))}
        </Secao>
      ))}

      <section className="mt-12 rounded-xl bg-papel-escuro p-6">
        <p className="font-serifa text-[15px] leading-relaxed text-papel-tinta2">
          {laudo.proveniencia}
        </p>
        <Link href="/registrar"
              className="mt-5 inline-flex h-12 items-center rounded-lg bg-laranja px-6 text-sm font-bold text-marinho-900 transition hover:bg-laranja-600 hover:text-white">
          Analisar minha gleba agora
        </Link>
      </section>
    </>
  );
}

function ContagemJuridica({ n, rotulo, cor }: { n: number; rotulo: string; cor: string }) {
  return (
    <div className="rounded-xl border border-papel-linha bg-white/50 p-5 text-center">
      <p className={`font-mono text-4xl font-bold tabular-nums ${cor}`}>{n}</p>
      <p className="mt-1.5 text-[13px] text-papel-tinta2">{rotulo}</p>
    </div>
  );
}
