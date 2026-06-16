# Fase 9.3 — Urbanismo: subdivisão de quadras (lote = o que a quadra comporta)

> **Correção de RAIZ** do gerador de lotes. As Fases 9/9.2 produziram lotes **uniformes e
> grandes** (885 m² idênticos, retalhos perdidos) porque o algoritmo era "impor um tamanho-alvo
> e fatiar a gleba". Em duas implementações distintas o mesmo erro reapareceu — sinal de que a
> falha era da **abordagem**, não do código. Esta fase troca o algoritmo: o gerador passa a
> **desenhar quadras e subdividir cada quadra inteira**, deixando o tamanho do lote ser o que a
> quadra comporta. Calibrada contra o **loteamento real do São Roque** (167 lotes, distribuição
> de tamanhos conhecida). Referencia `ARCHITECTURE.md` (§1-A, §2, §7) e as Fases 9/9.1.
> **IA propõe o programa; Python subdivide e mede.**

## 0. Por que esta fase existe (lição registrada)

A 9.2 especificou *o quê* (3 faixas de tamanho, fechar quadra) sem cravar *como* o tamanho de
cada lote nasce da geometria — e deixou o `lote_alvo_m2` (800) **dominar** o dimensionamento.
Resultado: lotes uniformes de 800-885, faixas padrão/compacto **nunca materializaram**, retalho
de 6%. **Falha da spec, não da implementação.** A 9.3 fecha o algoritmo e ancora em dado real.

**Três regras de negócio do operador (que reescrevem o modelo):**
1. **Lote alto padrão é ~450-640, não 800.** Faixas por perfil: baixo 125-250, médio 300-450,
   **alto 450-640**. O `lote_alvo_m2` de 800 estava fora da realidade.
2. **A maioria fica perto do PISO da faixa; lote grande é exceção.** Cobra-se por m² → lote
   grande encarece o tíquete e estreita o público. O urbanista **mantém o tamanho contido** e
   valoriza pelo **R$/m²**; quem quer maior **compra dois lotes lado a lado**. Logo a
   distribuição real é **apertada em torno do piso** (São Roque: 67% em 400-450), com cauda
   curtíssima (3% acima de 600).
3. **Tamanho e valor DESACOPLADOS.** Posição premium (cota alta, fundo de mata, frente lazer)
   **não aumenta o tamanho** — alimenta só o **score**, que governa o **R$/m²** (input do
   usuário). A **geometria da quadra** governa o tamanho. Isto desfaz o amarrado da 9.2 (onde
   premium = maior) — e é o que elimina o bug.

## 1. Objetivo

Gerar lotes por **subdivisão de quadra**: o gerador desenha as quadras (miolos cercados por
via) e subdivide cada uma inteira em lotes de **testada-alvo** derivada do perfil; o **tamanho
de cada lote é o que a quadra comporta** (varia naturalmente pela forma da quadra, sem sobra),
mirando o piso da faixa. Resultado fiel ao real: **média na faixa do perfil, variação contida,
sem retalho perdido, sem lote gigante**.

## 2. O que NÃO muda (não-regressão)

- **Fronteira do §2 imóvel:** a IA propõe **programa** (testada-alvo/faixa por perfil, arquétipo
  viário, esqueleto, % lazer, heurísticas de valor); o **Python desenha quadras, subdivide e
  mede**. Nenhum tamanho/coordenada/score vem do LLM.
- **`/medir` (sem LLM) e snapshot versionado** intactos; ouros de **quadro de áreas** de São
  Roque permanecem (a 9.3 muda *como os lotes nascem*, não a medição de áreas).
- Cenário aditivo (9 §8). Fases 1–8 byte a byte. Suítes 1…9.2 verdes (salvo os testes da 9.2
  que esta fase **substitui** — ver §6).
- A 9.1 (lazer materializado, viário por arquétipo, topografia) é **preservada**: a subdivisão
  acontece **dentro das quadras** que o viário da 9.1 já define.

## 3. O algoritmo (o núcleo — fechado, não mais latitude)

```
1. viário (9.1: esqueleto da IA + arquétipo + topografia) recorta a área aproveitável em QUADRAS
2. para CADA quadra (polígono fechado por vias):
   a. orienta a quadra pelo seu maior lado (frente para a via)
   b. testada_alvo = do perfil (alto ~15 m → ~450-500 m²; ajustável pela profundidade da quadra)
   c. n_lotes = round(largura_da_quadra / testada_alvo)
   d. testada_real = largura_da_quadra / n_lotes   ← FECHA a quadra exatamente (retalho → 0)
   e. fatia a quadra em n_lotes faixas de testada_real × profundidade-da-quadra
   f. cada lote = INTERSEÇÃO da faixa com a quadra → ÁREA É O QUE A QUADRA COMPORTA (varia)
3. lotes pequenos demais (< piso da faixa) na ponta → fundem com o vizinho (não viram retalho)
4. mede: distribuição de tamanhos, área média, testada/profundidade, viário, vendável
5. score por lote (posição: cota/verde/lazer/ruído) → heatmap → R$/m² por faixa de score (input)
```

**Por que isto gera a distribuição real (validado):** o tamanho **não é imposto** — emerge de
`testada_real × profundidade`, ambas ditadas pela **forma da quadra**. Quadras variam → tamanhos
variam pouco e naturalmente em torno do alvo (São Roque real: média 450, cv 12%; o algoritmo
reproduz: média ~444, cv ~9%). **Lote grande só aparece por sobra geométrica inevitável**
(ponta de quadra irregular que não dá para fundir), nunca por estratégia — fiel à regra "lote
grande é exceção".

**O `lote_alvo_m2` da IA vira REFERÊNCIA da faixa, não comando:** alimenta a `testada_alvo`
dentro dos limites do perfil; **não** força uma área única. Se a IA propuser 800 para alto
padrão, o Python **rebaixa para a faixa do perfil (450-640) e registra a divergência** — o
programa não atropela mais a geometria.

## 4. Calibração por perfil (referência do operador)

| Perfil | Faixa de lote (m²) | Alvo (piso) | Testada-alvo aprox. |
|---|---|---|---|
| baixo padrão | 125–250 | ~175 | ~8–10 m |
| médio padrão | 300–450 | ~340 | ~12 m |
| **alto padrão** | **450–640** | **~470** | **~15 m** |

Defaults rotulados *"referência de mercado — calibre com seu urbanista"*. A IA escolhe dentro da
faixa do perfil; o Python nunca sai dela.

## 5. Contrato de API

Sem endpoint novo. A subdivisão substitui o dimensionamento interno; a resposta
(`PropostaUrbanisticaOut`) troca o bloco de "faixas premium/padrão/compacto" (9.2) por
**distribuição de tamanhos**:
```jsonc
"programa": { /* … */ "testada_alvo_m": 15, "faixa_lote_m2": [450, 640],
              "lote_alvo_origem": "rebaixado_para_faixa: IA propôs 800; perfil alto = 450-640" },
"lotes": [ { "lote_id": "L001", "area_m2": 462.1, "testada_m": 15.2, "profundidade_m": 30.4,
             "score": 8.1, "quadra_id": "Q3" }, /* … */ ],   // tamanho MEDIDO, não imposto
"distribuicao_tamanhos": {
  "media_m2": 451, "desvio_m2": 48, "cv": 0.107, "min_m2": 392, "max_m2": 638,
  "faixas": [ { "de": 400, "ate": 450, "n": 41, "pct": 0.61 },
              { "de": 450, "ate": 500, "n": 18, "pct": 0.27 },
              { "de": 500, "ate": 640, "n": 8, "pct": 0.12 } ],
  "retalho_perdido_pct": 0.008, "viario_pct": 0.16 },
"heatmap": { /* score por posição — NÃO correlacionado a tamanho por construção */ },
"avisos": [ /* … 9/9.1 … */,
  "Tamanho do lote = o que a quadra comporta (subdivisão), mirando a faixa do perfil; lote grande é exceção geométrica. Quem quer maior junta dois lotes.",
  "Valor da posição vai para o R$/m² (seu input por faixa de score), não para o tamanho." ]
```
`/medir` inalterado.

## 6. Critérios de aceite (valores-ouro do São Roque REAL — calibração definitiva)

**Referência real (imagem Análise de Lotes, 167 lotes):** média **~447 m²**, **67% em 400-450**,
cauda **3% acima de 600**, **viário ~15%**, desvio ~54 m² (cv ~12%).

1. **Média no lugar certo (não 885):** num caso alto padrão sobre gleba tipo São Roque,
   `distribuicao_tamanhos.media_m2 ∈ [430, 520]` — a média de **885 da v1 FALHA** este critério.
2. **Variação CONTIDA (nem uniforme, nem explosão):** `cv ∈ [0.06, 0.18]` (desvio real ~12%).
   Uniforme (cv≈0, todos 885) **falha**; explosão 300-900 (cv>0.25) **falha**. Só a curva
   realista passa.
3. **Massa no piso da faixa:** **≥55% dos lotes na metade inferior da faixa** do perfil
   (alto: 450-545); cauda **≤10% acima de 600** — imita a concentração real.
4. **Retalho ~zero:** `retalho_perdido_pct ≤ 1.5%` (subdivisão fecha a quadra) — a v1 (6%)
   **falha**.
5. **Viário realista:** `viario_pct ≤ ~20%` (faixa plausível; São Roque real ~15%) — a v1 (26%)
   **falha**.
6. **`lote_alvo` rebaixado:** IA propondo 800 para alto padrão → Python gera na faixa 450-640 e
   `lote_alvo_origem` registra o rebaixamento; **nenhum lote uniforme de 800**.
7. **Tamanho × score DESACOPLADO:** a correlação tamanho×score **não é forçada** — o tamanho vem
   da quadra, o score da posição; teste verifica que o score reflete posição (cota/verde/lazer)
   e que lotes grandes **não** são sistematicamente os de score alto (desfaz o amarrado da 9.2).
8. **Subdivisão real (não tamanho imposto):** teste geométrico — numa quadra de forma irregular,
   os lotes têm **áreas diferentes entre si** (a forma gera variação), todos com testada ≈ alvo;
   ponta pequena **funde** com vizinho (não vira retalho nem lote minúsculo).
9. **Fronteira §2 + §1-A:** gerador-stub fornece programa; **nenhum tamanho vem do stub** —
   Python subdivide e mede. Rótulo "ESTUDO DE MASSA ESQUEMÁTICO" + "verificar com urbanista";
   regex sem "aprovado/viável/regular".
10. **Não-regressão:** `/medir` e ouros de **quadro de áreas** (Fase 9) inalterados; a 9.1
    (lazer/viário/topografia) preservada; fases 1–8 byte a byte; suítes 1…9.1 verdes.
    **Os testes da 9.2 (faixas premium/padrão/compacto com proporção) são SUBSTITUÍDOS** pelos
    desta fase — a 9.2 fica como histórico; a subdivisão é o modelo vigente.

> **Validação real:** quando houver a geometria dos lotes de um loteamento real, confere-se que
> a subdivisão reproduz a distribuição. Por ora, os ouros vêm da **distribuição medida do São
> Roque** (imagem Análise de Lotes) — caso real, não sintético.

## 7. Fora de escopo (registrado)

- **Otimização do traçado/lotes** (maximizar valor) — é o "quebrar a cabeça" do urbanista.
- **Lote grande sob demanda / remembramento automático** — no real, "quem quer maior junta dois
  lotes"; o tool não cria lotes fora do padrão (o comprador/urbanista funde depois).
- **Lago artificial, projeto aprovável, técnicos (água/esgoto/energia/drenagem), terraplenagem,
  custos (SINAPI/SICRO), edição interativa/3D/render** — mantidos fora (Fases 9/9.1).
- **Faixas premium/padrão/compacto com proporção imposta** (modelo da 9.2) — **abandonado**: era
  a fonte do bug; o tamanho agora emerge da quadra.

## 8. Arquivos esperados (latitude de implementação)

- `core/urbanismo_geom.py` — **reescrita do gerador de lotes**: desenha quadras (do viário 9.1) e
  `subdividir_quadra(quadra, testada_alvo, perfil)` → lotes por interseção (área emergente);
  fusão de ponta pequena; **Python puro**. Remove o caminho "impor lote_alvo único".
- `core/urbanismo_medida.py` — `distribuicao_tamanhos` (média, desvio, cv, faixas, retalho,
  viário); `score()` por posição (desacoplado de tamanho).
- `core/urbanismo_programa.py` — `lote_alvo`/`testada_alvo` calibrados por perfil (faixas do §4);
  rebaixamento registrado se a IA exceder a faixa.
- `models/schemas.py` — `DistribuicaoTamanhosOut`, `LoteOut` (área/testada/profundidade/quadra).
- `routers/urbanismo.py` — resposta troca faixas-de-mix por distribuição; `/medir` inalterado.
- Frontend: `CardUrbanismo` mostra a **distribuição de tamanhos** (histograma: massa no piso,
  cauda curta) e a média; heatmap por posição; nota "tamanho da quadra; valor no R$/m²"; selo
  ESQUEMÁTICO e §1-A. Front só renderiza.
- Testes: `tests/test_urbanismo_subdivisao.py` (média, cv, massa-no-piso, retalho, viário,
  rebaixamento, desacoplamento, subdivisão-de-quadra-irregular — calibrados no São Roque real,
  offline). **Substitui** `test_urbanismo_mix.py` (9.2).

A spec fixa **contrato + critérios + ALGORITMO** (desta vez sem latitude no núcleo). **A IA
propõe o programa; o Python desenha quadras e subdivide — o tamanho do lote é o que a quadra
comporta, mirando a faixa do perfil.** Fiel ao real, fronteira do §2 intacta, urbanista
insubstituível (§1-A).
