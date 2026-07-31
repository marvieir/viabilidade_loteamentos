import type { MetadataRoute } from "next";
import { listarPosts } from "@/lib/blog";

// /sitemap.xml gerado pelo Next: páginas públicas + artigos do blog (lidos do diretório
// de conteúdo em tempo de execução — artigo novo entra via revalidação, sem rebuild).
export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const base = "https://voaz.app";
  const fixas: MetadataRoute.Sitemap = [
    { url: `${base}/`, changeFrequency: "weekly", priority: 1 },
    { url: `${base}/loteadores`, changeFrequency: "weekly", priority: 0.9 },
    { url: `${base}/laudo-exemplo`, changeFrequency: "weekly", priority: 0.9 },
    { url: `${base}/blog`, changeFrequency: "weekly", priority: 0.8 },
    { url: `${base}/registrar`, changeFrequency: "monthly", priority: 0.6 },
    { url: `${base}/login`, changeFrequency: "monthly", priority: 0.3 },
  ];
  const posts = await listarPosts();
  const artigos: MetadataRoute.Sitemap = posts.map((p) => ({
    url: `${base}/blog/${p.slug}`,
    lastModified: p.atualizado ?? p.data,
    changeFrequency: "monthly",
    priority: 0.7,
  }));
  return [...fixas, ...artigos];
}
