// Marca voaz.app — balão de fala com barras de análise e a curva do terreno atravessando.
// Fonte única do símbolo: qualquer tela que precise do logo importa daqui, para a marca não
// divergir entre header, login e material impresso.

export function Simbolo({
  tamanho = 32,
  cor = "#ff914d",
  className = "",
}: {
  tamanho?: number;
  cor?: string;
  className?: string;
}) {
  return (
    <svg
      width={tamanho}
      height={tamanho}
      viewBox="0 0 100 100"
      className={className}
      role="img"
      aria-label="voaz.app"
    >
      {/* balão */}
      <rect x="14" y="14" width="72" height="60" rx="14" fill="none" stroke={cor} strokeWidth="7" />
      <path d="M34 74 L34 88 L48 74 Z" fill={cor} />
      {/* barras: a análise */}
      <rect x="34" y="36" width="8" height="26" fill={cor} />
      <rect x="47" y="28" width="8" height="34" fill={cor} />
      <rect x="60" y="33" width="8" height="29" fill={cor} />
      {/* curva: o terreno */}
      <path
        d="M22 62 C34 44, 52 72, 82 50"
        fill="none"
        stroke={cor}
        strokeWidth="7"
        strokeLinecap="round"
      />
    </svg>
  );
}

/** Símbolo + wordmark. ``tom`` escolhe o contraste conforme o fundo da superfície. */
export function Logo({
  tamanho = 30,
  tom = "laranja",
  className = "",
}: {
  tamanho?: number;
  tom?: "laranja" | "laranja-escuro" | "creme";
  className?: string;
}) {
  const cor =
    tom === "creme" ? "#fff4f4" : tom === "laranja-escuro" ? "#db6b1a" : "#ff914d";
  return (
    <span className={`inline-flex items-center gap-2 ${className}`}>
      <Simbolo tamanho={tamanho} cor={cor} />
      <b
        className="font-black tracking-[0.12em]"
        style={{ color: cor, fontSize: Math.round(tamanho * 0.48) }}
      >
        VOAZ.APP
      </b>
    </span>
  );
}
