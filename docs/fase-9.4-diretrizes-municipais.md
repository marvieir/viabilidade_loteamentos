# Fase 9.4 — Urbanismo: diretrizes municipais primeiro + clamp legal + boas práticas (ancorado em fonte)

> **Substitui a 9.3.** A 9.3 acertou o algoritmo (subdivisão de quadra → tamanho emerge da
> geometria) mas gerou absurdos nas pontas (lote de 50 m², lote de 850 m²) e inventou áreas
> verdes/doação sem olhar a exigência do município. A causa-raiz das três rodadas anteriores foi
> **eu (spec) chutar faixas de tamanho** em vez de ancorar em fonte. Esta fase corrige isso: o
> dimensionamento parte das **diretrizes do município** (LUOS da 1.8) e do **piso legal federal**
> (Lei 6.766), com **boas práticas pesquisadas** só para o que a lei não fixa. Referencia
> `ARCHITECTURE.md` (§1-A, §2, §5, §7) e as Fases 9/9.1/9.3. **IA propõe o programa; Python
> subdivide, clampa e mede.**

## 0. Hierarquia de fontes (a lição: lei primeiro, mercado depois, nada de chute)

O tamanho do lote, a doação e as áreas públicas obedecem a **três camadas, nesta ordem**:

```
1. MUNICÍPIO (piso inegociável) — LUOS da Fase 1.8, se confirmada:
     • lote legal mínimo da zona  • % de doação obrigatória  • doacao_split (viário/verde/institucional)
2. BOAS PRÁTICAS DE MERCADO (referência editável, rotulada) — só p/ o que a lei NÃO fixa:
     • tamanho-alvo dentro da faixa do perfil  • profundidade/testada típicas  • mix
3. PISO LEGAL FEDERAL (clamp absoluto, vale p/ TODOS) — Lei 6.766/79:
     • lote ≥ 125 m²  • frente ≥ 5 m
```
**O programa da IA nunca propõe menos que o município exige.** Pode propor *mais* (ex.: alto
padrão com mais área verde), nunca *menos*. Sem LUOS confirmada → degrada para piso federal +
boas práticas e **rotula** ("diretriz municipal não confirmada — verificar doação/lote/verde com
a prefeitura"), no padrão de cobertura `BASE_FEDERAL`/`COMPLETA` do produto.

## 1. Parâmetros ancorados em FONTE (não mais chutados)

| Parâmetro | Valor | Fonte |
|---|---|---|
| **Lote mínimo absoluto** | **125 m²**, frente **5 m** | Lei 6.766/79 (clamp federal) |
| Lote mínimo da zona | o que a LUOS diz (ex.: São Roque MUE 360 m²) | **Fase 1.8** (precede o mercado) |
| Doação obrigatória | % da gleba conforme município (gleba > 20.000 m² obriga; típico 35% incl. viário) | LUOS 1.8 / Lei 9.785 / quadros municipais |
| **Quadra — extensão máxima** | **200 m** | Leis de parcelamento (RJ/SP típicas) |
| Profundidade de lote | faixa prática **25–35 m** | prática consagrada (corredor de quadra dupla 50–70 m) |
| Testada residencial | mín. legal 5 m; prática **10–15 m** | Lei 6.766 + prática |
| **Via local** | faixa **≥ 12–14 m** (leito + 2 passeios ≥ 5 m cada lado) | leis municipais / GRAPROHAB |
| Via coletora | **≥ 21 m** | leis estaduais/municipais |
| **Remate de ponta** | até **2 lotes por série** com testada/área **−15%** no máx. | Lei parcelamento (remate) |
| Viário insuficiente | se < mínimo, **diferença vai p/ verde/institucional** | Decreto 57.558/16 (SP) e equivalentes |

**Faixas de mercado por perfil (referência editável — camada 2, rotulada "verificar com
urbanista"):**

| Perfil | Faixa de lote (m²) | Testada-alvo | Profundidade |
|---|---|---|---|
| baixo padrão | 125–250 | ~10 m | ~25 m |
| médio padrão | 300–450 | ~12 m | ~28 m |
| alto padrão | 450–640 | ~15 m | ~31 m |

> Estas faixas são **referência de mercado pesquisada**, **subordinadas** ao lote legal da zona
> (camada 1) e ao piso federal (camada 3). Se a zona exige 360 m² e o perfil é "médio" (300–450),
> o piso efetivo é **360** (o maior). **A lei sempre vence o mercado.**

## 2. O que NÃO muda (não-regressão)

- **Fronteira do §2 imóvel:** IA propõe **programa**; Python subdivide, **clampa** e mede.
  Nenhum tamanho/coordenada/score vem do LLM.
- **Subdivisão de quadra da 9.3 preservada** (é o motor certo do tamanho) — ganha o **clamp
  legal** e a **ancoragem nas diretrizes**. Lazer/viário/topografia da 9.1 preservados.
- `/medir` e snapshot versionado intactos; ouros de **quadro de áreas** de São Roque permanecem.
- Cenário aditivo. Fases 1–8 byte a byte. Suítes 1…9.1 verdes. Testes da 9.3 que tratavam o
  tamanho **sem clamp** são **substituídos** pelos desta fase.

## 3. O algoritmo (subdivisão da 9.3 + clamp + diretrizes)

```
0. DIRETRIZES (precedem tudo):
   piso_lote   = max(125, lote_legal_zona_1.8, piso_mercado_perfil)   ← a lei vence
   teto_lote   = teto_mercado_perfil (ex.: alto 640)
   doacao_min  = % da LUOS (1.8) ou default municipal; doacao_split idem
1. RESERVAR áreas públicas conforme doacao_min/split (verde + institucional) ANTES de lotear
   (9.1) — medido CONTRA o mínimo do município, não inventado
2. viário (9.1: arquétipo + topografia) recorta o restante em QUADRAS (extensão ≤ 200 m)
3. para CADA quadra:
   a. testada_alvo do perfil; profundidade = a da quadra (25–35 m típico)
   b. n = round(largura_quadra / testada_alvo); testada_real = largura / n (fecha sem retalho)
   c. cada lote = interseção faixa×quadra → ÁREA EMERGE da quadra
   d. CLAMP por lote: área < piso_lote OU > teto_lote → tratar (passo 4)
4. REMATE da ponta (regra legal, não invenção):
   • fatia < piso_lote → FUNDE com o vizinho (ou, se série permite, até 2 lotes −15% ≥ piso)
   • pedaço > teto_lote → SUBDIVIDE em dois (nunca um lote gigante)
   • o que não vira lote viável → devolve a área verde/institucional (não retalho)
5. MEDIR: distribuição de tamanhos (toda dentro de [piso,teto]), área média, viário, vendável;
   CONFORMIDADE: doação/verde/institucional/lote medidos × mínimos do município (atende/não atende)
6. score por posição → heatmap → R$/m² por faixa (input). Tamanho e valor DESACOPLADOS (9.3).
```

**O `lote_alvo_m2` da IA continua REFERÊNCIA, não comando** (9.3) — e agora é **subordinado às
diretrizes**: se a IA propõe 800 mas a zona é 360 e o perfil alto teto 640, o alvo efetivo fica
na faixa legal/mercado e o **clamp garante que nada saia de [piso, 640]**. Os lotes de 50 e 850
da tela **tornam-se impossíveis por construção**.

## 4. Contrato de API

`PropostaUrbanisticaOut` (9/9.1/9.3) ganha o bloco de **diretrizes** e **conformidade legal**:
```jsonc
"diretrizes": {
  "fonte": "LUOS confirmada (1.8) — São Roque/MUE" | "BASE_FEDERAL (diretriz não confirmada)",
  "lote_min_zona_m2": 360, "piso_lote_efetivo_m2": 360, "teto_lote_m2": 640,
  "doacao_min_pct": 0.20, "doacao_split": { "viario": 0.10, "verde": 0.06, "institucional": 0.04 },
  "aviso": "Mínimos do município são PISO; o estudo pode propor mais, nunca menos. Verificar na prefeitura." },
"distribuicao_tamanhos": {
  "media_m2": 451, "min_m2": 362, "max_m2": 638,   // SEMPRE dentro de [piso_efetivo, teto]
  "fora_da_faixa": 0,                               // clamp garante 0
  "faixas": [ /* histograma */ ], "retalho_perdido_pct": 0.006, "viario_pct": 0.15 },
"conformidade_legal": [
  { "item": "lote_minimo", "exigido_m2": 360, "medido_min_m2": 362, "status": "atende" },
  { "item": "doacao", "exigido_pct": 0.20, "medido_pct": 0.21, "status": "atende" },
  { "item": "area_verde", "exigido_pct": 0.06, "medido_pct": 0.15, "status": "atende_com_folga" },
  { "item": "institucional", "exigido_pct": 0.04, "medido_pct": 0.05, "status": "atende" } ],
"avisos": [ /* … 9/9.1/9.3 … */,
  "Dimensionamento ancorado em: diretrizes do município (LUOS/1.8) + piso legal 125 m² (Lei 6.766) + boas práticas de mercado (referência). Nenhum lote fora da faixa legal.",
  "Mínimos de doação/área verde/institucional MEDIDOS contra a exigência do município — verificar na prefeitura (art. 6º Lei 6.766)." ]
```
`/medir` inalterado.

## 5. Critérios de aceite (ancorados em FONTE — São Roque real + diretrizes da zona MUE)

1. **Clamp legal inviolável:** **nenhum lote < 125 m²** em nenhum perfil (o lote de 50 m² da
   tela **falha**); nenhum lote < lote legal da zona quando a 1.8 confirma (MUE 360 →
   `min_m2 ≥ 360`); nenhum lote > teto do perfil (o de 850 **falha**). `fora_da_faixa == 0`.
2. **Diretriz do município é piso:** com LUOS MUE (360 m², doação 20%), o estudo gera lotes
   `≥ 360` e doação `≥ 20%`; propor menos é **rejeitado**. Sem LUOS → piso 125 + rótulo
   `BASE_FEDERAL`.
3. **Remate da ponta (regra legal):** quadra com ponta estreita → a fatia residual **funde** ou
   vira ≤ 2 lotes com −15% **≥ piso**, **nunca** um lote de 50; pedaço largo → **subdivide**,
   nunca um lote de 850. Teste geométrico nas pontas.
4. **Reserva antes de lotear + conformidade:** verde/institucional reservados conforme o
   `doacao_split` da 1.8 **antes** dos lotes; `conformidade_legal` mede cada item × exigência e
   marca atende/não atende (como a 3.5).
5. **Subdivisão preservada (9.3):** tamanho **emerge** da quadra (lotes diferentes entre si),
   média na faixa, cv contido, retalho ≤ 1,5%, viário ≤ ~20% — calibrado no São Roque real
   (média ~447, viário ~15%).
6. **Mercado é só referência, subordinado à lei:** se zona (360) > piso de mercado do perfil
   médio (300), o piso efetivo é **360**; teste confirma `piso_lote_efetivo = max(...)`.
7. **Tamanho × valor desacoplado (9.3):** posição → score → R$/m²; tamanho → quadra. Score não
   determina tamanho.
8. **Fronteira §2 + §1-A:** stub fornece programa; nenhum tamanho vem do stub; rótulo "ESTUDO DE
   MASSA ESQUEMÁTICO" + "verificar com urbanista"; regex sem "aprovado/viável/regular".
9. **Degradação honesta:** sem LUOS → `BASE_FEDERAL` + piso 125 + rótulo; doação não calculável
   → pede/rotula, não inventa.
10. **Não-regressão:** `/medir` e ouros de quadro de áreas (Fase 9) inalterados; 9.1/9.3
    (subdivisão) preservadas no que vale; fases 1–8 byte a byte; suítes 1…9.1 verdes.

> **Proveniência dos parâmetros (auditável):** lote 125 m²/frente 5 m = Lei 6.766; quadra ≤ 200 m,
> via local ≥ 12–14 m, coletora ≥ 21 m, remate −15% = leis de parcelamento; lote da zona e doação
> = LUOS via Fase 1.8; faixas de mercado por perfil = referência pesquisada (rotulada). **Nenhum
> número inventado pela spec.**

## 6. Fora de escopo (registrado)

- **Projeto aprovável / diretrizes específicas da gleba** (Certidão de Diretrizes, art. 6º Lei
  6.766) — do urbanista/prefeitura; o tool faz triagem contra os mínimos gerais.
- **Otimização do traçado, lago artificial, técnicos (água/esgoto/energia/drenagem),
  terraplenagem, custos (SINAPI/SICRO), edição interativa/3D/render** — mantidos fora.
- **Faixas de tamanho impostas por proporção** (9.2) e **tamanho sem clamp legal** (9.3) —
  abandonados.

## 7. Arquivos esperados (latitude de implementação)

- `core/urbanismo_diretrizes.py` — resolve `piso_lote`/`teto_lote`/`doacao_min`/`split` da
  hierarquia (1.8 → mercado → federal); **Python puro**. Reusa o perfil da 1.8 (e `_param_zona`).
- `core/urbanismo_geom.py` — subdivisão da 9.3 + **clamp por lote** + **remate de ponta** (regra
  legal) + reserva de áreas públicas conforme split.
- `core/urbanismo_medida.py` — `distribuicao_tamanhos` (com `fora_da_faixa`), `conformidade_legal`
  (medido × exigência), `score()` por posição.
- `models/schemas.py` — `DiretrizesOut`, `ConformidadeLegalOut`, distribuição com clamp.
- `routers/urbanismo.py` — resposta com `diretrizes` + `conformidade_legal`; `/medir` inalterado.
- Frontend: `CardUrbanismo` mostra as **diretrizes do município** (piso de lote/doação/verde) no
  topo, a distribuição **toda dentro da faixa legal**, a conformidade (atende/não atende por
  item), o heatmap por posição; selo ESQUEMÁTICO e §1-A. Front só renderiza.
- Testes: `tests/test_urbanismo_diretrizes.py` (clamp legal, piso da zona, remate, conformidade,
  degradação — calibrados no São Roque real + zona MUE, offline). **Substitui** os testes de
  tamanho da 9.3.

A spec fixa **contrato + critérios + ALGORITMO + FONTES**. **A IA propõe o programa; o Python
subdivide a quadra, clampa pela lei (município → federal) e mede contra os mínimos legais** — o
lote de 50 e o de 850 ficam impossíveis por construção, o dimensionamento sai da diretriz real da
gleba (não de chute), e o urbanista segue insubstituível (§1-A).
