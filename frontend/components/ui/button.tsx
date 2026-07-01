import * as React from "react";

function cn(...c: (string | undefined | false)[]) {
  return c.filter(Boolean).join(" ");
}

/* Design system de botões — TODA a plataforma usa estas variantes (nada de estilo solto).
   Alturas fixas (h-9/h-8) garantem toolbars alinhadas; focus ring consistente (acessível).
   default = primary/md → compatível com os usos existentes de <Button>. */
const VARIANTES = {
  primary:
    "bg-slate-900 text-white border border-transparent shadow-sm hover:bg-slate-700",
  secondary:
    "bg-white text-slate-700 border border-slate-200 shadow-sm hover:bg-slate-50 hover:border-slate-300",
  ghost: "bg-transparent text-slate-600 border border-transparent hover:bg-slate-100",
  danger:
    "bg-rose-600 text-white border border-transparent shadow-sm hover:bg-rose-500",
} as const;

const TAMANHOS = {
  md: "h-9 gap-1.5 px-3.5 text-sm",
  sm: "h-8 gap-1 px-2.5 text-xs",
} as const;

export type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: keyof typeof VARIANTES;
  size?: keyof typeof TAMANHOS;
};

export function Button({
  className,
  variant = "primary",
  size = "md",
  ...props
}: ButtonProps) {
  return (
    <button
      className={cn(
        "inline-flex select-none items-center justify-center whitespace-nowrap rounded-lg font-medium transition-colors",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500/40 focus-visible:ring-offset-1",
        "disabled:pointer-events-none disabled:opacity-50",
        VARIANTES[variant],
        TAMANHOS[size],
        className
      )}
      {...props}
    />
  );
}
