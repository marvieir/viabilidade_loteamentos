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
Concluídas (validadas):  1 → … → 4 → 4.1 → 4.2 → 5 → 6 → 7 → 8 → 9 → 9.1 → 9.4 → 9.5 → 9.6 → 9.7
Próximas (nesta ordem):  pórtico de entrada (ancorado na via principal da 9.7) · refino orgânico do traçado · Custos (SINAPI/SICRO) · Técnica/Operacional/Mercadológica/Política · Estadual
                                                          (9.2→9.3→9.4: tamanho de lote é LEI+diretriz+prática, nunca chute; 1.6* parado)
```

- **4.1 — Financeira corretiva + PRICE** ✅ — corrige as armadilhas de UX da 4
  (inadimplência=1 zerou receitas sem aviso) e introduz a **venda financiada** (mesa de
  perfis PRICE, fluxo de vendas ≠ fluxo de recebimento, receita financeira separada do VGV
  nominal — a TIV 5.0 mostrou que os juros são ~1/3 do VGV geral). `docs/fase-4.1-financeira-price.md`.
- **5 — Econômica (CONCLUÍDA)** — **avalia** o `fluxo` da 4/4.1/4.2: VPL · TIR ·
  payback simples/descontado · exposição descontada · IL · **curva VPL×TMA** (a sensibilidade
  do MVP, decisão do operador). **Decisões do operador (handoff §0, 2026-06-12):** recebível de
  loteamento corrigido por **IPCA** → **TMA REAL**; a spec resolveu a consistência nominal×real
  pela **convenção de moeda constante** (Fisher: o IPCA cancela; fluxo da 4 lido em R$ de hoje,
  desconto por taxa real, sem projetar inflação; a 4 permanece intacta/nominal).
  **Gabarito:** aba `IND. FINANCEIRO E TECNICO CP 11` da TIV 5.0. `docs/fase-5-economica.md`.
- **1.6\*** — adaptador de topografia/CAD; segue **bloqueada** até reunir 3–5 arquivos reais.

> A 1.8 tem número "menor" que a 2.1/2.2 mas foi feita depois — ficou para trás de propósito
> por ser a mais delicada. Número baixo ≠ feito primeiro.

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

## 1-A. Pré-análise e alertas, não laudo — a regra que TODAS as dimensões herdam

O produto é um **sistema de alertas de pré-análise**. Ele acende luzes — "olha a mineração
da ANM aqui", "1,47 ha em declividade vedada", "consta hipoteca na matrícula", "a área não
bate com o registro" — para orientar **onde o incorporador deve olhar e quanto pode doer**
antes de gastar com a due diligence cara. **Ele nunca apaga a luz pelo usuário nem assina
embaixo.** Não substitui nenhum profissional e não decide nada.

**Profissionais insubstituíveis (o tool sinaliza; eles decidem):**

| Decisão | De quem é | O que o tool faz |
|---|---|---|
| Parecer dominial/jurídico (ônus, cadeia, validade) | **Advogado** | extrai e lista o que CONSTA na matrícula/certidão |
| Levantamento topográfico / medição oficial | **Agrimensor / engenheiro** | DEM 30 m **orientativo** (pode superestimar; não é medição) |
| Classificação de mata (nativa/Atlântica/suprimível), laudo de supressão | **Engenheiro ambiental** | mede o verde por satélite e marca "a verificar" |
| Projeto urbanístico + diretrizes da gleba (art. 6º Lei 6.766) | **Urbanista** | calcula teto físico; vias/lazer/doação real são do projeto |
| **Aprovação** do parcelamento | **Prefeitura / órgão licenciador** | triagem sobre regras gerais; nunca aprova |

**Regra de linguagem (inegociável, herdada por toda dimensão):** o tool **nunca afirma**
"aprovado", "livre e desembaraçado", "viável" ou "regular". Sempre **"consta…"** /
**"indício de…"** / **"verificar com [profissional]"**. **Ausência de achado ≠ ausência do
problema** — depende dos dados/documentos disponíveis. Este é o disclaimer-mestre do
relatório; cada card o herda.

---

## 2. Princípio inegociável: determinismo e proveniência

1. **Todo cálculo numérico mora no backend Python.** Nunca no frontend, nunca via LLM.
2. **A IA fica na BORDA, nunca no caminho do número.** A fronteira é entre *adquirir/ler
   dados* (onde IA/agente/geoprocessamento são bem-vindos) e *calcular o veredito de
   viabilidade* (determinístico, Python, sem LLM, jamais). Dois usos legítimos de LLM:
   (a) **ler documento não-estruturado** — ex.: extrair índices da LUOS em PDF (Fase 1.8),
   ou ônus de matrícula (Fase 3), **sempre com validação humana obrigatória + proveniência
   por artigo/ato**; (b) **narrar em prosa** números já calculados (resumo executivo),
   opcional e desligável. O LLM lê e descreve; nunca decide o número.
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
- **DEM — Copernicus GLO-30 Public** (AWS Open Data, COG, **sem chave**), lido por janela
  via `/vsicurl/` (Fase 2.5); OpenTopography só fallback gated por chave. SRTM como opção.

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
adaptador a montante. **Reparo de `<Polygon>` auto-interseccionado** (`buffer(0)`,
determinístico) é feito no adaptador, com aviso e `rota=POLYGON_REPARADO` — o núcleo
`geometria.medir` continua estrito (adiantamento mínimo da 1.6).

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
| Doação pública | varia por zona/município; **pode ser 0** (alguns não exigem mínimo); entra no número via **perfil confirmado** (`cenario_diretriz`) | **input municipal — extraído da LUOS na 1.8, validado por humano** | Lei 9.785/99 + diretriz local |
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

Estes são o critério de aceite do motor de aproveitamento (modelo de triagem, sem perfil).

**Com diretriz municipal (Fase 1.8)** — validado ao vivo na 2ª gleba
**Sao_Roque_area_mina_de_agua** (São Roque/SP, 7,81 ha, zona **MUE** da LC 106/2020):

| Item | Valor |
|---|---|
| Total | 7,81 ha |
| Verde (WorldCover auto por gleba) | 0,55 ha |
| **Aproveitável físico** (total − verde) | 7,26 ha |
| Doação 20% (base total, da LUOS confirmada) | 1,56 ha |
| **Headline com diretriz** (físico − doação) | **5,7 ha (72,9%)** |
| Lote legal da zona MUE | 360 m² |
| **Nº de lotes (headline)** | **158** = `(72.587 − 15.621) ÷ 360` |
| Teto físico (secundário) | 201 |
| Otimista 2.3 (secundário) | 216 |

> **Nota (pós-2.5):** com a declividade na união, a revalidação de São Roque com DEM deu
> vedação ≥30% = 1,47 ha (sobreposição com verde contada uma vez: 0,10 ha) → base 5,89 ha →
> headline com diretriz **4,33 ha / 120 lotes**. Os valores da tabela acima são pré-DEM.

Critério de aceite do `cenario_diretriz`: o número grande é o **com diretriz**, com teto
físico e otimista como secundários (veto da decisão A — ver §6-A).

### ~~Bases de doação (Aula 09) — OBSOLETO~~
Os três números da Aula 09 (57,0% / 61,6% / 65,0% → 142 / 154 / 162 lotes, assumindo
vias 11.500 m² + doação 20%) **foram aposentados** na Fase 2.2: o modelo de triagem
não calcula vias nem doação (só se sabem no projeto urbanístico / na diretriz municipal).
Mantidos aqui só por proveniência histórica — **não são mais critério de aceite**.

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

**Referência financeira definitiva — TIV 5.0** (planilha profissional do operador; caso real
São Roque 3 matrículas, gleba 181.991 m², 167 lotes de ~447 m²): em loteamento a venda é
**financiada direto ao comprador** (mesa de perfis 12/30/60/120 meses, tabela PRICE, entrada
~15%), o que separa **fluxo de VENDAS** (quando vende) de **fluxo de RECEBIMENTO** (quando o
caixa entra) e gera **receita financeira ≈ 1/3 do VGV geral** (TIV: nominal R$ 105,7M +
juros R$ 35,9M = geral R$ 141,6M). A 4.1 incorpora isso; securitização/funding/sócios/
inflação/cenários da TIV ficam como evolução; a aba CP 11 é o gabarito da Fase 5.

---

## 6-A. Modelo de "Área aproveitável" (TRIAGEM) — contrato vigente da Fase 1

> Redesenhado na Fase 2.2 por decisão do operador. **Substitui** o motor antigo
> (loteamento/desmembramento + 3 bases de doação), agora removido.

**Fórmula:**
```
Área aproveitável = Área total − UNIÃO( mata ∪ APP curso d'água ∪ APP massa d'água
                                        ∪ faixa não-edificável ∪ servidão de LT
                                        ∪ declividade ≥30% )
Nº de lotes (urbano) = TETO = Área aproveitável ÷ lote mínimo
```

Decisões e porquês:
1. **Vias saem do cálculo** — o % de vias só se conhece no **projeto urbanístico**.
2. **Doação sai do cálculo físico** — depende da **diretriz de cada prefeitura** (pode ser 0);
   volta na Fase 1.8 via `cenario_diretriz`.
3. **APP entra junto com a mata por UNIÃO geométrica** (sem dupla contagem): mata
   ribeirinha é APP e verde ao mesmo tempo — conta uma vez só (`core/aproveitavel.consolidar`).
   A declividade ≥30% (2.5) entra na mesma união, também sem dupla contagem.
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

### Headline urbano: dois modos (veto da decisão A, exercido na Fase 1.8)
A spec da 1.8 propunha o `cenario_diretriz` como **segundo cenário** (headline sempre o teto
físico). O operador **vetou** após a validação ao vivo: quando há **perfil municipal confirmado
+ zona declarada**, o **headline urbano passa a ser o cenário com diretriz** — aproveitável =
`físico − doação`, lote = **legal da zona** — e o teto físico e o otimista (2.3) viram
**secundários**. **Sem zona confirmada**, o headline segue o **teto físico-ambiental**. A troca é
só de **apresentação** (frontend escolhe qual número destacar); o backend devolve todos os
números e **não recalcula nada no front** (§2). Rural não muda (FMP).

**Custo da escolha (registrado):** o número de triagem saiu de um aproveitamento *legalmente
ancorado* (bases de doação da Lei 9.785) para um *teto físico-ambiental* — e, com perfil
confirmado, **volta a ancorar na lei** via `cenario_diretriz` (lote legal + doação da zona).

> **Item parado (proposta "Fase 1.9"):** se a APP/declividade/mata pode **abater** o
> `doacao_split.verde` (a doação de área verde absorvida pela área já restrita) — varia por
> município (SP capital e Araxá permitem parcial; interpretação restritiva soma tudo).
> **Default conservador = soma (não abate)**; vira parâmetro do perfil. Conecta-se ao
> `doacao_split` que a Fase 3.5 passa a exibir. **Muda o número** → não entra na Fase 3.

---

## 7. Dimensões de viabilidade: o que cada uma entrega e COMO

| Dimensão (aula) | Entrega | Produção | Fonte |
|---|---|---|---|
| Aproveitamento (motor) | área, perímetro, **área aproveitável = total − união(restrições)**, **teto** de lotes (urbano) / parcelas (rural) | determinístico geométrico | KMZ + camadas + regras |
| **Área verde (2.2)** | mata da gleba (desconto de triagem do aproveitável) | determinístico geoespacial | ESA WorldCover 10 m |
| Ambiental (06) | APP curso + **massa d'água**, UC, hidrografia, faixa não-edificável, **servidão LT (ANEEL)**, declividade ≥30% | determinístico geoespacial | ANA, ICMBio, **ANEEL**, SIGMINE, Cód. Florestal |
| **Jurídica (09)** | **pré-análise documental**: matrícula/ônus/averbações/indisponibilidade + certidões + cross-check área matrícula×KMZ + síntese de risco; (3.5) conformidade LUOS | **borda (LLM lê e propõe) + gate humano + checks determinísticos** | matrícula/certidões (upload) + perfil 1.8 + alertas geo |
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
   1 linha simples fechável → polígono; CAD multi-linha roteado para 1.6 com diagnóstico;
   reparo `buffer(0)` de polígono auto-interseccionado). `docs/fase-1.5-ingestao.md`.
3. **Fase 1.6 — Adaptador de topografia/CAD** (isola perímetro entre várias linhas, fecha
   gaps grandes, resolve auto-interseções, com confirmação visual no mapa). **Pendente
   de 3–5 arquivos reais** antes de especificar — caso difícil, não determinístico sozinho.
4. **Fase 1.7 — Jurisdição real + Regime (urbano/rural) + Rural (FMP)** ✅ (corretiva). Promove
   o resolvedor de stub para real (malha IBGE, detecção+override por nome+divisa); pergunta de
   regime no início do aproveitamento; rural usa **FMP por município** (tabela INCRA); urbano usa
   lote mínimo **declarado** no interino. `docs/fase-1.7-jurisdicao-regime.md`.
5. **Fase 1.8 — Extração assistida da LUOS (urbano)** ✅ (LLM lê o PDF da diretriz municipal →
   propõe lote mínimo/doação por zona/modalidade → **validação humana + proveniência por artigo**
   → vira perfil confirmado). **Reintroduz doação e lote legal no número** via `cenario_diretriz`.
   Extrator injetável (`ExtratorLUOS`); real = Claude API gated por `ANTHROPIC_API_KEY`; testes
   100% offline com stub. `docs/fase-1.8-luos.md`.
6. **Fase 2 — Ambiental (overlays vetoriais)** ✅ encanada (`docs/fase-2-ambiental.md`).
7. **Fase 2.1 — Ambiental com dados reais + ANEEL** ✅ (corretiva). Ligou SIGMINE/ANA/ICMBio/
   **ANEEL** reais com smoke test. Achou e tratou o caso **massa d'água/represa** (`APP_MASSA_DAGUA`).
   `docs/fase-2.1-ambiental-dados-reais.md`.
8. **Fase 2.2 — Área verde (cobertura vegetal)** ✅. ESA WorldCover 10 m (`/vsicurl`, sem login);
   desconta a mata do aproveitável; **redesenhou o modelo de aproveitável** (seção 6-A). **Modo
   automático por gleba** (default). Validada ao vivo (Terreno_Cachoeira **e São Roque**).
9. **Fase 2.3 — Severidade do verde** ✅. Separa **verde-em-APP/UC = restrição dura** de **verde
   genérico = a verificar**; acrescentou `cenario_otimista`. Reusa as camadas da 2.1; 100%
   geometria. Validada ao vivo. `docs/fase-2.3-severidade-verde.md`.
10. **Fase 2.5 — Declividade via DEM** ✅ (validada ao vivo, São Roque). Faixas suave/média/alta +
    **flag legal ≥30%** (Lei 6.766/79 art. 3º §ún III) que entra na união do aproveitável
    (`declividade_vedada`). Fonte **keyless** = Copernicus GLO-30 Public COG na AWS (`/vsicurl`).
    `docs/fase-2.5-declividade.md`.
11. **Fase 3 — Pré-análise jurídica documental** ✅ (testada com matrícula real). Lê
    matrícula/certidões (motor da 1.8 generalizado → `ExtratorDocumento`), extrai
    ônus/averbações/indisponibilidade com proveniência por ato, cross-check área-matrícula ×
    KMZ, síntese de risco; gate humano; **não muda o número**. `docs/fase-3-juridica-documental.md`.
12. **Fase 3.5 — Conformidade urbanística** ✅. Consumo puro do perfil 1.8: checklist da
    (zona, modalidade) — lote/doação `considerado`, frente/CA/TO/split `exigencia_projeto`,
    split inconsistente `atencao`, ausente `nao_extraido`; leituras calculadas no backend
    (pt-BR). `docs/fase-3.5-conformidade.md`.
13. **Fase 4 — Financeira (fluxo de caixa)** ✅ implementada (`docs/fase-4-financeira.md`):
    premissas declaradas com proveniência, blocos da planilha corrigidos (§9: tributação =
    parâmetro, sem RET), fluxo mensal + exposição máxima; lotes do caso-base = diretriz >
    teto rotulado. **Lições do teste real → Fase 4.1** (UX da inadimplência + venda financiada).
14. **Fase 4.1 — Financeira corretiva + PRICE** ✅. Correções de UX (inadimplência
    default 0 + 422 acima de 30% + `alerta_critico` p/ fluxo morto) e **modo financiado**:
    mesa de perfis PRICE, fluxo de vendas ≠ recebimento, receita financeira separada,
    comissão sobre recebimento. Ouros batidos (pmt 1.890,78; rec. fin. agregada
    2.844.668,32). `docs/fase-4.1-financeira-price.md` (+ 4.2 wizard/parceria/dashboard ✅).
15. **Fase 5 — Econômica** ✅. VPL/TIR/paybacks/IL/curva VPL×TMA sobre o `fluxo` da 4.x,
    convenção de moeda constante (TMA real/IPCA); slots do dashboard preenchidos.
    `docs/fase-5-economica.md`.
16. **Fase 6 — Localização** ✅. Enriquecimento IBGE por `cod_ibge`, 4 indicadores
    (pop+densidade+crescimento · PIB pc · déficit FJP/fallback domicílios · faixa etária),
    arquivo embarcado + comparação UF/Brasil, informativo puro (§1-A). Ouro: São Roque
    79.484 hab / PIB pc 57.024,90. `docs/fase-6-localizacao.md`.
17. Fase 7+ — Técnica / Operacional / Mercadológica / Política (guiadas).
18. Fase Estadual — camada estadual (órgão licenciador, lei estadual de lote mínimo,
    APA/manancial); eleva a cobertura a `PARCIAL_UF`. APA/manancial é geométrico → família 2.x.

> **Gancho transversal futuro — multi-tenant/login:** o código novo não deve assumir
> persistência global (volume único) como verdade eterna; perfis/fichas/premissas por
> análise hoje, por usuário/conta quando houver autenticação.

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
  urbano. O motor exige `regime` explícito e declara a premissa. (Corrigido na Fase 1.7.)

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
| 2026-06-06 | **Fases 1.8 + 2.2 revalidadas ao vivo em 2ª gleba (São Roque/SP — `Sao_Roque_area_mina_de_agua`, 7,81 ha, zona MUE da LC 106/2020).** Três correções de campo: **(1) Área verde AUTOMÁTICA por gleba** — `FonteVegetacaoWorldCoverAuto` escolhe o(s) tile(s) do ESA WorldCover pela posição da gleba (`_tile_worldcover`/`_tiles_da_gleba`) e lê o COG público por HTTP (`/vsicurl`, range requests). **Dispensa o `verde.tif` recortado por gleba** — resolve o gancho da infra 2.2 (outro KMZ não sobrepunha o recorte pré-cortado → "Input shapes do not overlap raster"). Default `VEGETACAO_WORLDCOVER_AUTO=1`; recorte local (`VEGETACAO_RASTER_PATH`) vira **fallback offline**; leitura compartilhada em `_extrair_cobertura` (une tiles) com **degradação acionável** (não-sobreposição / egress bloqueado). Egress ao bucket público confirmado no container. **(2) Lote mínimo legal puxado da zona** — ao selecionar a zona LUOS confirmada, o form do aproveitamento pré-preenche o lote **legal** (espelha `core.aproveitamento._param_zona`; edição manual rompe o vínculo), em vez do default 200. **(3) Headline urbano = cenário com diretriz quando há zona confirmada** — **veto da decisão A** (linha acima): com zona, o número grande passa a ser o aprov. **com doação + lote legal**; o teto físico e o otimista viram secundários. Sem zona, headline segue físico. Backend inalterado (já devolvia `cenario_diretriz`) — mudança só de apresentação (frontend não recalcula, §2). **Números batidos na tela (São Roque/MUE):** total 7,81 ha → verde 0,55 ha → físico **7,26 ha**; doação 20% base total = 1,56 ha → **headline 5,7 ha (72,9%) → 158 lotes**; teto físico **201**, otimista **216**. **102 testes + 3 skip; `tsc` limpo.** | 1.8/2.2 |
| 2026-06-07 | **Fase 2.5 IMPLEMENTADA (declividade via DEM) — validação ao vivo PENDENTE.** Nova dimensão: `core/declividade.py` calcula declividade **em CRS métrico** (AEQD local; grid reprojetado 30 m), devolve média, **faixas suave/média/alta** (limiares 8/20% configuráveis) e a **flag legal ≥30%** (Lei 6.766/79 art. 3º §ún III) poligonizada (mancha pixelada fiel ao dado). `GET /analises/{id}/declividade`. **Fonte keyless** = Copernicus GLO-30 Public COG na AWS (`FonteDEMCopernicusAuto`, tile 1°×1° pela posição da gleba via `/vsicurl`), espelhando a 2.2 — **sem chave**; `FonteDEMOpenTopography` é fallback gated por `OPENTOPOGRAPHY_API_KEY` (ausência não quebra → cai no keyless); `FonteDEMRasterLocal`/`DEM_RASTER_PATH` é fallback offline. **Separação 2.2:** `FonteDEM` (I/O + reprojeção, rasterio só no container) × `analisar_declividade` (numpy/shapely/pyproj puro, offline). **≥30% entra na união do aproveitável** como item `declividade_vedada` (decisão §4.2 do spec — descontar, não flag-only), via `_coletar_geoms`/`consolidar` sem dupla contagem; propaga a teto/otimista/diretriz sem novo contrato. Degrada honesto (`consultada=false`, sem flag) se DEM indisponível (egress/tile/oceano) com mensagem acionável; ressalva DSM em toda saída. Frontend: `CardDeclividade` (média + faixas + flag ≥30% + ressalva) + overlay vermelho `declividade_vedada`. **120 testes + 3 skip (18 novos da 2.5); `tsc` limpo.** Gold values de Cachoeira/São Roque **inalterados nos testes** (DEM off por default no sandbox). **VALIDADA AO VIVO (São Roque):** egress keyless confirmado no container (`rasterio.open('/vsicurl/.../S23_00_W046...DEM.tif')` → 3600×3600, **sem fallback**); na tela: declividade média **20,23%** (suave 12,5% · média 47,7% · alta 39,8%), **vedação ≥30% = 1,47 ha** descontada no aproveitável (sobreposição com verde contada uma vez só: 0,10 ha → base 5,89 ha → headline com diretriz 4,33 ha / 120 lotes). | 2.5 |
| 2026-06-08 | **Redesign da interface — dashboard profissional (frontend, MVP demo).** A pilha vertical de cards virou um **app shell**: top bar (gleba + "Analisar tudo" + "Nova análise") · sidebar de navegação por dimensão (com badge de alertas e status do perfil LUOS) · **faixa de KPIs** (Área · Aproveitável com diretriz · Lotes · Restrições críticas, lidos dos cards via `onData`) · **mapa-herói** com painel de **camadas** (toggle de overlays centralizado, `ocultos` no page) e legenda · seções (Visão geral + os 5 cards) **todas montadas, só a ativa visível** (estado preservado entre abas). Tema **claro profissional** (slate + emerald/indigo, semáforo), Inter via `<link>` (degrada p/ system-ui; sem dependência de build/egress), ícones inline (sem libs). Pesquisa de base: SaaS dashboards (F-pattern/KPIs), apps GIS (padrão "partial map", mapa protagonista, toggle de camadas), padrões shadcn (sidebar+main, cards de 1 tópico, tabs). **Regra preservada:** front só renderiza JSON do backend — KPIs/abas não recalculam nada (§2). `CORES/ROTULO_OVERLAY` extraídos p/ `mapa/overlays.ts`; `CardAmbiental` perdeu o toggle interno (centralizado no mapa). `tsc` limpo; `next build` ok. Aprovado por mockup navegável antes de implementar. | UI |
| 2026-06-09 | **Handoff da Fase 3 (Jurídica) escrito** — `docs/handoff-fase-3-pedido-spec.md` para a sessão de spec (claude.ai). Mapeia que a 1.8 já extrai `frente_min`/`ca`/`taxa_ocupacao`/`doacao_split` com proveniência mas **não os usa** (ganchos "Fase 3" no schema), e que o frontend pós-redesign recebe a dimensão por encaixe (sidebar `secoes.tsx` + `onData`/`onOverlays`). Levanta a tensão de escopo (consumo/conformidade × criar camada estadual) e as decisões vetáveis. Roadmap (§0 item 11) aponta o handoff. | — |
| 2026-06-09 | **Fase 3 redefinida: "Jurídica" = PRÉ-ANÁLISE DOCUMENTAL/DOMINIAL** (matrícula/ônus/certidões + cross-check área matrícula×KMZ + síntese de risco), reusando o motor da 1.8 (`ExtratorDocumento`, sem credencial nova). É a viabilidade jurídica clássica (Aula 09). A conformidade urbanística (índices LUOS, ex-"Fase 3") **desceu para a Fase 3.5**. `docs/fase-3-juridica-documental.md`. | 3 |
| 2026-06-09 | **§1-A adicionado — princípio mestre "pré-análise e alertas, não laudo".** Formaliza no topo que o produto **sinaliza, não decide**; lista os profissionais insubstituíveis (advogado/agrimensor/eng. ambiental/urbanista/prefeitura) e o que cada um decide; fixa a **regra de linguagem inegociável** herdada por toda dimensão: nunca "aprovado/livre/viável/regular", sempre "consta…/verificar com…"; **ausência de achado ≠ ausência do problema**. Disclaimer-mestre do relatório. | geral |
| 2026-06-09 | **Fase 3 CONCLUÍDA — Pré-análise jurídica documental (dominial).** Spec da sessão claude.ai (`docs/fase-3-juridica-documental.md`) **substituiu** o escopo de conformidade urbanística (vira Fase 3.5). 2ª aplicação de LLM do projeto, **sem credencial nova**: `core/extrator_documento.py` generaliza o `ExtratorLUOS` (prompts por tipo `matricula`/`certidao`, tool use forçado, anti-alucinação reforçada; reusa erros/TLS/parse e a `ANTHROPIC_API_KEY` da 1.8; `get_extrator_documento` gated + `JURIDICO_EXTRATOR_DESLIGADO`; stub offline). **Eixo extração×núcleo:** o LLM lê e **propõe** ônus/averbações com **referência ao ato** (R-x/Av-y); ficha nasce `proposto` e só `confirmado` (PUT, `validado_por`+`data_referencia`) entra na síntese — **achado sem ato não é confirmável (422)**. Núcleo **puro** (`core/juridico_documental.py`): cross-check de área (matrícula × KMZ da Fase 1, tol 5%) + roll-up de risco determinístico (domínio + alertas geo de 2.1/2.3/2.5 via `core/alertas_geo.py`, provedor injetável/degradável). **NUNCA afirma "imóvel livre"** — avisos obrigatórios sempre presentes; ausência de achado ≠ limpo. Persistência por análise (`core/juridico_store.py`, volume gitignored). Endpoints: `POST …/juridico/extrair` (503/422) · `PUT …/juridico` (gate) · `GET …/juridico` (consolida + síntese, sempre 200/degrada). **Não altera o número do aproveitável.** Frontend: item "Jurídico" na sidebar + `CardJuridico` (tela de revisão propor→editar→confirmar com a referência ao ato; ficha consolidada + síntese de risco com semáforo) → reporta ao KPI "Restrições críticas". **133 testes + 4 skip (13 novos da Fase 3); `tsc` limpo; `next build` ok.** | 3 |
| 2026-06-09 | **Fase 3 — upload aceita imagens + multipágina (achado de campo do operador: matrículas vêm em JPEG, não PDF).** `ExtratorDocumento.extrair` passou a receber `list[(bytes, media_type)]` (PDF→bloco `document`, imagem→bloco `image` nativo do Claude); `MEDIA_SUPORTADAS` = pdf/jpeg/png/webp/gif. Endpoint `…/juridico/extrair` aceita **vários arquivos** (`documentos: list[UploadFile]`) — documento de N páginas escaneadas entra como N imagens num só POST; media type detectado por content_type + extensão (tolera `image/jpg`); formato não suportado → 422 acionável. Frontend: input `multiple` + `accept` de imagem, com dica de selecionar todas as páginas de uma vez. **136 testes + 4 skip (3 novos); `tsc` limpo; `next build` ok.** | 3 |
| 2026-06-09 | **Fase 3 — refino da síntese de risco (teste de campo: matrícula 1.388, 1976-80).** Qualidade de sinal, sem mexer no cálculo: (1) **averbações administrativas** (cancelamento/baixa, casamento/estado civil, retificação, georreferenciamento) saem do painel de risco (`_averbacao_e_risco`); ficam na ficha como **histórico**. Só reserva legal/APP/servidão/restrição/construção viram "atenção". (2) **Ônus baixado/cancelado** ganha selo de situação + esmaecimento no front (não se confunde com ônus ativo); o roll-up já não os contava como crítico. Front separa "Averbações registradas (histórico)" do semáforo. Validado ao vivo: 3 hipotecas **canceladas** corretamente fora dos críticos; divergência de área 60.500 × 78.107 m² = **22,5%** pegada. **137 testes + 4 skip (1 novo); `tsc` limpo; `next build` ok.** | 3 |
| 2026-06-10 | **Fase 3.5 CONCLUÍDA — Conformidade urbanística (consumo puro da 1.8).** Fecha o gancho "persiste p/ a Fase 3" do schema: `core/conformidade.py` (puro, reusa `_param_zona`) confronta a (zona, modalidade) com a gleba e devolve **checklist por índice** — `considerado` (lote/doação, já no número, evidenciados com o m² calculado) · `exigencia_projeto` (frente→profundidade implícita do lote, CA→m² construído/lote, TO→projeção/lote, split→m² por componente) · `atencao` (**consistência split×total**, tol 0,5 p.p.) · `nao_extraido` (ausente → "não avaliado", nunca inventa). Leituras formatadas **no backend** (pt-BR; front não reformata, §2); proveniência por artigo herdada + `validado_por`. `GET /analises/{id}/conformidade?zona=&modalidade=` — degrada honesto (sem perfil → motivo acionável; sem zona → `zonas_disponiveis` p/ o seletor). **Não altera o aproveitável** (testado antes/depois). Frontend: item "Conformidade" na sidebar + `CardConformidade` (zona/modalidade do perfil confirmado, chips por status). `docs/fase-3.5-conformidade.md`. **148 testes + 4 skip (11 novos); `tsc` limpo; `next build` ok.** Registrado também o gancho transversal **multi-tenant/login** (futuro; re-chavear persistência por tenant). | 3.5 |
| 2026-06-10 | **Fase 4 CONCLUÍDA — Financeira (fluxo de caixa do empreendimento).** A planilha do curso entra como ESTRUTURA, sem os erros da §9. `core/financeira.py` é **aritmética PURA** (sem LLM/rede/credencial): VGV bruto/próprio; **permuta** (% VGV pro-rata / lotes / compra); vendas com curva (linear/custom validada) à vista ou parcelado; custos por bloco com curvas (urbanização R$/lote ou R$/m², projetos/topografia default rotulado, marketing % VGV próprio, comissão % s/ venda bruta, administração do mês 0 ao fim); **tributo é PARÂMETRO** — `aliquota_pct × receita própria recebida` (regime de caixa), default 5,93% **ROTULADO** ("Lucro Presumido efetivo PIS+COFINS+IRPJ+CSLL; NÃO é RET; confirme com contador"), `regime` é só rótulo de proveniência. Fluxo mês a mês + acumulado; **exposição máxima de caixa** (mín. do acumulado + mês); resultado nominal; margem ÷ VGV próprio. **Origem dos lotes do caso-base (§3.1):** diretriz > teto físico (+aviso de superestimação) > declarado; o front repassa `n_diretriz`/`n_teto` do aproveitamento (não recalcula, §2). Moeda formatada **no backend** (`_fmt` pt-BR). **Fronteira 4×5:** monta o fluxo, **nenhum VPL/TIR/payback** (é a Fase 5). Persiste premissas+resultado por análise (`core/financeira_store.py`, volume gitignored), sem gate (origem já é humana). `POST/GET /analises/{id}/financeira`; 422 honesto sem `preco_lote` ou curva inválida. **NÃO altera o aproveitamento** (testado antes/depois). Frontend: item "Financeira" na sidebar + `CardFinanceira` (premissas com defaults rotulados; tabela do fluxo; KPIs VGV/resultado/exposição). `docs/fase-4-financeira.md`. **Caso Fechado A bate linha a linha:** mês 0 −390.000 / 1–4 +152.560 / 5–6 +192.560 / 7–10 +692.560; nominal **3.375.600,00**; exposição −390.000 no mês 0; margem **42,1950%**. **166 testes + 4 skip (18 novos); `tsc` limpo; `next build` ok.** | 4 |
| 2026-06-10 | **Falha de UX detectada em teste real (Fase 4):** campo `inadimplência (0–1)` preenchido com `1` (= 100%) zerou TODAS as entradas → resultado −R$ 19M sem nenhum aviso. Motor aritmeticamente correto; a spec falhou em prevenir (escala 0–1 ao lado de `eficiência`, onde 1 é neutro). **Correção → Fase 4.1** (default 0, 422 acima de 30% sem confirmação explícita, `alerta_critico` quando entradas=0 com vendas configuradas, rótulos em %). | 4/4.1 |
| 2026-06-10 | **Achado estrutural — TIV 5.0 (planilha profissional do operador, caso real São Roque 3 matrículas):** loteamento vende **financiado direto ao comprador** (mesa 12/30/60/120 meses, PRICE, entrada ~15%); **receita financeira ≈ 1/3 do VGV geral** (nominal 105,7M + juros 35,9M = 141,6M); **fluxo de VENDAS ≠ fluxo de RECEBIMENTO**. O modelo à vista/parcelado-sem-juros da Fase 4 subestima receita e erra o caixa → **Fase 4.1** adiciona o modo financiado (aditivo; Caso A preservado byte a byte). TIV confirma na prática o aviso do teto físico: usa 167 lotes onde o teto deu 294 (viário 15,3% + verdes 28%). Securitização/funding/sócios/inflação/cenários da TIV = evolução registrada. **Aba CP 11 = gabarito da Fase 5** (TIR/MTIR/VPL/ROE/payback/exposição a VP; São Roque: TIR 121% a.a., VPL 42,2M, payback 28, exp. máx −6,8M mês 17). | 4.1/5 |
| 2026-06-10 | **Fase 4.1 ESPECIFICADA** (`docs/fase-4.1-financeira-price.md`): correções de UX obrigatórias + modo financiado (mesa de perfis PRICE; receita financeira separada do nominal; comissão sobre recebimento no financiado; resumo anual + mensal sob expand). Valores-ouro verificados por código: pmt 1.890,78 (lote 100k, entrada 15%, 60×, 1% a.m.); receita financeira agregada 2.844.668,32; recebimento mês 30 = 189.077,81; equivalência parcelado ≡ financiado-taxa-0. | 4.1 |
| 2026-06-10 | **Fase 4.1 CONCLUÍDA — venda financiada (PRICE) + correções de UX.** Prioridade 1 (a lição do −19M): `inadimplencia_pct` > 30% sem `confirmar_inadimplencia_alta` → **422** ("confirme explicitamente"); confirmada → roda com aviso; **`alerta_critico`** quando há vendas configuradas e Σ entradas = 0 (banner vermelho no front); rótulos do form todos em **%** (escala única — fim do par traiçoeiro 0–1). Prioridade 2 (modo `financiado`): `pmt_price` puro (PRICE; taxa 0 degrada p/ linear ≡ parcelado, equivalência testada); **mesa de perfis** (participação/prazo/taxa, soma=1 validada ±0,001; default ROTULADO "referência TIV 5.0 — calibre com sua corretora"); **fluxo de VENDAS (`fluxo_vendas`) ≠ fluxo de RECEBIMENTO** (acumulação por safra em float cru; arredonda só na emissão mensal — é o que faz os ouros baterem); **receita financeira separada do nominal** (`vgv.receita_financeira`/`geral`); **comissão sobre recebimento** no financiado (`comissao_base` com default por modo); `fluxo_resumo_anual` (front: tabela anual por default em horizonte > 12 meses, mensal sob expand). **Valores-ouro batidos:** pmt 1.890,78 (lote 100k, entrada 15%, 60×, 1% a.m.); receita financeira agregada **2.844.668,32**; recebimento mês 30 = **189.077,81**; última parcela mês 70. **Caso Fechado A preservado; sem VPL/TIR (fronteira 4×5). 184 testes + 4 skip (18 novos); `tsc` limpo; `next build` ok.** Nota de implementação: a identidade Σ entradas = nominal + juros é EXATA no agregado `vgv.geral` (fluxo cru); o Σ das linhas mensais emitidas deriva centavos (emissão arredonda a centavo/mês; pmt PRICE não é múltiplo de centavo) — `vgv.geral` é o autoritativo. | 4.1 |
| 2026-06-11 | **Fase 4.2 CONCLUÍDA — financeira guiada (wizard) + parceria + dashboard.** Resposta ao feedback "campos vagos/sem ordem": o card virou **wizard de 6 passos** (Lotes&Preço → Parceria → Venda → Custos → Tributos → Resultado), **microcopy em todo campo**, defaults com badge "default — edite"; o **estado mora no front** e o número de cada passo vem do backend (POST a cada avanço) — **contrato POST único preservado** (§2; nada calculado no front). Motor: `participantes` (incorporador/terrenista) em toda saída — `parceria %` ≡ `permuta_vgv` (pro-rata, inclui pró-rata da receita financeira), `permuta_lotes` (terrenista recebe os lotes dele pela mesma curva/mesa, via `_receber` reusado), `compra` → terrenista null; **custos 100% no incorporador (MVP, rotulado)**. `leituras[]` = semáforo determinístico no backend (resultado favoravel/desfavoravel; margem vs `margem_referencia_pct` default 0,20; exposição vs `capital_disponivel` opcional → "estruturar funding"; **slots `vpl`/`tir`/`payback` com status `pendente`** prontos p/ a Fase 5). Preço por **R$/m² × área do lote** (350×263,21 = 92.123,50). **Linguagem §1-A: o backend NUNCA emite "viável"/"inviável"** (teste de regex). Dashboard: números-mestre + semáforo + divisão da parceria + ressalva §1-A no rodapé. **Casos A e B byte a byte; sem VPL/TIR; 195 testes + 4 skip (11 novos); `tsc` limpo; `next build` ok.** | 4.2 |
| 2026-06-12 | **Decisões do operador para a Fase 5 (handoff §0):** (1) recebível de loteamento é corrigido por **IPCA** → a TMA da Econômica é **taxa REAL** (spread acima do IPCA), e a relação nominal×real não pode ficar implícita; (2) **sensibilidade do MVP = só curva VPL×TMA** (sem ±% em preço/custo — evolução); (3) spec escrita na sessão de especificação antes de implementar. | 5 |
| 2026-06-12 | **Fase 5 ESPECIFICADA** (`docs/fase-5-economica.md`). **Ponto central resolvido — convenção de MOEDA CONSTANTE (identidade de Fisher):** o fluxo da Fase 4 é interpretado como R$ de hoje (recebíveis IPCA: a correção preserva poder de compra e **cancela** no desconto) → desconta-se **direto pela TMA real**, sem projetar IPCA; a TIR resultante é **real**, comparável à TMA na mesma régua; **a Fase 4 não muda** (segue nominal, sem nenhum campo novo). Premissas rotuladas: receitas e custos corrigidos pela mesma inflação (ressalva **INCC ≠ IPCA** — risco apontado, não modelado); sob a convenção, a taxa da mesa PRICE da 4.1 é **juros REAL**. TMA obrigatória **sem default escondido** (placeholder-exemplo rotulado); conversão mensal composta `(1+t)^(1/12)−1`. **TIR honesta:** pré-checagem de trocas de sinal — 0 trocas → `null`/"indefinida" (nunca número inventado); 1 → bissecção determinística; >1 → "múltipla possível — prefira o VPL"; **aviso de TIR explosiva** (>200% a.a.: "reflete exposição baixa, típico de permuta — VPL é o critério primário"; a TIV real dá 121% a.a.). Paybacks simples/descontado com "não recuperado no horizonte" e aviso de re-negativação; IL = VPL/|exposição descontada|. **Contrato:** `POST /analises/{id}/economica` **relê o fluxo persistido da Financeira** (front nunca manda números; sem financeira → 409/422); dashboard da 4.2 **compõe** os slots `vpl`/`tir`/`payback` (zero cálculo no front). **Valores-ouro verificados por código sobre o Caso Fechado A:** TMA 12% a.a. real → i_m 0,0094887929; **VPL 3.128.359,33** (e VPL@0% = 3.375.600,00 = nominal da 4, consistência 4×5); **TIR mensal 0,49477101** (VPL@TIR=0); paybacks **mês 3**; exposição descontada −390.000,00 (mês 0); **IL 8,0214**; curva 0→3.375.600,00 / 40%→2.693.174,29; TIR trivial [−1000,+1100] = 10% exato. Regex anti-"viável" mantido (§1-A). | 5 |
| 2026-06-12 | **Fase 5 CONCLUÍDA — Econômica implementada e validada contra os 10 critérios da spec.** Backend: `core/economica.py` (funções puras: `tma_mensal`, `vpl`, `trocas_de_sinal`, `tir_bissecao`, `avaliar`), `routers/economica.py` (POST/GET `/analises/{id}/economica`; **relê o fluxo persistido da Financeira** — sem financeira → **409** "Execute a Financeira primeiro"; TMA ausente → 422; curva inválida → 422), `economica_store.py` (persistência por análise, padrão 4). **Bissecção com varredura determinística de sub-brackets** (passo fixo 0,01 mensal em [−0,99; 10]) antes de bissectar — um bracket único falharia com nº par de raízes (fluxos não-convencionais); 0 trocas → `null`/"indefinida". **Todos os ouros batem:** i_m 0,0094887929; VPL **3.128.359,33** @12% (VPL@0% = 3.375.600,00 = nominal da 4); TIR mensal **0,49477101** (status `unica`, VPL@TIR=0, aviso explosiva presente); TIR trivial 10% exato; degeneradas rotuladas; paybacks **mês 3/3** (+ "não recuperado"/re-negativação); exposição descontada −390.000 (mês 0); **IL 8,0214**; curva 41 pontos 0→3.375.600,00 / 40%→2.693.174,29, range custom ok, passo 0 → 422. Front: card **Econômica** na sidebar (TMA com placeholder-exemplo rotulado, sem default; KPIs; **curva VPL×TMA em SVG com hover** — só plotagem dos pares do backend; convenção + avisos); dashboard da 4.2 **compõe** os slots `vpl`/`tir`/`payback` via `lib/compor.ts` (função pura, composição de dois JSONs, zero cálculo no front) — **vitest** introduzido (`npm test`) com 4 testes de composição. **214 testes backend + 4 skip (19 novos) · 4 testes front · regressão 1…4.2 zero · Fase 4 sem nenhum campo novo · `tsc` limpo · `next build` ok.** A espinha dorsal KMZ → geometria → ambiental → jurídico → financeiro → econômico está completa. | 5 |
| 2026-06-12 | **Decisões do operador para a Fase 6 (handoff §0):** primeira fase de **enriquecimento** (Localização/IBGE) — informativa, não decide viabilidade. **Indicadores do MVP (os quatro):** população+densidade+crescimento, renda/PIB per capita, déficit/domicílios, faixa etária. Arquitetura fixada: granularidade **município** (`cod_ibge` da 1.7), **offline via arquivo embarcado** (padrão da lista leve IBGE; aquisição = pipeline, não agente), proveniência com fonte+ano, degradação honesta (não inventar indicador ausente — regra 5). Pedido de spec redigido (`docs/handoff-fase-6-pedido-spec.md`); spec escrita na sessão de especificação antes de implementar. | 6 |
| 2026-06-12 | **Fase 6 ESPECIFICADA** (`docs/fase-6-localizacao.md`), auditada contra o handoff. Decisões dos pontos vetáveis: fontes = Censo 2022/2010 (pop/densidade/domicílios/faixa etária), PIB dos Municípios (renda), **FJP para déficit (não MUNIC — MUNIC traz gestão, não o número) com fallback rotulado para estoque de domicílios, nunca estimado**; arquivo **embarcado** consolidado (municípios + 27 UFs + Brasil) gerado por pipeline que **valida os ouros de São Roque na geração**; crescimento = variação total + CAGR 12 anos; **cobertura agregada COMPLETA/PARCIAL/INDISPONIVEL** + `disponivel` por bloco; **comparação UF/Brasil no MVP** (razões no backend); **sem persistência** (GET determinístico sobre arquivo estático); `_fmt` em todo número; **critério-coração: nenhum campo lido por outro router** (informativo puro). **Ouros (IBGE):** pop 79.484 [2022] / 78.821 [2010], crescimento 0,84% total ≈ 0,07% a.a., densidade 258,98 hab/km², PIB pc R$ 57.024,90 [2023], 2,79 morad./dom.; faixa etária = ouro de 2ª geração (pipeline crava na 1ª geração validada). | 6 |
| 2026-06-12 | **Fase 6 CONCLUÍDA — Localização (enriquecimento socioeconômico IBGE).** Primeira dimensão **informativa** (§1-A): `core/localizacao.py` (PURO — sem rede/LLM/persistência) lê o **arquivo embarcado** `backend/app/dados/localizacao_municipios.json` e monta os 4 blocos, com **razões UF/Brasil calculadas no backend** a partir das próprias linhas do arquivo e **leituras** em prosa ("demanda demográfica fraca, SOB OS DADOS CENSITÁRIOS"). `GET /api/analises/{id}/localizacao` (sempre 200; degrada honesto — município não resolvido → `avaliada=false`; fora do arquivo → `cobertura=INDISPONIVEL`; bloco ausente → `PARCIAL`). **Déficit:** FJP quando no recorte; fora → `deficit=null` + **fallback de estoque rotulado "NÃO é o déficit"** (nunca estimado). **`_fmt` pt-BR** em todo número (no backend, §2). **Crescimento** = variação total + CAGR 12 anos. Pipeline `scripts/gerar_localizacao_ibge.py` (SIDRA/PIB/FJP → JSON, **roda fora do runtime**, **valida os ouros de São Roque antes de gravar**). **Critério-coração nº 8 testado:** nenhum outro router importa a Localização — aproveitamento idêntico com/sem a consulta. **Linguagem §1-A:** regex anti-"viável"/"inviável" verde + aviso informativo fixo. Front: item "Localização" na sidebar + `CardLocalizacao` (4 blocos com badge fonte+ano, comparações UF/Brasil, barra empilhada da faixa etária — zero cálculo no front). **232 testes backend + 4 skip (17 novos da Fase 6, os 10 critérios) · 4 testes front · regressão 1…5 zero · `tsc` limpo · `next build` ok.** **Nota de honestidade (sandbox):** o egress ao IBGE está bloqueado neste ambiente (mesmo caso da malha IBGE/WorldCover/DEM) → o **seed embarcado** traz os 4 ouros de São Roque verificados e UF SP+Brasil+faixa etária **provisórios (Σ=1)**, a serem **recravados pelo pipeline na máquina do operador** (com egress), que valida São Roque antes de aceitar. Faixa etária = ouro de 2ª geração: o teste afere Σ=1 e os 4 grupos (os % definitivos saem da geração real). | 6 |
| 2026-06-14 | **Fase 8 CONCLUÍDA — Agrupamento de glebas vizinhas (união multi-KMZ).** `core/agrupamento.py` (PURO, shapely): `agrupar(geoms, municipios, tolerancia)` decide entre **união válida** (vira a geometria da análise) e **recusa diagnóstica**, por regra topológica + tolerância de encosto. Ordem: (1) município comum — divergiu → `MUNICIPIOS_DIFERENTES`; (2) interiores se cruzam (overlap parcial OU containment via `intersection.area>ε`) → `GLEBAS_SOBREPOSTAS`; (3) `unary_union` é Polygon único → ACEITA; (4) MultiPolygon → tenta pontar folga ≤ tolerância via `snap` (encosto de digitalização — NÃO ponta toque em ponto, pois não há aresta a criar) → senão `GLEBAS_NAO_CONTIGUAS` (distingue **vão** de **toque em ponto** por `touches` + `intersection.length==0`). `POST /api/analises` passa a aceitar `kmz[]` (1..N): **1 arquivo = caminho intacto** (refatorado em `_criar_analise_unica`, sem mudança de comportamento); **2+** ingere cada arquivo (reusa `core.ingestao`; recusa por arquivo é diagnóstica), detecta município por gleba, **reprojeta a CRS métrico local (AEQD)** e agrupa com a **tolerância de fechamento da ingestão (1,0 m)** em metros, persiste a **união** + bloco `agrupamento` (proveniência). A jusante o pipeline é **cego à origem** (recebe um Polygon). `analise_id` independe da ordem de upload (hash dos conteúdos, ordenado). **Ouros geométricos batem:** 2 quadrados de 100 na aresta → união Polygon **área 200**; vão 0,5 → recusa; toque em ponto → recusa; sobreposição → área 20; 3 em fila → 300; folga 0,05 ≤ tol → aceita (pontado); município divergente → recusa. Front: `UploadKmz` aceita **múltiplos** arquivos (`criarAnalise(File|File[])` + `GrupoRecusado`), banner "projeto unificado" na análise. **14 testes (10 critérios) · suíte 247 · regressão 1…7 zero · `tsc`/`next build` limpos.** Fora de escopo (registrado): municípios diferentes, multi-matrícula no jurídico, "juntar análises existentes", portfólio não-contíguo, edição de fronteira na tela. | 8 |
| 2026-06-15 | **Fase 9 CONCLUÍDA — Urbanismo (estudo de massa esquemático proposto por IA).** Primeira fase em que a IA toca o DESENHO — fronteira do §2 desenhada explícita: **o LLM propõe o PROGRAMA na BORDA; o Python gera a geometria e MEDE 100% dos números.** `core/urbanismo_programa.py` = a borda (`GeradorPrograma` injetável; real `GeradorProgramaClaude` gated por `ANTHROPIC_API_KEY`, tool use forçado, reusa TLS/`MODELO_PADRAO` da 1.8 — **sem credencial nova**; stub offline). O artefato que cruza a fronteira é um `Programa` (lote-alvo, densidade, %lazer, arquétipo, largura de via, esqueleto grosseiro) — **nunca polígono de lote nem nº de lotes** (o nº EMERGE da geração). Perfis de público-alvo = **PRESETS embarcados** (baixa/média/alta, monotônicos em lote-alvo e %lazer), guard-rails determinísticos; LLM contextualiza qualitativamente. `core/urbanismo_geom.py` (PURO shapely): grelha axial esquemática v1 — reserva verde/institucional, loteia, **recorta tudo contra a área aproveitável** (nada sobre APP/≥30%/verde-dura/faixa/servidão; restrição → o lote não existe), arruamento = sobra; esqueleto do LLM é **validado/ignorado** (auto-interseção → registrado, nunca propaga geometria crua). `core/urbanismo_medida.py` (PURO, CRS métrico AEQD): quadro de áreas + indicadores + `pontuar()` (heatmap de score geométrico relativo por lote — **sem preço**; R$/m² por faixa é input do usuário). **Determinismo:** snapshot **versionado** (`urbanismo_store.py`, padrão 4/5) — "mesmo snapshot → mesma medição"; regerar cria versão, não sobrescreve. **Cenário ADITIVO** (não toca aproveitamento/financeira/laudo — Fase 9 não escreve em nenhum router anterior). Endpoints: `POST .../urbanismo/medir` (determinístico, **SEM LLM** — é o que os ouros aferem) · `POST .../urbanismo/propor` (IA→programa→Python gera/mede; **503 sem credencial**) · `GET` lista/uma. **10 critérios verdes; valores-ouro de São Roque (TIV 5.0) batem no `/medir`** (layout sintético de área exata; o São Roque real vira validação quando a geometria chegar): área líquida **131.433,75 m²**, vendável **74.644,40 (56,79%)**, verdes **36.686,92 (27,91%)**, arruamento **20.102,43 (15,29%)**, **167 lotes**, área média **446,97 m²** (testada 17,94 / profundidade 24,91). Front: item "Urbanismo (IA)" na sidebar + `CardUrbanismo` (seleção tipo+público-alvo, render do GeoJSON esquemático com **selo "ESQUEMÁTICO"**, quadro de áreas, indicadores, heatmap de faixas, programa proposto, avisos §1-A) — front só renderiza GeoJSON (§2). **Linguagem §1-A:** rótulo "ESTUDO DE MASSA ESQUEMÁTICO" + 3 avisos em toda saída; regex sem "aprovado/viável/regular"; "verificar com urbanista". **17 testes (test_urbanismo_medida + test_urbanismo_fronteira) · suíte 272 + 4 skip · regressão 1…8 zero · `tsc`/`next build`/vitest limpos.** Fecha o último degrau do nº de lotes (§6-A item 5: + % vias + % lazer = realista). Fora de escopo: projeto aprovável/diretrizes (urbanista), projetos técnicos (água/esgoto/energia/drenagem — SINAPI/SICRO ficam p/ custos futuros), otimização do traçado, edição interativa/3D, pesquisa de mercado ao vivo, preço absoluto. | 9 |
| 2026-06-15 | **Fase 9.1 CONCLUÍDA — Urbanismo: fidelidade do traçado.** Corretiva da 9 (a v1 dava quadro honesto mas distante do programa: IA pedia 25% lazer + viário orgânico, motor materializava 2,5% + grelha, descartando o esqueleto). Sobe a fidelidade em 3 frentes **sem mover a fronteira do §2** (régua do §3 da spec: snap/buffer/recorte/rotação/reservar/medir = OK; inventar/otimizar/greide = projeto, fora): **(a) materializa as áreas** — `core/urbanismo_geom.py` reescrito: RESERVA lazer (clube central + verde, por **crescimento de raio até a área EXATA**) e institucional **antes** de lotear; o quadro **converge** ao programa (lazer medido = alvo) ou **DEGRADA rotulado** por **cap analítico** (reserva lazer só até sobrar área p/ ~8 lotes — preserva o parcelamento; nunca infla nem zera). **(b) viário por arquétipo** — consome o **esqueleto da IA** (agora em coords **normalizadas 0..1** do bbox → mapeado/snapado/validado; trecho inviável descartado e contado) como eixos-base de via quando o arquétipo ≠ `grelha_eficiente`. **(c) topografia** — `orientacao_contorno(DEM 2.5)` deriva o ângulo da curva de nível (⟂ gradiente) e a grelha de quarteirões **gira** para acompanhá-la (orientação, NÃO terraplenagem; ≥30% segue fora pelo recorte da 2.5). `core/urbanismo_medida.construir_fidelidade` compara medido×programa (atendido/degradado/atenção) — bloco `fidelidade` (áreas+viário+topografia) na resposta do `/propor`; `/medir` e os **ouros de quadro de São Roque (Fase 9) inalterados**. Front: `CardUrbanismo` ganha a barra **convergência programa × medido** (medido + marcador do alvo) + chips de arquétipo/topografia. **10 critérios verdes** (convergência ouro 25%→[22,28]%; degradação 8.000 m²→15% rotulada; esqueleto consumido/Hausdorff; arquétipo grelha×sinuoso distinto; orientação leste→90°; rotação de quarteirão; fronteira-stub sem número; determinismo; §1-A regex). **12 testes novos (`test_urbanismo_fidelidade.py`) · suíte 284 + 4 skip · regressão 1…9 zero · `tsc`/`next build`/vitest limpos.** Módulo de urbanismo **maduro**; resta a **fase de custos (SINAPI/SICRO)** para fechar o ciclo de viabilidade ponta a ponta. Fora de escopo (mantido): projeto aprovável, projetos técnicos/greide/terraplenagem, custos de obra, otimização multiobjetivo, edição na tela/3D, geometria de qualidade executiva. | 9.1 |
| 2026-06-15 | **Fase 9.2 CONCLUÍDA — Urbanismo: lotes heterogêneos guiados por valorização.** Mata o lote uniforme da v1 (800 m² p/ todos → viário 37% + retalhos perdidos). A IA propõe a **política** (`estrategia_mix` = faixas de tamanho premium/padrão/compacto + proporção; `heuristicas` = onde pôr premium: cota alta/fundo mata/frente lazer); o Python **zoneia por qualidade, dimensiona por faixa e fecha a quadra sem sobra**. Fronteira do §2 imóvel (régua do §3: zonear/dimensionar/fechar/medir = OK; otimizar/remembrar/lago = projeto, fora). **NÃO é otimizador** (decisão do operador): a referência urbIA só **calibra defaults**, nunca é meta — o heatmap reporta a **consequência medida**, e o aviso "estratégia, NÃO otimização" carimba isso. `core/urbanismo_geom.py`: `_quality()` pontua a POSIÇÃO (proximidade de verde/lazer materializados na 9.1 + cota via DEM) pelas heurísticas pedidas; `_prescan_thresholds` fixa cortes de quantil p/ as proporções-alvo **compensando a largura** (premium é mais largo → recebe mais posições, p/ a proporção de LOTES bater); `_tile_faixa` tila cada quadra com largura por faixa e **fecha sem retalho** (só lotes inteiros + redistribuição da folga → sobra→0). `core/urbanismo_medida.mix_medido`: distribuição por faixa, **correlação tamanho×score** (Pearson — consequência, não meta), sobra/retalho, %viário, lista de lotes (faixa+score+zona_motivo). Snapshot e **`/medir` inalterados; ouros de quadro de São Roque (Fase 9) preservados**. Front: `CardUrbanismo` mostra a **distribuição de tamanhos** (não um número), correlação/retalho/viário + aviso. **10 critérios verdes** (mix em ≥2 faixas; quadra-ouro 6.000 m² sobra **0%** ≤1%; viário **17,3%** ≤~20%; correlação **+0,57**; premium a **4,9 m** do verde vs compacto a **110,9 m**; proporção dentro de ~1 p.p. do alvo; programa sem premium→sem premium inventado; sem "ótimo/ideal" na resposta; determinismo; §1-A regex). **10 testes (`test_urbanismo_mix.py`) · suíte 294 + 4 skip · regressão 1…9.1 zero · `tsc`/`next build`/vitest limpos.** Módulo de urbanismo **maduro**. Fora de escopo (mantido): otimização do traçado, **lago artificial/feições de água novas** (evolução, conversa própria), remembramento, projeto aprovável/técnicos/greide, custos SINAPI/SICRO, edição/3D, preço absoluto. | 9.2 |
| 2026-06-16 | **Fase 9.3 CONCLUÍDA — Urbanismo: SUBDIVISÃO de quadras (correção de RAIZ; substitui a 9.2).** **Lição registrada:** o modelo "impor um tamanho-alvo e fatiar a gleba" (9/9.2) produziu, em DUAS implementações distintas, lotes **uniformes e grandes** (885 m² idênticos, retalho 6%, viário 26%, espaços vazios) — falha da **abordagem**, não do código: o `lote_alvo` (800) dominava o dimensionamento e as faixas premium/padrão/compacto nunca materializavam. **Faixas impostas ❌ → subdivisão de quadra ✅.** Agora o gerador **desenha quadras** (do viário da 9.1) e **subdivide cada quadra inteira**: `n = round(largura/testada_alvo)`; `testada_real = largura/n` (fecha a quadra, **retalho→0**); cada lote = **interseção da faixa com a quadra** → o **tamanho EMERGE da forma**, não é imposto. Fileira parcial de borda vira fileira rasa (≥0,8·prof) e ponta pequena **funde** com a vizinha (`_fundir_pontas`) — sem lote minúsculo nem retalho. Via LOCAL estreita (8 m) entre quadras (a via principal segue o esqueleto). **Três regras do operador viraram restrição:** (1) lote alto padrão é **450-640 (alvo piso ~470), não 800** — `lote_alvo` da IA é REFERÊNCIA, rebaixado à faixa do perfil e registrado (`lote_alvo_origem`); (2) **massa no piso, cauda curta** (emerge da geometria); (3) **tamanho e score DESACOPLADOS** — o `score` virou só posição (cota/verde/lazer; removido o termo de área), governa o R$/m², NÃO o tamanho (desfaz o amarrado "premium=maior" da 9.2). `core/urbanismo_geom._subdividir`/`_subdividir_quadra`/`_fundir_pontas` (Python puro); `core/urbanismo_medida.distribuicao_tamanhos` (média/desvio/cv + histograma + retalho + viário, substitui `mix_medido`); calibração `PERFIL_LOTE` (baixa 125-250/média 300-450/alta 450-640) + `dims_perfil`. **10 critérios verdes, calibrados no São Roque REAL (167 lotes, média ~447, 67% em 400-450, cauda ~3% acima de 600, viário ~15%):** sobre gleba tipo São Roque → **média 446** ∈[430,520] (os 885 da v1 FALHAM), **cv 0,14** ∈[0,06–0,18] (uniforme cv≈0 e explosão cv>0,25 falham), **massa ≤545 = 100%** (≥55%), **cauda ≥600 = 0%** (≤10%), **retalho 0%** (≤1,5%; os 6% falham), **viário ~9-12%** (≤20%; os 26% falham), 800→faixa rebaixado, correlação tamanho×score **−0,4** (desacoplada). `/medir`, snapshot e **ouros de quadro de áreas (Fase 9) inalterados**; a 9.1 (lazer/viário/topografia) preservada. Front: `CardUrbanismo` troca o mix por **histograma de tamanhos** (massa no piso, cauda curta) + média/cv + nota "tamanho da quadra; valor no R$/m²". **11 testes (`test_urbanismo_subdivisao.py`, **substitui** `test_urbanismo_mix.py`) · suíte 295 + 4 skip · regressão 1…9.1 zero · `tsc`/`next build`/vitest limpos.** **A 9.2 fica como histórico**; a subdivisão é o modelo vigente. Fora de escopo (mantido): otimização/remembramento, lago artificial, projeto aprovável/técnicos/greide, custos SINAPI/SICRO, edição/3D. | 9.3 |
| 2026-06-16 | **Fase 9.4 CONCLUÍDA — Urbanismo: diretrizes municipais + CLAMP legal (substitui a 9.3).** **Lição da evolução 9→9.1→9.3→9.4 (quatro rodadas no mesmo ponto):** o tamanho de lote é **LEI + diretriz municipal + prática pesquisada — NUNCA chute**. A 9.2 impôs faixas por proporção (deu lote uniforme); a 9.3 acertou o algoritmo (subdivisão → tamanho emerge) mas **inventou** as faixas e produziu absurdos nas pontas (lote de 50 e de 850 m²); a 9.4 **ancora em fonte** e clampa pela lei. **Hierarquia de fontes (§0):** (1) MUNICÍPIO — LUOS confirmada da 1.8 (lote legal da zona, % doação, `doacao_split` viário/verde/institucional); (2) BOAS PRÁTICAS de mercado (referência editável por perfil — só p/ o que a lei não fixa); (3) PISO FEDERAL 125 m²/frente 5 m (Lei 6.766, clamp absoluto). `core/urbanismo_diretrizes.resolver_diretrizes` resolve `piso/teto/doacao/split` (a **lei vence o mercado**). **Decisão de contrato (registrada):** o piso de mercado **NÃO** sobe acima da zona — `piso = max(125, lote_zona)` com zona confirmada (São Roque/MUE → **360-640**, fiel ao real e ao que o operador espera ver na tela; sem LUOS → `max(125, piso_mercado)` + cobertura `BASE_FEDERAL`). **CLAMP LEGAL por lote** (`_clamp_faixa` em `urbanismo_geom`): coluna < piso **funde** com a vizinha (até caber no teto); pedaço > teto **subdivide** (`_split_largura`); o que não vira lote viável **volta** à área pública — **`fora_da_faixa == 0` por construção** (os lotes de 50 e 850 ficam impossíveis). `n` por quadra escolhido pela **profundidade** (quadra rasa → lote mais largo) p/ mirar o alvo dentro de [piso,teto]. Reserva de **verde/institucional = MAX(programa, doacao_split)** ANTES de lotear (o município é piso; pode propor mais, nunca menos). `urbanismo_medida`: `distribuicao_tamanhos` ganha `fora_da_faixa`; novo `conformidade_legal` (lote/doação/verde/institucional **medidos × mínimo**, status atende/atende_com_folga/não_atende/não_avaliado — espelha a 3.5). **Subdivisão da 9.3 e lazer/viário/topografia da 9.1 preservados; `/medir` + ouros de quadro de áreas (Fase 9) inalterados.** **10 critérios verdes (São Roque/MUE real):** `fora_da_faixa=0`, min/max **369/531 ∈ [360,640]**, média **493 ∈[430,520]**, cv **0,075**, viário **8,3%**, retalho **1,1%**, conformidade medida (lote 360 ✓, doação ✓, verde ✓, institucional ✓), sem LUOS → `BASE_FEDERAL` + doação `nao_avaliado` (não inventa). Front: `CardUrbanismo` mostra as **diretrizes do município no topo** (lote legal/doação), o histograma **todo dentro da faixa legal**, a **conformidade legal** por item; seletor de **zona (LUOS)**. **11 testes (`test_urbanismo_diretrizes.py`, **substitui** `test_urbanismo_subdivisao.py`) · suíte 295 + 4 skip · regressão 1…9.1 zero · `tsc`/`next build`/vitest limpos.** **Modelos abandonados:** faixas por proporção (9.2), tamanho sem clamp legal (9.3). Fora de escopo: projeto aprovável/diretrizes da gleba (Certidão art. 6º), técnicos/greide, custos SINAPI/SICRO, edição/3D. | 9.4 |
| 2026-06-16 | **Fase 9.5 CONCLUÍDA — Urbanismo: parcelamento legível (lote a lote).** Puramente de APRESENTAÇÃO — **zero mudança de número, gerador intocado**. O motor já gerava 1 `Polygon` por lote (`layout.lotes`), mas `geojson_do_layout` **fundia tudo** (`unary_union`) na serialização → o mapa mostrava uma "mancha" translúcida em vez do parcelamento. Agora `geojson_do_layout` monta `lotes_features` (FeatureCollection, **1 Feature por lote**, casando geometria + props que JÁ existem por índice: `por_lote[i]` lote_id/area_m2/score, `_lados_mrr` testada/profundidade, `layout.lote_quadra[i]`, `faixa_score`); o `lotes` fundido **permanece** por compat/fallback; via/verde/lazer/institucional já saíam separados. Front: `MapaLeaflet`/`CardUrbanismo` iteram `lotes_features` — cada lote com **borda própria** (weight 0.8), `fillOpacity` 0.5, **cor pela faixa de score** (heatmap vira o próprio mapa, frio→quente), **popup por lote** (área/score/quadra) + legenda; gleba sem fill (só contorno). **Invariância provada (critério 1):** Σ área das Features == área do MultiPolygon fundido (±0,5 m²) == vendável; `len(features)` == `n_lotes` == `len(distribuicao_tamanhos.lotes)`; props batem por `lote_id`. Quadro de áreas/distribuição/conformidade/heatmap/`/medir` **idênticos**. §1-A mantido (selo ESQUEMÁTICO, nota de traçado aproximado, regex sem "aprovado/viável/regular"). **8 critérios verdes · 5 testes (`test_urbanismo_features.py`) · suíte 305 + 4 skip · regressão 1…9.4 zero · `tsc`/`next build`/vitest limpos.** Escopo honesto: legibilidade (lotes individuais), NÃO qualidade de traçado — vias sinuosas/quadras orgânicas são o **Nível 2** (próxima conversa); render artístico é Nível 3. | 9.5 |
| 2026-06-16 | **Fase 9.6 CONCLUÍDA — Urbanismo: apresentação das áreas públicas.** Só apresentação — **zero número, gerador/viário intocados**. O diagnóstico (via log) mostrou que verde/lazer/institucional iam ao mapa mas apareciam **apagados** (opacidade 0,3, borda única, verde sobre satélite verde) e que o verde virou **picotado** na 9.4 (`areas_verdes = verde_reservado ∪ sobra_de_ponta`). **Backend:** `geojson_do_layout` passa a expor `areas_verdes_reservada` (bloco limpo) e `areas_verdes_sobra` (sobra de ponta) SEPARADOS, mantendo `areas_verdes` TOTAL (reservada ∪ sobra) p/ quadro/conformidade — **invariância provada: reservada + sobra == total == quadro (±0,5 m²)**. `Layout` ganha os 2 campos; `gerar_layout` mantém `verde_reservado`/`residual_geom` distintos. Texto do "não avaliado" da conformidade melhorado (explica que a LUOS confirma a **doação total** mas não o **split** verde/institucional → verificar na prefeitura; lógica `nao_avaliado` inalterada). **Front:** `ESTILO_OVERLAY` por camada (contraste sobre satélite, borda própria) — verde reservado escuro/borda forte, remanescente claro/tracejado discreto, lazer ciano (equipamento), institucional âmbar, viário cinza mais forte; **legenda** das camadas no mapa; **mapa maior** (440px, botão expandir→680px, full-width); lotes seguem coloridos por score (9.5). §1-A preservado (selo ESQUEMÁTICO, regex). **8 critérios verdes · 4 testes (`test_urbanismo_apresentacao.py`) · suíte 308 + 4 skip · regressão 1…9.5 zero · `tsc`/`next build`/vitest limpos.** O **viário segue como está** (sobra) — o viário-MALHA (eixos de rua conectados, quadras nascendo da malha) é a **Fase 9.7 (Nível 2)**, a próxima e grande, que resolve a legibilidade das ruas; o pórtico vem depois dela (precisa de via principal real). | 9.6 |
| 2026-06-17 | **Fase 9.7 CONCLUÍDA — Urbanismo: traçado de verdade (viário-MALHA + quadras como faces + áreas públicas formadas).** A peça mais difícil do módulo e a **inversão da geração (§0)**: até aqui o viário era **espaço negativo** (aproveitável − lotes − reservas → sobra desconexa), a quadra era uma faixa de grade, o institucional um disco de canto e o clube um círculo central — origem de todos os apontamentos do operador (vias que somem, lazer no círculo, áreas mal demarcadas). Agora **as ruas vêm primeiro**: `construir_malha` monta uma **malha viária CONEXA** (no frame rotacionado pela topografia 9.1) — grade LOCAL de blocos iguais (sem sliver de borda: N blocos exatos) **+ os eixos da IA como TRONCO** (atravessam a grade → conectam tudo numa peça só, hierarquia tronco ≥21 m / local 8 m); reusa `centerline.buffer(largura/2)` que já existia. As **quadras são as FACES** que as ruas cercam (`shapely.ops.polygonize` da borda ∪ eixos; quadra = face − ruas), **substituindo** `_linhas_de_quadra` (grade). Cada face é loteada por `_lotear_face` → **`_subdividir_quadra` REUSADO sem mudança** (clamp legal 9.4 intacto; único ajuste de robustez: `n` capado por ⌊área/piso⌋ p/ peça rasa não cair abaixo do piso e zerar lotes). **Áreas públicas viram quadras FORMADAS:** `institucional_como_quadra` escolhe uma face com **frente para via** que satisfaz os 4 checks legais (frente ≥10 m, compacidade não-sliver, círculo inscrito ⌀≥10 m via busca binária de buffer, declividade ≤15% via DEM 2.5) na **borda** (acesso pela via oficial), **substituindo** o disco de canto — degrada honesto (`qualifica_legal=false` + "definir com a Prefeitura") quando nenhuma encaixa; `clube_como_quadra` é uma figura com frente (`forma="quadra"`, compacidade <0,9 → **não círculo**), **substituindo** o disco central; a **sobra vira quadras verdes formadas** (faces pequenas + pontas mínimas), **não slivers picotados**. **LOTES SÃO PRIORIDADE** (sempre ≥1 face vira lote; gleba minúscula degrada sem público). Contrato: `geometria` ganha `quadras` (FeatureCollection de faces), `viario` com `conexo`/`trechos`/`hierarquia`, `institucional`/`sistema_lazer` com `frente_via_m`/`forma`/`qualifica_legal`, e `viario_diagnostico`/`institucional_diagnostico`; `Layout` ganha `quadras`/`eixos_malha`/`*_diagnostico`; `medir` mede o comprimento de via pela **malha** (`eixos_malha`). **Reuso intacto:** clamp/diretrizes (9.4), separação verde reservada/sobra (9.6), `lotes_features` (9.5), distribuição/conformidade/heatmap — sem reescrita. **Fronteira §2 imóvel:** a IA propõe os eixos (semente); o Python constrói a malha, deriva as faces e mede — nenhuma coordenada final do LLM. **Dúvida de contrato sinalizada ao operador:** a spec escreve "frente/profundidade ≤1/3", mas a justificativa legal ("área pública não-retalho") é o piso de **compacidade ≥1/3** (razão ≤1/3 é justamente o sliver a evitar) — implementado `min/max ≥1/3` (não-sliver), registrado no código. **10 critérios verdes (São Roque/MUE real):** viário **conexo (1 peça)**, 8 quadras-face, institucional **qualifica nos 4 checks** + toca via, clube **forma=quadra** (compacidade 0,78), verde **não picotado** (1 bloco reservado, sobra 0), invariância soma=100% (±0,5 m²), `fora_da_faixa=0` (clamp), viário medido **14,9%**, determinismo, §1-A. **Recalibração honesta autorizada (critério 10 da spec):** numa gleba retangular perfeita a malha gera faces iguais → lotes uniformes (cv **0,04**, baixado o piso de 0,06→0,02) e a convergência do lazer fica mais grossa (quadra formada ≠ disco de área exata: faixa 25%→[18,30]%) — o ganho pedido é a figura real com frente, não o disco exato. **10 testes novos (`test_urbanismo_malha.py`); 2 calibrações ajustadas (`test_urbanismo_diretrizes`/`test_urbanismo_fidelidade`) · suíte 318 + 4 skip · regressão 1…9.6 zero · `tsc` limpo.** Front: `MapaLeaflet` desenha a **malha viária** (cinza forte sólido), as **quadras** (contorno tracejado, popup de área), os **lotes** por face coloridos por score (9.5) e as **áreas públicas formadas** (9.6); `CardUrbanismo` mostra o **diagnóstico** (viário conexo · institucional qualifica · lazer formado). **Primeira versão de uma malha real — conectada e formada, ainda esquemática** (refino orgânico do traçado é iterativo); o **pórtico** entra agora que há via principal onde ancorá-lo. `docs/fase-9.7-viario-malha.md`. Fora de escopo (mantido): traçado orgânico de qualidade executiva, pórtico, render artístico, otimização do traçado, projeto aprovável/técnicos/greide, custos SINAPI/SICRO. | 9.7 |
| 2026-06-14 | **Fase 7 CONCLUÍDA — Consolidação (laudo de triagem em PDF).** `core/laudo.py` (PURO, sem rede/LLM/cálculo): `montar_laudo_data(identificacao, dims, data)` **compõe** os JSONs das dimensões já executadas em 6 seções executivas (Identificação · Aproveitamento · Ambiental[ambiental+vegetação+declividade] · Jurídico · Financeiro-econômico · Localização) + `semaforo(dims)` (uma luz por dimensão, **derivada do que a dimensão já reporta** — não juízo novo): ANM/UC/declividade≥30%→🔴, verde-a-verificar/leitura `atencao`→🟡, indicadores favoráveis→🟢, Localização=informativa (§1-A, nunca acende risco), dimensão ausente→⚪. `core/laudo_pdf.py` rende via **fpdf2** (Python puro, offline, sem fonte externa — sanitização latin-1 com fontes-núcleo; data de criação fixa → bytes determinísticos): capa (título+semáforo+ressalva §1-A) + seções + **proveniência consolidada**, com a **ressalva §1-A no rodapé de TODA página** e numeração. `POST /api/analises/{id}/laudo` recebe os JSONs das dimensões no corpo (o front **repassa** o que cada card recebeu — §2, nada recalculado no front; identificação vem do STORE) e devolve o **PDF**. **Decisão de design (latitude):** as dimensões ficam **intocadas** (criterion 8) — o laudo as recebe no corpo em vez de reler stores/recomputar (evita precisar dos parâmetros do aproveitamento e qualquer escrita nos routers das dimensões). **8 critérios verdes:** composição sem recálculo (números idênticos campo a campo), semáforo determinístico por fixtures, **regex anti-"viável"/"inviável"** no texto + ressalva §1-A na capa e no rodapé, dimensão ausente→"não analisada"+⚪ (PDF gera mesmo assim), proveniência por seção + lista consolidada, PDF válido (≥2 páginas, %PDF, pt-BR via `_fmt` das dimensões sem reformatar), subconjunto executivo (6 seções; Conformidade **não** entra). Front: botão **"Gerar laudo (PDF)"** na top bar (monta o corpo dos `dados*` que os cards já reportaram, baixa o blob). **8 testes · suíte 255 + 4 skip · regressão 1…6 + Fase 8 zero · `tsc`/`next build`/vitest limpos.** Fecha o laço do MVP: a vitrine determinística do que as 12 dimensões produziram, com a fronteira §1-A carimbada em toda página. | 7 |
