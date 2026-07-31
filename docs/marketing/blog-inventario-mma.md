# Blog do voaz.app — inventário do sistema MMA (voya) e plano de reaproveitamento

**Data:** 31/07/2026 · Fonte: código real de `voya/mma` + `voya/pipelines` enviado pelo operador
(93 arquivos de código analisados). Status: PROPOSTA para especificação da fase BLOG.

## 1. O que o sistema antigo é (inventário honesto)

Uma fábrica de conteúdo multi-canal construída para o projeto de viagens (marca "Voaz" da
época), em dois pacotes:

**`mma/` — geração e publicação:**
- **Blog** (`blog_generator.py` + `queues/blog_topics.yaml` + `scripts/run_blog_generator.sh`):
  fila de tópicos em YAML → gerador chama **Gemini** (flash-lite, temperatura 0.3, saída 16k)
  com um *context file* factual do destino no prompt → valida o JSON → grava
  `apps/web/content/blog/YYYY-MM-DD-slug.json` → marca `published: true` na fila → chama o
  webhook `/webhooks/revalidate` do Next.js (ISR on-demand: revalida `/blog/<slug>`, `/blog` e
  `/sitemap.xml` SEM rebuild, zero downtime). Rodava 1×/dia via cron/systemd com lock e log
  diário. Maduro e bem resolvido.
- **Descoberta de pauta**: `viral_researcher` (Apify coleta Reels viral de Instagram por
  hashtag) → `topic_extractor` (LLM lê os top 20 por engajamento + histórico de 4 semanas
  anti-repetição → propõe 14 temas novos) → `content_planner` (calendário).
- **Vídeo/carrossel** (não é alvo agora): script_writer, geradores, montador de vídeo,
  biblioteca de música, publicadores YouTube/TikTok/Pinterest.
- **Governança**: `review_queue` (fila aprovar/rejeitar ANTES de publicar) +
  `telegram_notifier` (manda o conteúdo pro celular do operador via bot) +
  `analytics_collector/analyzer` + histórico de temas.

**`pipelines/` — coleta e conhecimento:**
- Coletores: **YouTube Data API v3 + transcrições** (queries em 3 camadas, filtro de duração
  3-20 min e de recência 12 meses), **TikTok** (Apify scraper + transcrição Supadata),
  TripAdvisor, Google Maps/Places.
- Processamento: `llm_extractor` (estrutura o que os vídeos dizem), `trust_score`,
  `consolidator`, RAG (vector store + cache semântico).

**APIs externas usadas e custo:** Gemini (centavos/artigo), YouTube Data API (grátis por
quota), Apify (crédito grátis de US$ 5 cobria o uso), Supadata (transcrição TikTok),
Pexels/Pixabay/Unsplash/Flickr/Wikimedia (imagens, grátis), Telegram Bot (grátis). Custo
marginal por artigo de blog: **centavos**.

## 2. Diagnóstico para o voaz.app de hoje

O que PORTA direto (arquitetura provada):
1. **O ciclo do blog inteiro**: fila YAML → gerador → JSON por artigo → `/blog/[slug]` no
   Next.js com ISR on-demand via webhook secreto → cron com lock/log. É exatamente o desenho
   que queremos, já depurado (inclusive o caso "fila vazia = no-op sem erro").
2. **A fila de revisão + Telegram**: vira o GATE humano do blog (no sistema antigo o gate era
   só para vídeos; o blog publicava direto — aqui o gate passa a valer para o blog também).
3. **O coletor de YouTube com transcrições** (grátis): minera PAUTA nos canais/podcasts do
   setor de loteamento (Jornada do Loteamento etc.) — temas e perguntas, nunca reescrita de
   episódio (direito autoral + relacionamento; artigo nosso cita e linka a fonte).
4. **Histórico anti-repetição de temas** e o padrão "context file factual no prompt".

O que MUDA na adaptação:
1. **LLM**: Gemini → **API da Anthropic**, que já é a nossa infra (chave no backend, custo por
   uso já medido no admin via `uso_llm`). Um provedor só para operar.
2. **Grounding**: o "context file do destino" vira o nosso acervo verificado: as lições legais
   do projeto (piso 125 m², regime rural, índice ausente…), leis com artigo (Planalto) e dados
   agregados da plataforma. Regra do CLAUDE.md vale para o blog: afirmação legal exige
   lei/artigo verificado — entra um **estágio verificador de citações** antes da fila.
3. **Cadência**: 1/dia automático → **2-3/semana com aprovação do operador** (política Google
   de scaled content abuse + marca que vive de proveniência).
4. **Estilo**: Light Copy (skill marketing-vendas) + disclaimer de triagem onde couber.

## 3. Fases propostas (BLOG-1 a BLOG-4)

- **BLOG-1 — Blog no ar (sem automação):** `/blog` e `/blog/[slug]` no Next.js do voaz
  (artigos em JSON/MD no repo, ISR, sitemap dinâmico incluindo posts, JSON-LD Article,
  RSS opcional). 3 artigos de estreia escritos das lições que JÁ temos documentadas.
- **BLOG-2 — Gerador com gate:** port do `blog_generator` (Anthropic) + fila
  `blog_topics.yaml` + verificador de citação legal + webhook revalidate + aprovação
  (Telegram bot ou tela no admin) + cron 2-3×/semana no Lightsail.
- **BLOG-3 — Minerador de pauta:** port do coletor YouTube (transcrições dos canais do setor)
  + extrator de temas com histórico anti-repetição alimentando a fila (sempre como pauta
  sugerida, aprovada pelo operador antes de gerar).
- **BLOG-4 (depois, com dados):** pautas a partir de agregados da plataforma ("X% das glebas
  analisadas tinham APP não declarada") — conteúdo que só a voaz.app pode escrever.

Custos: BLOG-1 zero; BLOG-2/3 centavos por artigo (Anthropic) + APIs grátis (YouTube).
Decisões do operador antes do BLOG-2: canal de aprovação (Telegram × admin) e cadência.
