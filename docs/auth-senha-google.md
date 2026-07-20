# Recuperação de senha + Login com Google — runbook do operador

**Data:** 20/07/2026 · Recursos: (1) "Esqueci minha senha" por e-mail (Gmail SMTP),
(2) troca de senha logado (menu do avatar), (3) login/cadastro com o Google.

## Como funciona (resumo técnico)

- `POST /api/auth/esqueci` responde **sempre 200 com a mesma mensagem** (não revela se o
  e-mail existe) e, quando a conta existe, envia um link `/redefinir?token=...` por e-mail.
  No banco fica só o **SHA-256** do token; validade 60 min (`RESET_SENHA_TTL_MIN`); uso
  único; um pedido novo invalida o link anterior.
- `POST /api/auth/redefinir` troca a senha e **derruba as sessões refresh antigas**: o
  refresh token carrega a impressão da senha (claim `sh`); senha mudou → refresh antigo
  morre no próximo uso. Efeito colateral do deploy: **todo mundo faz 1 re-login** (tokens
  antigos não têm o claim).
- `POST /api/auth/trocar-senha` (logado) exige a senha atual; a própria sessão recebe um
  cookie novo e continua viva.
- `POST /api/auth/google` recebe o ID token do botão do Google, valida no endpoint
  `tokeninfo` do Google (assinatura + expiração) e confere `aud` = `GOOGLE_CLIENT_ID` e
  `email_verified`. Conta nova nasce **sem senha** (`senha_hash` vazio); e-mail já
  cadastrado é **vinculado** (mesmo usuário, análises preservadas). Sem `GOOGLE_CLIENT_ID`
  no backend o endpoint responde 503 e sem `NEXT_PUBLIC_GOOGLE_CLIENT_ID` no front o botão
  nem aparece.
- Sem `SMTP_USER`/`SMTP_PASS` o backend entra em **modo dev**: não envia e-mail e imprime
  o link de redefinição no log da API (dá para testar o fluxo inteiro sem credencial).

## Passo a passo 1 — senha de app do Gmail (para o SMTP)

Pré-requisito: a conta Google precisa ter **verificação em duas etapas ativa** (sem ela o
Google não mostra a página de senhas de app).

1. Abra <https://myaccount.google.com/apppasswords> e entre com a conta que será a
   remetente dos e-mails.
2. Em "Nome do app", digite `viabilidade-homeeye` e clique **Criar**.
3. O Google mostra uma senha de **16 letras** (ex.: `abcd efgh ijkl mnop`). Copie-a agora —
   ela não aparece de novo.
4. Guarde no `backend/.env` (os espaços podem ficar; o Gmail aceita com ou sem).

## Passo a passo 2 — OAuth Client ID no Google Cloud Console

1. Abra <https://console.cloud.google.com/> e entre com sua conta Google.
2. Na barra superior, clique no seletor de projeto → **Novo projeto** → nome
   `viabilidade-homeeye` → **Criar** (e selecione o projeto criado).
3. Menu ☰ → **APIs e serviços → Tela de permissão OAuth** (Google Auth Platform):
   - Nome do app: `Viabilidade homeeye`; e-mail de suporte: o seu.
   - Público: **Externo**. Contato do desenvolvedor: o seu e-mail. Salvar.
   - Não precisa adicionar escopo nenhum (login básico usa e-mail/nome/foto).
   - Se aparecer "Status de publicação: Em teste", clique **Publicar app** (login básico
     não passa por verificação do Google).
4. Menu ☰ → **APIs e serviços → Credenciais** → **Criar credenciais → ID do cliente
   OAuth**:
   - Tipo de aplicativo: **Aplicativo da Web**. Nome: `viabilidade-web`.
   - **Origens JavaScript autorizadas** (adicione as três):
     - `http://localhost:3700`
     - `http://localhost` (o botão do Google exige a origem sem porta também, em dev)
     - `https://SEU_DOMINIO` (troque pelo domínio real quando a AWS entrar)
   - URIs de redirecionamento: **deixe vazio** (o botão GIS não usa redirect).
   - **Criar**.
5. Copie o **ID do cliente** (formato `1234567890-abc123.apps.googleusercontent.com`).
   O client secret NÃO é usado (fluxo de ID token só precisa do ID, que é público).

## Configuração (dev local no Mac)

No `backend/.env` (troque pelos valores reais):

```
SMTP_USER=SEU_EMAIL@gmail.com
SMTP_PASS=SENHA_DE_APP_16_LETRAS
APP_URL_BASE=http://localhost:3700
GOOGLE_CLIENT_ID=SEU_CLIENT_ID.apps.googleusercontent.com
```

No front, o mesmo Client ID entra como `NEXT_PUBLIC_GOOGLE_CLIENT_ID` — é argumento de
**build** (fica no bundle), então containers precisam de rebuild com a env exportada.

## Produção (docker-compose.prod.yml)

- `APP_URL_BASE` já sai de `https://${DOMINIO}` automaticamente.
- `SMTP_USER`/`SMTP_PASS`/`GOOGLE_CLIENT_ID` vêm do `backend/.env` da instância.
- Exporte `NEXT_PUBLIC_GOOGLE_CLIENT_ID` no ambiente do `docker compose ... up --build`
  (build arg do serviço `web`).
- No Google Cloud Console, confirme que `https://SEU_DOMINIO` está nas Origens
  JavaScript autorizadas.

## Teste de aceitação (roteiro)

1. Sem SMTP configurado: pedir "Esqueci minha senha" → o link aparece no log da API
   (`[EMAIL MODO DEV...]`); abrir o link, criar senha nova, logar.
2. Com SMTP: mesmo fluxo, e-mail real na caixa de entrada.
3. Link usado 2ª vez → erro "inválido, já foi usado ou expirou".
4. Botão "Continuar com o Google" no /login e /registrar: conta nova entra direto;
   e-mail já cadastrado entra na MESMA conta (análises preservadas).
5. Conta nascida pelo Google tentando logar com senha → mensagem orientando usar o
   Google ou criar senha; no menu do avatar, "Alterar senha" define a primeira senha
   sem pedir a atual.
