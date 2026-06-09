import {
  IconAmbiental,
  IconAproveitamento,
  IconDeclividade,
  IconJuridico,
  IconLuos,
  IconVerde,
  IconVisao,
} from "@/components/Icons";

export type Secao =
  | "visao"
  | "ambiental"
  | "verde"
  | "declividade"
  | "aproveitamento"
  | "juridico"
  | "luos";

export const SECOES: {
  id: Secao;
  rotulo: string;
  Icone: (p: React.SVGProps<SVGSVGElement>) => JSX.Element;
}[] = [
  { id: "visao", rotulo: "Visão geral", Icone: IconVisao },
  { id: "ambiental", rotulo: "Ambiental", Icone: IconAmbiental },
  { id: "verde", rotulo: "Área verde", Icone: IconVerde },
  { id: "declividade", rotulo: "Declividade", Icone: IconDeclividade },
  { id: "aproveitamento", rotulo: "Aproveitamento", Icone: IconAproveitamento },
  { id: "juridico", rotulo: "Jurídico", Icone: IconJuridico },
  { id: "luos", rotulo: "Diretriz (LUOS)", Icone: IconLuos },
];
