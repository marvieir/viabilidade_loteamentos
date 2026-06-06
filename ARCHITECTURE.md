# ARCHITECTURE.md — Pré-Viabilidade de Loteamento

> Documento de decisões **transversais e estáveis**. Vale para todas as fases.
> As specs de cada fase (`docs/fase-N-*.md`) referenciam este arquivo e não o contradizem.
> Quando uma fase é concluída, atualize a seção "Histórico de decisões" ao final.

---

## 0. Ordem de execução (o número da fase é ETIQUETA de escopo, não cronologia)

Os números das fases identificam **onde a peça encaixa na arquitetura** (família 1.x =
casca/jurisdição/regime; 2.x = ambiental/geo), **não a ordem em que foram feitas**.
Fases com número quebrado (1.5, 1.7, 2.1, 2.2) foram encaixadas "no meio" sem renumerar
o resto. Por isso a ordem de execução real **não** segue a ordem numérica — consulte sempre
esta lista, não o número.

```
Concluídas (validadas):  1 → 1.5 → 1.7 → 2.1 → 2.2 → 2.3 → 1.8
Próximas (nesta ordem):  1.6* → 2.5 → 3 → 4 → 5 → 6 → 7+
```

- **1.6\*** — adaptador de topografia/CAD; segue **bloqueada** até reunir 3–5 arquivos reais.
- **2.5 (próxima)** — declividade via DEM (exige chave OpenTopography).
- **3 — Jurídica** — consome o **perfil municipal que a 1.8 cria** (lote legal/doação/usos por zona).

> A 1.8 tem número "menor" que a 2.1/2.2 mas ainda não foi feita — ficou para trás de
> propósito por ser a mais delicada. Número baixo ≠ feito primeiro.

---

## 1. O que o produto é (e o que não é)

MVP de **pré-viabilidade / triagem** de áreas de loteamento. Recebe o KMZ de uma
gleba e produz uma análise que orienta **onde gastar com due diligence** — não
decide aprovação.

**O tool NÃO decide:**
- Aprovação municipal do parcelamento (depende de protocolo na prefeitura e de campo).
- Diretrizes específicas da gleba emitidas por projeto (art. 6º da Lei 6.766/79:
  traçado viário, áreas reservadas para aquela área específica).
- Condições que exigem campo/engenheiro (solo, lençol freático, sondagem).

O tool **faz triagem** sobre regras gerais (federais/estaduais/municipais) e
geometria. Tudo que não é calculável é **declarado pelo incorporador** ou marcado
como **julgamento externo**.

---

## 2. Princípio inegociável: determinismo e proveniência

1. **Todo cálculo numérico mora no backend Python.** Nunca no frontend, nunca via LLM.
2. **A IA fica na BORDA, nunca no caminho do número.** A fronteira é entre *adquirir/ler
   dados* (onde IA/agente/geoprocessamento são bem-vindos) e *calcular o veredito de
   viabilidade* (determinístico, Python, sem LLM, jamais). Dois usos legítimos de LLM:
   (a) **ler documento não-estruturado** — ex.: extrair índices da LUOS em PDF (Fase 1.8),
   **sempre com validação humana obrigatória + proveniência por artigo**; (b) **narrar em
   prosa** números já calculados (resumo executivo), opcional e desligável. O LLM lê e
   descreve; nunca decide o número.
3. **Todo número carrega proveniência**: qual perfil de jurisdição, qual base legal,
   qual data de referência, quem validou. O relatório é auditável.
4. O frontend **apenas renderiza JSON**. Geo-matemática em JavaScript é proibida.
5. **Aquisição de dado oficial é pipeline, não agente** (endpoint/arquivo fixo →
   download+cache). Agente/busca só onde o alvo é não-estruturado e disperso (mercado).

Critério de não-regressão: a mesma entrada produz sempre a mesma saída, e cada
saída é rastreável até a fonte.

---

## 3. Stack

| Camada | Tecnologia | Papel |
|---|---|---|
| Backend | FastAPI (Python) | Parse KMZ, geometria, declividade, jurisdição, cálculo financeiro |
| Geo | shapely, pyproj, rasterio | Geometria, CRS/geodésico, DEM |
| Frontend | Next.js (React) + Tailwind + shadcn/ui | UI por cards; só renderiza JSON |
| Mapa | react-leaflet (MVP) → MapLibre GL (evolução) | Polígono + buffers + WMS oficiais |
| Deploy | Lightsail + Docker Compose (api + web) | Igual ao padrão HomeEye |

Decisão de mapa: react-leaflet no MVP porque o requisito dominante é **sobrepor
WMS dos geoserviços do governo** (INDE/ANA/ICMBio) ao polígono e aos buffers —
first-class no Leaflet (`TileLayer.WMS` + `GeoJSON`). MapLibre fica para polimento
vetorial posterior, sem mexer no backend.

**Convenção de portas (este projeto):** frontend em porta **> 3700**; backend em
porta **> 8700**.

---

## 4. Modelo de jurisdição: três camadas + degradação graciosa

Abrangência nacional é propriedade do **motor e do schema**, não de ter o Brasil
pré-carregado. Roda em qualquer KMZ desde o dia 1; o que varia é a profundidade.

| Camada | Cobertura | Esforço de popular | Quando |
|---|---|---|---|
| Federal + geoespacial nacional | Brasil inteiro | wire **uma vez** | já |
| Estadual (órgão licenciador, lote mín. estadual, APA/manancial) | 27 UFs | leve | por UF, sob demanda |
| Municipal (zoneamento/LUOS por zona) | ~5.570 | pesado — sem base nacional | por cidade, sob demanda |

**Resolvedor (duas peças desacopladas):**
- **Detectar** (precisa de geometria): centróide → point-in-polygon na **malha geométrica
  IBGE** → `cod_ibge`. Se o ponto cai num gap de generalização perto da divisa, fallback
  para o município mais próximo (nearest) marcado como "aproximado — confirmar", em vez
  de "não resolvido".
- **Corrigir** (só precisa da lista): busca/autocomplete por **nome** sobre a **lista leve
  IBGE** (`cod_ibge + nome + UF`, ~150 KB, embarcada no repo). O usuário digita "São Roque",
  nunca o código. Funciona mesmo se a malha geométrica não carregou (plano B sobrevive).

A proveniência registra `detectado` vs `informado` vs `aproximado`. **Divisa:** se o
polígono inteiro intersecta >1 município, mostra os candidatos **com % de área em cada
um** ("82% em São Roque, 18% em Mairinque"), sugere o de maior área como default e
**exige confirmação humana** — não aplica "mais restritivo" automático (a regra do mais
restritivo vale para empilhar camadas da mesma jurisdição, não para escolher entre
municípios). Centróide fora de tudo → seleção manual por nome, sem inventar.

Sem perfil municipal, **não bloqueia e não inventa** — degrada para o nível federal
e rotula a cobertura:

- `BASE_FEDERAL` — só piso nacional + geoespacial.
- `PARCIAL_UF` — federal + estadual; falta zoneamento municipal.
- `COMPLETA` — federal + estadual + zona municipal.

O relatório estampa o nível e diz explicitamente o que não foi considerado.

### Backbone de dados nacional (carrega uma vez, pipeline de download — não agente)
- **Malha geométrica IBGE** — polígonos dos ~5.570 municípios, **nível intermediário**
  (cheia é lenta no point-in-polygon; muito simplificada erra na divisa). Usada só para
  **detectar** o município. **Não vai no git**: hospedada em volume do Lightsail, baixada
  por pipeline (build/bootstrap). Fallback nearest na borda.
- **Lista leve IBGE** — `cod_ibge + nome + UF` (~150 KB), **embarcada no repo**. Usada para
  **corrigir/buscar por nome** e para rotular o resultado da detecção. Desacoplada da malha
  pesada → o override funciona mesmo sem a malha.
- **FMP — Fração Mínima de Parcelamento por município** — tabela INCRA (Instrução Especial
  nº 5/2022, Anexo IV; valor oficial também no CCIR do imóvel). É o **piso do parcelamento
  RURAL** (Lei 5.868/72 art. 8º; Estatuto da Terra art. 65) — **não confundir com módulo
  fiscal** (que serve a ITR/enquadramento, não a parcelamento). Varia por município; piso
  legal de 2 ha. Ausente na tabela → default 2 ha + aviso "confirmar no CCIR".
- Hidrografia — base ANA/IBGE (para buffers de APP). Inclui **massa d'água/represa**
  (`APP_MASSA_DAGUA`), além de cursos d'água (achado e tratado na Fase 2.1).
- Unidades de conservação — ICMBio/CNUC (federal/estadual/municipal/RPPN), WMS/WFS.
- **Linhas de transmissão — ANEEL/SIGEL** (para faixa de servidão por tensão).
- **Cobertura vegetal — ESA WorldCover 10 m (2021)**, Cloud-Optimized GeoTIFF na AWS Open
  Data, **pública e sem login**. Lida por janela da gleba via `/vsicurl/` (rasterio), sem
  baixar o tile inteiro. **MapBiomas/Google Earth Engine foi descartado** (o
  `earthengine authenticate` esbarra no bloqueio de login do Google). Usada na Fase 2.2.
- DEM — SRTM (MVP) ou Copernicus GLO-30 (evolução); fonte trocável por config.

---

## 4-A. Camada de ingestão de geometria (classificar por conteúdo)

Decisão central: ~99% dos arquivos reais chegam como export de topografia/CAD
(linhas, não polígonos). A ingestão é, portanto, **gargalo de viabilidade do produto**
e precede as dimensões de análise.

O que decide o tratamento é **o conteúdo do arquivo**, não a origem (Google Earth,
AutoCAD, software de topografia). Três rotas:

| Rota | Condição | Ação |
|---|---|---|
| `POLYGON_DIRETO` | ≥1 `<Polygon>` | usa direto (vários → maior + `aviso`) |
| `LINHA_FECHAVEL` | exatamente 1 `<LineString>` simples, fechada ou com gap ≤ tolerância | fecha e converte |
| `TOPOGRAFIA_CAD` | demais casos sem polígono (multi-linha, aberta além da tolerância, auto-intersectada) | recusa com diagnóstico → Fase 1.6 |

Regras invioláveis da ingestão: nunca fechar linha em silêncio (sempre declarar o
gap); nunca adivinhar qual linha é o perímetro quando há várias (isso exige
confirmação humana, Fase 1.6); recusa sempre diagnóstica (conta o que viu e orienta).
O motor de geometria permanece **puro** (`Polygon` entra → área sai); a ingestão é um
adaptador a montante.

---

## 5. Parâmetros legais verificados (piso nacional)

Fontes cruzadas com legislação. Valores federais são **constantes**; o resto é
**parâmetro** do perfil de jurisdição.

| Parâmetro | Valor / regra | Tipo | Fonte |
|---|---|---|---|
| Lote mínimo | 125 m² (piso); alvo configurável | constante + input | Lei 6.766 art. 4º II |
| Frente mínima | 5 m | constante | Lei 6.766 art. 4º II |
| Declividade — flag | ≥30% = vedação (salvo exigência específica) | constante (flag) | Lei 6.766 art. 3º §ún III |
| Faixa não-edificável | 15 m de cada lado (águas/rodovia/ferrovia) | buffer auto | Lei 6.766 art. 4º III |
| Doação pública | varia por município; **pode ser 0** (alguns não exigem mínimo); fora do cálculo até a 1.8 | **input municipal (Fase 1.8)** | Lei 9.785/99 + diretriz local |
| APP curso d'água | 30/50/100/200/500 m por largura | buffer (fase geo) | Lei 12.651 art. 4º I |
| APP nascente | 50 m de raio | buffer (fase geo) | Lei 12.651 art. 4º IV |
| Servidão LT | 20/40/70 m conforme 69/230/500 kV | **input por tensão** | NBR 5422 |
| ~~Aproveitamento desmembramento ~74%~~ | **OBSOLETO** — motor removido na 2.2 (ver seção 6-A) | — | — |
| ~~Aproveitamento loteamento 57–65%~~ | **OBSOLETO** — substituído pelo modelo de triagem (união de restrições) | — | — |
| **Verde / cobertura vegetal** | desconto de triagem do aproveitável (classes árvores/arbustiva/úmida/mangue; pasto NÃO conta) | buffer auto (Fase 2.2) | ESA WorldCover 10 m |
| **Regime RURAL — FMP** | piso de parcelamento = **FMP do município** (≠ módulo fiscal; ≠ 125 m²); piso legal 2 ha | **tabela INCRA por município** | Lei 5.868/72 art. 8º; Estatuto da Terra art. 65; IE INCRA 5/2022 |
| **Rural → urbano** | lote urbano só se gleba dentro do perímetro urbano (exige conversão) | flag | Lei 5.868/72; exceção FMP |

**Variação por estado é real** (competência concorrente, art. 24 CF): normas
estaduais podem ser **mais restritivas**, e o licenciamento de loteamento costuma
ser **estadual** (CETESB-SP, INEA-RJ, IAT-PR...) salvo município habilitado (LC 140/2011).
Regra do motor: aplicar o **mais restritivo aplicável** entre as camadas, **como
triagem conservadora** (não como veredito jurídico) e marcar para verificação.

### VALORES-OURO do aproveitamento (modelo de TRIAGEM — vigente)
Validado ao vivo na gleba **Terreno_Cachoeira** (São José dos Campos/SP, 24,08 ha):

| Item | Valor |
|---|---|
| Verde (WorldCover, classes de mata) | 13,77 ha (57,2%) |
| APP (curso + massa d'água) | 5,35 ha |
| Sobreposição mata∩APP (não conta 2×) | 1,94 ha |
| **União das restrições** | 17,18 ha (**71,33%** da gleba) |
| **Área aproveitável** | 6,9 ha (**28,7%** da gleba) |
| **Teto de lotes** (lote 200 m²) | **345** |

Estes são o critério de aceite do motor de aproveitamento (modelo de triagem).

### ~~Bases de doação (Aula 09) — OBSOLETO~~
Os três números da Aula 09 (57,0% / 61,6% / 65,0% → 142 / 154 / 162 lotes, assumindo
vias 11.500 m² + doação 20%) **foram aposentados** na Fase 2.2: o modelo de triagem
não calcula vias nem doação (só se sabem no projeto urbanístico / na diretriz municipal).
Mantidos aqui só por proveniência histórica — **não são mais critério de aceite**.
Doação e lote mínimo legal **voltam ao número na Fase 1.8** (perfil municipal).

---

## 6. Costura de dados entre dimensões

Confirmada pela planilha financeira do curso (12 abas). A dependência **não é arbitrária**:

```
Motor de Aproveitamento ──(aproveitamento %, total de lotes)──▶ Financeira
Financeira ──(fluxo de caixa)──▶ Econômica (VPL / TIR / TMA / Retorno de Capital)
```

A aba `Dados do Parcelamento de Solo` parte de `Aproveitamento %`, `Área Útil =
Área × Aproveitamento` e `Total de Lotes = Área Útil ÷ Metragem do Lote` — exatamente
a saída do motor. Por isso a ordem de construção respeita essa cascata.

---

## 6-A. Modelo de "Área aproveitável" (TRIAGEM) — contrato vigente da Fase 1

> Redesenhado na Fase 2.2 por decisão do operador. **Substitui** o motor antigo
> (loteamento/desmembramento + 3 bases de doação), agora removido.

**Fórmula:**
```
Área aproveitável = Área total − UNIÃO( mata ∪ APP curso d'água ∪ APP massa d'água
                                        ∪ faixa não-edificável ∪ servidão de LT )
Nº de lotes (urbano) = TETO = Área aproveitável ÷ lote mínimo
```

Decisões e porquês:
1. **Vias saem do cálculo** — o % de vias só se conhece no **projeto urbanístico**.
2. **Doação sai do cálculo** — depende da **diretriz de cada prefeitura** (pode ser 0);
   volta na Fase 1.8.
3. **APP entra junto com a mata por UNIÃO geométrica** (sem dupla contagem): mata
   ribeirinha é APP e verde ao mesmo tempo — conta uma vez só (`core/aproveitavel.consolidar`).
4. **% sempre sobre a gleba inteira** (não sobre base já reduzida — evita número inflado).
5. **Lotes = TETO** (limite superior). Reduções futuras o apertam, nesta ordem:
   ```
   Hoje (triagem):       teto = (total − união(restrições)) ÷ lote mínimo
   Fase 1.8 (diretriz):  + doação municipal (pode ser 0) + lote mínimo legal
   Fase projeto urbano:  + % vias + % lazer (informados do urbanismo)
                         = nº de lotes realista
   ```
   O "teto" é honesto **por se chamar teto**: é o piso físico-ambiental que as etapas
   seguintes só podem reduzir, nunca aumentar.

**Custo da escolha (registrado):** o número saiu de um aproveitamento *legalmente
ancorado* (bases de doação da Lei 9.785) para um *teto físico-ambiental*. É mais
defensável para "vale a pena gastar com due diligence?", porém menos comparável ao
estudo de viabilidade tradicional do curso — até a 1.8 reintroduzir doação e lote legal.

---

## 7. Dimensões de viabilidade: o que cada uma entrega e COMO

| Dimensão (aula) | Entrega | Produção | Fonte |
|---|---|---|---|
| Aproveitamento (motor) | área, perímetro, **área aproveitável = total − união(restrições)**, **teto** de lotes (urbano) / parcelas (rural) | determinístico geométrico | KMZ + camadas + regras |
| **Área verde (2.2)** | mata da gleba (desconto de triagem do aproveitável) | determinístico geoespacial | ESA WorldCover 10 m |
| Ambiental (06) | APP curso + **massa d'água**, UC, hidrografia, faixa não-edificável, **servidão LT (ANEEL)**, declividade ≥30% | determinístico geoespacial | ANA, ICMBio, **ANEEL**, SIGMINE, Cód. Florestal |
| Jurídica (09) | lote mín., doação, via, infra vs. perfil; checklist documentação | auto (perfil) + declarado | perfil municipal/estadual |
| Técnica (07) | declividade auto; solo, lençol, ETE/EEE, LT como campos guiados | misto auto + declarado | DEM + incorporador |
| Financeira (02) | preço/lote, carteira, custo, parceria, ponto de equilíbrio | determinístico de cálculo | **lotes do motor** + inputs |
| Econômica (03) | VPL, TIR, TMA, Retorno de Capital | determinístico financeiro | fluxo da financeira |
| Localização (05) | população, renda, PIB, faixa etária | auto (enriquecimento) | IBGE (nacional) |
| Mercadológica (04) | concorrentes, perfil comprador, fornecedores | declarado + IBGE parcial | incorporador + IBGE |
| Operacional (08) | mão de obra, máquinas, insumos, redes | declarado | incorporador |
| Política (01) | isenção IPTU, relação prefeitura, benefícios | externo (relacional) | fora do tool |

---

## 8. Catálogo de fases (por posição lógica — NÃO é a ordem de execução)

> Esta lista está em **ordem numérica/lógica** (família 1.x, depois 2.x). A **ordem real
> de execução** está na **seção 0** (ex.: a 2.3 vem antes da 1.8 mesmo tendo número maior).
> Status: ✅ = concluída e validada.

A casca compartilhada vem antes de qualquer dimensão. A **ingestão fura a fila** logo
após a casca, porque ~99% dos arquivos reais precisam dela e nenhuma dimensão agrega
valor sobre uma gleba que o sistema não conseguiu ler. Depois, as dimensões por valor ×
automatização, respeitando a cascata de dados.

1. **Fase 1 — Casca + Aproveitamento** ✅ (mapa, upload KMZ, resolvedor de jurisdição,
   moldura de relatório, motor de aproveitamento geométrico).
2. **Fase 1.5 — Ingestão determinística** ✅ (classificador por conteúdo; `Polygon` direto +
   1 linha simples fechável → polígono; CAD multi-linha roteado para 1.6 com diagnóstico).
   `docs/fase-1.5-ingestao.md`.
3. **Fase 1.6 — Adaptador de topografia/CAD** (isola perímetro entre várias linhas, fecha
   gaps grandes, resolve auto-interseções, com confirmação visual no mapa). **Pendente
   de 3–5 arquivos reais** antes de especificar — caso difícil, não determinístico sozinho.
4. **Fase 1.7 — Jurisdição real + Regime (urbano/rural) + Rural (FMP)** ✅ (corretiva). Promove
   o resolvedor de stub para real (malha IBGE, detecção+override por nome+divisa); pergunta de
   regime no início do aproveitamento; rural usa **FMP por município** (tabela INCRA); urbano usa
   lote mínimo **declarado** no interino. Corrigiu a premissa urbana silenciosa do aproveitamento.
   `docs/fase-1.7-jurisdicao-regime.md`.
5. **Fase 1.8 — Extração assistida da LUOS (urbano)** ✅ (LLM lê o PDF da diretriz municipal →
   propõe lote mínimo/doação por zona/modalidade → **validação humana + proveniência por artigo**
   → vira perfil confirmado). **Reintroduz doação e lote legal no número** via `cenario_diretriz`
   (aditivo ao headline físico-ambiental da 2.2/2.3). Extrator injetável (`ExtratorLUOS`); real =
   Claude API atrás da interface, gated por `ANTHROPIC_API_KEY`; testes 100% offline com stub.
   `docs/fase-1.8-luos.md`.
6. **Fase 2 — Ambiental (overlays vetoriais)** ✅ encanada (`docs/fase-2-ambiental.md`).
7. **Fase 2.1 — Ambiental com dados reais + ANEEL** ✅ (corretiva). Ligou as camadas oficiais
   reais (SIGMINE, ANA, ICMBio, **+ linhas ANEEL** p/ faixa de servidão) com smoke test ao
   vivo. Resolveu o "fonte não configurada". Achou e tratou o caso **massa d'água/represa**
   (`APP_MASSA_DAGUA`). `docs/fase-2.1-ambiental-dados-reais.md`.
8. **Fase 2.2 — Área verde (cobertura vegetal)** ✅. ESA WorldCover 10 m (`/vsicurl`, sem login);
   desconta a mata do aproveitável; **redesenhou o modelo de aproveitável** (seção 6-A: união
   de restrições, teto de lotes, vias/doação removidas). Validada ao vivo (Terreno_Cachoeira).
9. **Fase 2.3 — Severidade do verde (PRÓXIMA na execução)**. Separa **verde-em-APP/UC =
   restrição dura** (proibição legal) de **verde genérico = a verificar** (depende de laudo).
   Reusa as camadas da 2.1 (interseção geométrica a mais); não troca o WorldCover. Mantém o
   verde descontado do aproveitável (conservador), mas para de tratar uma APP de rio e um pasto
   arborizado igual. Ganchos: composição por classe (árvores vs arbustiva); série temporal (futuro).
10. Fase 2.5 — Declividade via DEM (exige chave OpenTopography).
11. Fase 3 — Jurídica (perfil municipal/estadual; consome o que a 1.8 extraiu).
12. Fase 4 — Financeira (consome lotes do motor).
13. Fase 5 — Econômica (consome fluxo da financeira).
14. Fase 6 — Localização (enriquecimento IBGE).
15. Fase 7+ — Técnica / Operacional / Mercadológica / Política (guiadas).

Cada dimensão = **um endpoint no FastAPI + um card no Next.js**. Adiciona uma sem tocar nas outras.

---

## 9. Correções registradas (não repetir os erros do material do curso)

- **RET 1% / 4% NÃO se aplica a loteamento** — é restrito a incorporação de edifícios.
  Loteamento usa Lucro Presumido ou Lucro Real. O `5,93%` que aparece na planilha é a
  faixa de **incorporação no lucro presumido** (art. 4º Lei 10.931/2004), não de loteamento.
  → Na Fase Financeira/Econômica, tributação é **parâmetro validável**, não constante.
- **Servidão de LT não é 70 m fixo** — varia por tensão (20/40/70 m para 69/230/500 kV).
- **Aproveitamento ~74% / ~60% não tem âncora legal** — é regra de mercado; default editável com aviso.
- **APP urbana**: divergência 15 m (Lei 6.766) × 30 m (Cód. Florestal), modulada pela
  Lei 14.285/2021. Aplicar o maior buffer como triagem e marcar "verificar legislação municipal".
- **Aproveitamento NÃO pode assumir regime urbano em silêncio** (falha detectada na Fase 2):
  a Lei 6.766 (lote 125 m², doação) é **urbana**; terra **rural** rege-se pelo INCRA e não
  pode ser fracionada abaixo da **FMP** do município (~2 ha), salvo se dentro do perímetro
  urbano. O motor exige `regime` explícito e declara a premissa; sem isso, número é ilustrativo.
  (Corrigido na Fase 1.7.)

---

## Histórico de decisões

| Data | Decisão | Fase |
|---|---|---|
| 2026-06-01 | **Fase 1 concluída e testada** (casca + motor de aproveitamento). Demo ponta a ponta: upload KMZ → mapa Leaflet → área/perímetro geodésicos → jurisdição → aproveitamento. 15 testes `pytest` verdes, cobrindo os 7 critérios de aceite. | 1 |
| 2026-06-01 | **Resolvedor de jurisdição = stub injetável.** O de-para centróide→município/UF/IBGE é uma interface injetável; em produção retorna "não resolvido" (`municipio=null`, `cobertura=BASE_FEDERAL`), nos testes injeta-se São Roque/SP/3550605. Resolução geográfica real (malha IBGE ou API) fica para fase futura. Mantém determinismo e testes 100% offline. | 1 |
| 2026-06-01 | **Parser de KMZ aceita apenas `<Polygon>` na Fase 1.** Múltiplos polígonos → usa o de maior área + registra em `avisos`. Geometria inválida → 422. Sem inventar contorno. (Generalizado pela camada de ingestão na Fase 1.5.) | 1 |
| 2026-06-01 | **Docker/Compose sem `apt`:** os wheels manylinux de `shapely`/`pyproj`/`lxml` já embarcam GEOS/PROJ/libxml2 — dispensa libs de sistema. Build mais magro e portátil (validado com Podman no macOS ARM). | 1 |
| 2026-06-01 | **Ingestão fura a fila (antes das dimensões).** ~99% dos arquivos reais chegam como topografia/CAD (linhas, não polígonos); sem ler a entrada nenhuma dimensão agrega valor. Camada de ingestão classifica **por conteúdo** (não por origem), em 3 rotas: `POLYGON_DIRETO`, `LINHA_FECHAVEL`, `TOPOGRAFIA_CAD`. Ver seção 4-A. | 1.5/1.6 |
| 2026-06-01 | **Ingestão quebrada em 1.5 (determinística) + 1.6 (CAD sujo).** 1.5 resolve casos sem ambiguidade (polígono direto; 1 linha simples fechável) e roteia o resto com diagnóstico — especificada (`docs/fase-1.5-ingestao.md`). 1.6 (isolar perímetro, fechar gaps grandes, auto-interseção, confirmação visual) fica **pendente de 3–5 arquivos reais** para especificação. | 1.5/1.6 |
| 2026-06-01 | **Fase 1.5 concluída e testada** — camada de ingestão substituiu o parser cru; 10 critérios de aceite verdes (26 testes no total: 15 da Fase 1 sem regressão + 11 da 1.5). **Tolerância de fechamento:** `1,0 m` (constante `TOLERANCIA_FECHAMENTO_M`), **configurável por chamada** via parâmetro `tolerancia_m` de `ingerir(...)`; gap medido geodesicamente (`pyproj.Geod`) entre 1º e último ponto. **Formato final de `origem_geometria`:** objeto `{rota, descricao}` em toda resposta de sucesso — `rota ∈ {POLYGON_DIRETO, LINHA_FECHAVEL}` (apenas rotas de sucesso entram no schema) e `descricao` em prosa auditável (`"polígono direto do arquivo"`; `"linha já fechada do arquivo (anel)"`; `"linha fechada automaticamente (gap = X,XX m ≤ 1,0 m)"`). Linha fechada nunca em silêncio: o gap fechado também vai em `avisos`. **Ajustes de contrato vs. spec:** (a) além das 3 rotas, recusa **`SEM_GEOMETRIA`** (motivo `sem_geometria`) para arquivo sem polígono e sem linha — ex.: só `<Point>`; (b) `diagnostico.n_pontos` incluído quando há pontos; (c) linha simples porém degenerada (área 0 / inválida) é recusada como `TOPOGRAFIA_CAD` motivo `auto_intersecao`. `<Polygon>` direto preserva byte-a-byte a saída da Fase 1 (não-regressão). | 1.5 |
| 2026-06-01 | **Pendência registrada (não implementada):** KMZ exportado de topografia/CAD traz só `LineString` (sem `Polygon`) — ex.: memorial descritivo/georreferenciamento. Recusado corretamente com diagnóstico na Fase 1.5; reconstrução assistida (isolar perímetro entre várias linhas) é a Fase 1.6. | 1.6 |
| 2026-06-01 | **Falha detectada em teste real (gleba rural Bocaina, 109 ha):** o aproveitamento assumia parcelamento URBANO em silêncio e a jurisdição não era resolvida (stub) — gerou "4048 lotes de 200 m²" em área rural de serra. Terra rural rege-se pela FMP do INCRA (~2 ha), não pela Lei 6.766. **Correção → Fase 1.7**: resolvedor IBGE real (detecção+override+divisa), pergunta de regime urbano/rural, FMP por município no rural, lote declarado no urbano (extração da LUOS = Fase 1.8). | 1.7 |
| 2026-06-01 | **Falha detectada em teste real (Ambiental "não configurada"):** a Fase 2 passou nos 10 critérios porque eram todos offline com stubs; a integração com dados reais ficou fora dos critérios → no app real a camada não consultava nada. **Correção → Fase 2.1**: ligar SIGMINE/ANA/ICMBio/ANEEL reais + smoke test ao vivo; adicionar linhas de transmissão (ANEEL) para faixa de servidão. | 2.1 |
| 2026-06-01 | **Decisão: detecção de município com override.** Detecta por point-in-polygon do centróide; mostra o resultado; usuário corrige por busca local (lista IBGE); alerta de divisa quando o polígono cruza >1 município; proveniência `detectado`/`informado`. Offline, sem agente. | 1.7 |
| 2026-06-01 | **Decisão: aquisição de dado oficial é pipeline, não agente.** Malha IBGE, módulo fiscal INCRA, SIGMINE, ANA, ICMBio, ANEEL têm endpoint/arquivo fixo → download+cache. Agente/LLM só onde o alvo é não-estruturado: extração da LUOS (Fase 1.8, com validação humana) e busca de mercado (Mercadológica). Descartada detecção ambiental por visão sobre satélite (sem proveniência, propensa a erro). | geral |
| 2026-06-02 | **Refino de contrato da 1.7 (dúvidas resolvidas):** (1) piso rural é a **FMP por município** (Lei 5.868/72 art. 8º), **não** o módulo fiscal — Bocaina = 54 parcelas só se a FMP dela for 2 ha; ausente → default 2 ha + aviso. (2) **Lista leve IBGE** (cod+nome+UF, ~150 KB) embarcada no repo, desacoplada da malha geométrica → busca/override por **nome** funciona sem a malha. (3) Modalidade urbana é **só rótulo** na 1.7; regra por modalidade é da 1.8 (depende da LUOS). (4) **Divisa = escolha humana** com % de área por município + default no maior; **não** "mais restritivo" automático. (5) Malha **intermediária** em volume Lightsail (pipeline), fallback nearest na borda. | 1.7 |
| 2026-06-03 | **Fase 1.7 fechada (validada no navegador):** detecção automática de município passou a funcionar com a malha real carregada (resolve "detectado", não só "informado"); busca por **nome** (não código IBGE); seletor de modalidade no urbano; rótulo de lote provisório. Foi o teste de verdade que destravou as fases seguintes. | 1.7 |
| 2026-06-03 | **Fase 2.1 fechada (validada ao vivo):** SIGMINE/ANA/ICMBio/ANEEL reais ligados com smoke test. **Achado novo:** represa/massa d'água gera APP própria → tipo `APP_MASSA_DAGUA` (além de `APP` de curso d'água). | 2.1 |
| 2026-06-03 | **Fase 2.2 concluída e validada ao vivo** (Terreno_Cachoeira, São José dos Campos/SP, 24,08 ha; branch `claude/eager-dirac-IoO3K`; 70 testes + 4 skip; `tsc` limpo). Nova dimensão **Área verde** via **ESA WorldCover 10 m** (`/vsicurl`, COG na AWS Open Data, sem login). **MapBiomas/GEE descartado** (login Google bloqueado). Classes verde = `{10 árvores, 20 arbustiva, 90 úmida, 95 mangue}`; **pasto (30) NÃO conta** (decisão do operador: pasto é aproveitável). Validação: verde 13,77 ha (57,2%). | 2.2 |
| 2026-06-03 | **Redesenho do "Aproveitável" (muda contrato da Fase 1 — ver seção 6-A):** `aproveitável = total − UNIÃO(mata ∪ APP curso ∪ APP massa d'água ∪ faixa não-edif. ∪ servidão LT)`; lotes = **TETO** ÷ lote mínimo. **Vias e doação saem do cálculo** (vias = só projeto urbanístico; doação = só diretriz municipal, pode ser 0). APP entra com a mata por **união geométrica sem dupla contagem**; % sempre sobre a gleba inteira. **Removidos:** motor loteamento/desmembramento, 3 bases de doação, campos vias/doação/fator, e os **valores-ouro da Aula 09** (obsoletos). Novos valores-ouro: união 71,33% → aproveitável 28,7% → teto 345 lotes. | 2.2/1 |
| 2026-06-03 | **Comentário do operador (doação):** doação **só volta ao número na Fase 1.8** (carga da diretriz municipal), e é parâmetro que **pode ser zero** (alguns municípios não exigem mínimo) — nunca constante no código. | 1.8 |
| 2026-06-03 | **Comentário do operador + recomendação (verde):** classificar mata nativa/Atlântica/suprimível é **laudo de engenheiro em campo, fora do escopo** — nenhum dado de satélite faz isso com segurança jurídica. O verde segue **desconto conservador de triagem**, não veredito de supressão. Melhoria aceita → **Fase 2.3**: cruzar o verde com APP/UC (que a 2.1 já traz) para separar **restrição dura** (verde em APP/UC) de **a verificar** (verde genérico), em vez de descontar tudo igual. Ganchos: composição por classe; persistência temporal (Aula 06). | 2.3 |
| 2026-06-03 | **Número de lotes — encadeamento (decisão de produto):** `teto (hoje) → + diretriz 1.8 (doação+lote legal) → + projeto urbanístico (% vias+lazer) = nº realista`. O teto de hoje é o piso físico-ambiental; as etapas seguintes só o reduzem. | geral |
| 2026-06-03 | **Numeração = etiqueta de escopo, não cronologia.** Adicionada a **seção 0 (ordem de execução)**: feito 1→1.5→1.7→2.1→2.2; próximas **2.3 → 1.8**. A seção 8 passou a ser catálogo por posição lógica, apontando para a seção 0. | geral |
| 2026-06-03 | **Infra (Fase 2.2):** `rasterio==1.4.3`; **Dockerfile do backend compila GDAL** (`gdal-bin libgdal-dev build-essential`) — rasterio sem wheel linux-arm64. `python-dotenv` + `--env-file .env` (fim dos `export`). `VEGETACAO_RASTER_PATH` + volume do `verde.tif`; `AMBIENTAL_FONTE_REAL=1` liga as 4 fontes. Rasters/`.env` no `.gitignore` (volume, não git). **Gancho:** hoje o `verde.tif` é pré-baixado por região; produção deve baixar o recorte WorldCover por gleba sob demanda. | 2.2 |
| 2026-06-06 | **Ingestão passa a auto-reparar `<Polygon>` auto-interseccionado (decisão do operador, achado em teste real — gleba Sao_Roque_area_mina_de_agua).** Antes: self-intersection → 422. Agora: `core.ingestao` aplica `buffer(0)` (determinístico; preservou os 7,811 ha no arquivo real), segue o cálculo e **rotula** `origem_geometria.rota='POLYGON_REPARADO'` + **aviso** ("confira o traçado no mapa"). Multipolígono resultante (auto-interseção ambígua) → maior parte, com aviso. Reparo que não vira polígono de área (agulha/colinear) **continua recusado** (422 honesto). O motor `geometria.medir` permanece **estrito** (reparo é no adaptador de ingestão, não no núcleo — §4-A). Adiantamento mínimo da Fase 1.6. **97 testes + 4 skip.** | 1.5/1.8 |
| 2026-06-06 | **Operação da 1.8 sob inspeção TLS corporativa (Cisco Secure Access) — achados de campo.** (1) `docker-compose` ganhou `env_file: ./backend/.env` (sem isso a `ANTHROPIC_API_KEY` não entrava no container → 503). (2) `main.py` faz `load_dotenv` (cobre uvicorn sem `--env-file`). (3) Extração via **tool use forçado** (não parsear prosa do Opus). (4) **TLS:** `_opcoes_tls` monta SSLContext = certifi + CA corporativa via `LUOS_CA_BUNDLE` (verificação ligada, caminho seguro) ou `LUOS_TLS_INSECURE=1` (escape explícito). Imagem ganhou `ca-certificates`; compose monta `./backend/certs:/certs:ro`. Validado ao vivo: extração da **LC 623/2019 (São José dos Campos)** com proveniência por artigo e anti-alucinação (índices ausentes → null + avisos). | 1.8 |
| 2026-06-06 | **Fase 1.8 CONCLUÍDA (extração assistida da LUOS).** Reintroduz **doação + lote mínimo legal** no número via `cenario_diretriz` — ADITIVO ao headline físico-ambiental (decisão A: não troca o headline, mesmo padrão do otimista da 2.3). **Eixo extração×cálculo:** o LLM lê o PDF e **propõe** índices por zona/modalidade com citação por artigo (`core/extrator_luos.py`, `ExtratorLUOS` injetável; real = Claude API `claude-opus-4-8`, PDF nativo + structured outputs, **gated por `ANTHROPIC_API_KEY`** e desligável; stub offline nos testes). **Gate humano (`PUT /municipios/{ibge}/perfil`):** perfil nasce `proposto` (não calcula); só `confirmado` (com `validado_por` + `data_referencia`) alimenta o cálculo; **valor sem citação não é confirmável** (422). Perfil persistido por `cod_ibge` em volume (`FontePerfilMunicipal`, `perfis/municipais/`, gitignored). **Cálculo determinístico** (`core.aproveitamento.cenario_diretriz`): `aprov_diretriz = físico − doação(base total/líquida)`, lote = **legal da zona**, `n_lotes = floor(...)`; modalidade volta a ter regra (override por modalidade; **doação 0 é válida**, distinta de "não considerado"). `POST /aproveitamento` aceita `zona` e devolve `cenario_diretriz` (null + `aviso_diretriz` se sem perfil/zona). Headline da 2.2/2.3 **inalterado**. Endpoints: extrair (503 sem credencial / 422 PDF ilegível) · PUT confirmar · GET (404 sem perfil). Frontend: card de revisão (propor→editar→confirmar, citação ao lado) + seletor de zona + card do cenário diretriz. **96 testes + 4 skip; `tsc` limpo.** Primeira credencial de LLM do projeto — IA na borda (leitura), nunca no número (§2). | 1.8 |
| 2026-06-06 | **Fase 2.3 CONCLUÍDA e validada ao vivo (Terreno_Cachoeira).** Severidade do verde: `core/severidade_verde.py` separa **restrição dura** (verde ∩ APP/UC) de **a verificar** (verde fora dessas zonas); `potencial_desbloqueavel = a_verificar − (faixa ∪ servidão)`. Headline da 2.2 **inalterado**. `GET /vegetacao` estende `severidade` (null se vegetação OU camadas não consultadas + aviso). `POST /aproveitamento` ganha `cenario_otimista` (hipotético, **incluído** por decisão do operador). Mapa: overlays `verde_dura` (vermelho) / `verde_verificar` (amarelo). Reusa `get_fonte_vegetacao` + `get_fonte_camadas`; 100% geometria, offline. **79 testes + 4 skip; `tsc` limpo.** **Valor-ouro batido na tela:** dura **1,94 ha (14,1%)** (= sobreposição mata∩APP), a verificar **11,83 ha (85,9%)**; cenário otimista **18,74 ha (77,8%) → 936 lotes** (= 6,9 + 11,83). Sem UC/faixa incidente. | 2.3 |
