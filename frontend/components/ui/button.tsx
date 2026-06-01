import * as React from "react";

function cn(...c: (string | undefined | false)[]) {
  return c.filter(Boolean).join(" ");
}

export function Button({
  className,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center rounded-lg bg-slate-900 px-4 py-2",
        "text-sm font-medium text-white transition-colors hover:bg-slate-700",
        "disabled:cursor-not-allowed disabled:opacity-50",
        className
      )}
      {...props}
    />
  );
}
