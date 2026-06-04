# ARCHITECTURE.md — Pré-Viabilidade de Loteamento

> Documento de decisões **transversais e estáveis**. Vale para todas as fases.
> As specs de cada fase (`docs/fase-N-*.md`) referenciam este arquivo e não o contradizem.
> Quando uma fase é concluída, atualize a seção "Histórico de decisões" ao final.

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
2. **LLM é opcional e desligável**, e só para *narrar em prosa* números já calculados
   (resumo executivo). Jamais no caminho do número.
3. **Todo número carrega proveniência**: qual perfil de jurisdição, qual base legal,
   qual data de referência, quem validou. O relatório é auditável.
4. O frontend **apenas renderiza JSON**. Geo-matemática em JavaScript é proibida.

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
- Hidrografia — base ANA/IBGE (para buffers de APP).
- Unidades de conservação — ICMBio/CNUC (federal/estadual/municipal/RPPN), WMS/WFS.
- **Linhas de transmissão — ANEEL/SIGEL** (para faixa de servidão por tensão).
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
| Doação pública | piso de fato ~35%; bases A/B/C | **input municipal** | Lei 9.785/99 + prática |
| APP curso d'água | 30/50/100/200/500 m por largura | buffer (fase geo) | Lei 12.651 art. 4º I |
| APP nascente | 50 m de raio | buffer (fase geo) | Lei 12.651 art. 4º IV |
| Servidão LT | 20/40/70 m conforme 69/230/500 kV | **input por tensão** | NBR 5422 |
| Aproveitamento desmembramento | ~74% (regra de mercado, NÃO lei) | **default editável** | aulas de modalidade |
| Aproveitamento loteamento | 57–65% conforme base de doação | derivado | Aula 09 + Lei 9.785 |
| **Regime RURAL — FMP** | piso de parcelamento = **FMP do município** (≠ módulo fiscal; ≠ 125 m²); piso legal 2 ha | **tabela INCRA por município** | Lei 5.868/72 art. 8º; Estatuto da Terra art. 65; IE INCRA 5/2022 |
| **Rural → urbano** | lote urbano só se gleba dentro do perímetro urbano (exige conversão) | flag | Lei 5.868/72; exceção FMP |

**Variação por estado é real** (competência concorrente, art. 24 CF): normas
estaduais podem ser **mais restritivas**, e o licenciamento de loteamento costuma
ser **estadual** (CETESB-SP, INEA-RJ, IAT-PR...) salvo município habilitado (LC 140/2011).
Regra do motor: aplicar o **mais restritivo aplicável** entre as camadas, **como
triagem conservadora** (não como veredito jurídico) e marcar para verificação.

### Bases de doação (aproveitamento de loteamento) — VALORES-OURO
Exemplo da Aula 09: área 50.000 m², vias 11.500 m², doação 20%, lote 200 m².

| Base | Fórmula | Resultado | % | Lotes |
|---|---|---|---|---|
| A — sobre área total | área − vias − (doação% × área) | 28.500 m² | 57,0% | 142 |
| B — sobre área líquida | bruto=área−vias; bruto − (doação% × bruto) | 30.800 m² | 61,6% | 154 |
| C — vias+doação combinados | área × (1 − combinado% 35%) | 32.500 m² | 65,0% | 162 |

Estes três números são critério de aceite do motor de aproveitamento.

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

## 7. Dimensões de viabilidade: o que cada uma entrega e COMO

| Dimensão (aula) | Entrega | Produção | Fonte |
|---|---|---|---|
| Aproveitamento (motor) | área, perímetro, declividade, lotes por modalidade | determinístico geométrico | KMZ + DEM + regras |
| Ambiental (06) | APP, UC, hidrografia, declividade ≥30%, faixa não-edificável | determinístico geoespacial | ANA, ICMBio, Cód. Florestal |
| Jurídica (09) | lote mín., doação, via, infra vs. perfil; checklist documentação | auto (perfil) + declarado | perfil municipal/estadual |
| Técnica (07) | declividade auto; solo, lençol, ETE/EEE, LT como campos guiados | misto auto + declarado | DEM + incorporador |
| Financeira (02) | preço/lote, carteira, custo, parceria, ponto de equilíbrio | determinístico de cálculo | **lotes do motor** + inputs |
| Econômica (03) | VPL, TIR, TMA, Retorno de Capital | determinístico financeiro | fluxo da financeira |
| Localização (05) | população, renda, PIB, faixa etária | auto (enriquecimento) | IBGE (nacional) |
| Mercadológica (04) | concorrentes, perfil comprador, fornecedores | declarado + IBGE parcial | incorporador + IBGE |
| Operacional (08) | mão de obra, máquinas, insumos, redes | declarado | incorporador |
| Política (01) | isenção IPTU, relação prefeitura, benefícios | externo (relacional) | fora do tool |

---

## 8. Ordem de construção (fases)

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
4. **Fase 1.7 — Jurisdição real + Regime (urbano/rural) + Rural (FMP)** (corretiva). Promove
   o resolvedor de stub para real (malha IBGE, detecção+override+divisa); pergunta de regime
   no início do aproveitamento; rural usa **FMP por município** (tabela INCRA); urbano usa lote
   mínimo **declarado** no interino. Corrige a premissa urbana silenciosa do aproveitamento.
   `docs/fase-1.7-jurisdicao-regime.md`.
5. **Fase 1.8 — Extração assistida da LUOS (urbano)** (LLM lê o PDF da diretriz municipal →
   propõe lote mínimo por modalidade → **validação humana** → vira perfil). Substitui o lote
   declarado da 1.7. **A especificar após a 1.7** (contrato depende dela).
6. **Fase 2 — Ambiental (overlays vetoriais)** ✅ encanada (`docs/fase-2-ambiental.md`).
7. **Fase 2.1 — Ambiental com dados reais + ANEEL** (corretiva). Liga as camadas oficiais
   reais (SIGMINE, ANA, ICMBio, **+ linhas ANEEL** p/ faixa de servidão) com smoke test ao
   vivo. Resolve o "fonte não configurada". `docs/fase-2.1-ambiental-dados-reais.md`.
8. Fase 2.5 — Declividade via DEM (exige chave OpenTopography).
9. Fase 3 — Jurídica (perfil municipal/estadual; consome o que a 1.8 extraiu).
10. Fase 4 — Financeira (consome lotes do motor).
11. Fase 5 — Econômica (consome fluxo da financeira).
12. Fase 6 — Localização (enriquecimento IBGE).
13. Fase 7+ — Técnica / Operacional / Mercadológica / Política (guiadas).

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
| 2026-06-02 | **Fase 1.7 concluída e testada** (jurisdição real + regime + rural FMP). 10 critérios de aceite verdes; suíte total **49 testes** (36 das Fases 1/1.5/2 sem regressão + 13 novos). **Valor-ouro confirmado:** Bocaina rural = `floor(1.094.111 / 20.000) = 54 parcelas` (vs. os "4048 lotes" urbanos sem sentido). Resolvedor de jurisdição promovido de stub→`FonteMalha` **injetável** (`jurisdicao.py`); loader de produção `malha_ibge.py` lê GeoJSON de `MALHA_IBGE_PATH` por point-in-polygon/interseção (stdlib `json` + `shapely.STRtree`, **sem dep nova**; egress bloqueado → não validado ao vivo, default degrada para município nulo). Regime obrigatório no aproveitamento (`regime_obrigatorio` 422); rural via `aproveitamento_rural`; novo `POST /analises/{id}/municipio` (override → origem `informado`); alerta `cruza_divisa` + candidatos. Frontend: seletor de regime no card de aproveitamento, correção/divisa no `BadgeCobertura`. | 1.7 |
| 2026-06-02 | **Fonte de FMP usada na 1.7 — PENDENTE de confirmação oficial.** Tabela `backend/app/perfis/fmp_municipios.json` (`{cod_ibge: fmp_m2}`), carregada por `core/fmp.py` (`get_fonte_fmp`, injetável; produção lê o seed se presente, senão None → usuário informa `fmp_m2`). Seed atual: **Bocaina/SP (3506607) = 20.000 m² (2 ha)** — valor-ouro da spec, **não confirmado** na base INCRA/EMBRAPA (egress bloqueado neste ambiente). Proveniência exibida: "FMP/módulo fiscal do município (INCRA; Lei 5.868/72 art. 8º)". **Ação ao operar:** confirmar a FMP/módulo fiscal real por município na fonte INCRA/EMBRAPA e popular a tabela (mesmo tratamento dado às URLs da ambiental). | 1.7 |
| 2026-06-02 | **Detecção automática de município: código pronto, DADO ausente (bloqueio aberto).** Em teste real o município veio "não resolvido": confirmado que `get_fonte_malha()` retorna `None` em produção (sem arquivo de malha) e que o egress ao IBGE está **bloqueado (HTTP 403)** — não foi possível baixar a malha aqui. O caminho de produção foi **provado end-to-end** com um GeoJSON no formato real do IBGE (`from_env`→point-in-polygon detecta Bocaina, `origem: detectado`, sem fixture). Adicionado o pipeline `scripts/baixar_malha_ibge.py` (localidades + malhas v3 por UF → GeoJSON; junção `montar_geojson` coberta por teste offline, HTTP não validado ao vivo). **Pendência para fechar o plano A:** popular `MALHA_IBGE_PATH` (rodar o script com rede liberada ou fornecer o arquivo). Até lá, a detecção degrada honesta e o override (plano B) cobre. | 1.7 |
| 2026-06-02 | **Override por NOME (não por código) + modalidade obrigatória no urbano.** Busca de município por nome via `GET /api/municipios?q=` sobre a malha local, tolerante a acento/caixa (`normalizar_nome`); o código IBGE é resolvido internamente e nunca exibido (autocomplete no `BadgeCobertura`). Aproveitamento URBANO passou a exigir `modalidade` (desmembramento / loteamento aberto / fechado / condomínio de lotes / edilício) — 422 `parametros_urbano_incompletos` sem ela; UI deixa explícito que o lote mínimo é **declarado e provisório** ("pendente extração da LUOS — Fase 1.8"). Suíte total **54 testes** verdes. | 1.7 |
| 2026-06-02 | **Refino de contrato da 1.7 (dúvidas resolvidas):** (1) piso rural é a **FMP por município** (Lei 5.868/72 art. 8º), **não** o módulo fiscal — Bocaina = 54 parcelas só se a FMP dela for 2 ha; ausente → default 2 ha + aviso. (2) **Lista leve IBGE** (cod+nome+UF, ~150 KB) embarcada no repo, desacoplada da malha geométrica → busca/override por **nome** funciona sem a malha. (3) Modalidade urbana é **só rótulo** na 1.7; regra por modalidade é da 1.8 (depende da LUOS). (4) **Divisa = escolha humana** com % de área por município + default no maior; **não** "mais restritivo" automático. (5) Malha **intermediária** em volume Lightsail (pipeline), fallback nearest na borda. | 1.7 |
| 2026-06-02 | **Refino da 1.7 implementado e testado** (spec `docs/fase-1.7-jurisdicao-regime.md` reescrita com as 5 decisões). **#1** `core/fmp.py`+router: proveniência só **FMP** (`PROV_RURAL` "FMP por município — Lei 5.868/72 art. 8º"); FMP ausente **não bloqueia mais** (era 422 `fmp_indisponivel`) → piso de 2 ha + `fmp_origem ∈ {tabela INCRA, informado pelo usuário, default 2 ha (confirmar no CCIR)}`. **#2** `core/lista_municipios.py` + `perfis/lista_municipios.json` (seed São Roque/Bocaina): busca (`/municipios`) e override (`/municipio`) usam a **lista leve**, desacoplada da malha → sobrevivem sem ela; `malha_ibge.montar_lista` + `baixar_malha_ibge.py --lista` populam o dataset completo. **#4** divisa devolve `candidatos[{…, pct_area}]` (% de área **geodésica**, `geometria.area_geodesica`), ordenados desc, principal = o de maior área; campo `municipios_candidatos`→**`candidatos`**. **#5** `resolver_jurisdicao`: gleba toca 1 município mas centróide fora → `origem:"aproximado"` (nearest), não "não resolvido". Frontend só-render (`%` por município, badge `aproximado`, origem da FMP). **55 testes** verdes; `tsc` limpo. Pendência herdada: popular malha/lista/FMP completas via pipeline (egress IBGE 403 neste ambiente). | 1.7 |
| 2026-06-04 | **Diagnóstico da detecção (1.7) — causa raiz confirmada.** "Município não resolvido" NÃO é bug de código: o badge sai `detectado` com município `null` porque `get_fonte_malha()` é `None` (nenhum `.geojson` de malha presente, `MALHA_IBGE_PATH` não setado). A detecção É chamada no upload; só não tem dado. O caminho de produção tem teste verde (`test_malha_ibge`). **Egress deste ambiente = 100% bloqueado (HTTP 403 até para `example.com`)** → a malha não pôde ser baixada aqui; o fix é operacional: rodar `python -m scripts.baixar_malha_ibge` + `export MALHA_IBGE_PATH=...` numa máquina com rede. A busca/override por **nome** já funciona sem a malha (lista leve embarcada). | 1.7 |
| 2026-06-04 | **Fase 2.1 implementada OFFLINE — smoke ao vivo PENDENTE (não marcada concluída).** Adicionado: ANEEL/LT (`FeicaoLinhaTransmissao`; alerta `FAIXA_SERVIDAO_LT` com semi-faixa por tensão 20/40/70 m p/ 69/230/500 kV, `faixa_servidao()`; tensão desconhecida → 70 m conservador); **degradação por camada** (`Camadas.consultadas`/`indisponiveis`, códigos SIGMINE/ANA/ICMBio/ANEEL → contrato `camadas_consultadas`/`camadas_indisponiveis`); o aviso "fonte não configurada" só aparece SEM fonte, nunca com fonte ligada. `camadas_inde.py` ganhou o bloco ANEEL (`URL_LT` DECLARADO — validar em rede) e o rastreio por camada. Ligar a aquisição real: `AMBIENTAL_FONTE_REAL=1` → `get_fonte_camadas` devolve `FonteCamadasINDE` (análogo ao `MALHA_IBGE_PATH`). Frontend só-render (overlay `linhas_transmissao`, lista de camadas consultadas/indisponíveis). **60 testes offline verdes + 2 smoke skipped**; `tsc` limpo. **Critério nº1 (smoke SIGMINE ao vivo) NÃO validável aqui** (egress 403): `tests/test_ambiental_smoke.py` gated por `RUN_LIVE_SMOKE=1` para rodar na máquina do operador. A fase **não está pronta** pela definição da spec até esse smoke passar com rede. | 2.1 |
| 2026-06-04 | **1.7 e 2.1 VERIFICADAS AO VIVO (máquina do operador) — concluídas.** Egress liberado no Mac: malha IBGE baixada (`baixar_malha_ibge` com fix de **gzip** — IBGE devolve `1f 8b`), 5.570 municípios. **1.7**: detecção real confirmada (gleba da Serra → **Gonçalves/MG** automático; São Roque/SP idem). **2.1**: as 4 fontes ao vivo via container — SIGMINE (159 processos reais), ANA hidrografia (`Curso_dÁgua`, 26 cursos), ICMBio/UC e ANEEL/LT. Descobertas operacionais: o catálogo de metadados da ANA não expõe WFS usável, mas o **ArcGIS REST da ANA** (`/services/DADOSABERTOS`) serve hidrografia e UC → viraram os defaults; endpoints **sobrescrevíveis por env** (`AMB_URL_*`). Fixes: resposta `{error}` do ArcGIS tratada como falha (não 0-feições); deploy por **container** exige passar `MALHA_IBGE_PATH`/`AMBIENTAL_FONTE_REAL` e **montar a malha como volume** (gitignored) — feito no `docker-compose.yml`. | 1.7, 2.1 |
| 2026-06-04 | **Bug real achado pelo operador: massa d'água ausente → corrigido (2.1).** Gleba na beira de represa não gerava alerta porque só consultávamos `Curso_dÁgua` (rios=linha); lago/represa é `Massa_dágua` (polígono). Adicionado `FeicaoMassaDagua` + consulta a `Massa_dágua` e `Massa_dÁgua_Grande` (ANA) + alerta `APP_MASSA_DAGUA` (APP marginal, Cód. Florestal art. 4º II/III, mín. 30 m). | 2.1 |
| 2026-06-04 | **DECISÃO — Fase 2.2 (Área verde): identificar cobertura vegetal e descontar do aproveitável.** Requisito do operador: a plataforma é TRIAGEM, não laudo. Não classifica mata nativa/Mata Atlântica/removível (isso é do engenheiro ambiental depois) — apenas **identifica a área verde da gleba e a remove da área aproveitável**, conservador (verde = fora do aproveitável até prova em contrário). Fonte candidata: **MapBiomas** (uso/cobertura 30 m, raster) lido com `rasterio`, no mesmo padrão da malha (baixar uma vez → volume → `MAPBIOMAS_RASTER_PATH`). Spec em `docs/fase-2.2-area-verde.md`. Motor determinístico + fonte injetável; cálculo só no backend; proveniência obrigatória. | 2.2 |
| 2026-06-04 | **2.2 implementada (motor + endpoint + integração + pipeline) — raster real PENDENTE de validação.** `core/vegetacao.py`: `analisar_vegetacao` mede o verde dentro da gleba em CRS métrico local e devolve `area_liquida = total − verde` (proveniência + ressalva "triagem, não laudo"); fonte injetável; `FonteVegetacaoRaster` lê MapBiomas via `rasterio` (import tardio; degrada honesto). Endpoint `GET /analises/{id}/vegetacao` (`VegetacaoOut`). **Integração com aproveitamento**: quando a vegetação é consultada, a base do cálculo vira `total − verde` (URBANO e RURAL), exposta em `desconto_verde` — front mostra banner verde no card. Pipeline `scripts/baixar_mapbiomas.py` (GEE `getDownloadURL`, recorte pequeno por KMZ/bbox → `app/perfis/mapbiomas.tif`; `pip install earthengine-api` + `earthengine authenticate`). `rasterio` nas deps; volume do raster comentado no compose. **67 testes + 4 skip** (raster gated por `importorskip rasterio`; smoke ao vivo p/ o Mac); `tsc` limpo. **A confirmar no Mac**: asset/banda da coleção MapBiomas vigente e o conjunto `CLASSES_VERDE_MAPBIOMAS` (legenda). | 2.2 |
