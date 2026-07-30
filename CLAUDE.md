# CLAUDE.md — Convenções do projeto

> Leia este arquivo e o `ARCHITECTURE.md` no início de cada sessão.
> A spec da fase atual está em `docs/fase-N-*.md`. Esses três são a fonte de verdade.

## Idioma (INEGOCIÁVEL)
- **Fale SEMPRE em português com o operador. Nunca em outra língua**, em nenhuma
  circunstância (respostas, resumos, status, avisos). Código/identificadores em inglês
  quando for a convenção da linguagem, mas toda comunicação com o operador é em português.

## O projeto
Ferramenta de **pré-viabilidade de loteamento**: recebe o KMZ de uma gleba e produz
uma análise de triagem (não decide aprovação municipal). Backend FastAPI + frontend
Next.js. Detalhes e parâmetros legais em `ARCHITECTURE.md`.

## Regras inegociáveis (quebrar isto é regressão)
1. **Cálculo numérico só no backend Python.** Nunca no frontend, nunca via LLM.
2. **Frontend só renderiza JSON.** Proibido geo-matemática em JavaScript.
3. **Todo número devolvido carrega proveniência** (fonte legal, perfil, data de referência).
4. **Determinismo:** mesma entrada → mesma saída, sempre.
5. **Não inventar dado de jurisdição ausente.** Sem perfil municipal → degradar para
   nível federal e rotular cobertura (`BASE_FEDERAL` / `PARCIAL_UF` / `COMPLETA`).

## Convenção de portas (este projeto)
- Frontend: porta **> 3700** (default `3700`).
- Backend: porta **> 8700** (default `8700`).

## Backend
- Python 3.11+, FastAPI, Pydantic v2.
- Geo: `shapely` 2.x, `pyproj`, `rasterio`. Área/perímetro por **cálculo geodésico**
  (`pyproj.Geod`), não por área em graus.
- Cada dimensão de viabilidade = **um router/endpoint** isolado.
- Testes: `pytest`. Toda fase tem testes contra os **valores-ouro** da sua spec.
  Não considere a fase pronta sem esses testes passando.
- Estrutura sugerida:
  ```
  backend/
    app/
      main.py
      routers/        # um arquivo por dimensão
      core/           # parse KMZ, geometria, jurisdição (motor determinístico)
      models/         # schemas Pydantic (contratos de API)
      perfis/         # camadas federal/estadual/municipal
    tests/            # valores-ouro por fase
  ```

## Frontend
- Next.js (App Router), TypeScript, Tailwind, **shadcn/ui** para componentes (cards,
  tabs, dialog, table, badge).
- Mapa: **react-leaflet**. Polígono e buffers vêm como GeoJSON do backend;
  camadas oficiais entram como `TileLayer.WMS`.
- Cada dimensão = **um card** que chama seu endpoint sob demanda.
- O front nunca recalcula nem reformata números — exibe o que o backend mandou,
  incluindo a proveniência.
- Estrutura sugerida:
  ```
  frontend/
    app/
    components/
      mapa/           # MapaLeaflet, camadas WMS, render do polígono
      cards/          # um card por dimensão
      ui/             # shadcn
    lib/api.ts        # cliente do backend
  ```

## Disciplina de implementação
- **Incrementos pequenos e testáveis.** Se quebrar, volte ao último estado estável (git).
- **Sem over-engineering.** A spec fixa contrato e restrições; o resto é latitude sua.
  Não adicione abstração, fila, cache ou microsserviço que a fase não pediu.
- Pense na solução completa mais simples antes de codar. Nada de solução parcial que gere retrabalho.
- Não tire conclusão sem ter a informação. Em dúvida de **design/contrato**, pare e
  pergunte (a dúvida volta para a sessão de especificação, não se resolve chutando).

## Deploy
- Docker Compose com dois serviços: `api` (FastAPI) e `web` (Next.js). Alvo: Lightsail.

## Produção (AWS Lightsail) — dados fixos da operação
- **IP da instância:** `54.245.119.252` (SSH: `ssh ubuntu@54.245.119.252`)
- **Domínio:** `https://voaz.app` (desde 30/07/2026; `viabilidade.homeeye.ai` redireciona 301
  via bloco `DOMINIO_ANTIGO` do Caddyfile — o DNS antigo precisa continuar apontando p/ a instância)
- Código na instância em `~/viabilidade_loteamentos`, branch `main`; deploy:
  `docker compose -f docker-compose.prod.yml up -d --build`
  **São DOIS arquivos de ambiente** (lição da migração de domínio, 30/07 — custou 4 rodadas):
  `.env` da RAIZ = variáveis do compose (`DOMINIO`, `DOMINIO_ANTIGO`, `POSTGRES_PASSWORD`,
  `NEXT_PUBLIC_GOOGLE_CLIENT_ID`); `backend/.env` = variáveis internas da api
  (`ALLOWED_HOSTS`, `CORS_ORIGINS`, `ANTHROPIC_API_KEY`…). Trocar domínio exige tocar nos dois.
  `ALLOWED_HOSTS` DEVE incluir o host interno: `voaz.app,api` — o SSR do Next chama a api por
  `http://api:8700`, e sem o `api` na lista o TrustedHost responde 400 em todo o SSR.
  Google OAuth: o Client ID precisa de `https://voaz.app` nas Authorized JavaScript origins.
- Fluxo obrigatório: alterações → teste no Mac do operador (podman) → só então AWS.
- **Ritual de atualização no Mac (lição de 26/07 — o `up -d` NÃO recria container com
  imagem nova, e build sem espaço falha deixando a imagem velha no ar):**
  `git pull` → `podman-compose build --no-cache <serviços>` → `podman-compose down` →
  `podman-compose up -d` → **verificar com `podman-compose exec api grep -c "<string
  do commit>" <arquivo>`** antes de testar no navegador. Nunca `up --build`.

## Verdade antes de resposta (INEGOCIÁVEL)
- **Nunca responder "para dar uma resposta".** Se não houver certeza fundamentada
  (conhecimento treinado sólido OU verificação feita agora), a resposta certa é: pesquisar
  primeiro, perguntar depois — nunca chutar.
- **Matéria legal/regulatória** (parcelamento urbano × rural, Lei 6.766, Estatuto da
  Terra/Lei 5.868/INCRA, Código Florestal/Lei 12.651, LUOS, registro imobiliário):
  VERIFICAR a base legal ANTES de implementar qualquer regra no produto, citando
  lei/artigo na resposta e no código. Regra de produto sem base legal identificada =
  parar e perguntar ao operador.
- **Fontes de pesquisa, nesta ordem:** texto da lei (Planalto), doutrina/artigos
  técnicos e sites confiáveis do setor registral/urbanístico, livros, e conteúdo de
  referência do mercado de loteamentos (ex.: podcast **Jornada do Loteamento**).
- Se após pesquisar a dúvida persistir → **perguntar ao operador como resolver**, com as
  opções encontradas. Ele é do setor; a decisão de produto é dele.
- **Lição registrada (21-22/07/2026):** o regime RURAL difere do urbano em pontos que
  estavam em lei e foram herdados sem verificação — sem doação institucional, sem área
  verde de doação, vedação de declividade 30% é urbana (rural: APP só ≥45°), piso de
  lote é a FMP/INCRA. Cada um custou uma rodada de teste do operador. Não repetir o
  padrão: régua legal se verifica na fonte, não se assume.
- **Lição registrada (27/07/2026):** NÃO existe "piso de lote por padrão/público" em lei —
  o piso é o federal de 125 m² (Lei 6.766/79, art. 4º, II) e, acima dele, só o mínimo da
  ZONA quando a LUOS está confirmada. O "piso de mercado" do perfil é mira/orientação
  rotulada, nunca trava. O piso inventado colapsava a janela do alto padrão ([450,450])
  e gerava 1 lote / 63% de sobra em silêncio. Restrição no produto exige base legal.
- **Regra geral (28/07/2026, decisão do operador):** índice que NÃO estiver no documento
  carregado não vira restrição. Se a LUOS/diretriz do município não traz o lote mínimo,
  o motor usa SEMPRE o piso federal de 125 m² (Lei 6.766/79, art. 4º, II) e rotula
  `BASE_FEDERAL` — vale para qualquer urbanismo gerado. **Nunca hardcode número de
  município no código**, mesmo que o operador cite o valor em conversa (ex.: "sei que
  nesse município é 180 m²"): informação de conversa não é fonte legal. O caminho para
  o valor entrar é o documento extraído + confirmação humana, ou o campo de piso
  informado na tela (que só pode SUBIR o piso, nunca descer abaixo da lei).

- **Lição registrada (28/07/2026) — medir COBERTURA, não só precisão:** na importação de DWG
  a auditoria dizia "diferença mediana 0,05%" e passava total confiança, enquanto o motor
  achava só 115 dos 129 lotes que o desenho declara (78% da área). A régua media *"os lotes
  que achei estão certos?"* e nunca *"achei todos os lotes?"*. Sempre que o insumo DECLARA um
  total (soma dos rótulos de área do CAD, quadro-resumo da planta, área do levantamento),
  comparar o que produzimos contra esse total — e avisar quando não bate. Precisão alta sobre
  amostra incompleta é o pior tipo de número: parece confiável e está errado.
- **Lição registrada (28/07/2026) — não abandonar pista por relato:** cheguei a testar a
  camada certa ('P2'), vi 127 lotes, e ABANDONEI a pista porque o relato repassado dizia 115
  lotes. O desenho declarava 129, e o dono do projeto confirmou 129 depois. Relato de memória
  não vence medição do arquivo: quando divergem, medir de novo antes de descartar a hipótese.

## Comunicação com o operador (INEGOCIÁVEL)
- **Sempre passe instruções COMPLETAS e prontas para colar.** Nada de comando pela metade.
  Para qualquer passo no Mac do operador, inclua: **de qual diretório** rodar (`cd …` com o
  caminho absoluto), o comando exato, e o que esperar de saída.
- Ao mexer no que roda em **container**: diga explicitamente se precisa **`git pull`**,
  se precisa **rebuildar** (`podman-compose up --build -d`) ou só reiniciar, e como ver logs.
- Ao mexer no que roda **local (dev)**: diga se precisa reiniciar o `uvicorn`/`npm run dev`,
  e quais **variáveis de ambiente** ligar (preferir `backend/.env`, não `export` solto).
- Placeholders (ex.: `SUA_GLEBA.kmz`) devem vir marcados como "troque pelo caminho real".
- Se uma ação depende de algo que o operador precisa ter (arquivo, dado, rede), **diga antes**
  e ofereça o plano B. Prefira errar por excesso de detalhe a deixar o operador adivinhando.
