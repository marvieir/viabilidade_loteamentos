"use client";

// Fase 12 — contexto de autenticação. Mantém o usuário logado em memória e expõe
// login/registrar/logout. No mount tenta um refresh silencioso (o cookie httpOnly
// sobrevive ao reload, o access token em memória não) para reidratar a sessão.

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import type { Usuario } from "@/lib/auth";
import * as auth from "@/lib/auth";

interface AuthContextValue {
  usuario: Usuario | null;
  carregando: boolean; // true enquanto tenta o refresh inicial
  entrar: (email: string, senha: string) => Promise<void>;
  entrarComGoogle: (credential: string) => Promise<void>;
  cadastrar: (email: string, senha: string, nome?: string) => Promise<void>;
  sair: () => Promise<void>;
  // Atualiza o usuário em memória (ex.: após completar o perfil no modal obrigatório).
  atualizarUsuario: (u: Usuario) => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [usuario, setUsuario] = useState<Usuario | null>(null);
  const [carregando, setCarregando] = useState(true);

  // Reidrata a sessão no load: se houver cookie de refresh válido, recupera o usuário.
  useEffect(() => {
    let vivo = true;
    (async () => {
      try {
        await auth.refresh();
        const u = await auth.me();
        if (vivo) setUsuario(u);
      } catch {
        if (vivo) setUsuario(null);
      } finally {
        if (vivo) setCarregando(false);
      }
    })();
    return () => {
      vivo = false;
    };
  }, []);

  const entrar = useCallback(async (email: string, senha: string) => {
    await auth.login(email, senha);
    setUsuario(await auth.me());
  }, []);

  const entrarComGoogle = useCallback(async (credential: string) => {
    await auth.loginGoogle(credential);
    setUsuario(await auth.me());
  }, []);

  const cadastrar = useCallback(
    async (email: string, senha: string, nome?: string) => {
      await auth.registrar(email, senha, nome);
      setUsuario(await auth.me());
    },
    [],
  );

  const sair = useCallback(async () => {
    await auth.logout();
    setUsuario(null);
  }, []);

  const atualizarUsuario = useCallback((u: Usuario) => setUsuario(u), []);

  return (
    <AuthContext.Provider
      value={{
        usuario,
        carregando,
        entrar,
        entrarComGoogle,
        cadastrar,
        sair,
        atualizarUsuario,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth precisa de <AuthProvider>.");
  return ctx;
}
