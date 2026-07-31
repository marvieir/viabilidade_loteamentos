import type { MetadataRoute } from "next";

// /robots.txt gerado pelo Next. Política (31/07, pedido do operador): TODOS os robôs são
// bem-vindos nas páginas públicas — inclusive os crawlers de IA (GPTBot, ClaudeBot,
// Google-Extended, PerplexityBot etc.), que herdam a regra "*". A área logada e os fluxos
// de senha ficam fora do índice.
export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: "*",
        allow: "/",
        disallow: ["/app", "/admin", "/esqueci", "/redefinir"],
      },
    ],
    sitemap: "https://voaz.app/sitemap.xml",
  };
}
