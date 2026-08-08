# Detalhamento de Requisitos — voaz.app

> Par do `docs/requisitos.md`: para cada requisito, **como funciona por dentro**, as decisões
> que o moldaram, **onde mora no código** e como é testado — em linguagem para o operador,
> não para a máquina. Mesmos IDs. Atualizado em 30/07/2026.
>
> Arquitetura em uma frase: o **frontend** (Next.js, `frontend/`) só mostra JSON; toda conta
> vive no **backend** (FastAPI, `backend/app/`), onde cada dimensão é um *router* (a porta de
> entrada HTTP, `routers/`) que chama o *core* (o motor de verdade, `core/`); os contratos de
> dados são os *schemas* Pydantic (`models/schemas.py`); e os testes-ouro (`tests/`) congelam
> o comportamento certo para ninguém quebrar sem perceber.

---

## RF-ENT — Entrada e identificação

**Como funciona.** O KMZ é descompactado e o KML lido; a plataforma classifica o conteúdo por
forma (polígono grande = gleba; linhas/pontos = contexto). Área e perímetro saem do
`pyproj.Geod` — cálculo sobre o elipsoide, o mesmo princípio do agrimensor, nunca "área em
graus". O município vem de apontar o centróide na malha do IBGE. Vários KMZ vizinhos são
unidos numa geometria só antes de tudo. No upload, a análise já nasce salva (auto-save) e o
salvar manual só atualiza a mesma linha (upsert pelo id de trabalho `_analise_id`).

- Código: `core/ingestao.py`, `core/geometria.py`, `core/jurisdicao.py`, `routers/analises.py`, `routers/salvas.py`, `core/levantamento.py` (DWG do levantamento).
- Testes: `test_ingestao.py`, `test_geometria.py`, `test_auto_salvar.py`, `test_agrupamento.py`.

## RF-AMB — Ambiental

**Como funciona.** A gleba é cruzada por **interseção espacial** com cada camada oficial
(baixadas por provedores injetáveis — em teste entram stubs, em produção as fontes reais).
Cada interseção vira um alerta com tipo, área, severidade (ALERTA/INFORMATIVO), fonte e data.
A vegetação (raster WorldCover) é recortada e classificada em **dura** (cruza APP/UC — não
loteável) × **a verificar**. A declividade sai do DEM Copernicus reamostrado: faixas
informativas + máscara ≥30% (vedação urbana). Desde 30/07, rodar a análise grava um
**marcador no servidor** (`ambiental_store`) — é ele que faz a trilha reconhecer a execução
na hora; o resultado completo continua indo no snapshot da salva.

- Decisões: triagem conservadora, nunca veredito; camada indisponível é DECLARADA (ex.: "Indisponíveis: ANEEL"); no rural a vedação de 30% vira atenção (a régua rural é APP ≥45°).
- Código: `routers/ambiental.py`, `routers/vegetacao.py`, `routers/declividade.py`, `core/alertas_geo.py`, `core/camadas*.py`, `core/ambiental_store.py`, `core/bacia.py`, `core/bioma.py`.
- Testes: `test_ambiental.py`, `test_camadas_crs.py`, `test_declividade.py`, `test_alertas_geo_rural.py`.

## RF-APR — Aproveitamento

**Como funciona.** Aproveitável = gleba − união(restrições). A união evita contar duas vezes
onde mata e encosta se sobrepõem. O teto físico de lotes divide o aproveitável pelo lote
mínimo **legal** aplicável; com perfil municipal confirmado nasce o cenário "com diretriz"
(desconta a doação e usa o lote da zona).

- Código: `routers/aproveitamento.py`, `core/aproveitamento.py`, `core/regime.py` (urbano×rural).
- Testes: `test_aproveitamento.py`, `test_areas_canonicas.py`, `test_cenario_diretriz.py`.

## RF-URB — Urbanismo

**Como funciona.** É o coração da plataforma, em duas metades bem separadas. A **IA propõe o
programa** (lote-alvo, % lazer, caráter — texto, nunca número final); o **motor determinístico**
(`urbanismo_geom.py`, ~milhares de linhas de geometria pura) desenha tudo: orienta a malha,
traça o viário conexo (gramática "faixas fluidas" no alto padrão, grelha eficiente no
econômico), corta quadras, subdivide lotes respeitando a janela legal [piso, teto], reserva
verde/institucional/lazer, posiciona lago no ponto baixo do DEM e o pórtico na entrada. São
geradas **5 variantes** e a **função de valor** (INTEL-2: valor posicional − penalidades de
sobra/viário + aderência à faixa + bônus de amenidade, pesos por público editáveis em
`{perfil}.json`) escolhe a vencedora — as 5 ficam disponíveis na tela. Uma **2ª passada**
re-lota sobras grandes (MOTOR-SOBRA: sobra caiu de 31,8% para ~2%). A **medição**
(`urbanismo_medida.py`) produz o quadro de áreas que fecha em 100% e o GeoJSON do mapa.

**Gleba estreita/fragmentada (RF-URB-10, caso Caverá).** Quando a mata rasterizada pica uma
faixa estreita em dezenas de bolsões, o motor antigo afinava o quarteirão ao mínimo e desenhava
labirinto: viário 50%, vendável 21%. Hoje valem cinco réguas determinísticas: o quarteirão nunca
afina além do ponto em que a grade teórica passa de ~30% de via (freio de via); ilha-FAIXA
(menos de ~2 fileiras de quarteirão na largura útil) fica no teto do perfil — afinar ali só
multiplica travessas; a coletora de 21 m só entra em gleba com porte (≥ 3 ha úteis); no regime
FRAGMENTADO (muitos bolsões sub-lote) o canvas ganha borda limpa e o lote é recortado contra a
mata FECHADA (superset da crua — mais conservador que a lei exige), saindo com borda reta em vez
de escadinha de pixel; e porção com largura média menor que rua + 1 fileira de lote NÃO é
urbanizável por construção — vira verde remanescente rotulado, nunca teia de via. Bolsão menor
que 1 lote legal vira verde/remanescente e o quadro sai com os avisos **GLEBA FRAGMENTADA** e de
porção estreita descartada — o rendimento baixo aparece ROTULADO, não disfarçado em traçado
denso. No quadro de áreas, esse não-loteável declarado tem linha própria — **"Verde remanescente
(não loteável — restrição/forma)"**, sem o alerta de "meta: reduzir" — separado da sobra
geométrica operacional (que volta a ser pequena, só retalho de subdivisão); a 2ª passada de
recuperação não re-loteia o remanescente. No caso real: 18 lotes-teia/viário 51%/"sobra" 36% →
~21-26 lotes de verdade/viário 24-27%/sobra ⚠ 8-10% + remanescente 27-28% rotulado.

- Decisões-chave: PISO É LEI (125 m² federal ou zona confirmada; mercado é só mira); regime rural com FMP; estilo por público versionado em arquivo (muda sem rebuild); memória de avaliações vira few-shot do programa.
- Código: `routers/urbanismo.py` (orquestra), `core/urbanismo_geom.py` (gera), `core/urbanismo_medida.py` (mede), `core/urbanismo_diretrizes.py` (régua legal), `core/urbanismo_programa.py`, `core/urbanismo_valor.py`, `core/urbanismo_estilo.py`, `core/urbanismo_tracado.py`/`_loops.py`, `core/custo_infra*`.
- Testes: ~20 arquivos `test_urbanismo_*.py` + `test_alto_padrao.py` + `test_custo_infra.py` (valores-ouro sobre a gleba real de São Roque).

## RF-IMP — Importação DWG

**Como funciona.** O DWG vira DXF no servidor (dwg2dxf compilado na imagem; conversões com
lixo pontual passam por um saneador). O inventário conta entidades por camada e sugere papéis;
a sugestão testa as camadas em "Ignorar" **medindo quanto da área declarada nos rótulos cada
uma recupera** — foi assim que a camada "P2" de Porto Real (10 linhas, nome mudo) foi achada.
O fechamento une segmentos, costura pontas com overshoot e poligoniza; os rótulos "A.: 429,94m²"
casam faces a áreas declaradas (auditoria) e os textos de uso classificam faces — com teto de
credibilidade (uma face 46× maior que o maior rótulo não vira "institucional" por causa de um
texto; vira pendência). O encaixe ancora na divisa detectada (IoU dos cascos), corrige vista
deslocada na prancha e tira a escala dos rótulos do próprio CAD.

- Lições que viraram regra: medir COBERTURA além de precisão (115→127 lotes achados de 129 declarados); relato de memória não vence medição do arquivo.
- Código: `core/importacao_dwg.py` (tudo), `routers/urbanismo.py` (endpoints importar/confirmar), front `components/cards/ImportarProjetoDwg.tsx`.
- Testes: `test_importacao_dwg.py` (23 casos, incluindo os golden do caso real).

## RF-LUOS — Diretriz municipal

**Como funciona.** O(s) PDF(s) vão numa única chamada à API da Anthropic (documentos nativos +
saída estruturada forçada por tool_choice). O prompt proíbe inventar: valor sem
artigo/página/trecho não é proposto; documento de outro município é ignorado com aviso. A
resposta passa por validação **tolerante** (Pydantic com coerção: "1,5"→1,5, "250 m²"→250,
página "8-9"→8) — falha de formato gera dump de diagnóstico, nunca perde a extração inteira.
O perfil nasce `proposto` e só entra no cálculo após o PUT de confirmação humana.

- Código: `core/extrator_luos.py`, `routers/perfil.py`, `core/perfil_municipal.py`, schemas `ParamProv/ZonaPerfil/NormasUrbanisticas` (validação tolerante em `models/schemas.py`).
- Testes: `test_perfil_luos.py` (stub offline — sem rede nem chave).

## RF-JUR — Jurídico

**Como funciona.** Mesmo padrão da LUOS: IA lê matrícula/certidão e propõe a ficha (ônus com
ato "R-5", averbações, indisponibilidade, débitos), humano confirma cada ficha, e o **núcleo
determinístico** consolida: rola o risco (alto/médio/baixo) a partir das classes dos achados +
alertas geo, cruza a soma das áreas das matrículas com o KMZ, e gera o checklist de diligência
por proprietário (PF/PJ) e UF, com anexos por item.

- Código: `routers/juridico.py`, `core/extrator_documento.py`, `core/juridico_nucleo.py`, `core/juridico_checklist.py`, `core/juridico_store.py`.
- Testes: `test_juridico*.py`.

## RF-FIN / RF-LOC — Financeiro, econômico, localização

**Como funciona.** O financeiro monta o fluxo mês a mês: receitas da venda financiada (Price),
custos de infra (do RF-URB-8) e despesas; sai VGV, exposição máxima, resultado. O econômico
desconta a TMA declarada → VPL em moeda constante, TIR real, paybacks. Nenhum número é
"recomendação": as leituras são rotuladas *sob as premissas declaradas*. Localização é
contexto IBGE puro.

**FIN-2 Onda A (07/08).** O ritmo de venda ganhou curva declarada — "rampa de lançamento"
usa pesos linearmente decrescentes (1º mês pesa N, o último pesa 1; fórmula na
proveniência) — e cenários nomeados (Conservador/Base/Otimista): o motor roda o fluxo
inteiro para CADA cenário, o ativo vira o resultado principal e os demais aparecem lado a
lado; a Econômica avalia VPL/TIR/paybacks de todos (fluxos persistidos no store). A obra
ganhou cronograma por disciplina (cada uma com início/duração/curva; a soma prevalece
sobre o R$/lote único) e o PICO de desembolso sai declarado. Novos indicadores na
Econômica: MTIR (captação e reinvestimento à TMA), ROE nominal e anualizado, exposição
média e tempo no vermelho; e a Financeira entrega o quadro ESTÁTICO (a conta de guardanapo
estruturada). Tudo aditivo — sem cenários/disciplinas o comportamento é idêntico ao
anterior (ouros preservados).

- Código: `routers/financeira.py`, `routers/economica.py`, `core/financeira*.py`, `core/economica*.py`, `routers/localizacao.py`.
- Testes: `test_financeira*.py`, `test_economica.py`, `test_fin2_onda_a.py`.

## RF-PORT — AI Portfolio Insights

**Como funciona.** O cliente que analisou várias glebas compara todas numa tela só
(`/app/insights`): o backend varre as análises SALVAS do usuário (tabela `analises`),
extrai KPIs de cada dimensão presente no snapshot (financeira, econômica, jurídico,
ambiental, aproveitamento) e busca o urbanismo no store de propostas via `_analise_id`
(último snapshot). Tudo que é conta — normalizar percentuais (as fontes misturam fração
0-1 e escala 0-100), derivar VGV/ha, lotes/ha, múltiplo de capital, eleger destaques,
montar o radar — acontece no router `portfolio.py`; o front só ordena colunas e desenha.
Dimensão que o usuário não rodou aparece como "não calculado" (nunca zero), e premissas
divergentes (TMA) viram aviso de comparabilidade em vez de comparação silenciosa. O radar
publica a própria fórmula na tela ("como calculamos").

**Gate.** Gratuito tem prévia de 30 dias contada do primeiro ACESSO ao painel (gravada
por usuário em `PORTFOLIO_DIR`); a tela mostra o contador. No dia 31 o servidor para de
enviar as linhas (o bloqueio não é cosmético) e a tela oferece os planos, deixando claro
que as análises continuam guardadas. Admin não tem gate e pode liberar um cliente pago
manualmente (`PUT /api/portfolio/liberacao/{usuario_id}`) enquanto não existe billing.

- Código: `routers/portfolio.py`, `core/portfolio_store.py`; front `app/app/insights/`, `lib/portfolio.ts`.
- Testes: `test_portfolio.py` (agregação/escalas, gate 30 dias, liberação, multi-tenant).
- Spec e mockups aprovados: `docs/fase-dashboard-portfolio.md`, `docs/mockups/`.

## RF-LAUDO — Consolidação

**Como funciona.** O front repassa os JSONs das dimensões executadas (nada recalculado);
`core/laudo.py` deriva o semáforo (favorável/atenção/restrição/informativa/não analisada) das
classes que cada dimensão JÁ reporta e monta as seções; `laudo_pdf.py`/`laudo_excel.py`
renderizam. Um teste varre o texto inteiro proibindo "viável/aprovado" (§1-A). A trilha
(`routers/trilha.py`) computa os 6 passos do servidor: stores por dimensão + snapshot da salva
+ marcador ambiental.

- Testes: `test_laudo*.py` (inclui a regex anti-veredito), `test_trilha.py`.

## RF-CONTA — Contas e admin

**Como funciona.** JWT com refresh automático no front (sessão não cai no meio da análise);
Google Identity Services opcional; reset por e-mail (SMTP Gmail). O modal de contato bloqueia
o app até nome+celular existirem (coluna `celular` com migração automática idempotente no
start). Admin lista clientes (com nome/telefone), métricas e o custo real de IA por
cliente/análise (`core/uso_llm.py` registra tokens de cada chamada). Gestão de contas
(ADMIN-1, 06/08): na lista de clientes o admin DESATIVA/reativa (a conta perde o acesso
na hora — `usuario_atual` e o login já recusavam `ativo=False`; as análises ficam
guardadas) e EXCLUI definitivamente (digitar o e-mail confirma; o backend exige o mesmo
e-mail de novo, apaga análises em cascata, tokens de reset e os arquivos por-usuário dos
stores — é o mecanismo do pedido LGPD de remoção). Conta admin não é gerenciável pelo
painel: nasce e morre só pelo seed `criar_admin`.

- Código: `core/auth.py`, `routers/auth.py`, `routers/admin.py`, `core/db.py` (migração leve), front `components/auth/*`.
- Testes: `test_auth*.py`, `test_admin.py`, `test_admin_gestao.py`, `test_google_login.py`.

## RF-PUB — Site e laudo de exemplo

**Como funciona.** O site público usa a identidade voaz.app (tokens no Tailwind: marinho
estrutura, laranja é o único acento, verde SÓ significa estado). O laudo de exemplo tem dois
modos: **retrato publicado** (admin clica "Publicar como exemplo público" → o corpo do laudo
PDF vai ao servidor, que remove a seção jurídica inteira, injeta as contagens por severidade
derivadas das classes dos ônus, roda um removedor recursivo de chaves sensíveis e grava em
volume) e **fallback vivo** (o motor gera na hora um laudo da gleba-ouro de São Roque embarcada
na imagem). Performance: cache em memória na api (invalidado por mtime) + ISR de 60 s na página.

- Código: `routers/exemplo.py`, `frontend/app/laudo-exemplo/page.tsx`, `components/marketing/*`, `components/marca/Logo.tsx`, `tailwind.config.ts`.
- Testes: verificação de 200 sem auth + 401 no publicar sem admin.

**SEO e descobribilidade por IA (RF-PUB-4, 31/07).** O Next gera `robots.txt` e `sitemap.xml`
(`app/robots.ts` e `app/sitemap.ts`): páginas públicas liberadas para todos os robôs, inclusive
os de IA (GPTBot, ClaudeBot etc., que herdam a regra `*`); `/app`, `/admin` e os fluxos de senha
ficam fora do índice. O `layout.tsx` define o domínio canônico (`metadataBase`) e a imagem de
compartilhamento `/og.jpg` (1200×630: print real da plataforma + faixa da marca, JPEG leve para
o WhatsApp mostrar o preview). Cada página pública declara sua URL canônica. A home injeta
JSON-LD (Organization, WebSite, SoftwareApplication com plano grátis, e FAQPage gerado do MESMO
array do FAQ da página — uma fonte só). `public/llms.txt` resume a plataforma na convenção que
os assistentes de IA leem. No Caddy, `www.voaz.app` redireciona 301 para o apex.

## RF-BLOG — Blog

**Como funciona (BLOG-1, 31/07).** Cada artigo é um JSON em `frontend/content/blog/` (blocos
tipados p/h2/ul/aviso + seção de fontes com lei/artigo e link do Planalto). As páginas `/blog`
e `/blog/[slug]` LEEM o diretório em tempo de execução (não importam no build) e rodam com ISR:
é o desenho do sistema MMA do projeto voya, portado — no BLOG-2, o gerador grava o arquivo num
volume e chama `POST /webhooks/revalidate?path=...&secret=...` para publicar sem rebuild (o
Dockerfile copia `content/` explicitamente porque o tracer do standalone não segue leitura por
fs). Sem `REVALIDATE_SECRET` no ambiente, o webhook responde 401 sempre. Artigos de estreia
escritos das lições legais já verificadas do projeto. Decisões de marca: sem persona fictícia
(a voz é "Equipe voaz.app"), afirmação legal sempre com fonte, aviso de triagem em todo artigo,
cadência futura 2-3/semana com aprovação do operador via Telegram (decisão de 31/07).

- Código: `frontend/lib/blog.ts`, `frontend/app/blog/`, `frontend/app/webhooks/revalidate/route.ts`, `frontend/content/blog/*.json`.
- Referência do sistema original: `docs/marketing/blog-inventario-mma.md`.

**Gerador com gate (RF-BLOG-3, 31/07).** Roda DENTRO do container da api (que já tem a chave
Anthropic e o medidor de custo): `scripts/blog/gerar.py` pega o próximo tópico da fila
versionada (`fila_topicos.yaml`), escreve via API usando como única base legal permitida o
`acervo_legal.md` (item novo no acervo exige verificação na fonte + commit), passa no
verificador determinístico (`nucleo.verificar`: toda lei citada no texto precisa de fonte com
domínio oficial; Light Copy; aviso de triagem obrigatório; 1 retry com os erros no prompt) e
manda a proposta ao Telegram com botões. `scripts/blog/aprovacoes.py` (cron a cada 10 min,
polling getUpdates com offset persistido — sem daemon) processa a resposta: aprovar publica o
JSON no volume compartilhado com o web e revalida; rejeitar arquiva. Estado e artigos no
volume `blog_conteudo` (dev: bind em `frontend/content/blog`, o aprovado vira arquivo
commitável). Ativação e cron: `docs/blog-operacao.md`. Testes: `test_blog_gerador.py`
(verificador, fila, publicação — tudo offline).

## RF-INTEL — Inteligência do motor

**Como funciona.** O placar (`scripts/placar_motor.py`) roda o motor sem IA sobre o corpus e
compara KPIs com a base fixada — é o juiz de qualquer mudança no gerador. A função de valor
(INTEL-2) está descrita no RF-URB. A calibração (INTEL-4, `core/urbanismo_calibracao.py` +
`scripts/calibrar_estilo.py`) extrai métricas dos projetos importados (lote/quadra/frações de
uso), agrega por padrão declarado (mínimo 3 projetos, mediana, dispersão) e PROPÕE ajustes de
estilo com proveniência — aplicar é um comando explícito do operador.

- Testes: `test_placar_motor.py`, `test_intel2_valor.py`, `test_intel4_calibracao.py`.

---

## Mapa do repositório (para se localizar)

```
backend/app/routers/   ← portas HTTP: um arquivo por dimensão (o "índice" do que existe)
backend/app/core/      ← motores: geometria, urbanismo, jurídico, laudo, stores
backend/app/models/    ← schemas.py = todos os contratos de dados (o "dicionário")
backend/tests/         ← valores-ouro por fase (quebrou = regressão)
frontend/app/          ← páginas (App Router): (site), app, admin, login, laudo-exemplo
frontend/components/   ← cards por dimensão, mapa Leaflet, marca, marketing
docs/                  ← este documento, requisitos.md, mapa-mental, specs fase-*.md
ARCHITECTURE.md        ← decisões transversais profundas · CLAUDE.md ← convenções e lições
```
