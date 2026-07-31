import type { MetadataRoute } from "next";

// /sitemap.xml gerado pelo Next: só as páginas públicas que queremos indexadas.
export default function sitemap(): MetadataRoute.Sitemap {
  const base = "https://voaz.app";
  return [
    { url: `${base}/`, changeFrequency: "weekly", priority: 1 },
    { url: `${base}/loteadores`, changeFrequency: "weekly", priority: 0.9 },
    { url: `${base}/laudo-exemplo`, changeFrequency: "weekly", priority: 0.9 },
    { url: `${base}/registrar`, changeFrequency: "monthly", priority: 0.6 },
    { url: `${base}/login`, changeFrequency: "monthly", priority: 0.3 },
  ];
}
