# Fluxo de trabalho: Mac (teste) → AWS (produção)

> Dois ambientes, duas branches. Nada vai pra produção sem passar pelo teste no Mac.
>
> - **`dev`** — branch de trabalho/teste. O **Mac** roda e testa esta.
> - **`main`** — branch de produção. A **AWS** roda **só** esta. `main` só avança depois que o Mac aprova.

```
  (alteração) ──push──> dev ──pull──> MAC testa ──aprovou?──> merge dev→main ──pull──> AWS deploy
                         (teste)                              (promoção)              (produção)
```

## Fase 1 — Alteração (no código)
Eu (assistente) faço a mudança, rodo os testes automáticos (pytest + tsc/vitest) e **empurro pra `dev`**.
Você não precisa fazer nada aqui além de pedir a alteração. (Se você editar direto no Mac: `git add -A && git commit -m "..." && git push origin dev`.)

## Fase 2 — Testar no MAC (ambiente de teste)
```bash
cd ~/CAMINHO/viabilidade_loteamentos          # ajuste o caminho
git checkout dev && git pull origin dev
podman-compose up -d --build                  # (ou: docker compose up -d --build) — stack DEV em localhost
# abra http://localhost:3700 e teste o que mudou
# logs: podman-compose logs -f api
```
> O Mac usa o `docker-compose.yml` (dev): portas em localhost, **sem** `ENV=production`. O `.env` de dev do Mac é local e gitignored — `git pull` não mexe nele.

## Fase 3 — Promover pra produção (só depois de aprovar no Mac)
```bash
git checkout main && git pull origin main
git merge dev && git push origin main
git checkout dev                              # volta pra dev p/ continuar trabalhando
```
> Posso fazer essa promoção por você quando você disser "aprovado no Mac".

## Fase 4 — Deploy na AWS (produção)
```bash
ssh -i ~/Downloads/LightsailDefaultKey-*.pem ubuntu@54.245.119.252
cd ~/viabilidade_loteamentos
git checkout main && git pull origin main
docker compose -f docker-compose.prod.yml up -d --build
```
**Mais rápido — rebuilda só o serviço que mudou:**
```bash
# só frontend mudou:
docker compose -f docker-compose.prod.yml up -d --build web
# só backend mudou:
docker compose -f docker-compose.prod.yml up -d --build api
```
> O `backend/.env` de **produção** (segredos, `ENV=production`) fica só na instância, gitignored — `git pull` nunca o sobrescreve.

## Rollback (se um deploy quebrar a produção)
```bash
# na AWS
git log --oneline -8                          # ache o último commit BOM
git reset --hard <commit-bom>
docker compose -f docker-compose.prod.yml up -d --build
```

## Regras de ouro
1. **Nunca** rode a Fase 4 (AWS) sem ter feito a Fase 2 (testar no Mac).
2. `main` = o que está em produção. Trate como sagrado.
3. **Segredos/.env nunca entram no git** (já gitignored) — cada máquina tem o seu.
4. **Mudou o schema do banco?** Em produção, `create_all` só CRIA tabela nova; **não altera** coluna existente. Quando começar a evoluir o schema com dados reais → **Alembic** (pendente). Até lá, mudanças de schema pedem cuidado manual.
5. **Hard refresh no navegador** (Cmd+Shift+R) depois de subir o frontend — o bundle JS fica em cache.
