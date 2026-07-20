"use client";

// Botão "Entrar com o Google" (Google Identity Services). O Google renderiza o botão e
// devolve um ID token (JWT) no callback; NÓS só o repassamos ao backend, que verifica e
// abre a sessão normal (access em memória + refresh em cookie). Gate por env:
// sem NEXT_PUBLIC_GOOGLE_CLIENT_ID o componente não renderiza nada — a página de login
// continua idêntica em ambientes sem a integração configurada.

import { useEffect, useRef, useState } from "react";

const CLIENT_ID = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID;
const GSI_SRC = "https://accounts.google.com/gsi/client";

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (cfg: {
            client_id: string;
            callback: (resp: { credential: string }) => void;
          }) => void;
          renderButton: (el: HTMLElement, opts: Record<string, unknown>) => void;
        };
      };
    };
  }
}

export function BotaoGoogle({
  onCredential,
  onErro,
}: {
  onCredential: (credential: string) => void;
  onErro: (mensagem: string) => void;
}) {
  const alvo = useRef<HTMLDivElement>(null);
  const [pronto, setPronto] = useState(false);

  useEffect(() => {
    if (!CLIENT_ID) return;
    const iniciar = () => {
      if (!window.google || !alvo.current) return;
      window.google.accounts.id.initialize({
        client_id: CLIENT_ID,
        callback: (resp) => onCredential(resp.credential),
      });
      window.google.accounts.id.renderButton(alvo.current, {
        theme: "outline",
        size: "large",
        text: "continue_with",
        locale: "pt-BR",
        width: 320,
      });
      setPronto(true);
    };

    if (window.google) {
      iniciar();
      return;
    }
    // Carrega o script do Google uma única vez (páginas de login e cadastro compartilham).
    let script = document.querySelector<HTMLScriptElement>(`script[src="${GSI_SRC}"]`);
    if (!script) {
      script = document.createElement("script");
      script.src = GSI_SRC;
      script.async = true;
      document.head.appendChild(script);
    }
    script.addEventListener("load", iniciar);
    script.addEventListener("error", () =>
      onErro(
        "Não foi possível carregar o login do Google (rede ou bloqueador). " +
          "Entre com e-mail e senha.",
      ),
    );
    return () => script?.removeEventListener("load", iniciar);
    // onCredential/onErro estáveis o bastante (setState/handlers do form).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (!CLIENT_ID) return null;

  return (
    <div>
      <div className="my-5 flex items-center gap-3">
        <span className="h-px flex-1 bg-slate-200" />
        <span className="text-xs text-slate-400">ou</span>
        <span className="h-px flex-1 bg-slate-200" />
      </div>
      <div ref={alvo} className="flex justify-center" />
      {!pronto && (
        <p className="text-center text-xs text-slate-400">Carregando login do Google…</p>
      )}
    </div>
  );
}
