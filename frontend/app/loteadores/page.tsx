// Página de vendas — loteador em operação. Implementa docs/marketing/pagina-vendas.md v1.1.
// Copy em Light Copy; prints reais via PrintReal; preço da assinatura: A DEFINIR (oculto até
// o operador fechar o valor; a mecânica dos planos aparece).

import type { Metadata } from "next";
import Link from "next/link";
import { PrintReal } from "@/components/marketing/PrintReal";
import {
  BotoesCta,
  FooterSite,
  HeaderSite,
  LINK_DEMO,
} from "@/components/marketing/site";

export const metadata: Metadata = {
  title: "Viabilidade homeeye para loteadores | Triar 10 glebas no tempo de 1 estudo",
  description:
    "A pré-análise que corta do seu funil a gleba que morre na diligência, antes de você pagar o estudo caro por ela. Grátis: 1 gleba por mês, com até 5 análises.",
};

const MUDANCAS = [
  "Triar uma gleba em minutos, no lugar de semanas de espera por relatório",
  "Responder ao corretor com números ainda na mesma reunião",
  "Concentrar o orçamento de diligência nas 2 ou 3 áreas que passaram",
  "Descobrir o passivo ambiental antes do sinal, quando ainda vira desconto",
  "Comparar todas as glebas do funil com a mesma régua, sempre",
  "Rodar até 600 análises por ano sem fila de fornecedor",
  "Testar a mesma gleba em dois objetivos: Rendimento (mais lotes) ou Paisagem (desenho premium)",
  "Chegar ao investidor com quadro de áreas, VGV e fontes em vez de conversa",
];

const CAMINHO = [
  {
    titulo: "O KMZ vira gleba medida",
    texto: "Contorno sobre a foto de satélite, área e perímetro por cálculo geodésico.",
    src: "/marketing/passo-1-gleba.png",
  },
  {
    titulo: "As restrições aparecem no mapa",
    texto: "Mata, APP e declividade desenhadas sobre a gleba, cada mancha com a fonte.",
    src: "/marketing/passo-2-restricoes.png",
  },
  {
    titulo: "O pré-projeto nasce respeitando a lei",
    texto:
      "Traçado que contorna a mata, quadro de áreas fechando 100%, lotes com testada e área média.",
    src: "/marketing/passo-3-tracado.png",
  },
  {
    titulo: "O valor aparece lote a lote",
    texto: "Heatmap de valorização e VGV posicional no seu preço de m².",
    src: "/marketing/passo-4-heatmap.png",
  },
  {
    titulo: "A conformidade vem com o artigo ao lado",
    texto: "Item a item da diretriz, com o que atende e o que verificar.",
    src: "/marketing/passo-5-conformidade.png",
  },
];

const OBJECOES = [
  {
    objecao: "Análise de escritório não substitui quem conhece a região.",
    quebra:
      "Conhecimento de região é amostra: cobre as glebas de uma carreira num raio conhecido. A regra escrita cobre todas, nos 5.570 municípios. O seu faro continua na mesa; a análise entra com a parte que memória nenhuma cobre. Você já usa instrumento em tudo que é grande (topografia, sondagem, certidão); a triagem só aplica o mesmo critério à porta de entrada.",
  },
  {
    objecao: "A prefeitura é quem decide.",
    quebra:
      "Exatamente, e o relatório declara isso em cada página (art. 6º, Lei 6.766/79). O estudo vale antes do protocolo: corta as rodadas de exigência que nascem de erro evitável, como doação abaixo do mínimo da zona e via sobre faixa não edificável. Cada rodada evitada são meses que você não perde na fila.",
  },
  {
    objecao: "Já tenho engenheiro e topógrafo de confiança.",
    quebra:
      "O laboratório não substitui o médico; faz a consulta render. A Viabilidade homeeye entrega à sua equipe as glebas pré-qualificadas com mapa e fontes, e a hora sênior deles rende no que exige julgamento. O que você economiza descartando mico por método caro paga a triagem do ano.",
  },
  {
    objecao: "Se a análise errar, quem paga sou eu.",
    quebra:
      "Por isso todo número mostra a fonte antes de qualquer real sair do bolso, e o relatório declara o que cobriu e o que falta verificar. Entre uma análise auditável com limites declarados e uma opinião que não se deixa auditar, o risco cai na primeira. E o teste custa zero.",
  },
  {
    objecao: "Está caro para o quanto eu usaria.",
    quebra:
      "O custo que importa é o custo por decisão, e cada decisão de gleba movimenta milhões. Usar pouco custa R$ 0,00: o plano gratuito dá 1 gleba por mês com até 5 análises. Com 200 áreas e 600 análises por ano, a assinatura tria um funil inteiro: contando as 4 dimensões por gleba, dá para fechar mais de 12 áreas completas por mês.",
  },
];

const FAQ_OPERACIONAL = [
  {
    pergunta: "O que conta como 1 análise?",
    resposta:
      "Cada rodada de uma dimensão: uma análise ambiental, uma jurídica, uma financeira ou uma geração de urbanismo. No plano gratuito são até 5 por mês, todas na mesma gleba; a gleba escolhida fica fixa até o mês virar.",
  },
  {
    pergunta: "O que eu preciso ter?",
    resposta:
      "O KMZ da gleba (o contorno do Google Earth). Se tiver o levantamento planialtimétrico das matrículas em DWG, anexe: o traçado passa a seguir a cota real. Sem ele, a plataforma usa o relevo de satélite e avisa.",
  },
  {
    pergunta: "Funciona em qualquer município?",
    resposta:
      "Sim. Onde o perfil municipal ainda não foi confirmado, a análise roda no piso federal/estadual e declara a cobertura usada.",
  },
  {
    pergunta: "Quanto tempo leva?",
    resposta: "Minutos por gleba, na tela, sem fila.",
  },
  {
    pergunta: "O que a análise não faz?",
    resposta:
      "Não aprova parcelamento, não mede oficialmente, não emite laudo nem parecer. O relatório aponta o que verificar com advogado, agrimensor, ambiental e urbanista.",
  },
  {
    pergunta: "Posso regenerar o urbanismo?",
    resposta:
      "Sim, inclusive trocando o objetivo (Rendimento ou Paisagem) para comparar teses na mesma gleba. Cada regeneração consome 1 análise.",
  },
];

function LinhaPlanos() {
  const linhas: [string, string, string][] = [
    ["Áreas (glebas)", "1 por mês (fixa no mês)", "200 por ano"],
    ["Análises", "Até 5 por mês, somando as dimensões", "600 por ano"],
    ["Dimensões (ambiental, jurídica, urbanística, financeira)", "Todas", "Todas"],
    ["Proveniência em todo número", "Sim", "Sim"],
    ["Para quem", "Testar na sua gleba real", "Operação de originação"],
    ["Investimento", "R$ 0,00", "Fale com a gente"],
  ];
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[560px] border-collapse text-left text-sm">
        <thead>
          <tr className="border-b border-slate-300">
            <th className="py-3 pr-4"></th>
            <th className="py-3 pr-4 text-base">Gratuito</th>
            <th className="py-3 text-base text-emerald-700">Assinatura anual</th>
          </tr>
        </thead>
        <tbody>
          {linhas.map(([rotulo, gratis, anual]) => (
            <tr key={rotulo} className="border-b border-slate-200">
              <td className="py-3 pr-4 font-medium text-slate-600">{rotulo}</td>
              <td className="py-3 pr-4">{gratis}</td>
              <td className="py-3">{anual}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function PaginaLoteadores() {
  return (
    <div className="bg-white text-slate-900">
      <HeaderSite />

      {/* 1. Abertura */}
      <section className="bg-slate-900 pb-16 pt-14 text-white">
        <div className="mx-auto max-w-3xl px-5 text-center">
          <p className="text-sm font-semibold uppercase tracking-widest text-emerald-400">
            Para quem vive de originar áreas
          </p>
          <h1 className="mt-4 text-4xl font-extrabold leading-tight tracking-tight sm:text-5xl">
            Triar 10 glebas no tempo de 1 estudo tradicional
          </h1>
          <p className="mt-5 text-lg leading-relaxed text-slate-300">
            A pré-análise que corta do seu funil a gleba que morre na diligência, antes de você
            pagar o estudo caro por ela.
          </p>
          <div className="mt-8">
            <BotoesCta escuro />
          </div>
          <p className="mt-3 text-sm text-slate-400">
            Grátis: 1 gleba por mês, com até 5 análises.
          </p>
        </div>
      </section>

      {/* 2. A cena que você conhece */}
      <section className="py-16">
        <div className="mx-auto max-w-2xl space-y-5 px-5 text-[17px] leading-relaxed text-slate-700">
          <h2 className="text-3xl font-bold tracking-tight text-slate-900">
            A cena que você conhece
          </h2>
          <p>
            O corretor liga na segunda-feira com “a área perfeita”. Na terça você dirige duas
            horas para ver mato e promessa. Na semana seguinte, paga um estudo para descobrir o
            que a gleba tem de verdade.
          </p>
          <p>
            O estudo chega depois de um mês. A mancha de vegetação come o acesso, a declividade
            derruba um terço dos lotes, e a conta que fechava bonita no guardanapo não fecha no
            papel. O dinheiro do estudo foi, o mês foi, e o funil continua vazio.
          </p>
          <p>
            Enquanto isso, a área boa daquele mesmo mês foi para o concorrente que respondeu em
            três dias. Ele viu a mesma indicação que você. A diferença foi a velocidade de dizer
            sim.
          </p>
          <p>
            Quem origina área vive esse ciclo: pagar caro para descartar, demorar para aprovar, e
            perder a boa por causa das ruins. O problema nunca foi o seu faro. É o custo e a
            lentidão de cada verificação.
          </p>
          <p className="text-xs text-slate-400">Cenário ilustrativo.</p>
        </div>
      </section>

      {/* 3. O custo de continuar assim */}
      <section className="bg-slate-50 py-16">
        <div className="mx-auto max-w-2xl space-y-5 px-5 text-[17px] leading-relaxed text-slate-700">
          <h2 className="text-3xl font-bold tracking-tight text-slate-900">
            O custo de continuar assim
          </h2>
          <p>
            Faça a conta do seu último ano: quantas áreas chegaram, quantas mereciam estudo,
            quantas morreram depois do estudo pago. Cada gleba descartada por método caro
            consumiu dinheiro de diligência e semanas de calendário que não voltam.
          </p>
          <p>
            O custo maior está no que você deixou de fazer nesse tempo: o estoque de lotes que
            não se formou, a parceria que esfriou na espera, a área boa que outro levou. Em
            originação, o funil parado cobra juros de oportunidade todo mês.
          </p>
        </div>
      </section>

      {/* 4. A virada: Análise com Proveniência */}
      <section className="py-16">
        <div className="mx-auto max-w-2xl space-y-5 px-5 text-[17px] leading-relaxed text-slate-700">
          <h2 className="text-3xl font-bold tracking-tight text-slate-900">
            A virada: Análise com Proveniência
          </h2>
          <p>
            A Viabilidade homeeye roda a pré-análise da gleba em minutos a partir do KMZ, sobre
            um princípio que batizamos de <strong>Análise com Proveniência</strong>: todo número
            sai com a origem impressa ao lado, a lei que incide, o perfil de jurisdição aplicado
            e a data de referência.
          </p>
          <p>
            O motor cruza camadas oficiais (APP, vegetação e Mata Atlântica, declividade por
            faixas, hidrografia, unidades de conservação, entre outras) e aplica a regra legal
            por código: o traçado proposto se recusa a desenhar via sobre mata declarada (Lei
            11.428/2006) e distingue onde a declividade veda o lote da onde a via segue possível
            (Lei 6.766, art. 3º). O quadro de áreas fecha em 100%, com número de lotes, testada e
            área média, heatmap de valor e VGV no preço de m² que você define.
          </p>
          <p>
            O método antigo entrega opinião em formato de relatório: cada urbanista com uma
            régua, cada estudo num padrão, sem fonte ao lado do número. Aqui a régua é fixa e
            declarada: mesma entrada, mesma saída, para toda gleba do funil. Quando falta o
            perfil do seu município, a análise avisa e mostra a cobertura usada, em vez de fingir
            completude.
          </p>
        </div>
      </section>

      {/* 5. O que muda na sua operação */}
      <section className="bg-slate-50 py-16">
        <div className="mx-auto max-w-3xl px-5">
          <h2 className="text-center text-3xl font-bold tracking-tight">
            O que muda na sua operação
          </h2>
          <ul className="mt-8 grid gap-3 sm:grid-cols-2">
            {MUDANCAS.map((m) => (
              <li
                key={m}
                className="flex items-start gap-2.5 rounded-lg border border-slate-200 bg-white p-4 text-sm leading-relaxed text-slate-700"
              >
                <span className="mt-0.5 text-emerald-500">✔</span>
                {m}
              </li>
            ))}
          </ul>
        </div>
      </section>

      {/* 6. Veja o caminho inteiro */}
      <section className="py-16">
        <div className="mx-auto max-w-4xl px-5">
          <h2 className="text-center text-3xl font-bold tracking-tight">Veja o caminho inteiro</h2>
          <div className="mt-10 space-y-10">
            {CAMINHO.map((c, i) => (
              <div
                key={c.titulo}
                className={`grid items-center gap-6 md:grid-cols-2 ${
                  i % 2 === 1 ? "md:[&>*:first-child]:order-2" : ""
                }`}
              >
                <div>
                  <h3 className="text-lg font-semibold">
                    <span className="mr-2 text-emerald-600">{i + 1}.</span>
                    {c.titulo}
                  </h3>
                  <p className="mt-2 text-sm leading-relaxed text-slate-600">{c.texto}</p>
                </div>
                <PrintReal src={c.src} alt={c.titulo} />
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* 7. A prova é o produto */}
      <section className="bg-slate-900 py-16 text-white">
        <div className="mx-auto max-w-2xl px-5 text-center">
          <h2 className="text-3xl font-bold tracking-tight">A prova é o produto</h2>
          <p className="mt-4 leading-relaxed text-slate-300">
            Não vamos pedir que você acredite em depoimento. A prova da Viabilidade homeeye se
            verifica em dez minutos: crie a conta gratuita, suba uma gleba que você já conhece
            bem e compare o resultado com o que a realidade mostrou. A análise que erra por
            esconder, você descarta. A análise que mostra a fonte de cada número, você audita.
          </p>
        </div>
      </section>

      {/* 8. Planos */}
      <section id="planos" className="py-16">
        <div className="mx-auto max-w-3xl px-5">
          <h2 className="text-center text-3xl font-bold tracking-tight">Planos</h2>
          <div className="mt-8 rounded-2xl border border-slate-200 p-6">
            <LinhaPlanos />
            <p className="mt-4 text-xs leading-relaxed text-slate-500">
              Cada rodada de dimensão conta como 1 análise. Regenerar o urbanismo da mesma gleba,
              por exemplo, consome 1 análise.
            </p>
          </div>
          <div className="mt-8">
            <BotoesCta />
          </div>
        </div>
      </section>

      {/* 9. As objeções, de frente */}
      <section className="bg-slate-50 py-16">
        <div className="mx-auto max-w-3xl px-5">
          <h2 className="text-center text-3xl font-bold tracking-tight">As objeções, de frente</h2>
          <div className="mt-8 space-y-4">
            {OBJECOES.map((o) => (
              <div key={o.objecao} className="rounded-xl border border-slate-200 bg-white p-5">
                <h3 className="font-semibold">“{o.objecao}”</h3>
                <p className="mt-2 text-sm leading-relaxed text-slate-600">{o.quebra}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* 10. Risco reverso */}
      <section className="py-16">
        <div className="mx-auto max-w-2xl px-5 text-center">
          <h2 className="text-3xl font-bold tracking-tight">Risco reverso</h2>
          <p className="mt-4 leading-relaxed text-slate-600">
            O plano gratuito é permanente: 1 gleba por mês, até 5 análises, todas as dimensões,
            com proveniência. Você valida o método na sua área real, no seu ritmo, e assina
            quando o funil pedir mais. A decisão de pagar chega depois da prova.
          </p>
        </div>
      </section>

      {/* 11. FAQ operacional */}
      <section className="bg-slate-50 py-16">
        <div className="mx-auto max-w-3xl px-5">
          <h2 className="text-center text-3xl font-bold tracking-tight">Perguntas operacionais</h2>
          <div className="mt-8 space-y-3">
            {FAQ_OPERACIONAL.map((f) => (
              <details
                key={f.pergunta}
                className="group rounded-xl border border-slate-200 bg-white p-5"
              >
                <summary className="cursor-pointer list-none font-semibold marker:hidden">
                  {f.pergunta}
                </summary>
                <p className="mt-3 text-sm leading-relaxed text-slate-600">{f.resposta}</p>
              </details>
            ))}
          </div>
        </div>
      </section>

      {/* 12. Fechamento */}
      <section className="bg-slate-900 py-16 text-white">
        <div className="mx-auto max-w-3xl px-5 text-center">
          <h2 className="text-3xl font-bold tracking-tight">
            O próximo KMZ que chegar já pode ser decidido em 1 dia
          </h2>
          <p className="mt-4 leading-relaxed text-slate-300">
            Crie a conta gratuita agora e rode a primeira gleba hoje. Se quiser ver o fluxo com
            um especialista antes,{" "}
            <a href={LINK_DEMO} className="underline decoration-emerald-400 underline-offset-4">
              agende a demonstração online
            </a>
            .
          </p>
          <div className="mt-8">
            <BotoesCta escuro />
          </div>
          <p className="mt-6 text-xs text-slate-400">
            <Link href="/" className="hover:text-slate-200">
              ← Voltar para a página principal
            </Link>
          </p>
        </div>
      </section>

      <FooterSite />
    </div>
  );
}
