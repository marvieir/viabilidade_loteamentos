import type { Metadata } from "next";
import { FormAuth } from "@/components/auth/FormAuth";

export const metadata: Metadata = {
  title: "Criar conta grátis — voaz.app",
  description:
    "Crie a conta gratuita da voaz.app e rode a primeira pré-análise de viabilidade na sua própria gleba, a partir do KMZ.",
  alternates: { canonical: "/registrar" },
};

export default function RegistrarPage() {
  return <FormAuth modo="registrar" />;
}
