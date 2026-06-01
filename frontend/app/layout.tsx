import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Pré-Viabilidade de Loteamento",
  description: "Triagem determinística de viabilidade de loteamento a partir do KMZ da gleba.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="pt-BR">
      <body className="min-h-screen bg-slate-50 text-slate-900 antialiased">
        {children}
      </body>
    </html>
  );
}
