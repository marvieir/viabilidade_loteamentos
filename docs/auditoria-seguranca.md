# Auditoria de Segurança Web — Pré-Viabilidade de Loteamento

> Revisão do código real (FastAPI + Next.js) para o deploy de produção (AWS Lightsail).
> Severidades: **CRÍTICO / ALTO / MÉDIO / BAIXO**. **MUST-FIX** = não expor à internet sem corrigir.

## 1) Autenticação / Login / JWT
Base razoável (bcrypt real, access em memória, refresh em cookie httpOnly, segredos separados), mas faltam controles de abuso e o boot tolera segredo default.

- **[CRÍTICO · MUST-FIX] Segredos JWT com default inseguro.** `core/auth.py:31-32` usa `JWT_SECRET`/`JWT_REFRESH_SECRET` com fallback `"dev-inseguro-*"`, repetidos no `docker-compose.yml` e no `.env.example`. Quem ler o repo forja um access token de admin. → Gerar segredos aleatórios (`secrets.token_urlsafe(48)`), só por env/secret manager; **abortar o boot** se ausentes/iguais ao default quando `ENV=production`.
- **[ALTO · MUST-FIX] Sem rate limiting / anti-brute-force** em `/login`, `/registrar`, `/refresh` (`routers/auth.py`). `/registrar` aberto → criação massiva de contas. → `slowapi` por IP + lockout por conta após N falhas; CAPTCHA no registro.
- **[MÉDIO] Cookie de refresh com `Secure` desligado por default** (`COOKIE_SECURE=0`). → exigir `COOKIE_SECURE=1` em produção HTTPS.
- **[MÉDIO] Política de senha fraca** (`min_length=8`, sem complexidade). → aumentar e checar senhas comuns.
- **[MÉDIO] Refresh stateless sem revogação** — logout não invalida o token (7 dias). → tabela de refresh (jti) com revogação + detecção de reuso (pós-MVP).
- **[BAIXO] Validação de e-mail manual** (`"@" in email`). → usar `EmailStr`.

## 2) Banco de Dados
- **[CRÍTICO · MUST-FIX] Senha default do Postgres = `viabilidade`** no `docker-compose.yml`. → exigir `POSTGRES_PASSWORD` forte por env/secret (sem default); usuário de app sem superuser.
- **[BAIXO — OK] SQL injection: baixo risco** — tudo via ORM SQLAlchemy parametrizado; isolamento multi-tenant correto nas análises *salvas* (`salvas.py:1161-1165`).
- **[MÉDIO] DB sem TLS / sem least-privilege explícito.** → `sslmode=require` se o banco for externo (RDS/Lightsail Managed); usuário sem DDL em produção.
- **[MÉDIO] Sem migrações** — `create_all` no boot (Alembic está nas deps mas não é usado). → adotar Alembic antes de dados reais.

## 3) Backend / API
- **[CRÍTICO · MUST-FIX] Endpoints de análise SEM autenticação e SEM dono.** Só `admin`/`salvas`/`auth` exigem login; os 13 routers de dimensão (`analises`, `ambiental`, `vegetacao`, `urbanismo`, …) são abertos. O `STORE` é um dict global em memória indexado por `analise_id` = **UUID5 determinístico do hash do KMZ** (`analises.py:566,722`) — previsível. Qualquer um lê/recalcula a análise de outro. → proteger **todos** com `Depends(usuario_atual)`; vincular cada registro ao `usuario.id` e validar dono; trocar o ID determinístico por token de sessão não adivinhável.
- **[ALTO · MUST-FIX] CORS default `*` com `allow_credentials=True`** (`main.py:57-64`) se `CORS_ORIGINS` não setado. → exigir origem explícita (domínio do front) em produção.
- **[ALTO · MUST-FIX] Upload sem limite de tamanho** (`analises.py:684`, `juridico.py:88`, `perfil.py:70`) → DoS de memória. Pior: `/juridico/extrair` e `/municipios/{cod}/perfil` chamam **LLM pago (Anthropic) sem auth e sem limite** → DoS financeiro anônimo da `ANTHROPIC_API_KEY`. → teto de tamanho (10–25 MB) antes de `read()`; **autenticar + cotar** os endpoints de LLM.
- **[ALTO] Zip-bomb no parser de KMZ** (`core/kmz.py:34-46`) — lê o `.kml` descomprimido sem checar tamanho. → checar `zipinfo.file_size` somado contra um teto antes de `read()`.
- **[ALTO · MUST-FIX] Sem security headers / sem TrustedHost** (`main.py` só tem CORS). → middleware com `Strict-Transport-Security`, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`/CSP, `Referrer-Policy` + `TrustedHostMiddleware` (ou no reverse proxy).
- **[MÉDIO] Vazamento de stack trace** se `DEBUG`/reload for ligado por engano. → garantir `ENV=production` desliga debug + handler genérico.
- **[BAIXO — OK] SSRF baixo** — hosts externos fixos (WorldCover/Copernicus/OpenTopography/Overpass), sem URL arbitrária do usuário.

## 4) Frontend
- **[OK] Token em memória, não em localStorage** (`lib/auth.ts`) + refresh em cookie httpOnly — resistente a XSS de roubo.
- **[OK] Sem sink de XSS** (nenhum `dangerouslySetInnerHTML` no app).
- **[OK] Sem segredo no bundle** — só `NEXT_PUBLIC_API_BASE` (público por design). → apontar p/ HTTPS de produção.

## 5) Segredos / Config
- **[CRÍTICO · MUST-FIX] Defaults inseguros nos 3 segredos** (JWT×2 + POSTGRES_PASSWORD). → sem default; boot falha se ausentes; trocar literais do `.env.example` por `CHANGE_ME`.
- **[OK] `.env` gitignored** — nenhum segredo real commitado.

## 6) Deploy / TLS / Infra (Lightsail)
- **[CRÍTICO · MUST-FIX] Sem TLS / sem reverse proxy** — compose expõe `api:8700` e `web:3700` em HTTP puro. Login/JWT trafegam em claro. → reverse proxy com TLS (Caddy/nginx + Let's Encrypt); só o proxy exposto.
- **[ALTO · MUST-FIX] API publicada no host** (`8700:8700`) contorna o proxy. → não publicar 8700/3700 no host em produção; firewall do Lightsail só 443.
- **[MÉDIO] Containers rodam como root** (Dockerfiles sem `USER`). → usuário não-root.
- **[BAIXO] Dependências defasadas** (`next@14.2.21`). → `npm audit`/`pip-audit` + patch do `next`.

## TOP-10 MUST-FIX antes de expor (Lightsail)
1. **Auth + propriedade por usuário em TODOS os routers de dimensão**; trocar o `analise_id` determinístico por token não adivinhável (CRÍTICO).
2. **Eliminar segredos default** (JWT×2 + Postgres): sem fallback, boot falha se ausentes; `.env.example` com `CHANGE_ME` (CRÍTICO).
3. **TLS + reverse proxy** (Caddy/nginx + Let's Encrypt); não publicar 8700/3700; só 443 (CRÍTICO).
4. **Autenticar + cotar endpoints de LLM** (`/juridico/extrair`, `/perfil`) — DoS financeiro (ALTO).
5. **Limite de upload + anti zip-bomb** (KMZ/PDF) (ALTO).
6. **Rate limiting** em login/registro/refresh (ALTO).
7. **CORS explícito** (domínio do front), nunca `*` com credentials (ALTO).
8. **Security headers + TrustedHost** (ALTO).
9. **`COOKIE_SECURE=1`** em produção (MÉDIO, depende do #3).
10. **Postgres com senha forte + não-root + TLS no DB se externo**; adotar Alembic (MÉDIO).

### Já correto (não regredir)
bcrypt real; access em memória + refresh httpOnly; ORM parametrizado; isolamento multi-tenant nas *salvas*/admin; segredos access≠refresh com checagem de `tipo`; `.env` gitignored; SSRF baixo.

> **Achado central:** o isolamento multi-tenant existe na camada *persistida* (`salvas`/`admin`), mas é **inexistente** na camada *de trabalho* (`STORE` em memória + routers de dimensão) — onde mora toda a análise ativa. É o item nº1.
