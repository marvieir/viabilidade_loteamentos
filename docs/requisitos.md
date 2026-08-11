# Documento de Requisitos — voaz.app

> **O que é este documento:** a lista COMPLETA do que a plataforma faz (requisitos funcionais)
> e das regras que ela obedece (não-funcionais), em linguagem de negócio. O COMO cada item
> funciona por dentro está no par deste documento: `docs/requisitos-detalhados.md`.
>
> **Como se mantém:** toda fase nova de desenvolvimento adiciona/altera o(s) RF(s) daqui, o
> detalhamento correspondente e o mapa mental (`docs/mapa-mental.md`) — no mesmo commit da
> fase. Requisito sem ID aqui não existe oficialmente.
>
> Atualizado em: 30/07/2026 · Cobertura: tudo que está em produção em `voaz.app`.

---

## 1. Visão do produto

A voaz.app é uma plataforma de **pré-viabilidade (triagem) de loteamento**: recebe o KMZ de
uma gleba e responde, em minutos, quantos lotes cabem, quanto sobra, o que trava e onde vale
gastar com due diligence — com a fonte legal ao lado de cada número.

**Não é**: aprovação municipal, projeto executivo, parecer jurídico nem medição oficial.
Toda tela e todo laudo declaram isso (regra §1-A).

**Atores:** *visitante* (site público + laudo de exemplo), *cliente* (analisa as próprias
glebas), *admin* (painel, custos de IA, publicação do exemplo), *operador* (Marco — decisões
de produto e perfis municipais).

---

## 2. Requisitos funcionais

### RF-ENT — Entrada e identificação da gleba
- **RF-ENT-1** Receber KMZ/KML da gleba; classificar o conteúdo (polígono da gleba × outras camadas).
- **RF-ENT-2** Aceitar 2+ KMZ vizinhos e tratá-los como projeto único (união geométrica).
- **RF-ENT-3** Medir área e perímetro por **cálculo geodésico** (nunca em graus).
- **RF-ENT-4** Detectar município/UF/código IBGE pela geometria (malha IBGE), com correção manual.
- **RF-ENT-5** Auto-salvar a análise no upload; upsert em "Minhas análises" (um trabalho = uma linha).
- **RF-ENT-6** Receber levantamento planialtimétrico (DWG/DXF) no nível da gleba.

### RF-AMB — Pré-análise ambiental
- **RF-AMB-1** Cruzar a gleba com camadas oficiais: APP/hidrografia (ANA), unidades de conservação (ICMBio), mineração (SIGMINE/ANM), Reserva Legal (SICAR/CAR), domínio Mata Atlântica (IBGE), malha fundiária (SIGEF/SNCI), massa d'água. Cada alerta com fonte e data.
- **RF-AMB-2** Vegetação: cobertura (ESA WorldCover) com severidade **restrição dura × a verificar** (cruzamento com APP/UC).
- **RF-AMB-3** Declividade (DEM Copernicus): faixas + vedação ≥30% (urbano, Lei 6.766 art. 3º); no regime rural a régua muda (APP só ≥45°, Lei 12.651).
- **RF-AMB-4** Bacia hidrográfica e bioma como contexto descritivo.
- **RF-AMB-5** Execução registrada no servidor (a trilha reconhece na hora, sem depender de salvar).
- **RF-AMB-6** Camada indisponível → declarar "não consultada", nunca inferir ausência de problema.
- **RF-AMB-7** **Reconciliação pós-vistoria (AMB-EXC, planos pagos, Brasil todo):** manchas do
  "verde a verificar" numeradas com **segunda opinião automática** por mancha (WorldCover ×
  MapBiomas Col.10 × CAR — nada é liberado por satélite); registro do **laudo de campo** que
  declara FATOS (estágio/formação/achados) e o motor aplica a consequência legal citando o
  dispositivo (régua em 3 camadas com degradação honesta: federal Lei 12.651 → bioma — Mata
  Atlântica arts. 25/30/31, Pampa IN 01/2021 → perfil de UF); efeito **bidirecional** (libera
  E adiciona banhado/nascente achados em campo); histórico versionado com proveniência
  (laudo, RT, data, artigo); o aproveitável/urbanismo passam a usar a área reconciliada.
  **Nativa "mediante autorização" NÃO conta na base** (decisão do operador, 09/08): entra só no
  cenário otimista do Aproveitamento; vedada/preservação obrigatória fica fora até do otimista.

### RF-APR — Aproveitamento
- **RF-APR-1** Área aproveitável = gleba − união das restrições físicas/ambientais, com memória do desconto.
- **RF-APR-2** Teto físico de lotes pelo lote mínimo aplicável (ver RF-LUOS/RNF-LEI).
- **RF-APR-3** Cenário "com diretriz" quando há perfil municipal confirmado (doação descontada).

### RF-URB — Urbanismo (estudo de massa)
- **RF-URB-1** Gerar layout completo determinístico: lotes, quadras, viário conexo, verde, institucional, sistema de lazer, pórtico — a IA propõe apenas o *programa* (alvos); **toda geometria e todo número saem do motor Python**.
- **RF-URB-2** Gerar K=5 variantes de traçado e escolher pela **função de valor por público** (INTEL-2); usuário alterna entre variantes sem perder as demais.
- **RF-URB-3** Heatmap de valor posicional por lote (multiplicador + fatores explicados).
- **RF-URB-4** Programa de lazer por cobertura de 400 m + praças; lago no ponto baixo do DEM (prioritário no alto padrão).
- **RF-URB-5** Regime **rural**: piso = FMP/INCRA, sem doação institucional/verde urbana, chácaras parcela-cheia.
- **RF-URB-6** Recuperação de sobra: componentes grandes de sobra geométrica são re-loteados na 2ª passada.
- **RF-URB-7** Conformidade legal do layout (frente mínima, institucional qualificado, normas de condomínio da LUOS) com citação por item.
- **RF-URB-8** Custo de infraestrutura paramétrico por disciplina, com BDI e padrão (econômico/médio/alto).
- **RF-URB-9** Avaliação (rating) de propostas alimenta a memória do gerador (few-shot).
- **RF-URB-10** Gleba **estreita/fragmentada** não degenera (caso Caverá, 07-08/08/2026): a
  grade adaptativa tem **freio de via** (não afina o quarteirão além de ~30% de via teórica),
  **ilha-faixa** (< ~2 fileiras de quarteirão na largura útil) fica no teto do perfil, coletora
  de 21 m só em gleba com porte (≥ 3 ha de aproveitável) e o quadro sai **rotulado** com o aviso
  `GLEBA FRAGMENTADA`. No **regime fragmentado** (muitos bolsões sub-lote de máscara raster):
  borda limpa no canvas mesmo sem `tracado` no estilo e grampo do **lote** contra a restrição
  FECHADA (closing = superset da crua, mais conservador) — lote sai com borda reta, não em
  escadinha de pixel. **Ilha estreita demais** (largura média < rua + 1 fileira de lote) não é
  urbanizável por construção: vira verde remanescente rotulado, nunca teia de via. O quadro
  separa **"Verde remanescente (não loteável — restrição/forma)"** (linha própria, sem alerta;
  protegido da 2ª passada) da **"Sobra geométrica ⚠"** (retalho operacional a minimizar).
- **RF-URB-11** **Doação mínima informada (URB-DOA, 10/08/2026):** sem LUOS carregada o motor
  NÃO inventa mínimo de doação (piso = 0; os % do quadro são mira de mercado proposta pela IA,
  capada pelo preset do público). Dois campos no card Urbanismo — **doação verde mín. (%)** e
  **institucional mín. (%)** — declaram o mínimo que o usuário conhece: entram como piso
  ROTULADO ("informação de tela, não fonte legal; verificar na prefeitura"), com LUOS
  confirmada vêm PRÉ-PREENCHIDOS com o valor da zona e a edição só pode SUBIR o piso legal;
  clamps de sanidade nos tetos do motor (verde ≤ 60%, institucional ≤ 30%) com aviso.

### RF-IMP — Importação de projeto pronto (DWG/DXF)
- **RF-IMP-1** Wizard de 3 passos: arquivo → papel das camadas (de-para) → conferência. Conversão DWG→DXF no servidor, com saneamento de arquivos corrompidos.
- **RF-IMP-2** Encaixe na gleba: reprojeção direta quando georreferenciado (UTM/SIRGAS); senão best-fit ancorado na divisa detectada, com correção de vista deslocada na prancha e escala pelos rótulos de área do próprio CAD.
- **RF-IMP-3** Ajuste manual de 2 cliques (translação; 2º par corrige rotação/escala).
- **RF-IMP-4** Auditoria medido × declarado por lote + **cobertura**: comparar a área encontrada com o TOTAL que o desenho declara e avisar quando <95% (lote faltando nunca passa em silêncio).
- **RF-IMP-5** Sugestão automática da camada que fecha as quadras (medida pela recuperação da área declarada), pré-marcada e revisável.
- **RF-IMP-6** Textos do desenho (ÁREA VERDE/INSTITUCIONAL/LAZER) classificam faces — com teto de credibilidade (face desproporcional vira pendência, não uso).
- **RF-IMP-7** Quem importa declara o público-alvo do projeto (alimenta INTEL-4); pendências viram pinos clicáveis no mapa.

### RF-LUOS — Diretriz municipal
- **RF-LUOS-1** Extração assistida da LUOS por IA a partir de PDF(s) — **múltiplos documentos** numa extração (lei + anexos); a IA lê e PROPÕE com citação (artigo/página/trecho); nada entra no cálculo sem **confirmação humana**.
- **RF-LUOS-2** Índices por zona (lote mínimo, doação e split, CA, recuos, APAC…) + normas urbanísticas de condomínio no nível do município.
- **RF-LUOS-3** Valor sem citação não é confirmável; perfil confirmado carrega quem validou e quando.
- **RF-LUOS-4** Documento de outro município é ignorado com aviso, nunca misturado.

### RF-JUR — Jurídico documental
- **RF-JUR-1** Extração assistida de matrículas e certidões (PDF/imagens), multi-matrícula, com gate humano por ficha.
- **RF-JUR-2** Síntese de risco (alto/médio/baixo) consolidando ônus (conforme/atenção/vedado), averbações, indisponibilidade, certidões e alertas geo.
- **RF-JUR-3** Cross-check área das matrículas × KMZ; checklist de diligência personalizado por proprietário (PF/PJ) e UF, com anexos.

### RF-FIN — Financeiro e econômico
- **RF-FIN-1** Fluxo de caixa do empreendimento com venda financiada (tabela Price), VGV nominal e geral, exposição máxima de caixa.
- **RF-FIN-2** VPL em moeda constante, TIR real, paybacks; leituras favorável/atenção/desfavorável **sob as premissas declaradas**.
- **RF-FIN-3** Avaliação econômica com TMA declarada; premissas sempre visíveis.
- **RF-FIN-4** *(FIN-2)* Ritmo de vendas com curva declarada (linear/rampa de lançamento/custom) e até 3 CENÁRIOS nomeados de venda — mesmo VGV, indicadores lado a lado (exposição/payback no fluxo; VPL/TIR por cenário na Econômica).
- **RF-FIN-5** *(FIN-2)* Cronograma físico-financeiro da obra por disciplina (início/duração/curva por disciplina; prevalece sobre o valor único) com pico de desembolso exposto.
- **RF-FIN-6** *(FIN-2)* Indicadores adicionais: MTIR (à TMA), ROE nominal/anualizado, exposição média + tempo no negativo, e quadro de viabilidade ESTÁTICA (custos÷VGV com composição obra/terreno/demais, custo por lote).

### RF-LOC — Localização
- **RF-LOC-1** Contexto socioeconômico IBGE (população, PIB per capita, domicílios, faixa etária) — informativo.

### RF-PORT — AI Portfolio Insights (portfólio do usuário)
- **RF-PORT-1** Painel `/app/insights` agrega POR USUÁRIO as análises salvas em KPIs comparáveis (risco, aproveitamento, retorno); TODA agregação no backend (`/api/portfolio`); percentuais normalizados para 0-100 num único lugar; dimensão não calculada = "não calculado", nunca zero.
- **RF-PORT-2** Destaques (maior VGV, VGV/ha, mais lotes, menor exposição, positivo mais cedo, menor risco ambiental, melhor TIR, maior múltiplo) e avisos de comparabilidade (TMA divergente) computados no backend, cada um com origem declarada.
- **RF-PORT-3** Radar de risco por área (ambiental/jurídico/urbanístico/financeiro, 0-100) com fórmula ABERTA no payload e na tela — régua de triagem, não veredito.
- **RF-PORT-4** Gate comercial: prévia de 30 dias para o gratuito contada do PRIMEIRO acesso (persistida por usuário em `PORTFOLIO_DIR`); contador visível; após o prazo o servidor deixa de enviar as linhas (bloqueio real); bypass para admin e liberação manual `PUT /api/portfolio/liberacao/{usuario_id}` (admin) enquanto não há billing.

### RF-LAUDO — Consolidação e exportação
- **RF-LAUDO-1** Laudo PDF e Excel compondo as dimensões executadas; dimensão ausente sai como "não analisada".
- **RF-LAUDO-2** Semáforo por dimensão DERIVADO do que cada uma reporta (nunca juízo novo); texto auditável sem "viável/aprovado".
- **RF-LAUDO-3** Trilha da análise (6 passos com estado) guiando o próximo passo.

### RF-CONTA — Contas, acesso e administração
- **RF-CONTA-1** Cadastro/login por e-mail+senha e por Google; reset de senha por e-mail; troca de senha logado.
- **RF-CONTA-2** Modal obrigatório de nome + celular no primeiro login (não sai da tela sem preencher).
- **RF-CONTA-3** Minhas análises: salvar, reabrir (reidratação sob o mesmo id), renomear.
- **RF-CONTA-4** Admin: métricas, lista de clientes com **nome e telefone**, custos de IA por cliente/análise.
- **RF-CONTA-5** Gestão de contas pelo admin: **desativar/reativar** (reversível; corte de acesso imediato — login e token recusam conta inativa) e **excluir definitivamente** (apaga conta + análises salvas + tokens + arquivos por-usuário; dupla confirmação por e-mail; atende pedido LGPD). Guardas: admin não altera a própria conta nem outra conta admin pelo painel.

### RF-PUB — Site público e exemplo
- **RF-PUB-1** Site de marketing (home, loteadores, para quem é, como funciona) na identidade voaz.app.
- **RF-PUB-2** **Laudo de exemplo público** (`/laudo-exemplo`, sem login): análise REAL publicada pelo admin com um clique; jurídico sai APENAS como contagens por severidade (críticos/moderados/sem impacto); nomes, matrículas e CPF/CNPJ nunca saem (sanitização em duas camadas). Sem exemplo publicado, a página degrada para um laudo gerado pelo motor na hora.
- **RF-PUB-3** Publicar avisa quais dimensões estão vazias na sessão antes de confirmar.
- **RF-PUB-4** SEO e descobribilidade por IA: metadados completos com domínio canônico e imagem de compartilhamento, `sitemap.xml` e `robots.txt` gerados (área logada fora do índice; crawlers de IA bem-vindos nas páginas públicas), dados estruturados JSON-LD na home (Organization, WebSite, SoftwareApplication, FAQPage) e `llms.txt` descrevendo a plataforma para assistentes de IA; `www` redireciona para o apex.

### RF-BLOG — Blog
- **RF-BLOG-1** Blog público em `/blog` e `/blog/{slug}`: artigos em JSON versionado (blocos p/h2/ul/aviso + fontes), superfície editorial da marca, JSON-LD Article, canônicas e presença no sitemap; artigo com afirmação legal SEMPRE cita lei/artigo na seção de fontes; aviso de triagem em todo artigo.
- **RF-BLOG-2** Publicação sem rebuild: páginas com ISR e webhook `POST /webhooks/revalidate` protegido por segredo (sem segredo configurado, endpoint desligado); artigo novo no diretório de conteúdo vira página após revalidação.
- **RF-BLOG-3** Gerador automático com gate humano: fila de tópicos YAML versionada → geração via API Anthropic com grounding EXCLUSIVO no acervo legal verificado → verificador determinístico (toda lei citada tem fonte oficial correspondente; estilo Light Copy; bloco de aviso obrigatório) → proposta no Telegram com botões → SÓ publica com aprovação do operador (revalida via webhook); cadência 2-3/semana via cron; sem persona fictícia nem experiência inventada; custo por artigo no medidor do admin.
- **RF-BLOG-4** *(planejado)* Minerador de pauta: transcrições de canais do setor (YouTube Data API) viram TEMAS sugeridos na fila (nunca reescrita de conteúdo alheio; artigo original cita e linka a fonte).

### RF-INTEL — Inteligência do motor
- **RF-INTEL-1** Corpus de glebas-ouro + placar de KPIs por caso×público; comparação com base fixada (regressão marcada).
- **RF-INTEL-2** Função de valor por público (pesos auditáveis, editáveis por perfil sem rebuild) escolhe entre as K variantes.
- **RF-INTEL-4** Calibração dos alvos de estilo pelos projetos DWG importados: propostas com proveniência, mínimo de 3 projetos por padrão, aceitação manual — nada muda sozinho.

---

## 3. Requisitos não-funcionais

- **RNF-DET (Determinismo):** mesma entrada → mesma saída, sempre. Nenhum número de negócio vem de LLM.
- **RNF-PROV (Proveniência):** todo número carrega fonte legal/perfil/data. Front nunca recalcula nem reformata.
- **RNF-LEI (Base legal):** restrição no produto exige lei citada. Piso de lote = 125 m² federal (Lei 6.766 art. 4º II) ou o mínimo da zona com LUOS confirmada; índice ausente no documento NÃO vira restrição; "piso de mercado" é mira, nunca trava.
- **RNF-HON (Degradação honesta):** dado indisponível → rotular (BASE_FEDERAL/PARCIAL_UF/COMPLETA; "não consultada"), nunca inventar. Erro interno → mensagem humana, nunca stacktrace.
- **RNF-IA (IA só na borda):** LLM lê documentos e propõe programa; humano confirma; motor calcula. Custo de IA medido por chamada e atribuído a cliente/análise.
- **RNF-SEG (Segurança):** JWT com refresh; TrustedHost + CORS explícitos em produção; security headers; admin por papel; multi-tenant por dono da análise.
- **RNF-PRIV (Privacidade/LGPD):** dados de contato coletados com propósito declarado; conteúdo público sanitizado (RF-PUB-2); glebas de clientes fora do repositório.
- **RNF-DESEMP:** laudo público servido de cache (memória + ISR 60 s); teto de RAM da api em produção com restart automático.
- **RNF-OPER:** portas 3700/8700; deploy Docker Compose (Lightsail); domínio `voaz.app` com redirect 301 do antigo; DOIS arquivos de ambiente (raiz=compose, backend/.env=api); fluxo Mac (podman) → AWS.
- **RNF-QUAL:** toda fase tem testes contra valores-ouro; cobertura mede "achei tudo?", não só "o que achei está certo?".
- **RNF-IDIOMA:** toda comunicação com usuário e operador em português.

---

## 4. Base legal aplicada (resumo)

| Lei | Uso na plataforma |
|---|---|
| Lei 6.766/79 (parcelamento) | Piso de lote 125 m²/frente 5 m (art. 4º II); vedação ≥30% (art. 3º); diretrizes municipais (art. 6º) |
| Lei 12.651/2012 (Código Florestal) | APP, Reserva Legal (uso restrito), APP de encosta ≥45° no rural |
| Lei 11.428/2006 (Mata Atlântica) | Alerta de supressão/compensação no domínio |
| Lei 5.868/72 + Estatuto da Terra (INCRA) | FMP como piso do lote rural |
| Lei 10.257/2001 (Estatuto da Cidade) | Instrumentos citados nos planos diretores lidos |
| LGPD | Sanitização do conteúdo público; dados de contato |
