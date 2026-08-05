// Área das entrevistas de validação do MVP — NÃO listada (sem link em menu, fora do
// sitemap) e com noindex. O conteúdo real ainda exige login com papel admin; este layout
// só garante que buscador nenhum indexe a casca.

import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Entrevistas do MVP | voaz.app",
  robots: { index: false, follow: false },
};

export default function LayoutEntrevistas({ children }: { children: React.ReactNode }) {
  return children;
}
