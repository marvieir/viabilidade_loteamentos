import { Badge } from "@/components/ui/badge";
import type { Jurisdicao } from "@/lib/api";

const rotulo: Record<string, string> = {
  BASE_FEDERAL: "Cobertura: Base Federal",
  PARCIAL_UF: "Cobertura: Parcial (UF)",
  COMPLETA: "Cobertura: Completa",
};

const variante: Record<string, "warning" | "info" | "success"> = {
  BASE_FEDERAL: "warning",
  PARCIAL_UF: "info",
  COMPLETA: "success",
};

export function BadgeCobertura({ jurisdicao }: { jurisdicao: Jurisdicao }) {
  const { cobertura, nao_considerado, municipio, uf } = jurisdicao;
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant={variante[cobertura]}>{rotulo[cobertura]}</Badge>
        <span className="text-sm text-slate-600">
          {municipio ? `${municipio}${uf ? ` / ${uf}` : ""}` : "Município não resolvido"}
        </span>
      </div>
      {nao_considerado.length > 0 && (
        <div className="rounded-lg bg-amber-50 p-3 text-xs text-amber-900">
          <p className="mb-1 font-medium">Não considerado nesta análise:</p>
          <ul className="list-disc space-y-0.5 pl-4">
            {nao_considerado.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
