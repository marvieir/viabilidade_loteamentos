# Migração para AWS Lightsail — plano

> Objetivo: rodar a plataforma (api FastAPI + web Next.js + Postgres) no Lightsail, **com HTTPS e
> segura**. Pré-requisito: os **MUST-FIX** de `docs/auditoria-seguranca.md` (a app hoje **não pode**
> ser exposta à internet — todos os endpoints de análise são anônimos e os segredos têm default).

## 1) Arquitetura alvo
```
            Internet (443)
                │  HTTPS (Let's Encrypt)
        ┌───────▼────────┐
        │  Caddy (proxy) │  termina TLS, injeta security headers
        └───┬────────┬───┘
            │        │
     /api/* │        │ /  (resto)
        ┌───▼──┐  ┌──▼───┐
        │ api  │  │ web  │   (NÃO publicam porta no host)
        │8700  │  │3700  │
        └──┬───┘  └──────┘
           │ rede interna
        ┌──▼───┐
        │  db  │   Postgres (volume; porta NÃO exposta)
        └──────┘
```
- **1 instância Lightsail** (Ubuntu, mín. **2 GB RAM / 2 vCPU** — o rasterio/pyogrio/Overpass pesam; 4 GB folgado) com Docker + Compose.
- **Caddy** como reverse proxy: HTTPS automático (Let's Encrypt), o ÚNICO serviço com porta pública (443/80). `api` e `web` ficam só na rede interna do Compose.
- **Postgres**: começa como container com volume + backup (snapshot Lightsail). Evoluir p/ **Lightsail Managed Database** (TLS + backups automáticos) quando houver dados reais.
- **IP estático** Lightsail + **domínio** apontando pra ele; Caddy emite o certificado.

## 2) Pré-requisitos de segurança (FAZER ANTES de expor) — resumo dos MUST-FIX
1. **Auth em todos os routers de dimensão** + dono por usuário + `analise_id` não adivinhável.
2. **Segredos sem default** (JWT×2 + Postgres); boot falha se ausentes em produção.
3. **Caddy + TLS**; não publicar 8700/3700; firewall só 443/80/22.
4. **Autenticar + cotar** endpoints de LLM; **limite de upload + anti zip-bomb**.
5. **Rate limiting** login/registro/refresh; **CORS explícito**; **security headers**; **`COOKIE_SECURE=1`**.
6. **Postgres senha forte**; containers **não-root**.

> Sem 1–2–3 a migração não deve ir ao ar. 4–6 entram junto ou logo em seguida.

## 3) Mudanças de código/infra necessárias (issues a abrir)
- **`config` central com `ENV`**: em `ENV=production`, abortar boot se `JWT_SECRET`/`JWT_REFRESH_SECRET`/`POSTGRES_PASSWORD`/`CORS_ORIGINS` ausentes ou default.
- **Dependência de auth** nos routers de dimensão (`Depends(usuario_atual)`) + `STORE` escopado por `usuario.id` (ou persistir e validar dono).
- **Middlewares**: rate limit (`slowapi`), security headers, `TrustedHostMiddleware`, limite de body.
- **`docker-compose.prod.yml`**: remove `ports:` de api/web; adiciona serviço `caddy` (com volume de certs); `restart: unless-stopped`; `env_file` só de segredos.
- **`Caddyfile`**: `dominio { reverse_proxy /api/* api:8700 ; reverse_proxy web:3700 ; header { Strict-Transport-Security ... } }`.
- **Dockerfiles**: `USER appuser` (não-root) em api e web; `web` buildado com `NEXT_PUBLIC_API_BASE=https://<dominio>`.

## 4) Passo a passo do deploy
1. **Provisionar**: instância Lightsail Ubuntu + IP estático; abrir no firewall só **22, 80, 443**.
2. **Base**: `ssh`; instalar Docker + Compose plugin; criar usuário deploy.
3. **DNS**: apontar `A` do domínio (e `www`) para o IP estático.
4. **Código**: `git clone` (branch de produção) na instância.
5. **Segredos**: criar `backend/.env` na instância (NÃO no repo) com segredos **gerados** (`openssl rand -base64 48`): `JWT_SECRET`, `JWT_REFRESH_SECRET`, `POSTGRES_PASSWORD`, `ANTHROPIC_API_KEY`, `CORS_ORIGINS=https://<dominio>`, `COOKIE_SECURE=1`, `ENV=production`.
6. **Subir**: `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build`.
7. **TLS**: o Caddy emite o cert automaticamente no primeiro acesso 443 (ter DNS já propagado).
8. **Smoke**: `https://<dominio>` carrega; login funciona; cookie `Secure`+`HttpOnly`; `curl http://<ip>:8700` **recusa** (porta fechada); endpoints de análise exigem login.
9. **Backups**: habilitar **snapshots automáticos** do Lightsail (instância) + dump periódico do Postgres (`pg_dump` em cron → bucket/Lightsail object storage).
10. **Dados ambientais**: copiar os `.gpkg` (CAR/Mata Atlântica/etc.) p/ um volume na instância e apontar os `AMBIENTAL_*_PATH` (ver `docs/baixar-dados-ambientais.md`).

## 5) Checklist de hardening (pós-subida)
- [ ] `nmap`/scan externo: só 22/80/443 abertas; 8700/3700/5432 fechadas.
- [ ] Headers OK (`curl -I`): HSTS, nosniff, X-Frame-Options/CSP.
- [ ] Login com rate limit (testar N tentativas → 429).
- [ ] Endpoints de análise/LLM retornam 401 sem token.
- [ ] Cookie de refresh `Secure; HttpOnly; SameSite=Lax; Path=/api/auth`.
- [ ] Upload grande (>limite) → 413; KMZ zip-bomb → recusado.
- [ ] SSH só por chave (senha desabilitada); `ufw`/firewall do Lightsail ativo.
- [ ] `pip-audit` / `npm audit` sem CVE crítica; `next` no último 14.2.x.
- [ ] Backups testados (restaurar um snapshot/dump).

## 6) Custo / dimensionamento (referência)
- Instância 2 GB ≈ faixa de US$ ~10–12/mês; 4 GB ≈ US$ ~20/mês. IP estático grátis enquanto anexado.
- Managed Database (quando migrar o Postgres) entra como custo adicional, com TLS+backup inclusos.
- Egress: as consultas externas (WorldCover/Overpass/ArcGIS) saem da instância — Lightsail inclui franquia de transferência generosa; monitorar.

## Ordem sugerida de execução
**Fase A (bloqueia o go-live):** segredos sem default + boot guard → auth nos routers + dono → Caddy/TLS + firewall.
**Fase B (junto/logo após):** rate limit + upload/zip-bomb + LLM cotado + headers + CORS + cookie secure.
**Fase C (robustez):** Alembic + Managed DB + não-root + backups automatizados + audit de deps.
