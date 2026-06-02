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

**Resolvedor:** centróide do polígono → point-in-polygon na malha IBGE → município,
UF, código IBGE. **Detecção com override** (Fase 1.7): o município detectado é
mostrado e o usuário pode corrigir por busca/autocomplete sobre a lista IBGE local;
a proveniência registra `detectado` vs `informado`. Se o **polígono inteiro** cruza
mais de um município (comum em gleba rural grande, na divisa), sinaliza
`cruza_divisa` e pede confirmação — nunca crava em silêncio. Centróide fora de
qualquer município → exige seleção manual, sem inventar.

Sem perfil municipal, **não bloqueia e não inventa** — degrada para o nível federal
e rotula a cobertura:

- `BASE_FEDERAL` — só piso nacional + geoespacial.
- `PARCIAL_UF` — federal + estadual; falta zoneamento municipal.
- `COMPLETA` — federal + estadual + zona municipal.

O relatório estampa o nível e diz explicitamente o que não foi considerado.

### Backbone de dados nacional (carrega uma vez, pipeline de download — não agente)
- **Malha municipal IBGE** — polígonos dos ~5.570 municípios; usada para resolver
  município/UF por point-in-polygon do centróide (resolvedor real, Fase 1.7).
- **Módulo fiscal / FMP por município** — tabela INCRA (publicada pela EMBRAPA),
  uma linha por município (ha); piso do parcelamento RURAL. Varia por município
  (tipicamente 2–5 ha; piso clássico 2 ha / 20.000 m²). Usada no regime rural (Fase 1.7).
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
| **Regime RURAL — FMP** | piso de parcelamento = FMP/módulo fiscal do município (não 125 m²) | **input/tabela por município** | Lei 5.868/72 art. 8º; Estatuto da Terra art. 65 |
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
4. **Fase 1.7 — Jurisdição real + Regime (urbano/rural) + Rural (FMP)** ✅ (corretiva). Promove
   o resolvedor de stub para real (malha IBGE, detecção+override+divisa); pergunta de regime
   no início do aproveitamento; rural usa FMP/módulo fiscal por município; urbano usa lote
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
