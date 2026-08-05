// Página de PREÇOS para validação no MVP (v1.3 do plano de marketing) — NÃO LISTADA:
// sem link em menu/rodapé, fora do sitemap e com noindex. Só quem recebe a URL vê.
// Fonte única dos valores: docs/marketing/plano-marketing-vendas.md (Quadro v1.3).
// Copy em Light Copy (sem travessão, sem exclamação). Paleta e casca do site público.

import type { Metadata } from "next";
import Link from "next/link";
import { Reveal } from "@/components/marketing/Reveal";
import { FooterSite, HeaderSite, LINK_DEMO } from "@/components/marketing/site";

export const metadata: Metadata = {
  title: "Planos e preços | voaz.app",
  description: "Planos e preços da voaz.app em validação com participantes do MVP.",
  robots: { index: false, follow: false },
};

// As 4 ofertas do Quadro v1.3. Qualquer mudança de preço acontece PRIMEIRO no documento
// de marketing e depois aqui, nunca só aqui.
const PLANOS = [
  {
    nome: "Gratuito",
    preco: "R$ 0",
    parcelas: "para sempre",
    porGleba: null,
    selo: null,
    destaque: false,
    resumo: "Conhecer a plataforma na sua própria gleba",
    itens: [
      "1 gleba nova por mês",
      "1 rodada de cada dimensão determinística",
      "Urbanismo com IA: 1 geração por gleba",
      "Diretriz municipal (LUOS): 1 município novo por mês",
      "Pré-análise jurídica: 1 rodada por gleba",
      "Resultado completo na tela, com marca d'água",
    ],
    naoInclui: ["Laudo PDF e Excel", "Variantes e regeneração do urbanismo", "Importação de DWG"],
    cta: { rotulo: "Começar de graça", href: "/registrar", externo: false },
  },
  {
    nome: "Pacote 5 glebas",
    preco: "R$ 597",
    parcelas: "ou 3× de R$ 199 no cartão",
    porGleba: "R$ 119 por gleba",
    selo: null,
    destaque: false,
    resumo: "Para quem paga quando tem área na mão",
    itens: [
      "5 glebas, créditos válidos por 12 meses",
      "Análises ilimitadas nas glebas do saldo",
      "Urbanismo com IA ilimitado: regenerar, variantes, Rendimento × Paisagem",
      "Pré-análise jurídica completa",
      "Importação de projeto pronto (DWG) e levantamento planialtimétrico",
      "Laudo PDF e Excel, sem marca d'água",
    ],
    naoInclui: [],
    cta: { rotulo: "Falar com a gente", href: LINK_DEMO, externo: true },
  },
  {
    nome: "Assinatura semestral",
    preco: "R$ 1.194",
    parcelas: "em 6× de R$ 199 no cartão",
    porGleba: "R$ 99 por gleba",
    selo: "Para a operação",
    destaque: true,
    resumo: "Para o loteador com funil girando",
    itens: [
      "12 glebas no semestre, saldo do período inteiro",
      "Tudo do Pacote 5 glebas, ilimitado nas glebas do saldo",
      "Cota sem expiração mensal: use no seu ritmo dentro do semestre",
      "Estourou o saldo? O Pacote 5 soma mais glebas na hora",
    ],
    naoInclui: [],
    cta: { rotulo: "Falar com a gente", href: LINK_DEMO, externo: true },
  },
  {
    nome: "Assinatura anual",
    preco: "R$ 2.148",
    parcelas: "em 12× de R$ 179 no cartão",
    porGleba: "R$ 72 por gleba",
    selo: "Menor preço por gleba",
    destaque: false,
    resumo: "Para quem quer a gleba mais barata do cardápio",
    itens: [
      "30 glebas no ano, saldo do período inteiro",
      "Tudo do Pacote 5 glebas, ilimitado nas glebas do saldo",
      "Cota sem expiração mensal: use no seu ritmo dentro do ano",
      "Estourou o saldo? O Pacote 5 soma mais glebas na hora",
    ],
    naoInclui: [],
    cta: { rotulo: "Falar com a gente", href: LINK_DEMO, externo: true },
  },
];

// Tabela comparativa (linhas do Quadro v1.3). Célula string simples; "—" vira "Não".
const COMPARATIVO: { rotulo: string; valores: [string, string, string, string] }[] = [
  { rotulo: "Preço", valores: ["R$ 0", "R$ 597 (até 3× R$ 199)", "R$ 1.194 (6× R$ 199)", "R$ 2.148 (12× R$ 179)"] },
  { rotulo: "Glebas incluídas", valores: ["1 nova por mês", "5", "12 no semestre", "30 no ano"] },
  { rotulo: "Preço por gleba", valores: ["R$ 0", "~R$ 119", "~R$ 99", "~R$ 72"] },
  {
    rotulo: "Vigência",
    valores: ["permanente", "créditos valem 12 meses", "6 meses (saldo do período)", "12 meses (saldo do período)"],
  },
  {
    rotulo: "Dimensões determinísticas (ambiental, declividade, vegetação, aproveitamento, financeiro, econômico, localização)",
    valores: ["1 rodada de cada por gleba", "Ilimitadas nas glebas do saldo", "Ilimitadas", "Ilimitadas"],
  },
  {
    rotulo: "Urbanismo com IA",
    valores: [
      "1 geração por gleba, sem regenerar",
      "Ilimitado: regenerar, variantes, Rendimento × Paisagem",
      "Ilimitado",
      "Ilimitado",
    ],
  },
  { rotulo: "Diretriz municipal (LUOS)", valores: ["Sim, 1 município novo por mês", "Sim", "Sim", "Sim"] },
  { rotulo: "Pré-análise jurídica", valores: ["1 rodada por gleba", "Completa", "Completa", "Completa"] },
  { rotulo: "Importar projeto pronto (DWG)", valores: ["Não", "Sim", "Sim", "Sim"] },
  { rotulo: "Levantamento planialtimétrico (DWG das matrículas)", valores: ["Não", "Sim", "Sim", "Sim"] },
  {
    rotulo: "Laudo PDF e Excel",
    valores: ["Não (só na tela, marca d'água)", "Sim, sem marca d'água", "Sim", "Sim"],
  },
  {
    rotulo: "Comprar mais glebas",
    valores: ["Não", "Outro pacote", "Pacote 5 soma ao saldo", "Pacote 5 soma ao saldo"],
  },
  {
    rotulo: "Para quem",
    valores: [
      "Conhecer a plataforma na própria gleba",
      "Corretor, incorporador, entrante",
      "Loteador em operação",
      "Quem quer o menor preço por gleba",
    ],
  },
];

const CONDICOES = [
  {
    titulo: "A unidade é a gleba, não a análise",
    texto:
      "Dentro de uma gleba do saldo o uso é livre: reanalisar dimensões, regenerar o urbanismo, testar variantes e anexar DWG não consomem crédito. Iterar até a decisão é o diferencial contra o estudo encomendado.",
  },
  {
    titulo: "Parcelamento no cartão",
    texto:
      "As parcelas são no cartão de crédito, via link de pagamento. No Pix o valor é à vista. Em todas as portas pagas a parcela parte de R$ 199 ou menos.",
  },
  {
    titulo: "Saldo do período, não cota mensal",
    texto:
      "Nas assinaturas as glebas valem pelo período inteiro (semestre ou ano). Nenhuma cota expira no fim do mês: funil de gleba é irregular e o plano respeita isso.",
  },
  {
    titulo: "Assinante que precisa de mais",
    texto:
      "O Pacote 5 glebas soma ao saldo de qualquer assinatura, a qualquer momento, pelo mesmo preço de tabela.",
  },
];

function CardPlano({ plano }: { plano: (typeof PLANOS)[number] }) {
  const Cta = plano.cta.externo ? (
    <a
      href={plano.cta.href}
      className={`mt-7 inline-flex h-11 items-center justify-center rounded-xl text-sm font-semibold transition ${
        plano.destaque
          ? "bg-[#ff914d] text-[#170d48] hover:bg-[#db6b1a] hover:text-white"
          : "bg-[#241862] text-[#fff4f4] hover:bg-[#1d1252]"
      }`}
    >
      {plano.cta.rotulo}
    </a>
  ) : (
    <Link
      href={plano.cta.href}
      className="mt-7 inline-flex h-11 items-center justify-center rounded-xl border border-[#241862] text-sm font-semibold text-[#241862] transition hover:bg-[#241862] hover:text-[#fff4f4]"
    >
      {plano.cta.rotulo}
    </Link>
  );
  return (
    <div
      className={`relative flex h-full flex-col rounded-2xl p-7 ${
        plano.destaque
          ? "border-2 border-[#ff914d] bg-white shadow-2xl shadow-[#241862]/15"
          : "border border-[#f3e9e0] bg-[#fdfbf5] shadow-lg shadow-[#241862]/5"
      }`}
    >
      {plano.selo && (
        <span
          className={`absolute -top-3 left-6 rounded-full px-3 py-1 text-[11px] font-bold uppercase tracking-wider ${
            plano.destaque ? "bg-[#ff914d] text-white" : "bg-[#241862] text-[#fff4f4]"
          }`}
        >
          {plano.selo}
        </span>
      )}
      <h3 className="font-display text-xl text-[#1d1252]">{plano.nome}</h3>
      <p className="mt-1 text-[13px] text-[#96796a]">{plano.resumo}</p>
      <p className="font-display mt-5 text-4xl text-[#241862]">{plano.preco}</p>
      <p className="mt-1 text-sm text-[#5b4a3e]">{plano.parcelas}</p>
      {plano.porGleba && (
        <p className="mt-2 inline-flex w-fit rounded-full bg-[#241862]/10 px-3 py-1 text-xs font-semibold text-[#241862]">
          {plano.porGleba}
        </p>
      )}
      <ul className="mt-6 flex-1 space-y-2.5 text-sm text-[#4a3f7a]">
        {plano.itens.map((item) => (
          <li key={item} className="flex items-start gap-2.5">
            <span className="mt-0.5 font-semibold text-[#241862]">✓</span>
            <span>{item}</span>
          </li>
        ))}
        {plano.naoInclui.map((item) => (
          <li key={item} className="flex items-start gap-2.5 text-[#96796a]">
            <span className="mt-0.5">✕</span>
            <span>{item}</span>
          </li>
        ))}
      </ul>
      {Cta}
    </div>
  );
}

export default function PaginaPlanosMvp() {
  return (
    <div className="bg-[#fbf6f1] text-[#1d1252]">
      <HeaderSite />

      {/* Faixa de contexto do MVP: esta página existe para VALIDAR os valores */}
      <div className="border-b border-[#f0d9c4] bg-[#fff4f4] px-5 py-3 text-center text-[13px] text-[#5b4a3e]">
        <span className="mr-2 rounded-full bg-[#ff914d] px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-white">
          Prévia do MVP
        </span>
        Estes planos estão em validação com os primeiros clientes. O seu retorno define a tabela
        final.
      </div>

      {/* Abertura */}
      <section className="bg-[#170d48] px-5 pb-16 pt-14 text-center text-white">
        <Reveal>
          <p className="text-xs font-semibold uppercase tracking-[0.3em] text-[#ffad78]">
            Planos e preços
          </p>
          <h1 className="font-display mx-auto mt-4 max-w-3xl text-4xl leading-tight text-[#fffafa] sm:text-5xl">
            Pague por gleba analisada, não por mês de ansiedade
          </h1>
          <p className="mx-auto mt-5 max-w-2xl text-lg leading-relaxed text-[#c3b8e8]">
            A unidade é a gleba: dentro de cada uma, análises e iterações livres. Quanto mais
            compromisso, mais barata a gleba: R$ 119 no pacote, R$ 99 na semestral, R$ 72 na
            anual.
          </p>
        </Reveal>
      </section>

      {/* Cards dos 4 planos */}
      <section className="mx-auto max-w-7xl px-5 py-14">
        <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-4">
          {PLANOS.map((p, i) => (
            <Reveal key={p.nome} atraso={i * 90}>
              <CardPlano plano={p} />
            </Reveal>
          ))}
        </div>
        <p className="mt-6 text-center text-xs text-[#96796a]">
          Parcelas no cartão de crédito, via link de pagamento. Pix à vista.
        </p>
      </section>

      {/* Tabela comparativa */}
      <section className="bg-[#fff4f4] py-16">
        <div className="mx-auto max-w-6xl px-5">
          <Reveal>
            <h2 className="font-display text-center text-3xl">Os planos lado a lado</h2>
            <p className="mt-3 text-center text-sm text-[#96796a]">
              Mesma plataforma em todos: o que muda é quantas glebas e o que você leva da tela.
            </p>
          </Reveal>
          <Reveal>
            <div className="mt-10 overflow-x-auto rounded-2xl border border-[#f3e9e0] bg-white shadow-lg shadow-[#241862]/5">
              <table className="w-full min-w-[820px] border-collapse text-left text-sm">
                <thead>
                  <tr className="border-b border-[#f3e9e0] bg-[#170d48] text-[#fffafa]">
                    <th className="px-4 py-3.5 font-semibold" />
                    <th className="px-4 py-3.5 font-semibold">Gratuito</th>
                    <th className="px-4 py-3.5 font-semibold">Pacote 5 glebas</th>
                    <th className="bg-[#241862] px-4 py-3.5 font-semibold">Semestral</th>
                    <th className="px-4 py-3.5 font-semibold">Anual</th>
                  </tr>
                </thead>
                <tbody>
                  {COMPARATIVO.map((linha, i) => (
                    <tr
                      key={linha.rotulo}
                      className={`border-b border-[#f3e9e0] last:border-0 ${
                        i % 2 === 1 ? "bg-[#fdfbf5]" : ""
                      }`}
                    >
                      <th className="max-w-[260px] px-4 py-3 align-top text-[13px] font-semibold text-[#1d1252]">
                        {linha.rotulo}
                      </th>
                      {linha.valores.map((v, j) => (
                        <td
                          key={j}
                          className={`px-4 py-3 align-top text-[13px] text-[#4a3f7a] ${
                            j === 2 ? "bg-[#241862]/5" : ""
                          }`}
                        >
                          {v}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Reveal>
        </div>
      </section>

      {/* Como funciona a cobrança */}
      <section className="py-16">
        <div className="mx-auto max-w-5xl px-5">
          <Reveal>
            <h2 className="font-display text-center text-3xl">Como funciona a cobrança</h2>
          </Reveal>
          <div className="mt-10 grid gap-4 sm:grid-cols-2">
            {CONDICOES.map((c, i) => (
              <Reveal key={c.titulo} atraso={(i % 2) * 80}>
                <div className="h-full rounded-2xl border border-[#f3e9e0] bg-[#fdfbf5] p-6">
                  <h3 className="font-display text-lg text-[#1d1252]">{c.titulo}</h3>
                  <p className="mt-2.5 text-sm leading-relaxed text-[#4a3f7a]">{c.texto}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* Fechamento: pedido de retorno (o objetivo da página no MVP) */}
      <section className="bg-[#170d48] py-16 text-white">
        <Reveal>
          <div className="mx-auto max-w-2xl px-5 text-center">
            <h2 className="font-display text-3xl leading-snug text-[#fffafa]">
              O que você achou destes valores?
            </h2>
            <p className="mt-4 leading-relaxed text-[#c3b8e8]">
              Você está entre os primeiros clientes da voaz.app e esta tabela ainda não é
              pública. Diga com franqueza o que faz sentido e o que trava: é isso que vai
              definir os preços finais.
            </p>
            <a
              href={LINK_DEMO}
              className="mt-8 inline-flex h-12 items-center rounded-xl bg-[#ff914d] px-7 text-base font-semibold text-[#170d48] shadow-lg shadow-black/30 transition hover:bg-[#db6b1a] hover:text-white"
            >
              Enviar meu retorno
            </a>
          </div>
        </Reveal>
      </section>

      <FooterSite />
    </div>
  );
}
