// Blog (BLOG-1) — leitura dos artigos em content/blog/*.json.
// SÓ roda no servidor (fs). O diretório é lido EM TEMPO DE EXECUÇÃO (não importado no
// build) de propósito: no BLOG-2 o gerador grava artigo novo no mesmo diretório (volume)
// e o webhook de revalidação publica sem rebuild — mesmo desenho do sistema MMA original.

import { promises as fs } from "fs";
import path from "path";

export type BlocoPost =
  | { tipo: "p"; texto: string }
  | { tipo: "h2"; texto: string }
  | { tipo: "ul"; itens: string[] }
  | { tipo: "aviso"; texto: string };

export interface PostBlog {
  slug: string;
  titulo: string;
  descricao: string;
  data: string; // ISO (AAAA-MM-DD)
  atualizado?: string;
  autor: string;
  categoria: string;
  tempoLeituraMin: number;
  blocos: BlocoPost[];
  fontes: { rotulo: string; url?: string }[];
}

const BLOG_DIR =
  process.env.BLOG_CONTENT_DIR ?? path.join(process.cwd(), "content", "blog");

export async function listarPosts(): Promise<PostBlog[]> {
  let arquivos: string[];
  try {
    arquivos = await fs.readdir(BLOG_DIR);
  } catch {
    return []; // diretório ausente = blog vazio, nunca erro
  }
  const posts: PostBlog[] = [];
  for (const nome of arquivos) {
    if (!nome.endsWith(".json")) continue;
    try {
      const bruto = await fs.readFile(path.join(BLOG_DIR, nome), "utf-8");
      const post = JSON.parse(bruto) as PostBlog;
      if (post.slug && post.titulo && Array.isArray(post.blocos)) posts.push(post);
    } catch {
      // arquivo malformado não derruba o índice inteiro
    }
  }
  posts.sort((a, b) => (a.data < b.data ? 1 : -1));
  return posts;
}

export async function obterPost(slug: string): Promise<PostBlog | null> {
  const posts = await listarPosts();
  return posts.find((p) => p.slug === slug) ?? null;
}

const MESES = [
  "janeiro", "fevereiro", "março", "abril", "maio", "junho",
  "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
];

// Data por extenso, determinística (sem depender de locale do runtime).
export function formatarData(iso: string): string {
  const [ano, mes, dia] = iso.split("-").map(Number);
  if (!ano || !mes || !dia) return iso;
  return `${dia} de ${MESES[mes - 1]} de ${ano}`;
}
