// Página principal (marketing) — implementa docs/marketing/pagina-principal.md v1.1.
// Copy em Light Copy; visuais só com print real (PrintReal degrada para placeholder).
// O app autenticado mora em /app.

import type { Metadata } from "next";
import Link from "next/link";
import { PrintReal } from "@/components/marketing/PrintReal";
import {
  BotoesCta,
  FaixaHonestidade,
  FooterSite,
  HeaderSite,
} from "@/components/marketing/site";

export const metadata: Metadata = {
  title: "Viabilidade homeeye | Decidir em 1 dia se a gleba vira loteamento",
  description:
    "Pré-análise ambiental, jurídica, urbanística e financeira da sua gleba a partir do KMZ, com a fonte legal ao lado de cada número. Grátis: 1 gleba por mês, com até 5 análises.",
};

const DORES = [
  "Herdei uma área, pago ITR todo ano, e cada corretor fala um valor diferente.",
  "Avalio 30 áreas por ano. A maioria morre depois do estudo caro.",
  "O estudo que me entregam é de quem ganha se eu comprar.",
  "Quero lotear a minha terra e ninguém me diz por onde começar, nem quanto custa.",
];

const VIRADA = [
  {
    titulo: "Decidir rápido",
    texto:
      "A análise sai em minutos depois de subir o KMZ. A resposta ao corretor sai na mesma reunião, com mapa e quadro de áreas.",
  },
  {
    titulo: "Decidir com fonte",
    texto:
      "Cada número carrega a lei que incide, o perfil aplicado e a data de referência. O relatório declara o que cobriu e o que falta verificar.",
  },
  {
    titulo: "Decidir antes de gastar caro",
    texto:
      "A triagem mostra onde vale pagar advogado, agrimensor e urbanista. O orçamento de diligência vai só para gleba que passou.",
  },
];

const PASSOS = [
  {
    titulo: "Suba o KMZ da gleba",
    texto: "O mesmo contorno que você já tem no Google Earth.",
  },
  {
    titulo: "A plataforma roda as dimensões",
    texto:
      "Ambiental (APP, mata, declividade por faixas), diretriz municipal quando confirmada, pré-projeto urbanístico com traçado, quadro de áreas e VGV, e financeiro com fluxo, venda financiada, VPL e TIR.",
  },
  {
    titulo: "Você decide com números auditáveis",
    texto:
      "Relatório com a origem de cada valor, mapa sobre a foto de satélite e a lista do que verificar com cada profissional.",
  },
];

const PUBLICOS: { card: string; dor: string; transformacao: string; href: string }[] = [
  {
    card: "Tenho uma gleba parada",
    dor: "Paga imposto há anos em cima de um valor que ninguém sabe dizer",
    transformacao: "Saber quanto vale a gleba antes de sentar para negociar",
    href: "#cta",
  },
  {
    card: "Vivo de originar áreas",
    dor: "Estudo caro e lento para gleba que morre na diligência",
    transformacao: "Triar 10 glebas no tempo de 1 estudo tradicional",
    href: "/loteadores",
  },
  {
    card: "Avalio entrar no segmento",
    dor: "Validar a tese com o material de quem quer vender a área",
    transformacao: "Enxergar o risco ambiental antes de dar o sinal",
    href: "#cta",
  },
  {
    card: "Quero lotear minha terra",
    dor: "Começar sem saber as etapas, os custos, as exigências",
    transformacao: "Saber se compensa lotear em vez de vender",
    href: "#cta",
  },
  {
    card: "Estou entrando no mercado",
    dor: "Prospectar de mãos vazias diante de proprietário e investidor",
    transformacao: "Analisar gleba como quem faz isso há 20 anos",
    href: "#cta",
  },
];

const FAQ: { pergunta: string; resposta: string }[] = [
  {
    pergunta: "Análise de escritório substitui quem conhece a região?",
    resposta:
      "Ela soma ao conhecimento local. Quem conhece a região traz mercado e prática; a análise traz a APP medida, a declividade por faixa e o artigo que incide, coisas que memória nenhuma cobre nos 5.570 municípios do país. A gleba boa passa nos dois filtros.",
  },
  {
    pergunta: "A prefeitura é quem decide. Esse estudo vale o quê?",
    resposta:
      "Vale antes do protocolo. As diretrizes são da prefeitura (art. 6º, Lei 6.766/79) e o relatório declara isso. O que a triagem faz é cortar as rodadas de exigência que nascem de erro evitável: doação abaixo do mínimo, via sobre faixa não edificável, lote fora da zona.",
  },
  {
    pergunta: "Já tenho engenheiro e topógrafo de confiança.",
    resposta:
      "Eles continuam. O relatório imprime \"verificar com o profissional\" nos pontos que são deles. A plataforma faz a etapa anterior: triar muitas glebas para a hora cara da sua equipe render só nas que valem.",
  },
  {
    pergunta: "E se a análise errar?",
    resposta:
      "Todo número mostra a fonte para você conferir antes de gastar qualquer real. O relatório declara o que cobriu e o que não cobriu, e o plano gratuito custa zero: o custo de duvidar da gente é nenhum.",
  },
  {
    pergunta: "Vou usar pouco. Vale o preço?",
    resposta:
      "Usar pouco custa R$ 0,00: o plano gratuito dá 1 gleba por mês com até 5 análises entre as dimensões (ambiental, jurídica, urbanística, financeira). A assinatura só faz sentido quando o seu volume pedir mais áreas e mais análises. Comece de graça e deixe o uso decidir.",
  },
];

export default function PaginaPrincipal() {
  return (
    <div className="bg-white text-slate-900">
      <HeaderSite />

      {/* 1. Hero */}
      <section className="bg-slate-900 pb-16 pt-14 text-white">
        <div className="mx-auto max-w-6xl px-5">
          <div className="mx-auto max-w-3xl text-center">
            <h1 className="text-4xl font-extrabold leading-tight tracking-tight sm:text-5xl">
              Decidir em 1 dia se a gleba vira loteamento
            </h1>
            <p className="mt-5 text-lg leading-relaxed text-slate-300">
              A plataforma Viabilidade homeeye faz a pré-análise ambiental, jurídica,
              urbanística e financeira da sua gleba a partir do KMZ, com a fonte legal ao lado
              de cada número.
            </p>
            <div className="mt-8">
              <BotoesCta escuro />
            </div>
            <p className="mt-3 text-sm text-slate-400">
              Grátis: 1 gleba por mês, com até 5 análises.
            </p>
          </div>
          <div className="mx-auto mt-12 max-w-4xl">
            <PrintReal
              src="/marketing/hero-tracado.png"
              alt="Traçado urbanístico gerado sobre a foto de satélite, ao lado do quadro de áreas"
              legenda="Traçado gerado sobre a gleba real, com o quadro de áreas fechando em 100%"
            />
          </div>
        </div>
      </section>

      {/* 2. Espelho da dor */}
      <section className="py-16">
        <div className="mx-auto max-w-6xl px-5">
          <h2 className="text-center text-3xl font-bold tracking-tight">
            A gleba está aí. As respostas, não.
          </h2>
          <div className="mt-10 grid gap-4 sm:grid-cols-2">
            {DORES.map((d) => (
              <blockquote
                key={d}
                className="rounded-xl border border-slate-200 bg-slate-50 p-5 text-[15px] leading-relaxed text-slate-700"
              >
                “{d}”
              </blockquote>
            ))}
          </div>
        </div>
      </section>

      {/* 3. A virada */}
      <section className="bg-slate-50 py-16">
        <div className="mx-auto max-w-6xl px-5">
          <h2 className="text-center text-3xl font-bold tracking-tight">
            Do palpite ao número com fonte
          </h2>
          <div className="mt-10 grid gap-6 md:grid-cols-3">
            {VIRADA.map((b) => (
              <div key={b.titulo} className="rounded-xl border border-slate-200 bg-white p-6">
                <h3 className="text-lg font-semibold text-emerald-700">{b.titulo}</h3>
                <p className="mt-2 text-sm leading-relaxed text-slate-600">{b.texto}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* 4. Como funciona */}
      <section id="como-funciona" className="py-16">
        <div className="mx-auto max-w-6xl px-5">
          <h2 className="text-center text-3xl font-bold tracking-tight">
            Três passos entre o KMZ e a decisão
          </h2>
          <ol className="mx-auto mt-10 grid max-w-4xl gap-6 md:grid-cols-3">
            {PASSOS.map((p, i) => (
              <li key={p.titulo} className="rounded-xl border border-slate-200 p-6">
                <span className="grid h-9 w-9 place-items-center rounded-full bg-emerald-500 text-sm font-bold text-white">
                  {i + 1}
                </span>
                <h3 className="mt-3 font-semibold">{p.titulo}</h3>
                <p className="mt-2 text-sm leading-relaxed text-slate-600">{p.texto}</p>
              </li>
            ))}
          </ol>
          <div className="mt-8">
            <FaixaHonestidade />
          </div>
        </div>
      </section>

      {/* 5. Para quem é */}
      <section id="para-quem" className="bg-slate-50 py-16">
        <div className="mx-auto max-w-6xl px-5">
          <h2 className="text-center text-3xl font-bold tracking-tight">
            Encontre a sua cadeira na mesa
          </h2>
          <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {PUBLICOS.map((p) => (
              <div
                key={p.card}
                className="flex flex-col rounded-xl border border-slate-200 bg-white p-5"
              >
                <h3 className="font-semibold">{p.card}</h3>
                <p className="mt-2 text-sm text-slate-500">{p.dor}</p>
                <p className="mt-2 text-sm font-medium text-emerald-700">{p.transformacao}</p>
                <Link
                  href={p.href}
                  className="mt-auto pt-4 text-sm font-semibold text-emerald-600 hover:text-emerald-500"
                >
                  Ver como funciona para você →
                </Link>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* 6. Confiança */}
      <section className="py-16">
        <div className="mx-auto grid max-w-6xl items-center gap-10 px-5 md:grid-cols-2">
          <div>
            <h2 className="text-3xl font-bold tracking-tight">
              Você não precisa acreditar na gente
            </h2>
            <p className="mt-4 leading-relaxed text-slate-600">
              Cada número do relatório sai com a origem impressa ao lado: a lei, o perfil de
              jurisdição aplicado e a data de referência. Quando o seu município ainda não tem
              perfil confirmado, a análise avisa e declara a cobertura usada (federal, estadual
              ou completa). Ausência de achado aparece como limite declarado da base, nunca como
              garantia.
            </p>
            <p className="mt-4 font-medium text-slate-700">
              Mesma entrada, mesma saída: a análise é reproduzível. Rode duas vezes e confira.
            </p>
          </div>
          <PrintReal
            src="/marketing/conformidade.png"
            alt="Card de conformidade legal com os artigos citados ao lado de cada exigência"
            legenda="Conformidade item a item, com o artigo da lei ao lado de cada exigência"
          />
        </div>
      </section>

      {/* 7. FAQ de objeções */}
      <section className="bg-slate-50 py-16">
        <div className="mx-auto max-w-3xl px-5">
          <h2 className="text-center text-3xl font-bold tracking-tight">
            Perguntas que todo mundo faz antes
          </h2>
          <div className="mt-8 space-y-3">
            {FAQ.map((f) => (
              <details
                key={f.pergunta}
                className="group rounded-xl border border-slate-200 bg-white p-5"
              >
                <summary className="cursor-pointer list-none font-semibold marker:hidden">
                  “{f.pergunta}”
                </summary>
                <p className="mt-3 text-sm leading-relaxed text-slate-600">{f.resposta}</p>
              </details>
            ))}
          </div>
        </div>
      </section>

      {/* 8. CTA final */}
      <section id="cta" className="bg-slate-900 py-16 text-white">
        <div className="mx-auto max-w-3xl px-5 text-center">
          <h2 className="text-3xl font-bold tracking-tight">A primeira análise sai hoje</h2>
          <p className="mt-4 leading-relaxed text-slate-300">
            Crie a conta gratuita, suba o KMZ e veja a sua gleba em números: 1 gleba por mês, com
            até 5 análises, grátis. Se preferir ver antes com um especialista, agende a
            demonstração online.
          </p>
          <div className="mt-8">
            <BotoesCta escuro />
          </div>
        </div>
      </section>

      {/* 9. Rodapé */}
      <FooterSite />
    </div>
  );
}
