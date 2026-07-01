# Modelo de Negócios — Pré-Viabilidade de Loteamento

> Brainstorm de monetização do MVP. **Os números de custo de LLM abaixo são ESTIMATIVAS** (baseadas
> nos preços oficiais Anthropic de 2026-06 e em tamanhos típicos de documento), não medições. Para
> virar custo real, é preciso instrumentar o `usage` das chamadas (ver §7). Câmbio usado: ~R$ 5,5/US$.

---

## 1. Onde estão os custos (a pilha de custos)

| Categoria | O que é | Natureza |
|---|---|---|
| **LLM (Anthropic)** | Extração LUOS, Urbanismo IA, Extração Jurídica | **Variável por análise** — é o único custo de IA |
| **Infra (AWS Lightsail)** | Instância `api`+`web`, disco, banda | **Fixo mensal** — diluído por nº de análises |
| **Dados** | Rasters (DEM, MapBiomas), shapefiles (SIGEF, biomas, bacias, CAR) | Fixo (download único) + disco |
| **Aquisição (marketing/CAC)** | Ads, conteúdo, parcerias, vendas | **Variável por cliente** — tende a dominar tudo |
| **Seu tempo** | Suporte, confirmação de perfil LUOS, manutenção | Custo oculto, real |

**Insight central:** o custo de **compute por análise é baixíssimo** (marginal estimado ~R$ 2–6). O custo
que vai pesar de verdade é **aquisição de cliente (CAC)** — a precificação tem que mirar LTV, não COGS.

---

## 2. Custo de LLM por análise (o número que você pediu)

Só **3 pontos** chamam a IA; todas as outras dimensões (ambiental, declividade, vegetação, financeira,
econômica, custo de infra, malha fundiária, bacia, bioma, localização, conformidade) são **Python puro
= R$ 0 de LLM**.

> **Correção importante:** o **Fable 5 NÃO é usado** (não está disponível na org) — a cadeia cai para
> **Opus 4.8 hoje, em TODAS as 3 chamadas**. E o custo marginal por análise é **só o LLM**; a infra do
> Lightsail é **custo fixo** (§4), não entra no marginal.

### Cenário HOJE (tudo em Opus 4.8, US$ 5/25)
| Chamada | Input estimado | Output estimado | Custo estimado | Frequência |
|---|---|---|---|---|
| **Extração LUOS** | ~160k tok (PDF ~80 págs) | ~16k tok | ~US$ 1,20 | **1× por município** (amortizada!) |
| **Urbanismo IA** | ~6k tok | ~4k tok (×~2 gerações) | ~US$ 0,20 | por análise |
| **Extração Jurídica** | ~15k tok/matrícula | ~6k tok/matrícula | ~US$ 0,68 (3 matrículas) | por análise |

- **Marginal por análise (município já perfilado):** Urbanismo + Jurídico ≈ **US$ 0,88 ≈ R$ 5**.
- LUOS amortizada: US$ 1,20 ÷ (nº de análises na cidade). Com 10 análises/cidade → +US$ 0,12/análise.
- **Total marginal ≈ US$ 1,00 ≈ R$ 5,5 por análise completa.**

### Cenário OTIMIZADO (Sonnet 5 no LUOS + Jurídico; Opus 4.8 só no Urbanismo)
Sonnet 5 = US$ 3/15 (promo US$ 2/10 até 31/08/2026). Extração é tarefa estruturada — Sonnet dá conta.
| Chamada | Modelo | Custo estimado |
|---|---|---|
| Urbanismo IA | Opus 4.8 | ~US$ 0,20 |
| Extração Jurídica (3 matrículas) | Sonnet 5 | ~US$ 0,40 |
| Extração LUOS (amortizada) | Sonnet 5 | ~US$ 0,07 |

- **Total marginal ≈ US$ 0,67 ≈ R$ 3,7 por análise** (≈ **R$ 2,5** com preço promo do Sonnet).
- Ainda mais agressivo: **Haiku 4.5** (US$ 1/5) no Jurídico levaria o marginal a **~R$ 2**, se a acurácia
  da extração se sustentar (validar com valores-ouro antes).

### Resumo do custo marginal
| Cenário | Marginal por análise completa |
|---|---|
| Hoje (tudo Opus 4.8) | **~R$ 5–6** |
| Otimizado (Sonnet extração) | **~R$ 3–4** |
| Agressivo (Haiku no jurídico) | **~R$ 2** |

> O R$ 25 do brainstorm anterior estava **errado** — inflado por (a) precificar Fable 5, (b) somar infra
> fixa no marginal, (c) estimativas conservadoras. O custo real de mais uma análise é **poucos reais**.

---

## 3. Alavancas de custo (se quiser baixar o COGS)

1. **LUOS + Jurídico em Sonnet 5** (US$ 3/15) em vez de Opus 4.8 — extração é tarefa estruturada;
   mantém qualidade a ~40–60% do custo. **É só trocar 2 envs** (`LUOS_EXTRATOR_MODELO`,
   `JURIDICO_EXTRATOR_MODELO=claude-sonnet-5`), sem mexer em código. Validar acurácia com valores-ouro.
2. **Urbanismo fica em Opus 4.8** (o Fable nem está disponível). Se quiser cortar mais, testar
   Sonnet 5 também no traçado — mas aqui a qualidade importa mais, então avaliar com cuidado.
3. **Prompt caching** no system prompt do urbanismo (estável entre gerações da mesma análise) →
   ~90% de desconto no prefixo relido. Ganho real quando há múltiplas regenerações.
4. **Haiku 4.5** (US$ 1/5) no Jurídico — a mais agressiva; validar acurácia antes.
5. **LUOS é amortizada** — quanto mais análises por cidade, mais barato o custo médio. Concentrar
   vendas por região aproveita isso.

---

## 4. Modelos de cobrança

| Modelo | Como funciona | Prós | Contras |
|---|---|---|---|
| **Pay-per-análise** | R$ X por análise concluída | Alinha receita a custo; simples | Fricção a cada uso; receita imprevisível |
| **Assinatura (SaaS)** | R$ Y/mês, inclui N análises, excedente R$ Z | Receita recorrente, previsível | Exige volume recorrente do cliente |
| **Créditos pré-pagos** | Pacote (ex.: 10 análises por R$ 990) | Caixa antecipado, menos fricção | Cliente pode "estocar" e sumir |
| **Freemium** | 2 análises grátis → pago | Aquisição/baixa barreira | Custo do tier grátis (ver §5) |
| **Try & buy** | Trial de 7–14 dias com tudo liberado | Mostra valor completo | Pode ser usado e abandonado |
| **Tiered por feature** | Grátis = dimensões Python; Pago = features de IA | Free quase sem custo; monetiza o que custa | Precisa comunicar bem o valor do "pro" |

---

## 5. Recomendação: Freemium com gate por FEATURE (não por nº de análises)

O seu COGS está **concentrado nas 3 features de IA** (LUOS, Urbanismo, Jurídico). Logo:

- **Tier grátis = dimensões determinísticas ILIMITADAS** (ambiental, declividade, área verde,
  localização, malha fundiária, bacia, bioma, financeira, econômica). Custo marginal de LLM = **R$ 0**;
  só infra. O cliente já enxerga MUITO valor (triagem ambiental + financeira completa) de graça.
- **Tier Pro (pago) = features de IA + custo** (Urbanismo IA, Jurídico/cadeia dominial, Conformidade
  LUOS, Custo de infraestrutura). É onde está o seu diferencial caro e defensável.

Isso é melhor que "2 análises completas grátis" (que custariam ~R$ 4–12 por usuário, mesmo quem nunca
converte). Aqui o **free é quase de graça pra você** e ainda demonstra qualidade.

**Estrutura sugerida:**
| Plano | Preço (hipótese) | Inclui |
|---|---|---|
| **Free** | R$ 0 | Dimensões determinísticas ilimitadas + 1 análise Pro de degustação |
| **Pro mensal** | R$ 199–499/mês | N análises Pro completas/mês + excedente R$ 49–99 |
| **Créditos avulsos** | R$ 99–199/análise Pro | Para quem usa esporádico, sem assinar |

> Margem bruta no compute: **>95%** (custo marginal R$ 2–6 vs. preço R$ 99–499). O gargalo de lucro
> não é custo — é **CAC e conversão**.

---

## 6. Marketing / CAC (a parte que domina)

Não dá pra cravar números sem seus canais, mas o desenho:

- **Orgânico/conteúdo:** SEO em "viabilidade de loteamento", "como aprovar loteamento", calculadoras
  grátis. CAC baixo, retorno lento. O **free tier vira isca** de aquisição.
- **Paid (Google Ads):** keywords de loteamento são nicho e caras; CAC potencialmente alto. Testar
  com orçamento pequeno e medir conversão free→pago.
- **Parcerias:** corretores, engenheiros, escritórios de aprovação, AELO/SECOVI, cartórios. Canal
  provavelmente o de melhor CAC para esse público B2B.
- **Vendas diretas:** loteadoras médias/grandes — ticket alto, ciclo longo, mas LTV grande.

**Regra de ouro:** mire **LTV ≥ 3× CAC**. Com custo marginal de R$ 2–6 e preço de R$ 199–499/mês, o LTV é
alto; o que precisa ser controlado é o CAC e o churn.

---

## 7. Próximo passo crítico: MEDIR, não estimar

Os números de LLM acima são **estimativas**. A disciplina do projeto é não inventar dado. O passo
concreto é **instrumentar o `usage`** das 3 chamadas Anthropic (`response.usage.input_tokens` /
`output_tokens`, e `cache_read_input_tokens`), persistir por análise, e expor um **custo real por
análise** num pequeno painel/admin. Aí a precificação para de ser chute.

Posso implementar isso: logging de tokens nas 3 chamadas → custo calculado (tabela de preços) →
agregado por análise/mês no painel admin que já existe. Vira a base factual da decisão de preço.

---

## 8. Resumo executivo

- **Custo MARGINAL por análise completa:** **~R$ 5–6 hoje** (tudo Opus 4.8), **~R$ 3–4 otimizado**
  (Sonnet na extração), **~R$ 2 agressivo** (Haiku no jurídico). Infra do Lightsail é **fixa** (~R$ 220/mês),
  não por análise. O R$ 25 anterior estava errado.
- **Custo está em 3 features de IA**; o resto é R$ 0 de LLM.
- **Cobrança recomendada:** freemium com **gate por feature** (free = determinístico ilimitado; Pro =
  IA) + assinatura mensal com cota + créditos avulsos. Margem no compute **>95%**.
- **Maior alavanca de custo:** LUOS + Jurídico em Sonnet 5 (só trocar 2 envs, sem código).
- **O que decide o lucro não é o COGS — é o CAC e a conversão free→pago.**
- **Antes de cravar preço:** instrumentar o custo real por análise (§7).
