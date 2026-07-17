// Página de vendas — loteador em operação. Copy: docs/marketing/pagina-vendas.md v1.1.
// Redesign editorial premium (pedido do operador): pranchas SVG geradas pelo MOTOR REAL
// (replay do estudo de São Roque — 154 lotes, score v2 verdadeiro), tipografia display
// serifada (Fraunces), capítulos com rótulo lateral, banda de fatos, planos em cards,
// barra de CTA fixa e revelação suave ao rolar. Um único objetivo de conversão: criar conta.

import type { Metadata } from "next";
import Link from "next/link";
import { BarraCta } from "@/components/marketing/BarraCta";
import { PrintReal } from "@/components/marketing/PrintReal";
import { Reveal } from "@/components/marketing/Reveal";
import { BotoesCta, FooterSite, HeaderSite, LINK_DEMO } from "@/components/marketing/site";

export const metadata: Metadata = {
  title: "Viabilidade homeeye para loteadores | Triar 10 glebas no tempo de 1 estudo",
  description:
    "A pré-análise que corta do seu funil a gleba que morre na diligência, antes de você pagar o estudo caro por ela. Grátis: 1 gleba por mês, com até 5 análises.",
};

// Fatos REAIS (estudo de São Roque replayado pelo motor + arquitetura da plataforma).
const FATOS = [
  { numero: "154", rotulo: "lotes no estudo real ao lado, com a malha viária 100% conectada" },
  { numero: "4", rotulo: "dimensões numa régua só: ambiental, jurídica, urbanística, financeira" },
  { numero: "5.570", rotulo: "municípios cobertos pela base federal desde a primeira análise" },
  { numero: "100%", rotulo: "dos números com fonte legal, perfil e data de referência ao lado" },
];

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


// O tour tela a tela — prints REAIS da plataforma (gleba de São Roque). Os PNGs moram em
// public/marketing/print-*.png; enquanto um arquivo não existe, o PrintReal degrada para o
// quadro neutro. Números citados nas legendas vêm dos próprios prints (nada inventado).
const TOUR: {
  titulo: string;
  texto: string;
  itens?: string[];
  src: string;
  alt: string;
  legenda: string;
  selo: string;
}[] = [
  {
    titulo: "A visão geral sai em segundos",
    texto:
      "O KMZ vira painel: área total e aproveitável medidas por cálculo geodésico, contagem de lotes possível pela diretriz da zona e as restrições críticas já na primeira tela. O mapa liga e desliga as camadas oficiais sobre a foto de satélite.",
    src: "/marketing/print-visao-geral.png",
    alt: "Painel de visão geral: área total, aproveitável, lotes e restrições críticas sobre o mapa",
    legenda: "Gleba real: 18,71 ha, 13,48 ha aproveitáveis e 2 restrições críticas na 1ª tela",
    selo: "Print real",
  },
  {
    titulo: "Ambiental multicamada, com fonte em cada alerta",
    texto:
      "Cada camada oficial é cruzada com a gleba por interseção espacial e vira alerta com a área atingida, a fonte e a data de referência. No exemplo real: concessão de lavra da ANM com número de processo, três Reservas Legais averbadas no CAR e o domínio da Mata Atlântica (Lei 11.428/2006).",
    itens: [
      "APP e hidrografia",
      "Massas d'água",
      "Vegetação e Mata Atlântica",
      "Unidades de conservação",
      "Reserva Legal (CAR)",
      "Mineração (ANM)",
      "Terras indígenas",
      "Territórios quilombolas",
      "Assentamentos (INCRA)",
      "Linhas de transmissão (ANEEL)",
      "Dutovias",
      "Cavernas (CECAV)",
      "Mananciais",
      "Áreas úmidas",
      "Malha fundiária (SIGEF/SNCI)",
      "Patrimônio cultural (IPHAN)",
      "Áreas contaminadas (CETESB)",
    ],
    src: "/marketing/print-ambiental.png",
    alt: "Alertas ambientais com fonte e data: ANM, Reserva Legal do CAR e Mata Atlântica",
    legenda: "5 alertas com proveniência: processo ANM, CAR e Lei 11.428, com fonte e data",
    selo: "Print real",
  },
  {
    titulo: "Declividade por faixas, com a vedação legal",
    texto:
      "O relevo sai do modelo digital de elevação em oito faixas, com a vedação legal de ≥30% (Lei 6.766/79) descontada da área aproveitável e uma leitura de mobilidade urbana por faixa. No exemplo, relevo forte ondulado com 20,73% de média: exatamente o tipo de terreno onde errar a conta custa caro.",
    src: "/marketing/print-declividade.png",
    alt: "Análise de declividade: faixas coloridas, vedação legal e leitura de mobilidade",
    legenda: "8 faixas de declividade + análise de mobilidade sobre a gleba real",
    selo: "Print real",
  },
  {
    titulo: "Área verde, bioma e severidade",
    texto:
      "A cobertura vegetal é medida por satélite e descontada do aproveitável, separando a restrição dura (APP/UC) do verde a verificar, com o potencial desbloqueável mediante laudo de engenheiro ambiental. O bioma entra com fonte IBGE, e a área líquida canônica é a mesma nas abas de Aproveitamento e Urbanismo.",
    src: "/marketing/print-area-verde.png",
    alt: "Análise de área verde: bioma Mata Atlântica, verde descontado e severidade",
    legenda: "4,97 ha de verde descontado, 100% classificado como 'a verificar' (desbloqueável)",
    selo: "Print real",
  },
  {
    titulo: "O pré-projeto urbanístico completo",
    texto:
      "O motor desenha o estudo de massa respeitando a lei: vias que contornam a mata, cul-de-sacs onde a diretriz exige, pórtico, lago e quadro de áreas fechando em 100%. Você controla as variações: tipo de loteamento, público-alvo, lote-alvo dentro da faixa legal da zona e o objetivo Rendimento ou Paisagem.",
    itens: [
      "Arruamento em malha conexa",
      "Áreas verdes e doação",
      "Sistema de lazer e clube",
      "Institucional",
      "Heatmap por quintis",
      "Score de valor por lote",
      "VGV posicional",
      "Testada e área média",
    ],
    src: "/marketing/print-urbanismo.png",
    alt: "Parcelamento esquemático: lotes coloridos por valorização, verde, lazer, pórtico e lago",
    legenda: "Parcelamento real: lotes por quintil de valor, mata preservada, lazer e lago",
    selo: "Print real",
  },
  {
    titulo: "Jurídico: matrículas lidas e riscos nomeados",
    texto:
      "A pré-análise documental lê matrícula e certidões, lista ônus e averbações com a referência ao ato e à página, soma as áreas das matrículas e compara com o KMZ apontando divergência. Nada entra na síntese sem a sua confirmação: é pré-análise com gate humano, não parecer de advogado.",
    itens: [
      "Ônus e gravames com o ato",
      "Averbações",
      "Divergência de área × KMZ",
      "Checklist de documentos",
      "Semáforo de risco",
      "O que verificar com advogado",
    ],
    src: "/marketing/print-juridico.png",
    alt: "Pré-análise jurídica: matrículas lidas, ônus com referência ao ato e divergência de área",
    legenda: "2 matrículas reais lidas: ônus com ato e página, divergência de 39,5% apontada",
    selo: "Print real",
  },
  {
    titulo: "Financeira: do VGV ao fluxo, em seis passos",
    texto:
      "Um guiado de seis perguntas monta o fluxo do empreendimento: VGV com venda financiada, margem, exposição máxima de caixa, VPL, TIR e payback sob as premissas que você declara, além da divisão incorporador × terrenista para a conversa de parceria. O semáforo lê o resultado sob as suas premissas: pré-análise, não veredito.",
    itens: [
      "VGV nominal + juros",
      "Margem",
      "Exposição máxima de caixa",
      "VPL e TIR",
      "Payback simples e descontado",
      "Divisão da parceria",
    ],
    src: "/marketing/print-financeira.png",
    alt: "Análise financeira guiada: VGV, margem, exposição de caixa, VPL, TIR e divisão da parceria",
    legenda: "Fluxo real montado: VGV, margem, exposição e VPL/TIR sob premissas declaradas",
    selo: "Print real",
  },
];

// Rótulo lateral de capítulo (editorial long-form).
function Capitulo({
  numero,
  titulo,
  children,
  nota,
}: {
  numero: string;
  titulo: string;
  children: React.ReactNode;
  nota?: string;
}) {
  return (
    <div className="mx-auto grid max-w-5xl gap-8 px-5 md:grid-cols-[200px,1fr] md:gap-14">
      <div className="md:sticky md:top-24 md:self-start">
        <p className="text-xs font-semibold uppercase tracking-[0.25em] text-[#a4744d]">
          Capítulo {numero}
        </p>
        <h2 className="font-display mt-2 text-2xl leading-snug text-[#1c2a24]">{titulo}</h2>
        {nota && <p className="mt-3 text-xs italic text-[#9a937f]">{nota}</p>}
      </div>
      <div className="space-y-5 text-[17px] leading-[1.75] text-[#3c4a42]">{children}</div>
    </div>
  );
}

// Prancha do motor com moldura de prancheta (legenda + selo de origem).
function Prancha({
  src,
  alt,
  titulo,
  selo,
}: {
  src: string;
  alt: string;
  titulo: string;
  selo: string;
}) {
  return (
    <figure className="overflow-hidden rounded-2xl border border-[#e2dac6] bg-[#fdfbf5] shadow-xl shadow-[#1b4332]/10">
      <PrintReal src={src} alt={alt} className="[&_img]:rounded-none [&_img]:border-0 [&_img]:shadow-none [&_figure]:rounded-none [&_figure]:border-0" />
      <figcaption className="flex items-center justify-between gap-3 border-t border-[#eee7d4] px-4 py-2.5">
        <span className="text-xs font-medium text-[#5a5546]">{titulo}</span>
        <span className="rounded-full bg-[#1b4332]/10 px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-[#1b4332]">
          {selo}
        </span>
      </figcaption>
    </figure>
  );
}

export default function PaginaLoteadores() {
  return (
    <div className="bg-[#f7f3ea] text-[#1c2a24]">
      <HeaderSite />

      {/* 1. Abertura (dor + Promessa) */}
      <section className="relative overflow-hidden bg-[#16241f] pb-20 pt-16 text-white">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 opacity-[0.16]"
          style={{
            backgroundImage:
              "repeating-radial-gradient(ellipse at 85% 15%, transparent 0 54px, #7ba98e 54px 55px)",
          }}
        />
        <div className="relative mx-auto grid max-w-6xl items-center gap-12 px-5 lg:grid-cols-[1.05fr,1fr]">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.3em] text-[#9cc0ab]">
              Para quem vive de originar áreas
            </p>
            <h1 className="font-display mt-5 text-[2.6rem] font-medium leading-[1.08] text-[#f6f1e2] sm:text-6xl">
              Triar 10 glebas no tempo de 1 estudo tradicional
            </h1>
            <p className="mt-6 max-w-xl text-lg leading-relaxed text-[#c9d4c9]">
              A pré-análise que corta do seu funil a gleba que morre na diligência, antes de
              você pagar o estudo caro por ela.
            </p>
            <div className="mt-9 flex flex-col items-start gap-3 sm:flex-row">
              <Link
                href="/registrar"
                className="inline-flex h-12 items-center rounded-xl bg-[#e9dfc4] px-7 text-base font-semibold text-[#16241f] shadow-lg shadow-black/30 transition hover:bg-[#f3ecd8]"
              >
                Criar conta grátis
              </Link>
              <a
                href={LINK_DEMO}
                className="inline-flex h-12 items-center rounded-xl border border-[#4a6557] px-7 text-base font-semibold text-[#e6e0cd] transition hover:bg-[#22362d]"
              >
                Agendar demonstração online
              </a>
            </div>
            <p className="mt-4 text-sm text-[#8fa396]">
              Grátis: 1 gleba por mês, com até 5 análises.
            </p>
          </div>
          <Reveal>
            <div className="rotate-[0.6deg]">
              <Prancha
                src="/marketing/plano-masterplan.svg"
                alt="Masterplan gerado pelo motor sobre a gleba real de São Roque: 154 lotes, vias contornando a mata, lago e áreas verdes"
                titulo="Gleba de 18,7 ha · São Roque SP · 154 lotes · mata intocada"
                selo="Saída real do motor"
              />
            </div>
          </Reveal>
        </div>
      </section>

      {/* Banda de fatos */}
      <section className="border-b border-[#e2dac6] bg-[#f3efe4]">
        <div className="mx-auto grid max-w-6xl gap-8 px-5 py-10 sm:grid-cols-2 lg:grid-cols-4">
          {FATOS.map((f, i) => (
            <Reveal key={f.numero} atraso={i * 90}>
              <p className="font-display text-4xl text-[#1b4332]">{f.numero}</p>
              <p className="mt-2 text-[13px] leading-relaxed text-[#5a5546]">{f.rotulo}</p>
            </Reveal>
          ))}
        </div>
      </section>

      {/* 2. A cena que você conhece */}
      <section className="py-20">
        <Reveal>
          <Capitulo numero="01" titulo="A cena que você conhece" nota="Cenário ilustrativo.">
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
            <blockquote className="font-display border-l-2 border-[#a4744d] py-1 pl-6 text-[26px] leading-snug text-[#1b4332]">
              Enquanto isso, a área boa daquele mês foi para o concorrente que respondeu em três
              dias. A diferença foi a velocidade de dizer sim.
            </blockquote>
            <p>
              Quem origina área vive esse ciclo: pagar caro para descartar, demorar para aprovar,
              e perder a boa por causa das ruins. O problema nunca foi o seu faro. É o custo e a
              lentidão de cada verificação.
            </p>
          </Capitulo>
        </Reveal>
      </section>

      {/* 3. O custo de continuar assim */}
      <section className="bg-[#efe8d9] py-20">
        <Reveal>
          <Capitulo numero="02" titulo="O custo de continuar assim">
            <p>
              Faça a conta do seu último ano: quantas áreas chegaram, quantas mereciam estudo,
              quantas morreram depois do estudo pago. Cada gleba descartada por método caro
              consumiu dinheiro de diligência e semanas de calendário que não voltam.
            </p>
            <div className="rounded-2xl border border-[#ddd2b8] bg-[#faf6ec] p-6">
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[#a4744d]">
                A conta invisível do ano
              </p>
              <ul className="mt-4 space-y-3 text-[15px]">
                {[
                  "Estudos pagos por glebas que morreram na primeira restrição",
                  "Semanas de espera em cada resposta que o corretor precisava em dias",
                  "A área boa do trimestre, levada por quem respondeu antes",
                  "Horas sênior da equipe queimadas descartando mico",
                ].map((item) => (
                  <li key={item} className="flex items-start gap-3">
                    <span className="mt-1 text-[#b25b38]">✕</span>
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>
            <p>
              O custo maior está no que você deixou de fazer nesse tempo: o estoque de lotes que
              não se formou, a parceria que esfriou na espera. Em originação, o funil parado
              cobra juros de oportunidade todo mês.
            </p>
          </Capitulo>
        </Reveal>
      </section>

      {/* 4. A virada: Análise com Proveniência */}
      <section className="bg-[#16241f] py-20 text-[#d8d2c0]">
        <Reveal>
          <div className="mx-auto grid max-w-5xl gap-10 px-5 md:grid-cols-[200px,1fr] md:gap-14">
            <div className="md:sticky md:top-24 md:self-start">
              <p className="text-xs font-semibold uppercase tracking-[0.25em] text-[#a4744d]">
                Capítulo 03
              </p>
              <h2 className="font-display mt-2 text-2xl leading-snug text-[#f6f1e2]">
                A virada: Análise com Proveniência
              </h2>
            </div>
            <div className="space-y-5 text-[17px] leading-[1.75]">
              <p>
                A Viabilidade homeeye roda a pré-análise da gleba em minutos a partir do KMZ,
                sobre um princípio que batizamos de{" "}
                <strong className="text-[#f6f1e2]">Análise com Proveniência</strong>: todo número
                sai com a origem impressa ao lado, a lei que incide, o perfil de jurisdição
                aplicado e a data de referência.
              </p>
              {/* Chip de proveniência — o conceito central, mostrado como o produto mostra */}
              <div className="rounded-2xl border border-[#33503f] bg-[#1d3229] p-5">
                <p className="font-display text-3xl text-[#f6f1e2]">52.253,23 m²</p>
                <p className="mt-1 text-sm text-[#c9d4c9]">
                  Mata/APP preservada (não-edificável) · 27,9% da gleba bruta
                </p>
                <p className="mt-3 border-t border-[#33503f] pt-3 text-xs text-[#8fa396]">
                  Fonte: Lei 11.428/2006 (Mata Atlântica) · Lei 12.651/2012 (Código Florestal) ·
                  perfil São Roque/SP · data de referência da análise
                </p>
                <p className="mt-2 text-[11px] italic text-[#6f8577]">
                  Número real do estudo de São Roque. É assim que cada valor sai do relatório.
                </p>
              </div>
              <p>
                O motor cruza camadas oficiais (APP, vegetação e Mata Atlântica, declividade por
                faixas, hidrografia, unidades de conservação, entre outras) e aplica a regra
                legal por código: o traçado proposto se recusa a desenhar via sobre mata
                declarada (Lei 11.428/2006) e distingue onde a declividade veda o lote da onde a
                via segue possível (Lei 6.766, art. 3º). O quadro de áreas fecha em 100%.
              </p>
              <p>
                O método antigo entrega opinião em formato de relatório: cada urbanista com uma
                régua, cada estudo num padrão, sem fonte ao lado do número. Aqui a régua é fixa e
                declarada: mesma entrada, mesma saída, para toda gleba do funil. Quando falta o
                perfil do seu município, a análise avisa e mostra a cobertura usada, em vez de
                fingir completude.
              </p>
            </div>
          </div>
        </Reveal>
      </section>

      {/* 5. O caminho inteiro, tela a tela (prints reais + pranchas do motor) */}
      <section className="py-20">
        <div className="mx-auto max-w-6xl px-5">
          <Reveal>
            <p className="text-center text-xs font-semibold uppercase tracking-[0.25em] text-[#a4744d]">
              Capítulo 04
            </p>
            <h2 className="font-display mx-auto mt-2 max-w-2xl text-center text-3xl leading-snug">
              O caminho inteiro, tela a tela
            </h2>
            <p className="mx-auto mt-3 max-w-2xl text-center text-sm text-[#7d786a]">
              Tudo abaixo é a plataforma de verdade rodando sobre uma gleba real de São Roque ·
              SP: prints da interface e desenhos gerados pelo motor. Nada foi montado à mão.
            </p>
          </Reveal>

          <div className="mt-14 space-y-16">
            {TOUR.map((etapa, i) => (
              <Reveal key={etapa.titulo}>
                <div
                  className={`grid items-center gap-8 md:grid-cols-2 ${
                    i % 2 === 1 ? "md:[&>*:first-child]:order-2" : ""
                  }`}
                >
                  <div>
                    <p className="font-display text-xl text-[#a4744d]">{i + 1}</p>
                    <h3 className="font-display mt-1 text-2xl">{etapa.titulo}</h3>
                    <p className="mt-3 leading-relaxed text-[#3c4a42]">{etapa.texto}</p>
                    {etapa.itens && (
                      <ul className="mt-4 flex flex-wrap gap-1.5">
                        {etapa.itens.map((it) => (
                          <li
                            key={it}
                            className="rounded-full border border-[#d8cfb8] bg-[#faf6ec] px-2.5 py-1 text-[11px] font-medium text-[#5a5546]"
                          >
                            {it}
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                  <Prancha
                    src={etapa.src}
                    alt={etapa.alt}
                    titulo={etapa.legenda}
                    selo={etapa.selo}
                  />
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* 6. O que muda na operação */}
      <section className="bg-[#efe8d9] py-20">
        <div className="mx-auto max-w-5xl px-5">
          <Reveal>
            <h2 className="font-display text-center text-3xl">O que muda na sua operação</h2>
          </Reveal>
          <ul className="mt-10 grid gap-3 sm:grid-cols-2">
            {MUDANCAS.map((m, i) => (
              <Reveal key={m} atraso={(i % 2) * 80}>
                <li className="flex items-start gap-3 rounded-xl border border-[#ddd2b8] bg-[#faf6ec] p-4 text-[15px] leading-relaxed text-[#3c4a42]">
                  <span className="mt-0.5 font-semibold text-[#1b4332]">✓</span>
                  {m}
                </li>
              </Reveal>
            ))}
          </ul>
        </div>
      </section>

      {/* 7. A prova é o produto */}
      <section className="py-20">
        <Reveal>
          <div className="mx-auto max-w-3xl px-5 text-center">
            <p className="text-xs font-semibold uppercase tracking-[0.25em] text-[#a4744d]">
              A prova é o produto
            </p>
            <p className="font-display mt-6 text-[28px] leading-snug text-[#1b4332]">
              Não vamos pedir que você acredite em depoimento. Crie a conta gratuita, suba uma
              gleba que você conhece bem e compare o resultado com o que a realidade mostrou.
            </p>
            <p className="mt-5 text-[15px] leading-relaxed text-[#5a5546]">
              A análise que erra por esconder, você descarta. A análise que mostra a fonte de
              cada número, você audita.
            </p>
          </div>
        </Reveal>
      </section>

      {/* 8. Planos */}
      <section id="planos" className="bg-[#16241f] py-20">
        <div className="mx-auto max-w-4xl px-5">
          <Reveal>
            <h2 className="font-display text-center text-3xl text-[#f6f1e2]">Planos</h2>
            <p className="mt-3 text-center text-sm text-[#8fa396]">
              Cada rodada de dimensão conta como 1 análise. Regenerar o urbanismo da mesma gleba
              consome 1 análise.
            </p>
          </Reveal>
          <div className="mt-10 grid gap-6 md:grid-cols-2">
            <Reveal>
              <div className="flex h-full flex-col rounded-2xl border border-[#33503f] bg-[#1d3229] p-7">
                <h3 className="font-display text-xl text-[#f6f1e2]">Gratuito</h3>
                <p className="font-display mt-4 text-4xl text-[#f6f1e2]">R$ 0,00</p>
                <ul className="mt-6 flex-1 space-y-2.5 text-sm text-[#c9d4c9]">
                  <li>1 gleba por mês (fixa no mês)</li>
                  <li>Até 5 análises, somando as dimensões</li>
                  <li>Todas as dimensões: ambiental, jurídica, urbanística, financeira</li>
                  <li>Proveniência em todo número</li>
                </ul>
                <Link
                  href="/registrar"
                  className="mt-7 inline-flex h-11 items-center justify-center rounded-xl border border-[#4a6557] text-sm font-semibold text-[#e6e0cd] transition hover:bg-[#22362d]"
                >
                  Começar de graça
                </Link>
              </div>
            </Reveal>
            <Reveal atraso={120}>
              <div className="relative flex h-full flex-col rounded-2xl border-2 border-[#e9dfc4] bg-[#f7f3ea] p-7 shadow-2xl shadow-black/30">
                <span className="absolute -top-3 left-6 rounded-full bg-[#a4744d] px-3 py-1 text-[11px] font-bold uppercase tracking-wider text-white">
                  Para a operação
                </span>
                <h3 className="font-display text-xl text-[#1c2a24]">Assinatura anual</h3>
                <p className="font-display mt-4 text-4xl text-[#1b4332]">Fale com a gente</p>
                <ul className="mt-6 flex-1 space-y-2.5 text-sm text-[#3c4a42]">
                  <li>200 áreas por ano</li>
                  <li>600 análises por ano (cerca de 12 glebas completas por mês)</li>
                  <li>Todas as dimensões, com proveniência</li>
                  <li>Feita para o funil de originação girar sem fila</li>
                </ul>
                <a
                  href={LINK_DEMO}
                  className="mt-7 inline-flex h-11 items-center justify-center rounded-xl bg-[#1b4332] text-sm font-semibold text-[#f3ecd8] transition hover:bg-[#16382a]"
                >
                  Agendar demonstração online
                </a>
              </div>
            </Reveal>
          </div>
        </div>
      </section>

      {/* 9. Objeções */}
      <section className="py-20">
        <div className="mx-auto max-w-3xl px-5">
          <Reveal>
            <h2 className="font-display text-center text-3xl">As objeções, de frente</h2>
          </Reveal>
          <div className="mt-10 space-y-3">
            {OBJECOES.map((o, i) => (
              <Reveal key={o.objecao} atraso={i * 60}>
                <details className="group rounded-2xl border border-[#e2dac6] bg-[#fdfbf5] p-6 open:shadow-lg open:shadow-[#1b4332]/5">
                  <summary className="font-display cursor-pointer list-none text-lg leading-snug text-[#1c2a24] marker:hidden">
                    “{o.objecao}”
                    <span className="float-right text-[#a4744d] transition group-open:rotate-45">
                      +
                    </span>
                  </summary>
                  <p className="mt-4 text-[15px] leading-[1.75] text-[#3c4a42]">{o.quebra}</p>
                </details>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* 10. Risco reverso */}
      <section className="bg-[#efe8d9] py-16">
        <Reveal>
          <div className="mx-auto max-w-2xl px-5 text-center">
            <h2 className="font-display text-2xl">Risco reverso</h2>
            <p className="mt-4 leading-relaxed text-[#3c4a42]">
              O plano gratuito é permanente: 1 gleba por mês, até 5 análises, todas as
              dimensões, com proveniência. Você valida o método na sua área real, no seu ritmo,
              e assina quando o funil pedir mais. A decisão de pagar chega depois da prova.
            </p>
          </div>
        </Reveal>
      </section>

      {/* 11. FAQ operacional */}
      <section className="py-20">
        <div className="mx-auto max-w-3xl px-5">
          <Reveal>
            <h2 className="font-display text-center text-3xl">Perguntas operacionais</h2>
          </Reveal>
          <div className="mt-10 space-y-3">
            {FAQ_OPERACIONAL.map((f) => (
              <details
                key={f.pergunta}
                className="rounded-xl border border-[#e2dac6] bg-[#fdfbf5] p-5"
              >
                <summary className="cursor-pointer list-none font-semibold marker:hidden">
                  {f.pergunta}
                </summary>
                <p className="mt-3 text-sm leading-relaxed text-[#3c4a42]">{f.resposta}</p>
              </details>
            ))}
          </div>
        </div>
      </section>

      {/* 12. Fechamento */}
      <section className="bg-[#16241f] py-20 text-white">
        <Reveal>
          <div className="mx-auto max-w-3xl px-5 text-center">
            <h2 className="font-display text-4xl leading-tight text-[#f6f1e2]">
              O próximo KMZ que chegar já pode ser decidido em 1 dia
            </h2>
            <p className="mt-5 leading-relaxed text-[#c9d4c9]">
              Crie a conta gratuita agora e rode a primeira gleba hoje. Se quiser ver o fluxo
              com um especialista antes, agende a demonstração online.
            </p>
            <div className="mt-9">
              <BotoesCta escuro />
            </div>
            <p className="mt-8 text-xs text-[#6f8577]">
              <Link href="/" className="transition hover:text-[#c9d4c9]">
                ← Voltar para a página principal
              </Link>
            </p>
          </div>
        </Reveal>
      </section>

      <FooterSite />
      <BarraCta texto="Triar 10 glebas no tempo de 1 estudo tradicional." />
      {/* respiro para a barra fixa não cobrir o rodapé */}
      <div className="h-16" />
    </div>
  );
}
