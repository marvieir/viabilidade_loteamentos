# Fase 5 — Econômica (avaliação do fluxo: VPL · TIR · payback · curva VPL×TMA)

> A Fase 4 **monta** o fluxo; a 5 **avalia**. Consome o `fluxo` mensal persistido da
> Financeira (4/4.1/4.2) e preenche os slots `vpl`/`tir`/`payback` que o dashboard já
> reservou. Referencia `ARCHITECTURE.md` (§1-A, §2) e respeita as decisões do operador
> (handoff §0): **TMA real em termos de IPCA** e **sensibilidade = só curva VPL×TMA**.
> **Matemática financeira pura: sem LLM, sem rede, sem credencial.**

## 1. Objetivo

Dado o fluxo de caixa mensal da análise e uma **TMA real declarada**, devolver:
**VPL** à TMA · **TIR** (mensal e anualizada, com tratamento honesto de degenerações) ·
**payback simples e descontado** · **exposição máxima descontada** · **índice de
lucratividade** · **curva VPL × TMA** — tudo com leituras §1-A ("cria/destrói valor **sob as
premissas declaradas**", nunca "viável").

## 2. O que NÃO muda (não-regressão)

- **A Fase 4 permanece nominal e intacta** — a 5 não escreve nela, não recalcula o fluxo,
  não adiciona VPL/TIR lá. Casos-ouro A e B da 4/4.1 byte a byte; suítes 1…4.2 verdes.
- O fluxo é **relido da persistência** da Financeira (decisão do handoff, endossada): o
  front **nunca** envia números — sem financeira executada, a econômica degrada honesta.
- `_fmt` pt-BR no backend; proveniência em toda premissa; regex anti-"viável" mantido.

## 3. A convenção nominal × real (O PONTO CENTRAL — decisão §0.1 resolvida)

**Problema:** o fluxo da Fase 4 é nominal sem indexação (parcelas e custos em valores de
hoje); o operador fixou que o recebível de loteamento é **corrigido por IPCA** e que a TMA é
**real** (spread acima do IPCA). Descontar um pelo outro exige convenção explícita.

**Convenção adotada — MOEDA CONSTANTE (identidade de Fisher):**
```
fluxo nominal futuro = fluxo de hoje × correção IPCA acumulada
descontar (fluxo de hoje × IPCA) por (TMA real ⊕ IPCA)  ≡  descontar (fluxo de hoje) por (TMA real)
                                   └────────── o IPCA CANCELA ──────────┘
```
1. **O fluxo da Fase 4 é interpretado como moeda constante (termos reais, R$ de hoje)** —
   coerente com recebíveis indexados ao IPCA: a parcela "fixa" do motor é o valor real, e a
   correção apenas preserva o poder de compra.
2. **O desconto usa a TMA REAL diretamente** sobre esse fluxo. **Nenhuma projeção de IPCA é
   necessária** — é a elegância da moeda constante (não prevemos inflação; ela cancela).
3. **A TIR resultante é REAL**, comparável diretamente à TMA real informada.
4. **Premissas rotuladas (vão na proveniência e no card):**
   - *"Fluxo em moeda constante: assume receitas E custos corrigidos pela mesma inflação
     (IPCA). Custo de obra corrige por INCC, historicamente ≠ IPCA — diferença não modelada;
     risco apontado, não calculado (evolução)."*
   - *"Sob esta convenção, a taxa da mesa de financiamento (4.1) é JUROS REAL — acima da
     correção IPCA do recebível."*
5. A Fase 4 **não muda** (continua rotulada "nominal/moeda de hoje"); a leitura real é
   exclusiva da 5 e fica explícita — nunca implícita (exigência do handoff).

## 4. Como funciona (determinístico — `core/economica.py`, funções puras)

- **TMA**: `tma_aa_real` **obrigatória, sem default** (placeholder *"ex.: 12% a.a. real —
  defina a sua pelo seu custo de capital"* é exemplo rotulado, não default). Conversão
  mensal por equivalência composta: `i_m = (1+tma_aa)^(1/12) − 1`. Persistida por análise
  (`declarado` + data).
- **VPL**: `Σ fluxo[m] / (1+i_m)^m` (m=0 = primeiro mês do fluxo da 4).
- **TIR**: pré-checagem de **trocas de sinal** no fluxo:
  - **0 trocas** → `tir = null`, `tir_status: "indefinida"`, rótulo *"fluxo sem inversão de
    sinal — TIR não existe; use o VPL"*. **Nunca número inventado.**
  - **1 troca** (convencional) → **bissecção determinística** em `i ∈ [−0,99; 10]` mensal
    (tolerância 1e-12, máx. 500 iterações); `tir_status: "unica"`.
  - **>1 troca** → calcula a raiz da bissecção mas `tir_status: "multipla_possivel"` +
    aviso *"fluxo não-convencional — a TIR pode não ser única; prefira o VPL como critério"*.
  - Anualização exibida: `(1+i_m)^12 − 1`. **Aviso de TIR explosiva**: se TIR anualizada >
    200% a.a., acrescentar *"TIR muito alta reflete exposição de caixa baixa (típico de
    permuta) — o VPL é o critério primário"* (lição do Caso A e da própria TIV: 121% a.a.).
- **Payback simples**: primeiro mês com acumulado ≥ 0 (o acumulado da 4); se o acumulado
  re-negativa depois, aviso *"o caixa volta a ficar negativo após o payback (mês X)"*.
  **Payback descontado**: idem sobre o acumulado descontado à TMA. Sem recuperação →
  `null` + *"não recuperado no horizonte de N meses"`.
- **Exposição máxima descontada**: mínimo do acumulado descontado (valor + mês).
- **Índice de lucratividade (IL)**: `VPL ÷ |exposição máxima descontada|` — métrica
  secundária rotulada (*"R$ de valor criado por R$ de capital exposto, a valor presente"*);
  `null` se exposição = 0.
- **Curva VPL × TMA (a sensibilidade do MVP — §0.2):** VPL para TMA real de **0% a 40% a.a.,
  passo 1 p.p.** (range/passo parametrizáveis), pares `(tma_aa, vpl, vpl_fmt)` — leitura
  visual de "a que taxa o valor zera" (≈ TIR). **Sem ±% em preço/custo** (evolução).

## 5. Contrato de API

### 5.1 `POST /api/analises/{id}/economica` → `EconomicaOut`
```jsonc
// REQUEST
{ "tma_aa_real": 0.12,                       // obrigatória; 422 se ausente (pede, não chuta)
  "curva": { "min_aa": 0.0, "max_aa": 0.40, "passo_pp": 1 } }   // opcional (defaults acima)

// RESPONSE
{
  "convencao": "Moeda constante: fluxo da Financeira interpretado em R$ de hoje (recebíveis IPCA); desconto e TIR em termos REAIS. IPCA não projetado (cancela).",
  "tma": { "aa_real": 0.12, "mensal": 0.0094887929, "origem": "declarado", "data": "..." },
  "vpl": { "valor": 3128359.33, "valor_fmt": "R$ 3.128.359,33" },
  "tir": { "mensal": 0.49477101, "aa": 123.42166, "status": "unica",
           "aa_fmt": "12.342,17% a.a.", "avisos": ["TIR muito alta reflete exposição baixa…"] },
  "payback": { "simples_mes": 3, "descontado_mes": 3, "avisos": [] },
  "exposicao_descontada": { "valor": -390000.00, "mes": 0, "valor_fmt": "−R$ 390.000,00" },
  "indice_lucratividade": 8.0214,
  "curva_vpl_tma": [ { "tma_aa": 0.0, "vpl": 3375600.00, "vpl_fmt": "…" },
                     { "tma_aa": 0.12, "vpl": 3128359.33, "vpl_fmt": "…" }, /* … 0.40 */ ],
  "leituras": [
    { "status": "favoravel", "texto": "VPL de R$ 3.128.359,33 à TMA real de 12,00% a.a. — o fluxo cria valor SOB AS PREMISSAS DECLARADAS." },
    { "status": "favoravel", "texto": "TIR real acima da TMA informada." }
  ],
  "proveniencia": "Fluxo relido da Financeira desta análise (execução de DD/MM) · TMA declarada pelo usuário",
  "avisos": [
    "Moeda constante assume receitas e custos corrigidos pela mesma inflação; obra corrige por INCC ≠ IPCA — diferença não modelada.",
    "Sob esta convenção, a taxa da mesa de financiamento (4.1) é juros REAL.",
    "Pré-análise (§1-A): indicadores condicionados às premissas informadas — não é recomendação de investimento."
  ]
}
```
Sem financeira executada/persistida → **409/422 honesto**: *"execute a Financeira primeiro —
a Econômica avalia o fluxo dela"* (sem fluxo no corpo; o front nunca manda números).
`GET` devolve a última execução persistida.

### 5.2 Slots do dashboard (4.2)
O front, ao montar o dashboard da Financeira, **busca a Econômica da análise**: se existir,
preenche os slots `vpl`/`tir`/`payback` com os valores e `status` das `leituras`; senão,
mantém `pendente`. **Composição de dois JSONs — zero cálculo no front** (§2).

## 6. Critérios de aceite (valores-ouro calculados sobre o fluxo do Caso Fechado A)

Fluxo de entrada (relido da 4): `m0 = −390.000; m1–4 = +152.560; m5–6 = +192.560;
m7–10 = +692.560`.

1. **Conversão da TMA:** 12% a.a. real → `i_m = 0,0094887929` (±1e-9).
2. **VPL-ouro:** à TMA 12% a.a. real → **R$ 3.128.359,33** (±0,01). À TMA 0% → VPL =
   resultado nominal da 4 = **3.375.600,00** (consistência 4×5).
3. **TIR-ouro (bissecção):** `i_m = 0,49477101` (±1e-6), `status="unica"` (1 troca de
   sinal), `VPL@TIR = 0` (±0,01), anualizada exibida, **aviso de TIR explosiva presente**
   (> 200% a.a.).
4. **TIR trivial:** fluxo `[−1.000, +1.100]` → TIR mensal = **10,000000%** exato.
5. **TIR degenerada:** fluxo todo positivo → `tir=null`, `status="indefinida"`, sem número;
   fluxo com 2+ trocas de sinal → `status="multipla_possivel"` + aviso "prefira o VPL".
6. **Paybacks:** simples = **mês 3**; descontado (12% a.a.) = **mês 3**; fluxo que nunca
   recupera → `null` + "não recuperado no horizonte"; fluxo que re-negativa após o payback
   → aviso presente.
7. **Exposição descontada e IL:** exposição = **−390.000,00 no mês 0**; IL = **8,0214**
   (±0,001).
8. **Curva VPL×TMA:** 41 pontos (0–40%, passo 1 p.p.) com extremos-ouro `0% → 3.375.600,00`
   e `40% → 2.693.174,29` (±0,01); range custom respeitado; passo inválido → 422.
9. **Convenção e §1-A:** campo `convencao` presente; avisos de INCC≠IPCA e de juros-real-da-
   mesa presentes; `leituras` usam "sob as premissas declaradas"; **regex: nenhuma string
   "viável"/"inviável"** na resposta.
10. **Degradação + determinismo + não-regressão:** sem financeira persistida → 409/422 com a
    mensagem; sem `tma_aa_real` → 422 pedindo; mesma entrada → mesma saída; `_fmt` em todo
    monetário; **slots do dashboard preenchidos quando a econômica existe** (teste de
    composição no front); suítes 1…4.2 verdes e Fase 4 sem nenhum campo novo.

## 7. Fora de escopo (registrado)

- **Sensibilidade ±% em preço/custo/curva** (tornado/cenários) — evolução (decisão §0.2).
- **Projeção explícita de IPCA / fluxo indexado mês a mês / INCC sobre obra** — a moeda
  constante dispensa no MVP; indexação explícita é evolução (junto da 4).
- **MTIR, ROE, TIR do terrenista por participante** — evolução (gabarito TIV CP 11 cobre
  quando chegarem; o MVP avalia o fluxo do incorporador, que carrega os custos).
- **Cenários otimista/provável/pessimista** (TIV) — evolução.
- **Comparação entre análises/glebas** — evolução (ranking de oportunidades).

## 8. Arquivos esperados (latitude de implementação)

- `core/economica.py` — `vpl()`, `tir_bissecao()` (com pré-checagem de trocas de sinal),
  `paybacks()`, `curva_vpl_tma()`, `leituras()` — todas puras.
- `routers/economica.py` — `POST`/`GET /analises/{id}/economica`; relê a persistência da
  Financeira; persiste TMA + resultado por análise.
- `models/schemas.py` — `TmaOut`, `TirOut`, `PontoCurvaOut`, `EconomicaOut`.
- Frontend: item "Econômica" na sidebar + `CardEconomica` (TMA com placeholder-exemplo
  rotulado; VPL/TIR/paybacks; gráfico da curva VPL×TMA; avisos da convenção); dashboard da
  4.2 compõe os slots. Sem cálculo no front.
- Testes: `tests/test_economica.py` (ouro 1–10, offline, determinísticos).

A spec fixa **contrato + critérios**; o resto é latitude. **Sem LLM, sem rede** — VPL/TIR/
payback são matemática financeira fechada sobre o fluxo que a Fase 4 já padronizou.
