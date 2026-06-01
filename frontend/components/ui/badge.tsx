import * as React from "react";

function cn(...c: (string | undefined | false)[]) {
  return c.filter(Boolean).join(" ");
}

type Variant = "neutral" | "warning" | "success" | "info";

const styles: Record<Variant, string> = {
  neutral: "bg-slate-100 text-slate-700 border-slate-200",
  warning: "bg-amber-100 text-amber-800 border-amber-200",
  success: "bg-emerald-100 text-emerald-800 border-emerald-200",
  info: "bg-sky-100 text-sky-800 border-sky-200",
};

export function Badge({
  variant = "neutral",
  className,
  ...props
}: React.HTMLAttributes<HTMLSpanElement> & { variant?: Variant }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium",
        styles[variant],
        className
      )}
      {...props}
    />
  );
}
