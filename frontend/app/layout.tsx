import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "@/components/auth/AuthProvider";

// SEO (31/07): metadataBase resolve todas as URLs relativas de OG/canonical para o domínio
// público; robots.ts e sitemap.ts (nesta pasta) geram /robots.txt e /sitemap.xml; /llms.txt
// (em public/) descreve a plataforma para assistentes de IA. Canonical é POR PÁGINA (aqui no
// root ele valeria para todas as rotas — errado).
export const metadata: Metadata = {
  metadataBase: new URL("https://voaz.app"),
  title: "voaz.app — pré-viabilidade de loteamento",
  description:
    "Envie o KMZ da gleba e receba a triagem determinística: geometria, ambiental, "
    + "declividade, urbanismo e financeiro, com a lei citada em cada número.",
  applicationName: "voaz.app",
  keywords: [
    "viabilidade de loteamento",
    "pré-viabilidade",
    "análise de gleba",
    "loteamento",
    "estudo de viabilidade urbanística",
    "parcelamento do solo",
  ],
  robots: { index: true, follow: true },
  openGraph: {
    title: "voaz.app — a gleba fecha a conta?",
    description:
      "Pré-viabilidade de loteamento a partir do KMZ. Número com procedência, "
      + "mesma gleba e mesmo resultado sempre.",
    siteName: "voaz.app",
    locale: "pt_BR",
    type: "website",
    url: "https://voaz.app",
    images: [
      {
        url: "/og.jpg",
        width: 1200,
        height: 630,
        alt: "voaz.app — análise de pré-viabilidade de uma gleba real, com camadas ambientais e quadro de números",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "voaz.app — a gleba fecha a conta?",
    description:
      "Pré-viabilidade de loteamento a partir do KMZ, com a fonte legal ao lado de cada número.",
    images: ["/og.jpg"],
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="pt-BR">
      <head>
        {/* Inter via <link> (carrega no navegador, não no build) — degrada para a stack
            de sistema se a rede bloquear; não há dependência de build/egress. */}
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link
          rel="preconnect"
          href="https://fonts.gstatic.com"
          crossOrigin="anonymous"
        />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap"
          rel="stylesheet"
        />
        {/* Fraunces — serifa display das páginas públicas (marketing); degrada p/ Georgia. */}
        <link
          href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="min-h-screen bg-creme-100 text-marinho-900 antialiased">
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
