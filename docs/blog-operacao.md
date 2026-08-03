# Blog — operação do gerador com aprovação via Telegram (BLOG-2)

> Runbook de ATIVAÇÃO e operação. O código vive em `backend/scripts/blog/` (roda dentro do
> container da api); os artigos e o estado vivem no volume `blog_conteudo` (produção) ou em
> `frontend/content/blog` (dev no Mac, bind no próprio repo). Cadência decidida pelo
> operador (31/07): 2-3 propostas por semana, nada publica sem aprovação no Telegram.

## Como funciona (visão de 1 minuto)

1. Cron chama `gerar` (seg/qua/sex): pega o próximo tópico de `fila_topicos.yaml`, escreve
   o artigo via API Anthropic usando SÓ o acervo legal verificado (`acervo_legal.md`), passa
   no verificador (citações, fontes oficiais, estilo Light Copy) e manda a proposta pro SEU
   Telegram com botões Aprovar/Rejeitar. O rascunho fica em `_rascunhos/`.
2. Cron chama `aprovacoes` (a cada 10 min): lê suas respostas. Aprovou → publica o JSON no
   diretório do web, chama o webhook de revalidação e te devolve a URL. Rejeitou → arquiva.
3. Custo de cada artigo aparece no painel admin (dimensão "blog", medidor uso_llm).

## Ativação (uma vez)

### 1. Criar o bot no Telegram (2 min)
No Telegram: fale com **@BotFather** → `/newbot` → dê um nome (ex.: "voaz blog") e um
username (ex.: `voaz_blog_bot`). Ele devolve o **token** (formato `123456:ABC-...`).

### 2. Variáveis de ambiente
No `backend/.env` (Mac E AWS — a api é quem roda o gerador):

```
TELEGRAM_BOT_TOKEN="o-token-do-botfather"
TELEGRAM_CHAT_ID=""            # preenchido no passo 3
REVALIDATE_SECRET="uma-string-aleatoria-forte"
```

No `.env` da RAIZ (Mac E AWS — o compose repassa ao web):

```
REVALIDATE_SECRET="a MESMA string do backend/.env"
```

Gerar uma string forte: `openssl rand -hex 24`

### 3. Descobrir o seu chat_id
Abra o bot no Telegram e mande qualquer mensagem ("oi"). Depois:

```bash
# Mac (dev):
podman-compose exec -T api python -m scripts.blog.aprovacoes --descobrir-chat
# AWS (produção):
docker compose -f docker-compose.prod.yml exec -T api python -m scripts.blog.aprovacoes --descobrir-chat
```

Copie o `chat_id` impresso para `TELEGRAM_CHAT_ID` no `backend/.env` e recrie a api
(`podman-compose up -d api` / `docker compose -f docker-compose.prod.yml up -d api`).

### 4. Teste de ponta a ponta SEM gastar IA

```bash
docker compose -f docker-compose.prod.yml exec -T api python -m scripts.blog.gerar --sem-llm
```

Deve chegar uma proposta de teste no seu Telegram. Toque **Aprovar** e rode:

```bash
docker compose -f docker-compose.prod.yml exec -T api python -m scripts.blog.aprovacoes
```

O bot responde com a URL publicada. (Artigo de teste no ar? Apague o arquivo no volume e
revalide, ou simplesmente rejeite em vez de aprovar no teste.)

### 5. Cron no host da AWS (a cadência 2-3/semana)

`crontab -e` do usuário ubuntu, adicionar:

```cron
# Blog voaz.app — propostas seg/qua/sex 12:00 UTC (9h de Brasília)
0 12 * * 1,3,5 cd ~/viabilidade_loteamentos && /usr/bin/docker compose -f docker-compose.prod.yml exec -T api python -m scripts.blog.gerar >> ~/blog-gerador.log 2>&1
# Blog voaz.app — processa aprovações do Telegram a cada 10 min
*/10 * * * * cd ~/viabilidade_loteamentos && /usr/bin/docker compose -f docker-compose.prod.yml exec -T api python -m scripts.blog.aprovacoes >> ~/blog-aprovacoes.log 2>&1
```

## Operação do dia a dia

- **Pauta**: editar `backend/scripts/blog/fila_topicos.yaml` (versionado; slug novo = artigo
  novo na esteira). Regra: a IA só cita lei que esteja em `acervo_legal.md`; lei nova entra
  no acervo SÓ verificada na fonte (Planalto) e commitada.
- **Aprovar/rejeitar**: botões na mensagem do Telegram. Rejeitado não regenera sozinho.
- **Gerar fora de hora**: rodar o comando do cron na mão (com `--slug <slug>` para um tópico
  específico; `--dry-run` para ver sem enviar).
- **Logs**: `~/blog-gerador.log` e `~/blog-aprovacoes.log` no host da AWS.
- **Custo**: painel admin → uso de IA → dimensão "blog" (centavos por artigo).
