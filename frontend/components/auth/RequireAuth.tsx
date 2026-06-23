"use client";

// Fase 12 — porteiro de rota: sem login, redireciona para /login. Enquanto o refresh
// inicial corre, mostra um placeholder (evita piscar a tela protegida).

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/components/auth/AuthProvider";

export function RequireAuth({ children }: { children: React.ReactNode }) {
  const { usuario, carregando } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!carregando && !usuario) router.replace("/login");
  }, [carregando, usuario, router]);

  if (carregando || !usuario) {
    return (
      <main className="grid min-h-screen place-items-center">
        <p className="text-sm text-slate-500">Carregando…</p>
      </main>
    );
  }
  return <>{children}</>;
}
