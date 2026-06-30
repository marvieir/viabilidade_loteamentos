import {
  IconAmbiental,
  IconAproveitamento,
  IconConformidade,
  IconDeclividade,
  IconEconomica,
  IconFinanceira,
  IconJuridico,
  IconLocalizacao,
  IconLuos,
  IconUrbanismo,
  IconVerde,
  IconVisao,
} from "@/components/Icons";

export type Secao =
  | "visao"
  | "ambiental"
  | "verde"
  | "declividade"
  | "aproveitamento"
  | "urbanismo"
  | "custo"
  | "conformidade"
  | "juridico"
  | "financeira"
  | "economica"
  | "localizacao"
  | "luos";

export const SECOES: {
  id: Secao;
  rotulo: string;
  Icone: (p: React.SVGProps<SVGSVGElement>) => JSX.Element;
  sub?: boolean; // item filho (recuado sob o menu pai imediatamente acima)
}[] = [
  { id: "visao", rotulo: "Visão geral", Icone: IconVisao },
  { id: "ambiental", rotulo: "Ambiental", Icone: IconAmbiental },
  { id: "verde", rotulo: "Área verde", Icone: IconVerde, sub: true },
  { id: "declividade", rotulo: "Declividade", Icone: IconDeclividade, sub: true },
  { id: "aproveitamento", rotulo: "Aproveitamento", Icone: IconAproveitamento },
  { id: "urbanismo", rotulo: "Urbanismo (IA)", Icone: IconUrbanismo },
  { id: "custo", rotulo: "Custo (infra)", Icone: IconFinanceira },
  { id: "conformidade", rotulo: "Conformidade", Icone: IconConformidade },
  { id: "juridico", rotulo: "Jurídico", Icone: IconJuridico },
  { id: "financeira", rotulo: "Financeira", Icone: IconFinanceira },
  { id: "economica", rotulo: "Econômica", Icone: IconEconomica },
  { id: "localizacao", rotulo: "Localização", Icone: IconLocalizacao },
  { id: "luos", rotulo: "Diretriz (LUOS)", Icone: IconLuos },
];
