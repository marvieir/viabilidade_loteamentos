// Blog — índice (BLOG-1). Superfície editorial "papel" (mesma direção do laudo de exemplo).
// Regra da marca: artigo com afirmação legal SEMPRE cita a fonte; a lista mostra categoria,
// data e tempo de leitura vindos do JSON do artigo — nada calculado aqui.

import type { Metadata } from "next";
import Link from "next/link";
import { FooterSite, HeaderSite } from "@/components/marketing/site";
import { formatarData, listarPosts } from "@/lib/blog";

export const metadata: Metadata = {
  title: "Blog da voaz.app — viabilidade de loteamento com a lei ao lado",
  description:
    "Artigos sobre pré-viabilidade de loteamento: lote mínimo, declividade, regime urbano e rural, diretrizes municipais. Toda regra citada com a fonte legal.",
  alternates: { canonical: "/blog" },
};

// ISR: artigo novo aparece via webhook de revalidação (BLOG-2) ou em até 5 min.
export const revalidate = 300;

export default async function PaginaBlog() {
  const posts = await listarPosts();
  return (
    <div className="min-h-screen bg-papel text-papel-tinta">
      <HeaderSite />
      <main className="mx-auto max-w-3xl px-5 py-12">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-papel-tinta3">
          Blog da voaz.app
        </p>
        <h1 className="mt-2 font-serifa text-4xl font-semibold leading-tight">
          Viabilidade de loteamento, com a lei ao lado
        </h1>
        <p className="mt-4 max-w-2xl leading-relaxed text-papel-tinta2">
          A régua legal do parcelamento do solo explicada para quem decide sobre gleba.
          Toda regra citada com a fonte, no mesmo padrão dos laudos da plataforma.
        </p>

        <div className="mt-10 space-y-6">
          {posts.length === 0 && (
            <p className="text-papel-tinta3">Os primeiros artigos chegam em breve.</p>
          )}
          {posts.map((post) => (
            <Link
              key={post.slug}
              href={`/blog/${post.slug}`}
              className="block rounded-2xl border border-papel-linha bg-white p-6 transition hover:border-[#ff914d]"
            >
              <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-papel-tinta3">
                <span className="rounded-full border border-papel-linha px-2.5 py-0.5 font-medium">
                  {post.categoria}
                </span>
                <time dateTime={post.data}>{formatarData(post.data)}</time>
                <span>{post.tempoLeituraMin} min de leitura</span>
              </div>
              <h2 className="mt-3 font-serifa text-2xl font-semibold leading-snug">
                {post.titulo}
              </h2>
              <p className="mt-2 leading-relaxed text-papel-tinta2">{post.descricao}</p>
              <span className="mt-3 inline-block text-sm font-semibold text-[#db6b1a]">
                Ler o artigo
              </span>
            </Link>
          ))}
        </div>
      </main>
      <FooterSite />
    </div>
  );
}
