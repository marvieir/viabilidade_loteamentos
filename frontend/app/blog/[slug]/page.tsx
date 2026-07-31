// Blog — artigo (BLOG-1). Renderiza os blocos do JSON (p, h2, ul, aviso) e a seção de
// fontes: a marca vive de proveniência, então o artigo também. dynamicParams=true + ISR:
// arquivo novo no diretório (BLOG-2) vira página sem rebuild após a revalidação.

import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { FooterSite, HeaderSite } from "@/components/marketing/site";
import { formatarData, listarPosts, obterPost } from "@/lib/blog";

export const revalidate = 300;
export const dynamicParams = true;

export async function generateStaticParams() {
  const posts = await listarPosts();
  return posts.map((p) => ({ slug: p.slug }));
}

export async function generateMetadata({
  params,
}: {
  params: { slug: string };
}): Promise<Metadata> {
  const post = await obterPost(params.slug);
  if (!post) return { title: "Artigo não encontrado — voaz.app" };
  return {
    title: `${post.titulo} | voaz.app`,
    description: post.descricao,
    alternates: { canonical: `/blog/${post.slug}` },
    openGraph: {
      type: "article",
      title: post.titulo,
      description: post.descricao,
      publishedTime: post.data,
      url: `/blog/${post.slug}`,
    },
  };
}

export default async function PaginaArtigo({
  params,
}: {
  params: { slug: string };
}) {
  const post = await obterPost(params.slug);
  if (!post) notFound();

  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "Article",
    headline: post.titulo,
    description: post.descricao,
    datePublished: post.data,
    dateModified: post.atualizado ?? post.data,
    inLanguage: "pt-BR",
    author: { "@type": "Organization", name: post.autor, url: "https://voaz.app" },
    publisher: { "@type": "Organization", name: "voaz.app", url: "https://voaz.app" },
    mainEntityOfPage: `https://voaz.app/blog/${post.slug}`,
  };

  return (
    <div className="min-h-screen bg-papel text-papel-tinta">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
      <HeaderSite />
      <main className="mx-auto max-w-3xl px-5 py-12">
        <nav className="text-xs text-papel-tinta3">
          <Link href="/blog" className="transition hover:text-[#db6b1a]">
            Blog
          </Link>{" "}
          / {post.categoria}
        </nav>
        <h1 className="mt-3 font-serifa text-4xl font-semibold leading-tight">
          {post.titulo}
        </h1>
        <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-papel-tinta3">
          <span>{post.autor}</span>
          <time dateTime={post.data}>{formatarData(post.data)}</time>
          <span>{post.tempoLeituraMin} min de leitura</span>
        </div>

        <article className="mt-8 space-y-5">
          {post.blocos.map((bloco, i) => {
            switch (bloco.tipo) {
              case "h2":
                return (
                  <h2 key={i} className="pt-3 font-serifa text-2xl font-semibold leading-snug">
                    {bloco.texto}
                  </h2>
                );
              case "ul":
                return (
                  <ul key={i} className="list-disc space-y-2 pl-5 leading-relaxed text-papel-tinta2">
                    {bloco.itens.map((item, j) => (
                      <li key={j}>{item}</li>
                    ))}
                  </ul>
                );
              case "aviso":
                return (
                  <p
                    key={i}
                    className="rounded-xl border border-[#ffc9a5] bg-[#fff4ec] p-4 text-sm leading-relaxed text-papel-tinta2"
                  >
                    {bloco.texto}
                  </p>
                );
              default:
                return (
                  <p key={i} className="leading-relaxed text-papel-tinta2">
                    {bloco.texto}
                  </p>
                );
            }
          })}
        </article>

        <section className="mt-10 rounded-2xl border border-papel-linha bg-white p-6">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-papel-tinta3">
            Fontes deste artigo
          </h2>
          <ul className="mt-3 space-y-2 text-sm leading-relaxed text-papel-tinta2">
            {post.fontes.map((f, i) => (
              <li key={i}>
                {f.url ? (
                  <a
                    href={f.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="underline decoration-[#ffad78] underline-offset-4 transition hover:text-[#db6b1a]"
                  >
                    {f.rotulo}
                  </a>
                ) : (
                  f.rotulo
                )}
              </li>
            ))}
          </ul>
        </section>

        <section className="mt-10 rounded-2xl bg-[#170d48] p-8 text-center text-white">
          <h2 className="font-serifa text-2xl font-semibold">
            Veja essa régua aplicada numa gleba real
          </h2>
          <p className="mx-auto mt-3 max-w-xl text-sm leading-relaxed text-[#c3b8e8]">
            O laudo de exemplo público mostra a análise completa de uma gleba em São Roque/SP,
            com a fonte legal ao lado de cada número. E a conta gratuita roda a triagem na sua
            própria gleba a partir do KMZ.
          </p>
          <div className="mt-6 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <Link
              href="/laudo-exemplo"
              className="inline-flex h-11 items-center rounded-xl border border-[#ffad78] bg-white/10 px-6 text-sm font-semibold text-[#fff4f4] transition hover:bg-[#ffad78] hover:text-[#170d48]"
            >
              Ver o laudo de exemplo
            </Link>
            <Link
              href="/registrar"
              className="inline-flex h-11 items-center rounded-xl bg-[#ff914d] px-6 text-sm font-semibold text-[#170d48] transition hover:bg-[#db6b1a] hover:text-white"
            >
              Criar conta grátis
            </Link>
          </div>
        </section>
      </main>
      <FooterSite />
    </div>
  );
}
