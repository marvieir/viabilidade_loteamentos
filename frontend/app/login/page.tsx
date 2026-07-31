import type { Metadata } from "next";
import { FormAuth } from "@/components/auth/FormAuth";

export const metadata: Metadata = {
  title: "Entrar — voaz.app",
  alternates: { canonical: "/login" },
};

export default function LoginPage() {
  return <FormAuth modo="login" />;
}
