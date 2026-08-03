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

// DUAS origens (lição do deploy de 03/08 — volume compartilhado entre containers de UIDs
// diferentes dava blog vazio e erro de permissão em produção):
//   1. BLOG_CONTENT_DIR (default: content/blog da IMAGEM) — artigos SEMENTE versionados no
//      git; atualizam a cada deploy.
//   2. BLOG_CONTENT_DIR_EXTRA (produção: volume que SÓ a api escreve, montado ro aqui) —
//      artigos aprovados pelo gerador, sem rebuild.
// Mesmo slug nas duas → vale o do EXTRA (versão mais recente publicada pelo gerador).
const BLOG_DIR =
  process.env.BLOG_CONTENT_DIR ?? path.join(process.cwd(), "content", "blog");
const BLOG_DIR_EXTRA = process.env.BLOG_CONTENT_DIR_EXTRA ?? "";

async function lerDiretorio(dir: string): Promise<PostBlog[]> {
  let arquivos: string[];
  try {
    arquivos = await fs.readdir(dir);
  } catch {
    return []; // diretório ausente = origem vazia, nunca erro
  }
  const posts: PostBlog[] = [];
  for (const nome of arquivos) {
    if (!nome.endsWith(".json")) continue;
    try {
      const bruto = await fs.readFile(path.join(dir, nome), "utf-8");
      const post = JSON.parse(bruto) as PostBlog;
      if (post.slug && post.titulo && Array.isArray(post.blocos)) posts.push(post);
    } catch {
      // arquivo malformado não derruba o índice inteiro
    }
  }
  return posts;
}

export async function listarPosts(): Promise<PostBlog[]> {
  const porSlug = new Map<string, PostBlog>();
  for (const post of await lerDiretorio(BLOG_DIR)) porSlug.set(post.slug, post);
  if (BLOG_DIR_EXTRA) {
    for (const post of await lerDiretorio(BLOG_DIR_EXTRA)) porSlug.set(post.slug, post);
  }
  const posts = [...porSlug.values()];
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
