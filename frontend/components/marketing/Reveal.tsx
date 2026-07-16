"use client";

// Marketing — revelação suave ao rolar (IntersectionObserver). Microinteração discreta:
// pesquisa de conversão (Unbounce/MagicUI 2025) aponta microinterações como reforço de
// engajamento; `prefers-reduced-motion` é respeitado no CSS (.mkt-reveal).

import { useEffect, useRef } from "react";

export function Reveal({
  children,
  atraso = 0,
  className = "",
}: {
  children: React.ReactNode;
  atraso?: number;
  className?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    // Progressive enhancement: sem JS a página fica 100% visível; a classe no <html>
    // liga o estado escondido só quando o observer está pronto para revelar.
    document.documentElement.classList.add("mkt-js");
    const obs = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (e.isIntersecting) {
            (e.target as HTMLElement).classList.add("mkt-visivel");
            obs.unobserve(e.target);
          }
        }
      },
      { threshold: 0.12 }
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, []);

  return (
    <div ref={ref} className={`mkt-reveal ${className}`} style={{ transitionDelay: `${atraso}ms` }}>
      {children}
    </div>
  );
}
