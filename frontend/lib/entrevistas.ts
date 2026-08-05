// Entrevistas de validação do MVP — cliente da API /api/entrevistas (admin-only).
// As opções moram AQUI (uma fonte só para formulário e resumo). Os valores gravados são
// os próprios rótulos humanos: sem de-para, o resumo agrega e exibe o que foi marcado.

import { apiFetch } from "@/lib/auth";

export const PERFIS = [
  "Loteador em operação",
  "Corretor de áreas / entrante",
  "Incorporador ou investidor",
  "Terrenista / dono de terra",
  "Outro",
];

export const CANAIS = [
  "Rede pessoal",
  "Indicação",
  "Usuário do MVP",
  "LinkedIn",
  "Grupo WhatsApp/Telegram",
  "Outro",
];

export const ENTREVISTADORES = ["Marco", "Sócia"];

export const FAIXAS_GLEBAS_ANO = ["Até 3", "4 a 10", "11 a 30", "Mais de 30"];

export const FUNCIONALIDADES = [
  "Urbanismo IA",
  "Pré-análise jurídica",
  "Diretriz municipal (LUOS)",
  "Laudo PDF/Excel",
  "Importação DWG",
  "Financeiro/econômico",
];

export const REACOES = ["Barato", "Justo", "Caro", "Travou"];

export const ESCOLHAS = ["Nenhuma", "Gratuito", "Pacote 5", "Semestral", "Anual"];

export const COTA_COBRE = ["Sim", "Não", "Não se aplica"];

export const DESCONTO_FUNDADOR = ["Sim", "Talvez", "Não"];

export interface EntrevistaIn {
  nome: string;
  perfil: string;
  canal: string;
  entrevistador: string;
  ultima_gleba: string;
  glebas_ano: string;
  confianca: string;
  sumisse_amanha: string;
  mais_gostou: string[];
  capacidade_nova: string;
  dificuldades: string;
  sentiu_falta: string;
  pagaria_manter: string[];
  preco_caro: string;
  preco_barato: string;
  reacao_pacote5: string;
  reacao_semestral: string;
  reacao_anual: string;
  escolha: string;
  travou_motivo: string;
  cota_cobre: string;
  desconto_fundador: string;
  indicacoes: string;
  observacoes: string;
}

export interface Entrevista extends EntrevistaIn {
  id: string;
  ts: string;
}

export interface Contagem {
  rotulo: string;
  n: number;
}

export interface TextoEntrevista {
  nome: string;
  perfil: string;
  texto: string;
}

export interface PrecoEntrevista {
  nome: string;
  perfil: string;
  caro: string;
  barato: string;
}

export interface EntrevistaResumo {
  total: number;
  por_perfil: Contagem[];
  por_glebas_ano: Contagem[];
  escolhas: Contagem[];
  escolha_por_perfil: Record<string, Record<string, number>>;
  reacoes: Record<string, Record<string, number>>;
  mais_gostou: Contagem[];
  pagaria_manter: Contagem[];
  cota_cobre: Contagem[];
  desconto_fundador: Contagem[];
  precos: PrecoEntrevista[];
  travas: TextoEntrevista[];
  sentiu_falta: TextoEntrevista[];
  dificuldades: TextoEntrevista[];
  capacidades: TextoEntrevista[];
}

async function jsonOrThrow(res: Response) {
  if (!res.ok) {
    let detalhe = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (body?.detail) detalhe = body.detail;
    } catch {
      /* corpo não-JSON */
    }
    throw new Error(detalhe);
  }
  return res.json();
}

export async function salvarEntrevista(dados: EntrevistaIn): Promise<Entrevista> {
  return apiFetch("/api/entrevistas", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(dados),
  }).then(jsonOrThrow);
}

export async function listarEntrevistas(): Promise<Entrevista[]> {
  return apiFetch("/api/entrevistas").then(jsonOrThrow);
}

export async function obterResumoEntrevistas(): Promise<EntrevistaResumo> {
  return apiFetch("/api/entrevistas/resumo").then(jsonOrThrow);
}

export async function excluirEntrevista(id: string): Promise<void> {
  const r = await apiFetch(`/api/entrevistas/${id}`, { method: "DELETE" });
  if (!r.ok) throw new Error("Falha ao excluir a entrevista.");
}
