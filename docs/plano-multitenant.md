# Plano — Multi-tenant, Autenticação e Painel Admin (v1, para revisão)

> Status: **PROPOSTA para revisão** (nenhum código escrito ainda). Decisões do operador já fixadas:
> banco **PostgreSQL**, **auth de produção**, revisar este plano antes de codar.
> Objetivo: transformar a ferramenta single-tenant atual numa **plataforma multi-tenant (SaaS)** com
> clientes (registro/login), área do cliente (salvar/recarregar/editar análises) e painel admin.

---

## 0. Estado atual (ponto de partida)
- **Persistência:** nenhuma. `app/core/store.py` é um `dict` em memória (`STORE`), indexado por
  `analise_id` (hash do KMZ). **Some no restart.**
- **Auth:** nenhuma. Endpoints abertos.
- **Frontend:** uma página (`app/page.tsx`), sem login.
- **Deploy:** Docker Compose (`api` + `web`), sem serviço de banco.

Tudo isso é **aditivo** — o motor de análise (geo/urbanismo) não muda; ele passa a rodar **no
contexto de um usuário e de uma análise salva**.

---

## 1. Stack a adicionar (backend)
- **PostgreSQL 16** — serviço novo no Compose (`db`), com volume persistente.
- **SQLAlchemy 2.x** (ORM) + **Alembic** (migrações versionadas).
- **psycopg[binary]** (driver Postgres).
- **Auth:** `pyjwt` (tokens), `passlib[bcrypt]` (hash de senha), `python-multipart` (forms).
- **Pydantic v2** (já no projeto) para os schemas de request/response.

### Recomendação de auth (você pediu): **JWT próprio, padrão de produção**
- **Senha:** `bcrypt` (passlib), custo 12. Nunca em texto.
- **Tokens:** **access token** JWT curto (~30 min, assinado com `JWT_SECRET` por env) + **refresh
  token** longo (~7 dias) em **cookie httpOnly + Secure + SameSite=Lax** (não acessível por JS →
  resistente a XSS). Rotação de refresh no uso.
- **Guarda:** dependências FastAPI `usuario_atual` (decodifica o access token) e `requer_admin`.
- **Por que não uma lib?** Você precisa de papel admin, análises com dono e métricas próprias —
  schema customizado onde `fastapi-users` atrapalha mais do que ajuda. JWT próprio (~150 linhas) dá
  controle total e é produção de verdade. *(Alternativa gerenciada: Auth0/Cognito — só se quiser
  zero responsabilidade sobre senha/sessão, ao custo de 3º + mensalidade.)*

---

## 2. Modelos (tabelas)

### `usuarios`
| campo | tipo | nota |
|---|---|---|
| id | UUID (pk) | |
| email | citext único | login |
| senha_hash | text | bcrypt |
| nome | text? | opcional |
| papel | enum(`cliente`,`admin`) | default `cliente` |
| ativo | bool | default true (soft-disable) |
| criado_em | timestamptz | |

### `analises`
| campo | tipo | nota |
|---|---|---|
| id | UUID (pk) | |
| usuario_id | UUID (fk → usuarios) | **dono** (multi-tenant) |
| titulo | text | nome dado pelo cliente |
| kmz_nome | text | arquivo original |
| gleba_geojson | jsonb | a geometria da gleba (p/ recarregar sem reupload) |
| cidade | text? | da jurisdição resolvida |
| uf | text? | idem |
| area_ha | numeric? | |
| resultados | jsonb | **snapshot** das dimensões já medidas (p/ exibir sem re-rodar) |
| criada_em / atualizada_em | timestamptz | |

> "Salvar análise" = persistir `gleba_geojson` + `resultados` + metadados, vinculados ao usuário.
> "Carregar" = ler do banco e reidratar a tela. "Editar" = re-rodar uma dimensão (ex.: regenerar o
> urbanismo com outro perfil/lote-máx) e atualizar `resultados` + `atualizada_em`.

*(O `STORE` em memória vira um cache opcional; a fonte de verdade passa a ser o Postgres.)*

---

## 3. Endpoints (API)

### Auth (`/api/auth`)
- `POST /registrar` `{email, senha, nome?}` → cria `cliente`, devolve access token + set-cookie refresh.
- `POST /login` `{email, senha}` → access token + set-cookie refresh.
- `POST /refresh` (cookie) → novo access token.
- `POST /logout` → limpa o cookie.
- `GET /me` → dados do usuário logado.

### Cliente (`/api/analises`, exige login; escopo = só as suas)
- `GET /` → lista as análises do usuário (id, título, cidade, UF, área, datas).
- `POST /` → salva a análise atual (gleba + resultados) vinculada ao usuário.
- `GET /{id}` → carrega (só do dono; 403/404 senão).
- `PUT /{id}` → edita/re-roda e atualiza.
- `DELETE /{id}`.

### Admin (`/api/admin`, exige papel admin)
- `GET /metricas` → cards: nº de clientes, nº de análises, nº por cidade/UF, novos no mês.
- `GET /clientes` → lista: email, data de cadastro, nº de análises, cidades/UFs analisadas.

> As dimensões existentes (ambiental, declividade, urbanismo…) passam a exigir login e a operar
> sobre uma `analise` do usuário (o `analise_id` deixa de ser global anônimo).

---

## 4. Frontend
- **Páginas novas:** `/login`, `/registrar`. `/admin` (painel).
- **Contexto de auth:** guarda o access token em memória (não em localStorage → menos XSS); o refresh
  vem do cookie httpOnly. Um wrapper de `fetch` injeta o `Authorization: Bearer` e tenta `/refresh`
  no 401.
- **Rotas protegidas:** sem login → redireciona a `/login`.
- **Área do cliente (seu #2):** tela "Minhas análises" — lista (cards) das análises salvas; clicar
  **carrega** a análise na dashboard atual; botões **editar** (re-roda) e **excluir**. Botão "Salvar"
  na análise corrente.
- **Painel admin (seu #3):** `/admin` com **cards**: total de clientes, total de análises, novos
  clientes no mês, distribuição por cidade/UF; tabela de clientes (email, cadastro, nº análises,
  cidades). Visível só p/ `papel=admin`.

---

## 5. Deploy / Compose
- Novo serviço **`db`** (postgres:16) com volume `pgdata` e healthcheck.
- `api` ganha `DATABASE_URL`, `JWT_SECRET`, `JWT_REFRESH_SECRET` (env, gitignored), e roda
  **`alembic upgrade head`** no start (entrypoint) antes do uvicorn.
- Primeiro admin: criado por um **comando de seed** (`python -m scripts.criar_admin email senha`),
  não pela UI (segurança).

---

## 6. Segurança (produção)
- Senha bcrypt; segredos JWT por env (rotacionáveis); HTTPS obrigatório (cookie Secure).
- Refresh em cookie httpOnly+SameSite; access token curto.
- Autorização por dono em toda análise (nunca confiar no id do cliente sem checar `usuario_id`).
- Rate-limit no `/login` (fase 2 — evita brute force).
- **LGPD:** email é dado pessoal — guardar o mínimo, permitir exclusão de conta (fase posterior).
- Verificação de email e reset de senha: **fase posterior** (não bloqueiam o MVP).

---

## 7. Fases de entrega (cada uma testável e commitada)
1. **Fundação** — ✅ **FEITA (Fase 12.1).** Compose com Postgres (serviço `db` + volume + healthcheck);
   SQLAlchemy 2.x (Alembic listado, `create_all` no MVP); modelos `usuarios`/`analises`; auth
   (registrar/login/refresh/logout/me) + guardas `usuario_atual`/`requer_admin`; frontend `/login`,
   `/registrar`, `AuthProvider` (token em memória + refresh httpOnly), `RequireAuth` + Sair na TopBar.
   10 testes de auth; suíte verde (415 passed).
2. **Área do cliente (#2)** — ✅ **FEITA (Fase 12.2).** `/api/salvas` (CRUD escopado ao dono) +
   `POST /{id}/carregar` (reidrata a gleba no STORE → re-rodar = editar); tela "Minhas análises"
   (cards Abrir/Excluir) + botão Salvar/Atualizar na TopBar. 6 testes; isolamento multi-tenant.
3. **Painel admin (#3)** — ✅ **FEITA (Fase 12.3).** Papel admin + seed `scripts/criar_admin.py`;
   `/api/admin/metricas` e `/api/admin/clientes`; tela `/admin` com cards (3 KPIs + 2 distribuições)
   + tabela de clientes; link Admin na TopBar só p/ admin. 4 testes.

> **Plano concluído.** Próximos passos opcionais (não bloqueiam): Alembic versionado (hoje
> `create_all`), rate-limit no `/login`, verificação de e-mail / reset de senha, exclusão de
> conta (LGPD), pré-carregar os resultados salvos nos cards (hoje "carregar" reidrata e re-roda).

---

## 8. Decisões em aberto p/ você confirmar
1. **Onde roda o Postgres?** Container no Compose (mais simples, você gerencia backup) **ou** instância
   gerenciada (RDS/Lightsail Managed DB — mais robusto, custo)? *(Recomendo container no Compose p/
   começar; migra fácil.)*
2. **Cadastro aberto?** Qualquer um pode se registrar como cliente, ou só por convite/aprovação?
   *(Recomendo aberto no MVP, com possibilidade de desativar usuário.)*
3. **Edição de análise = re-rodar** (re-gera as dimensões com novos parâmetros) **ou** só editar
   metadados (título)? *(Recomendo re-rodar — é o valor real.)*
4. **Token no front:** em memória + refresh httpOnly (recomendado/seguro) está ok?

Confirma esses 4 pontos (ou ajusta) e eu começo pela **Fase 1**.
