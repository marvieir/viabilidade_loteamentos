# Changelog

Registro das mudanças relevantes do estudo de massa / urbanismo. Mais recente no topo.
Convenção: cada entrada traz o **problema**, a **correção** e o **efeito medido** (pipeline real
São Roque, salvo nota). A régua continua sendo a dos `CLAUDE.md`/`ARCHITECTURE.md`: cálculo só no
backend, determinismo, proveniência, e valores-ouro por fase passando.

## [não publicado] — 2026-06-23

### Fase 11.14 — fallback de IA no gerador de programa (Claude → Gemini → preset)
- **Problema (operador):** picos de `529 OverloadedError` (sobrecarga da Anthropic) derrubavam a
  proposta da IA direto para o preset — a cadeia era 100% Anthropic com 1 retry só.
- **Correção:** o gerador virou uma **cadeia de provedores** (`GeradorProgramaEmCadeia`): Claude
  (com `max_retries=2` no 529 + rung **Haiku** barato no fim da cadeia) → **Gemini** (fallback) →
  **preset** determinístico. O 1º que responder vence; todos falharem → preset com o motivo real na
  proveniência. A lógica de fusão/cap (consistência §4) foi extraída p/ `_montar_programa` — UM só
  lugar, idêntico p/ os dois provedores (mesmo contrato §2: a IA não devolve nº/área).
- **Gemini 3.5 Flash** com *thinking* nível **médio**: JSON mode (o formato de tool difere do
  Claude), SDK `google-genai` com import TARDIO e gated por `GOOGLE_API_KEY` (sem chave → ignora).
  Modelo e nível de thinking **configuráveis por env** (`URBANISMO_GEMINI_MODELO`,
  `URBANISMO_GEMINI_THINKING`) — corrige o ID/nível sem mexer no código. `_gemini_thinking` é
  robusto à versão do SDK (tenta `thinking_level`; cai p/ `thinking_budget`).
- **Wiring honesto:** o gerador liga se houver `ANTHROPIC_API_KEY` **e/ou**
  `GOOGLE_API_KEY`/`GEMINI_API_KEY` (funciona só com o Gemini também). Sem nenhuma → 503 honesto,
  como antes. `.env.example` documenta tudo. Suíte **448 passed** (+17 testes do fallback, todos
  offline — provedores e `types` fakes, sem rede).

### Fase 11.13 — motor de urbanismo consciente da declividade (slope-aware)
- **Problema (operador):** o motor jogava lotes para a encosta e deixava VERDE no platô plano.
  Causa: entre 0–30%, o motor era **cego à inclinação** — só conhecia a vedação binária ≥30%
  (Lei 6.766). A escolha de verde (`_selecionar_verde`) usava só a FORMA da face (irregular →
  verde), nunca a inclinação. Um platô plano de forma irregular virava verde; uma encosta de
  20–25% de forma regular virava lote — invertido do ponto de vista de terraplenagem/valor.
- **Correção:** a análise de declividade (que já calcula a malha de inclinação) passa a
  **poligonizar também a faixa acentuada >20%** (`geojson_acentuada`). O motor recebe essa faixa
  como **penalidade SUAVE**: faces predominantemente íngremes (≥25% cobertas por >20% de
  declividade) viram VERDE/preservação ANTES das planas — sobra o terreno plano para os lotes.
- **Determinismo preservado:** sem DEM (glebas sintéticas dos valores-ouro), a faixa é vazia → a
  ordenação é idêntica à anterior. Suíte **431 passed** (inalterada) + testes novos do
  comportamento slope-aware. Ressalva honesta mantida: GLO-30 é DSM 30 m (pode superestimar
  declividade sob mata), então é orientativo.
- **Declividade por LOTE no mapa:** o backend amostra a declividade média (%) de cada lote no DEM
  (`amostrar_declividade`, mesma grade de `analisar_declividade`) e a devolve nas propriedades de
  `lotes_features`. O popup do lote passa a exibir `decliv. X%` junto de tamanho/quadra/score. Tudo
  no backend (CLAUDE.md §1): o front só renderiza. Sem DEM → omite (não inventa). Lote menor que o
  pixel (30 m) cai no pixel mais próximo do centroide — ORIENTATIVO, não greide de projeto.

### Fase 12.3 — painel admin (SaaS, parte 3/3)
- **Backend:** router `/api/admin` (guarda `requer_admin`): `GET /metricas` (nº de clientes,
  nº de análises, novos clientes no mês, distribuição por UF e por cidade) e `GET /clientes`
  (e-mail, data de cadastro, nº de análises, cidades/UFs analisadas). `scripts/criar_admin.py`
  — seed do 1º admin (cria ou **promove** um e-mail; senha por prompt; idempotente). Admin
  **nunca** nasce pela UI. 4 testes (guarda 403/401, agregação, listagem).
- **Frontend:** página `/admin` com **cards** (3 KPIs + 2 distribuições) e tabela de clientes;
  link "Admin" na TopBar visível só para `papel=admin`; dupla checagem (front + backend).

### Fase 12.2 — área do cliente: salvar/carregar/editar/excluir análises (SaaS, parte 2/3)
- **Backend:** router `/api/salvas` (escopado ao dono — multi-tenant): `GET` lista, `POST`
  salva (gleba + snapshot de resultados), `GET/{id}` detalha, `PUT/{id}` edita, `DELETE/{id}`,
  e `POST/{id}/carregar` que **reidrata a gleba no STORE** (reaproveita todo o pipeline de
  dimensões) e devolve o shape do upload — daí o cliente re-roda (edita) com novos parâmetros.
  Isolamento testado (intruso recebe 404, não vê/edita/exclui). 6 testes.
- **Frontend:** componente "Minhas análises" (cards: título, cidade/UF, área, data; Abrir /
  Excluir) na tela inicial; botão **Salvar análise / Atualizar** na TopBar (POST 1ª vez, PUT
  depois) que persiste a geometria + os JSONs que os cards já receberam. `tsc` limpo.

### Fase 12.1 — fundação multi-tenant: banco + autenticação (SaaS, parte 1/3)
- **O quê:** primeiro passo do plano `docs/plano-multitenant.md` — a ferramenta deixa de ser
  single-tenant anônima e ganha **contas de cliente** (registro/login). Aditivo: o motor de
  análise não muda; passa a rodar sob um usuário autenticado.
- **Backend:**
  - `app/core/db.py` — camada SQLAlchemy 2.x agnóstica ao banco (SQLite no dev/teste, Postgres
    em produção, só a `DATABASE_URL` muda); `criar_tabelas()` idempotente no boot (lifespan).
  - `app/models/db_models.py` — modelos `usuarios` (id/email/senha_hash/nome/papel/ativo/criado_em)
    e `analises` (dono + gleba_geojson + cidade/uf/area_ha + resultados snapshot + datas).
  - `app/core/auth.py` — senha **bcrypt** (passlib); sessão **JWT** (access 30 min no header,
    refresh 7 dias em cookie httpOnly); guardas `usuario_atual` e `requer_admin`.
  - `app/routers/auth.py` — `/api/auth/registrar|login|refresh|logout|me`. Cadastro **aberto**
    (vira `cliente`); refresh rotacionado no uso; e-mail case-insensitive.
  - 10 testes de fluxo (`tests/test_auth.py`) — registro/login/refresh/me/guarda 401, e-mail
    duplicado, senha curta. Suíte **415 passed, 3 skipped** (sem regressão).
- **Frontend:** `AuthProvider` (token em **memória** + refresh silencioso no load), wrapper
  `apiFetch` (injeta Bearer, tenta refresh no 401), páginas `/login` e `/registrar`, porteiro
  `RequireAuth` (sem login → `/login`) e chip de usuário + **Sair** na TopBar. `tsc` limpo.
- **Deploy:** Compose ganha serviço **`db`** (postgres:16 + volume `pgdata` + healthcheck);
  `api` recebe `DATABASE_URL`/`JWT_SECRET`/`JWT_REFRESH_SECRET`/`COOKIE_SECURE` (env). `.env.example`
  e `requirements.txt` atualizados (SQLAlchemy, Alembic, psycopg, PyJWT, passlib[bcrypt]).
- **Próximo (12.2):** área do cliente — salvar/listar/carregar/editar/excluir análises.

### Fase 11.12 — alerta de VOCAÇÃO do terreno (topografia → perfil sugerido)
- **Ideia (operador):** alertar o cliente sobre a vocação do terreno pela topografia. O card de
  Urbanismo agora mostra, com base na declividade já calculada (média + fração ≥30%):
  serra (média ≥15% ou ≥12% em ≥30%) → **vocação ALTA RENDA** (lotes amplos, baixa densidade);
  plano (<8% e <5% em ≥30%) → viável p/ todos; relevo moderado → média/alta. Se o público-alvo
  selecionado **conflita** com a vocação (ex.: baixa renda em serra), o aviso fica âmbar e sugere
  ajustar — sem bloquear. Frontend-only; usa o `dadosDecliv` que a análise de declividade já produz.

### Fase 11.11 — validação de tamanho de lote na interface (o app corrige o usuário)
- **Princípio (operador):** o cliente pode errar ao sugerir tamanhos; o papel da app é corrigi-lo —
  (a) corrigir sozinha o que é seguro (já feito no 11.10: janela mínima no default), (b) AVISAR
  quando o usuário força algo ruim (sem bloquear).
- **Correção:** no campo "Lote máx.", quando o valor está perto demais do piso legal da zona (janela
  apertada → sobra), a interface mostra um aviso na hora com o tamanho recomendado (≥ 1,5× piso) ou
  sugere deixar vazio (padrão seguro). Frontend-only; usa o piso que o estudo já devolve.
- Pendente (próximo): alerta de VOCAÇÃO do terreno (topografia/localização → perfil sugerido).

### Fase 11.10 — folga mínima de janela de lote (mata a sobra da baixa renda)
- **Causa raiz:** quando a ZONA força o piso acima do teto de mercado (baixa renda em zona de mín.
  360 vs mercado 250), `[piso, teto]` COLAPSA para ≈ [360, 360] — quase nenhuma faixa cabe num lote
  de área exata → **sobra de 40-49%** (um retângulo limpo de 2.974 m² dava 1 lote só).
- **Correção:** sem `lote_max` do operador, garante `teto ≥ 1,5× piso` de janela p/ a subdivisão
  respirar (operador que fixa `lote_max` assume o aperto).
- **Efeito (baixa, São Roque):** vendável **11% → 38,1%**, lotes **21 → 58**, sobra **40% → 13,4%**.
  Suíte verde.

### Fase 11.8 — campo "lote máx." no menu (#1) + feedback do "Analisar tudo" (#3)
- **#1 — teto de lote pelo operador:** novo campo "Lote máx. (m²)" no menu de urbanismo (4º, ao lado
  de tipo/público/zona). Sobrepõe o teto de MERCADO do perfil (`resolver_diretrizes(..., lote_max_m2)`),
  nunca abaixo do piso legal. Vazio = padrão do perfil. Permite controlar o tamanho máximo de lote por
  estudo sem mexer no código (a generalização do 11.7).
- **#3 — "Analisar tudo" com progresso:** o botão não dava feedback (a prop `analisando` nem era
  passada → parecia que nada acontecia). Agora: botão vira "Analisando…", e cada item do menu lateral
  ganha um ponto âmbar pulsando (analisando) → verde (concluído). Implementado reaproveitando o
  `onData` que cada card já dispara ao concluir (sem editar os cards); timeout de segurança limpa
  estados presos. Suíte backend verde, tsc limpo.

### Fase 11.7 — teto de lote premium (alta renda): +area loteavel, -sobra
- **Descoberta (cobrança do operador):** o teto de 640 m² NÃO é legal (a LUOS São Roque/MUE só fixa
  o PISO de 360 m²; não há teto na diretriz). O 640 era a `faixa` de **referência de MERCADO** do
  perfil 'alta' no código (`PERFIL_LOTE`), uma convenção — não a prefeitura.
- **Correção:** teto de mercado do perfil **alta** 640 → **1.000 m²** (premium). Os lotes maiores
  ABSORVEM o fundo de quadra que virava sobra. Baixa/média mantêm tetos baixos (densidade).
- **Efeito (fixture real):** vendável **34,0% → 41,9%**, sobra **11,6% → 3,9%**, nº de lotes
  praticamente igual (46→45, lotes maiores em vez de sobra), área média 524 → 661 m². Suíte verde.

### Fase 11.6 — corrige `temperature` (quebrava a IA) + 3 verdes distintos no mapa
- **Bug crítico (regressão da 11.5):** `temperature=0.0` causava **400 "temperature is deprecated for
  this model"** (Opus 4.8/Fable 5) → a chamada à IA falhava e caía sempre no preset. Removido o
  parâmetro; a consistência fica com o CAP de lazer/largura (motor é dono da medida) + a regra 5 da
  instrução. A IA volta a propor de fato.
- **Cores (operador):** as áreas verde reservada / verde remanescente / bosque preservado usavam
  tons quase iguais (confundia). Agora 3 cores DISTINTAS: park = verde médio sólido (#22c55e);
  remanescente = lima claro amarelado (#bef264); bosque = floresta bem escuro (#14532d).

### Fase 11.5 — CONSISTÊNCIA: domar a variância da IA (mesma gleba → mesmo resultado)
- **Problema:** regenerar a mesma gleba dava resultados muito diferentes (51 lotes numa rodada, 36
  noutra) e o operador achava que o motor piorava a cada clique. Causa: a chamada ao LLM usava
  `temperature` default (**1.0 = máxima aleatoriedade**) → a IA sorteava lazer/esqueleto diferentes
  toda vez. O motor é determinístico; a borda da IA não era.
- **Correções:** (1) `temperature=0.0` na chamada ao LLM → mesma gleba propõe ~o mesmo programa
  sempre. (2) CAP de lazer no caminho do LLM: a IA pode REDUZIR o lazer (mais lote) mas não exceder
  o padrão do perfil (alta 20%, média 12%, baixa 5%) — não toca override EXPLÍCITO do usuário.
  (3) Regra 5 no `_INSTRUCAO`: consistência + qualidade (use valores-padrão do perfil, esqueleto
  limpo, prefira bons lotes a desenho rebuscado).
- **Efeito:** o resultado para de "pular" entre regenerações; o nº de lotes fica estável (~46) em vez
  de depender de sorte. Suíte verde.

### Fase 11.4 (revertida) — vias locais curvas p/ alta renda: funcionou no São Roque mas crashava em
  glebas sintéticas + conflitava com 2 valores-ouro (grade orientada, convergência lazer). Estética
  pura (não adiciona lote); fica para um esforço dedicado.

### Fase 11.3b — pórtico na ENTRADA real (onde a via toca a borda) + marcador magenta achável.

### Fase 11.3 — PÓRTICO/entrada visível no mapa
- **Problema:** o motor já calculava a entrada única (ponto do arruamento junto à borda de acesso) e
  contava `pórtico=1`, mas era só diagnóstico — **não aparecia** como componente no mapa.
- **Correção:** `Layout.portico` (disco no acesso, sobre a via-tronco) emitido no GeoJSON; frontend
  renderiza o overlay `urb_portico` (marcador laranja forte) + legenda "Pórtico / entrada".
- Pendente (componentes nomeados — mirante/quiosque/lago): amenidades ainda agrupadas como
  lazer/verde; nomeá-las é evolução futura.

### Fase 11.2 — verde na TERRA MARGINAL (boas práticas §3.4)
- **Problema:** `_selecionar_verde` reservava as MAIORES faces como verde → tomava a parcela nobre
  (o platô), que então virava sobra; as faces irregulares (que lotam mal) viravam lote ruim.
- **Correção (Unwin/Alexander, `boas-praticas-loteamento.md` §3.4):** reserva primeiro as faces
  MENOS aptas a lote (mais irregulares/côncavas), deixando as REGULARES e cheias para virar lote.
- **Efeito (fixture real):** vendável **29,9% → 34,0%**, **n 40 → 46 (+6 lotes)**, sobra cai. Suíte
  verde (2 valores-ouro de recuperação recalibrados: a recuperação/fusão viraram OPCIONAIS porque o
  layout §3.4 reduz a necessidade — os invariantes reais seguem: zero órfão p/ verde, clamp, n_lotes
  não regride).

### Fase 11.1 — subdivisão no EIXO PRÓPRIO da parcela (Lynch/Hack)
- A quadra se orienta à FORMA do sítio (menor retângulo rotacionado), não ao eixo global — recupera
  parcela oblíqua/irregular que a grelha global desperdiçava. Never-worse (compara e escolhe). +3
  lotes, invariância preservada.

### Fase 10.8b — ≥30% é verde preservado, não "sobra"
- **Problema:** o quadro contabilizava a faixa de declividade ≥30% (não-edificável por lei) como
  "sobra geométrica a reduzir", inflando a sobra para ~39% e assustando a leitura.
- **Correção:** as faces ≥30% vão para um balde próprio (`nao_edif_reg`) que soma ao **verde
  reservado/preservado**, fora da sobra — e fora da recuperação aditiva (que poderia tentar lotear
  o ≥30%, ilegal).
- **Efeito:** sobra geométrica **30,4% → 15,5%** (só a fragmentação real); verde
  reserva/preservada **14% → ~29%** (mesma faixa de áreas verdes da referência URBIA). Vendável
  inalterado (rótulo não cria lote).

### Fase 10.8 — A gleba vira UMA (≥30% veda LOTE, não VIA)
- **Problema:** o motor recortava a faixa ≥30% **inteira** do aproveitável (tirava via *e* lote),
  deixando a gleba partida em duas porções ligadas só por uma via diagonal em "dente de serra" que
  cruzava o meio. Era o "loteamento partido" reclamado.
- **Base legal:** Lei 6.766/79 art. 3º, parág. único, III — veda **parcelamento** (lote) em ≥30%,
  **não a via** (estrada é regida por greide/corte-aterro). Vedação relativa a lote.
- **Correção:** o ≥30% **não sai mais do domínio das vias** — a malha viária atravessa a faixa e
  junta a gleba num loteamento só; só os **lotes** a evitam (a parte ≥30% vira verde preservado).
  Mata/APP seguem bloqueando via + lote.
- **Efeito:** malha **conecta as duas metades** (antes saía em 7 componentes soltos);
  viário **24,5% → 17,1%**; **0 m² de lote no ≥30%**. Com a gleba conexa, a travessia diagonal
  deixa de ser necessária.

### Fase 10.6 — Corte de viário (largura de via)
- **Correção:** cap da largura de via em **11 m** na fronteira do programa (condomínio de lotes =
  vias privadas, coletora de pista única; engine é dono da medida, §2). Independe do que a IA
  proponha. `CAIXA_TRONCO_M` (conexão) 14 → 11.
- **Efeito (sintético comparável):** viário **31,4% → 28,0%**; vendável **36,4% → 37,4%**.

### Fase 10.5 — Backstop de densidade (acesso interno em faces fundas)
- **Problema:** faces muito fundas (profundidade ≥ ~4·prof) só loteavam 2 fileiras na frente e o
  miolo virava sobra.
- **Correção:** `_adensar_face` injeta vias locais internas que cortam a face funda em bandas
  rasas, dando frente ao miolo; a via é clipada à face (não vaza para a restrição).
- **Efeito (sintético):** vendável **32,6% → 36,4%**; sobra **20,5% → 15,0%**.

### Modelo de IA
- Cadeia de modelos para `/propor`: usa **Opus 4.8** hoje (melhor disponível); **Fable 5** atrás de
  flag para o futuro.

### Revertido / descartado (não está no código)
- **Fase 10.7** — tratar as metades como núcleos independentes (sem travessia quando há acesso
  externo): descartada. Deixava a gleba partida em loteamentos soltos (7 componentes), o oposto do
  desejado. A 10.8 resolve juntando de verdade.
- **Recuperação por "eixo próprio"** — relotear blocos de sobra no eixo do próprio bloco: descartada.
  Ganho mínimo (+2 lotes; o `garantir_frente_via` dropava as fileiras sem frente) e quebrava testes
  de invariância de área.

### Pendências
- Recuperar a sobra restante (~15%, concentrada em poucos blocos que precisam de acesso interno
  próprio, com conservação de área garantida).
- Inteligência de subdivisão **por perfil**: alta renda = posicionar **valor** (cul-de-sac premium,
  lote grande em cota alta/fundo de mata); baixa/média = **densidade máxima** (mini-malha).
- Apresentação da base do percentual (área líquida) quando o ≥30% entra no domínio das vias.
