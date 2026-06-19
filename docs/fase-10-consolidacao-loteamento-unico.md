# Fase 10 — Consolidação de dados + verde honesto + LOTEAMENTO ÚNICO (IA propõe o traçado de conexão)

> **Spec única e completa, em 4 partes implementáveis em sequência.** Resolve, de uma vez e
> ancorado no `catalogo-praticas-urbanismo.md`, os três problemas reais que ficaram:
> **(P1)** as abas se contradizem — três definições de "área líquida" convivendo, "verde" com dois
> significados; **(P2)** o "verde" esconde sobra geométrica disfarçada de área verde; **(P3)** o
> loteamento aparece **partido em duas porções**, e isso é **inaceitável** — loteamento real é
> **único e conectado**. A medição sobre o DEM bruto provou que a "barreira ≥30%" entre as porções
> **não existe**: é artefato de um recorte binário num grid de 30 m sobre um vão de 22 m
> (sub-pixel); o relevo real no contato é **~20% com desnível de poucos metros** — via normal
> atravessa. **A conexão é obrigatória.** Para o traçado de conexão (julgamento espacial), a
> **IA propõe o eixo** e o **Python materializa, mede o greide real e mede as áreas** — refinamento
> do §2 (a IA projeta o traçado; nunca mede). Referencia `ARCHITECTURE.md` (§1-A, §2), o catálogo,
> e as Fases 9.7–9.14.

## 0. Princípios desta fase

- **Loteamento é UM só.** Duas porções desconexas é produto inferior, não existe no mundo real
  (§8 do catálogo: o valor do alto padrão está na unidade — uma portaria, um clube, circulação
  interna). Só se descarta a área se for **comprovadamente impossível** conectar — e **não é o
  caso** (DEM real: contato ~20%, greide de travessia 0–16%, mais favorável ~0%).
- **§2 refinado (o ponto central):** a fronteira nunca foi "IA não toca traçado" — foi "IA não
  **mede**". Decidir **por onde** conectar (achar o ponto de sela suave, contornar a encosta ≥30%
  real, articular os dois lados) é **julgamento espacial → IA**. **Medir** o greide real, verificar
  legalidade e medir áreas é **determinístico → Python**. Nenhum número sai da IA.
- **§1-A:** triagem. O greide exato da travessia depende de **levantamento topográfico de campo**
  (o DEM público de 30 m não resolve vão de 22 m) — a ferramenta **propõe a conexão e alerta**,
  não entrega projeto geométrico. Selo "ESQUEMÁTICO"; "verificar com urbanista/topógrafo".

---

## PARTE 1 — Fonte canônica de área (acaba com as 3 definições divergentes)

**Problema medido (Claude Code):** três funções calculam "área líquida" subtraindo coisas
diferentes — `vegetacao.py:analisar_vegetacao` (gleba − vegetação = 7,26 ha), `aproveitavel.py:
consolidar` (uma terceira), `urbanismo_medida.py:medir` (gleba − vegetação − declividade − APP =
~5,89 ha). Nenhuma lê da outra. Daí "uma aba diz uma coisa, outra diz outra".

**Solução — uma fonte de verdade (a Taxonomia Canônica, §10 do catálogo):**
```
core/areas_canonicas.py  (NOVO — fonte única)
  computar_areas_canonicas(gleba, vegetacao, declividade, app) -> AreasCanonicas:
    gleba_bruta_m2
    restricoes_fisicas = { vegetacao_m2, declividade_30_m2, app_m2 }  (não sobrepor: union)
    area_liquida_aproveitavel_m2 = gleba_bruta − union(restricoes_fisicas)
    # ESTE é o único "líquida/aproveitável" do produto.
```
- **Todas as abas LEEM desta função.** Ambiental, Aproveitamento e Urbanismo param de recalcular.
- A aba **Ambiental** para de chamar "gleba − só vegetação" de "líquida". Ou mostra a líquida
  canônica, ou rotula explicitamente o seu número como **"parcial — só vegetação descontada"**
  (não "área líquida", para não colidir com a canônica).
- **Invariante:** o mesmo conceito (gleba, vegetação, declividade, líquida) exibe **o mesmo número
  em qualquer aba**. Divergência entre abas vira **falha de teste**.

**Critérios P1:** (1) existe `areas_canonicas` como fonte única; (2) as 3 abas leem dela (nenhuma
recalcula "líquida" por conta própria); (3) o número de "área líquida aproveitável" é **idêntico**
em Ambiental, Aproveitamento e Urbanismo; (4) a aba Ambiental não usa mais a palavra "líquida"
para "gleba − só vegetação" (renomeia para "parcial"); (5) teste de coerência inter-abas passa.

---

## PARTE 2 — Verde desmembrado (acaba com a sobra disfarçada de área verde)

**Problema medido:** a linha "Áreas verdes" soma **verde-reserva (7.672 m²)** + **verde-sobra
(5.997 m²)** — quase metade é sobra geométrica (faces que não viraram lote). O código **já
distingue** (`urbanismo_geom.py` L1224-1231: `verde_reserva_m2`, `verde_sobra_m2`), mas o quadro
**funde** na exibição. É problema de **exposição**, não de cálculo.

**Solução — expor as categorias canônicas separadas no quadro de áreas:**
```
QUADRO DE ÁREAS (sobre a área líquida aproveitável canônica):
  Vendável (lotes)
  Sistema viário (vias + calçadas)
  Área verde de doação/reserva   ← verde_reserva_m2 (legítimo: lei + programa)
  Sistema de lazer               ← já separado
  Institucional                  ← já separado
  Sobra geométrica  ⚠️           ← verde_sobra_m2 (NÃO é "área verde"; é sobra a minimizar)
  [Mata preservada]              ← se exposta: vegetação (restrição física, vem da Parte 1)
```
- A **sobra** ganha **linha própria, rotulada como sobra** (não "área verde"), com tooltip:
  "faces sem aproveitamento — meta é reduzir". Deixa de inflar o "verde".
- O "verde" que o usuário vê passa a ser **só verde de verdade** (reserva/doação + lazer).
- Conecta com a Parte 1: a **mata** (vegetação) é restrição física (sai antes da líquida), não se
  confunde com a área verde do parcelamento. O usuário nunca mais vê "33% verde" sem saber a
  decomposição.

**Critérios P2:** (1) o quadro mostra `verde_reserva` e `verde_sobra` em **linhas separadas**;
(2) a sobra é rotulada como sobra (não "área verde"); (3) a soma das linhas fecha 100% da líquida
canônica; (4) "área verde" exibida = só reserva/doação (+lazer em sua linha), nunca incluindo
sobra; (5) em São Roque, os números batem com o medido (reserva ~7.672, sobra ~5.997) até a
Parte 3 mudar o aproveitamento.

---

## PARTE 3 — Loteamento ÚNICO: corrigir a barreira-fantasma + IA propõe a travessia

**Problema medido (a causa-raiz):** o motor trata a área aproveitável como **recorte binário
≥30% num grid de 30 m**. Um vão de **22 m (sub-pixel)** entre as porções A e B virou "barreira
contínua de 530 m". Mas o **DEM bruto no contato mostra ~20% (0 de 6 pixels ≥30%), desnível
mediano 2,5 m, greide de travessia 0–16% (mais favorável ~0% em ~(−36,−23))**. **Não há parede.**
As encostas ≥30% reais existem no resto da gleba (153/726 px, máx 58%) — mas **não no vão A↔B**.

### 3.1 — Corrigir a separação-fantasma (determinístico)
```
ANTES de declarar porções "separadas":
  reavaliar o contato contra o RELEVO REAL, não o recorte binário grosseiro.
  para cada par de porções "separadas" pelo recorte:
    medir a declividade REAL na zona de contato (sobre o DEM, não o binário):
      - se o contato tem declividade < 30% (como A↔B: ~20%)  -> NÃO estão separadas:
        a "barreira" é artefato sub-pixel -> tratar como CONECTÁVEL (vai p/ 3.2).
      - se o contato é genuinamente ≥30% por toda a frente -> aí sim separadas
        (só então considerar inviável — e mesmo assim ver 3.3).
```
Isso mata a barreira-fantasma na raiz: a separação passa a depender do **relevo**, não de um
limiar binário sobre um grid mais grosso que o vão.

### 3.2 — IA propõe o eixo da travessia; Python materializa e mede (§2 refinado)
```
[IA — BORDA, julgamento espacial] propõe, junto com o programa de traçado:
  - o PONTO DE TRAVESSIA entre as porções (onde cruzar: o ponto de sela mais suave,
    o vão mais estreito, evitando a encosta ≥30% genuína do resto da gleba);
  - o EIXO da via-tronco coletora que LIGA A↔B passando por esse ponto;
  - como os dois lados se articulam (a tronco costura tudo — catálogo §9).
  Texto + eixo normalizado. NENHUM número, NENHUMA medida.

[Python — NÚMERO, determinístico] materializa e valida:
  - constrói a via sobre o eixo (caixa coletora ~14 m — catálogo §2.2);
  - MEDE o greide REAL da travessia sobre o DEM (desnível / extensão);
  - VERIFICA: greide ≤ ~12% -> via normal; 12–15% -> alerta "greide acentuado";
    > 15% -> NÃO materializa como via (seria escadaria/ponte) e tenta outro ponto
    proposto; se nenhum ponto serve, marca a porção como dependente de solução de
    engenharia (raro — não é o caso de São Roque);
  - UNE as porções + via de conexão -> mede que o loteamento é UMA peça;
  - mede TODAS as áreas (Parte 1/2). Nenhum número da IA.
```
**Resultado em São Roque:** a tronco cruza o ponto favorável (~22 m, greide ~0–11%), une A e B,
e o loteamento vira **único e conectado**. As faces antes órfãs da porção isolada ganham acesso
→ viram lote (a sobra-verde cai, o vendável sobe — agora **legitimamente**, porque a conexão é
real, não forçada).

### 3.3 — Descarte só se comprovadamente impossível (§1-A)
Se — e só se — **nenhum** ponto de travessia proposto pela IA medir greide viável (todo o contato
genuinamente ≥30%, sem sela), a ferramenta **não inventa** dois núcleos: alerta que a área pode
exigir solução de engenharia (corte/contenção/ponte) **ou** ser inviável para loteamento único —
e remete ao urbanista. **Nunca** entrega "dois loteamentos". (Não é o caso de São Roque.)

### 3.4 — Alerta de método (honestidade, §1-A)
A via de conexão é **diretriz de traçado de triagem**, não projeto. O greide exato depende de
**levantamento topográfico de campo** (DEM público de 30 m não resolve vão de 22 m). A ferramenta
exibe: "conexão proposta pelo ponto mais favorável medido; greide definitivo exige topografia."

**Critérios P3:** (1) a separação entre porções é decidida pelo **relevo real** (declividade no
contato), não pelo recorte binário — teste: A↔B de São Roque (contato ~20%) é classificado
**conectável**; (2) a **IA propõe** o ponto/eixo de travessia (consta no `proposto_llm`); (3) o
**Python mede** o greide real da travessia sobre o DEM e só materializa se ≤15% (senão tenta outro
ponto); (4) em São Roque o loteamento resultante é **UMA peça conectada** (`loteamento_conexo ==
true`), não dois núcleos; (5) faces antes órfãs viram lote → vendável sobe e verde-sobra cai vs o
estado partido; (6) nenhum número vem da IA (greide e áreas medidos pelo Python); (7) o alerta de
levantamento topográfico aparece; (8) se forçada uma gleba genuinamente ≥30% no contato, NÃO gera
dois núcleos (alerta de engenharia/descarte) — nunca "dois loteamentos".

---

## PARTE 4 — Elementos de alto padrão que faltam (do catálogo §8) — sobre o loteamento já conectado

Com o loteamento único (Parte 3), aplicar os elementos premium que o catálogo trouxe e faltavam:
- **Pórtico de entrada + portaria** na entrada **única** do loteamento (não duas) — catálogo §8.
- **Institucional/serviços perto da entrada** (setorização: entrada concentra serviço) — §8/§6.
- **Lotes premium** longe da entrada, voltados para mata/cota alta/vista — §8 (já no programa IA).
- **Arborização viária** na faixa de serviço da calçada (≥0,70 m) — §3/§8 (rótulo/“tag”, não muda
  área de lote).
- **Cul-de-sacs de bulbo** nos fundos de exclusividade — já em 9.14, mantidos.

**Critérios P4:** (1) **uma** portaria/pórtico, na entrada do loteamento conectado (não duas);
(2) institucional posicionado com acesso pela via, próximo à entrada; (3) elementos premium
exibidos como tags do estudo (sem violar §1-A: ilustração não define número/área); (4) não-
regressão das Partes 1-3.

---

## Contrato de API (consolidado)

```jsonc
"areas_canonicas": {                     // PARTE 1 — fonte única
  "gleba_bruta_m2": 78134,
  "restricoes_fisicas": { "vegetacao_m2": 5520, "declividade_30_m2": 13713, "app_m2": 0 },
  "area_liquida_aproveitavel_m2": 58900 },// o ÚNICO "líquida"
"quadro_areas": {                        // PARTE 2 — verde desmembrado
  "vendavel_m2": ..., "viario_m2": ...,
  "verde_reserva_m2": 7672, "verde_sobra_m2": 5997,   // SEPARADOS
  "lazer_m2": 5172, "institucional_m2": 2425,
  "mata_preservada_m2": 5520 },
"conexao": {                             // PARTE 3 — loteamento único
  "loteamento_conexo": true,
  "porcoes_detectadas": 2, "porcoes_conectadas": 2,
  "travessia": { "proposta_por": "llm", "ponto": [-36,-23],
                 "greide_medido_pct": 11, "caixa_via_m": 14,
                 "alerta_topografia": true },
  "barreira_reavaliada_contra_relevo": true },
"alto_padrao": { "porticos": 1, "institucional_na_entrada": true }  // PARTE 4
```
Coerência inter-abas: qualquer aba que exiba gleba/vegetação/declividade/líquida usa
`areas_canonicas` — **mesmo número em todo lugar**.

## Critérios de aceite globais

1. **Coerência inter-abas (P1):** "área líquida aproveitável" idêntica em Ambiental, Aproveitamento
   e Urbanismo; nenhuma recalcula; teste de coerência verde.
2. **Verde honesto (P2):** reserva e sobra em linhas separadas; sobra rotulada como sobra; "verde"
   exibido nunca inclui sobra; soma fecha 100% da líquida canônica.
3. **Loteamento único (P3):** São Roque conecta A↔B (contato ~20% → conectável); resultado é UMA
   peça; IA propõe a travessia, Python mede o greide real (≤15%) e as áreas; faces órfãs viram
   lote (vendável sobe, sobra cai); zero número vindo da IA; alerta de topografia presente.
4. **Sem dois núcleos (P3):** nunca gera "dois loteamentos"; se contato genuíno ≥30%, alerta de
   engenharia/descarte (não é o caso de São Roque).
5. **Alto padrão (P4):** uma portaria/pórtico; institucional na entrada; tags premium sem violar
   §1-A.
6. **§2 refinado:** a IA propõe o eixo de conexão (julgamento espacial); o Python materializa,
   mede greide e áreas, verifica legalidade. Nenhuma medida vem da IA.
7. **§1-A:** selo "ESQUEMÁTICO"; "verificar com urbanista/topógrafo"; regex sem "aprovado/viável/
   regular"; a via de conexão é diretriz de traçado, não projeto.
8. **Não-regressão:** subdivisão (9.4/9.11), filtro frente-via (9.12/9.13), clamp (9.4),
   reconciliação (9.10), cul-de-sacs/contorno úteis (9.14) — preservados.

## Ordem de implementação (entrega incremental — testar no navegador entre cada)

1. **Parte 1** (fonte canônica) → testar: o mesmo número de "área líquida" nas três abas.
2. **Parte 2** (verde desmembrado) → testar: quadro mostra reserva/sobra/lazer separados.
3. **Parte 3** (loteamento único) → testar: São Roque vira UMA peça conectada, sobra-verde cai.
4. **Parte 4** (alto padrão) → testar: uma portaria, institucional na entrada.

> **A questão central, resolvida:** o loteamento de São Roque é **UM só**. A "barreira ≥30%" entre
> as porções era **artefato de recorte binário** sobre um DEM grosso — o relevo real no vão é ~20%
> com desnível de poucos metros, e uma via normal o atravessa. A **IA propõe** por onde conectar
> (julgamento espacial); o **Python materializa, mede o greide real e mede as áreas** (§2 refinado:
> a IA projeta o traçado, nunca mede). Em paralelo, as abas passam a ler **uma fonte canônica** de
> área (fim das contradições) e o **verde é desmembrado** (fim da sobra disfarçada). Tudo ancorado
> no catálogo de práticas, com alerta honesto de que o greide definitivo exige topografia (§1-A).
