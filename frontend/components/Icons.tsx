import * as React from "react";

// Ícones inline (sem dependência externa) — traço fino, estilo "lucide".
type P = React.SVGProps<SVGSVGElement>;
const base = (props: P) => ({
  width: 18,
  height: 18,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 2,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  ...props,
});

export const IconVisao = (p: P) => (
  <svg {...base(p)}><rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" /><rect x="14" y="14" width="7" height="7" rx="1" /></svg>
);
export const IconAmbiental = (p: P) => (
  <svg {...base(p)}><path d="M10.3 3.2 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.2a2 2 0 0 0-3.4 0Z" /><path d="M12 9v4" /><path d="M12 17h.01" /></svg>
);
export const IconVerde = (p: P) => (
  <svg {...base(p)}><path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8 0 5.5-4.78 10-10 10Z" /><path d="M2 21c0-3 1.85-5.36 5.08-6" /></svg>
);
export const IconDeclividade = (p: P) => (
  <svg {...base(p)}><path d="m8 3 4 8 5-5 5 15H2L8 3z" /></svg>
);
export const IconAproveitamento = (p: P) => (
  <svg {...base(p)}><rect x="3" y="3" width="18" height="18" rx="2" /><path d="M3 9h18" /><path d="M9 21V9" /></svg>
);
export const IconLuos = (p: P) => (
  <svg {...base(p)}><path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z" /><path d="M14 2v5h5" /><path d="M8 13h8M8 17h6" /></svg>
);
export const IconLayers = (p: P) => (
  <svg {...base(p)}><path d="m12 2 9 5-9 5-9-5 9-5Z" /><path d="m3 12 9 5 9-5" /><path d="m3 17 9 5 9-5" /></svg>
);
export const IconPlus = (p: P) => (
  <svg {...base(p)}><path d="M5 12h14M12 5v14" /></svg>
);
export const IconPlay = (p: P) => (
  <svg {...base(p)}><polygon points="6 3 20 12 6 21 6 3" /></svg>
);
export const IconMap = (p: P) => (
  <svg {...base(p)}><path d="M14.1 4.1 9 2 3.6 3.8a1 1 0 0 0-.6.9V20a.5.5 0 0 0 .7.5L9 18l6 2 5.4-1.8a1 1 0 0 0 .6-.9V4a.5.5 0 0 0-.7-.5L15 5" /><path d="M9 2v16M15 5v16" /></svg>
);
export const IconChevron = (p: P) => (
  <svg {...base(p)}><path d="m9 18 6-6-6-6" /></svg>
);
export const IconConformidade = (p: P) => (
  <svg {...base(p)}><rect x="4" y="3" width="16" height="18" rx="2" /><path d="M9 3v2h6V3" /><path d="m8.5 12.5 2.5 2.5 4.5-5" /></svg>
);
export const IconJuridico = (p: P) => (
  <svg {...base(p)}><path d="M12 3v18" /><path d="M5 7h14" /><path d="m5 7-3 6a3 3 0 0 0 6 0L5 7Z" /><path d="m19 7-3 6a3 3 0 0 0 6 0l-3-6Z" /><path d="M7 21h10" /></svg>
);
