// Fase 12 — autenticação no front. O access token mora EM MEMÓRIA (não em
// localStorage → menos exposto a XSS). O refresh vem em cookie httpOnly que o
// browser envia sozinho para /api/auth/refresh. `apiFetch` injeta o Bearer e, no
// 401, tenta um refresh transparente uma vez antes de desistir.

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8700";

export interface Usuario {
  id: string;
  email: string;
  nome: string | null;
  celular: string | null; // dígitos (DDD+número); null → modal obrigatório no login
  papel: "cliente" | "admin";
  criado_em: string;
}

let accessToken: string | null = null;

export function getToken(): string | null {
  return accessToken;
}

export function setToken(token: string | null): void {
  accessToken = token;
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

export async function registrar(
  email: string,
  senha: string,
  nome?: string,
): Promise<string> {
  const res = await fetch(`${API_BASE}/api/auth/registrar`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include", // recebe o cookie de refresh
    body: JSON.stringify({ email, senha, nome: nome || undefined }),
  });
  const { access_token } = await jsonOrThrow(res);
  setToken(access_token);
  return access_token;
}

export async function login(email: string, senha: string): Promise<string> {
  const res = await fetch(`${API_BASE}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ email, senha }),
  });
  const { access_token } = await jsonOrThrow(res);
  setToken(access_token);
  return access_token;
}

// Troca o cookie de refresh por um novo access token. Lança se a sessão expirou.
export async function refresh(): Promise<string> {
  const res = await fetch(`${API_BASE}/api/auth/refresh`, {
    method: "POST",
    credentials: "include",
  });
  if (!res.ok) {
    setToken(null);
    throw new Error("Sessão expirada.");
  }
  const { access_token } = await res.json();
  setToken(access_token);
  return access_token;
}

export async function logout(): Promise<void> {
  setToken(null);
  try {
    await fetch(`${API_BASE}/api/auth/logout`, {
      method: "POST",
      credentials: "include",
    });
  } catch {
    /* logout é best-effort; o token já foi descartado em memória */
  }
}

export async function me(): Promise<Usuario> {
  return apiFetch("/api/auth/me").then((r) => r.json());
}

// Contato obrigatório do 1º login (nome + celular). O backend valida e normaliza o
// celular (dígitos, DDD + número); devolve o usuário atualizado.
export async function atualizarPerfil(
  nome: string,
  celular: string,
): Promise<Usuario> {
  const res = await apiFetch("/api/auth/perfil", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ nome, celular }),
  });
  return jsonOrThrow(res);
}

// "Esqueci minha senha": o backend responde a MESMA mensagem exista ou não a conta
// (anti-enumeração) e manda o link por e-mail quando ela existe.
export async function esqueciSenha(email: string): Promise<string> {
  const res = await fetch(`${API_BASE}/api/auth/esqueci`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });
  const { mensagem } = await jsonOrThrow(res);
  return mensagem;
}

export async function redefinirSenha(token: string, senha: string): Promise<string> {
  const res = await fetch(`${API_BASE}/api/auth/redefinir`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token, senha }),
  });
  const { mensagem } = await jsonOrThrow(res);
  return mensagem;
}

// Troca de senha logado. Conta nascida pelo Google (sem senha) omite senhaAtual.
export async function trocarSenha(
  senhaAtual: string | undefined,
  senhaNova: string,
): Promise<string> {
  const res = await apiFetch("/api/auth/trocar-senha", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ senha_atual: senhaAtual || undefined, senha_nova: senhaNova }),
  });
  const { mensagem } = await jsonOrThrow(res);
  return mensagem;
}

// Login com Google: troca o ID token do botão (GIS) por uma sessão normal nossa.
export async function loginGoogle(credential: string): Promise<string> {
  const res = await fetch(`${API_BASE}/api/auth/google`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ credential }),
  });
  const { access_token } = await jsonOrThrow(res);
  setToken(access_token);
  return access_token;
}

// Wrapper de fetch autenticado: injeta o Bearer e, no 401, tenta UM refresh e repete.
// `fetch()` só REJEITA (throw) em falha de REDE — quando não houve resposta nenhuma do servidor:
// backend reiniciando (após rebuild), serviço caído, conexão perdida ou operação longa demais que
// derrubou a conexão. O navegador dá "Failed to fetch", que não diz nada ao usuário. Trocamos por
// uma mensagem acionável. (Erros DA APLICAÇÃO não caem aqui — vêm com status HTTP e corpo próprio.)
async function _fetchOuErroDeRede(url: string, init: RequestInit): Promise<Response> {
  try {
    return await fetch(url, init);
  } catch {
    throw new Error(
      "Não foi possível falar com o servidor. O backend pode estar reiniciando (logo após um " +
        "rebuild), a operação pode ter demorado demais e a conexão caiu, ou o serviço parou. " +
        "Aguarde alguns segundos e tente de novo. Se persistir, veja os logs do backend " +
        "(ex.: `podman-compose logs --tail=100 api`).",
    );
  }
}

export async function apiFetch(
  path: string,
  init: RequestInit = {},
): Promise<Response> {
  const comAuth = (token: string | null): RequestInit => ({
    ...init,
    credentials: "include",
    headers: {
      ...(init.headers || {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });

  let res = await _fetchOuErroDeRede(`${API_BASE}${path}`, comAuth(accessToken));
  if (res.status === 401) {
    try {
      const novo = await refresh();
      res = await _fetchOuErroDeRede(`${API_BASE}${path}`, comAuth(novo));
    } catch {
      /* refresh falhou — devolve o 401 original para o chamador tratar */
    }
  }
  return res;
}
