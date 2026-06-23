// Fase 12 — autenticação no front. O access token mora EM MEMÓRIA (não em
// localStorage → menos exposto a XSS). O refresh vem em cookie httpOnly que o
// browser envia sozinho para /api/auth/refresh. `apiFetch` injeta o Bearer e, no
// 401, tenta um refresh transparente uma vez antes de desistir.

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8700";

export interface Usuario {
  id: string;
  email: string;
  nome: string | null;
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

// Wrapper de fetch autenticado: injeta o Bearer e, no 401, tenta UM refresh e repete.
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

  let res = await fetch(`${API_BASE}${path}`, comAuth(accessToken));
  if (res.status === 401) {
    try {
      const novo = await refresh();
      res = await fetch(`${API_BASE}${path}`, comAuth(novo));
    } catch {
      /* refresh falhou — devolve o 401 original para o chamador tratar */
    }
  }
  return res;
}
