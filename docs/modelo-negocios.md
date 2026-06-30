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

**Insight central:** o custo de **compute por análise é baixíssimo** (estimado R$ 11–17). O custo
que vai pesar de verdade é **aquisição de cliente (CAC)** — a precificação tem que mirar LTV, não COGS.

---

## 2. Custo de LLM por análise (o número que você pediu)

Só **3 pontos** chamam a IA; todas as outras dimensões (ambiental, declividade, vegetação, financeira,
econômica, custo de infra, malha fundiária, bacia, bioma, localização, conformidade) são **Python puro
= R$ 0 de LLM**.

| Chamada | Modelo | Input estimado | Output estimado | Custo estimado | Frequência |
|---|---|---|---|---|---|
| **Extração LUOS** | Opus 4.8 | ~160k tok (PDF ~80 págs) | ~16k tok | **~US$ 1,20** | **1× por município** (reutilizada!) |
| **Urbanismo IA** | Fable 5 | ~6k tok | ~4k tok (×2 gerações) | **~US$ 0,52** | por análise (mais se regenerar) |
| **Extração Jurídica** | Opus 4.8 | ~15k tok/matrícula | ~6k tok/matrícula | **~US$ 0,68** (3 matrículas) | por análise |

### Custo por análise completa
- **Regime estável** (município já tem perfil LUOS): Urbanismo + Jurídico ≈ **US$ 1,20 ≈ R$ 6,6** de LLM.
- **Primeira análise de um município novo**: + a extração LUOS (US$ 1,20) ≈ **US$ 2,40 ≈ R$ 13** de LLM.

### + Infra diluída
Lightsail ~US$ 40/mês. Diluído: 50 análises/mês → US$ 0,80/análise; 200/mês → US$ 0,20.

### COGS marginal por análise completa
| Cenário | LLM | Infra (50/mês) | **Total ≈** |
|---|---|---|---|
| Município já perfilado | US$ 1,20 | US$ 0,80 | **US$ 2,00 ≈ R$ 11** |
| Município novo (1ª vez) | US$ 2,40 | US$ 0,80 | **US$ 3,20 ≈ R$ 17** |

> Mesmo com regeneração intensa de urbanismo (cada nova geração +US$ 0,26) e mais matrículas, o COGS
> dificilmente passa de **R$ 25/análise**. Para um produto cujo objeto vale milhões, é desprezível.

---

## 3. Alavancas de custo (se quiser baixar o COGS)

1. **Urbanismo IA usa Fable 5 (US$ 10/50 — o mais caro).** Trocar por **Opus 4.8** (US$ 5/25) corta
   o custo do urbanismo pela metade; **Sonnet 5** (US$ 3/15, promo US$ 2/10) corta ~70%. Tradeoff de
   qualidade do traçado — testar antes. É a maior alavanca isolada.
2. **Prompt caching** no system prompt do urbanismo (estável entre gerações da mesma análise) →
   ~90% de desconto no prefixo relido. Ganho real quando há múltiplas regenerações.
3. **LUOS/Jurídico em Sonnet 5** em vez de Opus 4.8 para PDFs — extração é tarefa estruturada; pode
   manter qualidade a ~60% do custo. Validar acurácia com valores-ouro antes.
4. **LUOS é amortizada** — quanto mais análises por cidade, mais barato o custo médio. Concentrar
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

Isso é melhor que "2 análises completas grátis" (que custariam ~R$ 22–34 por usuário, mesmo quem nunca
converte). Aqui o **free é quase de graça pra você** e ainda demonstra qualidade.

**Estrutura sugerida:**
| Plano | Preço (hipótese) | Inclui |
|---|---|---|
| **Free** | R$ 0 | Dimensões determinísticas ilimitadas + 1 análise Pro de degustação |
| **Pro mensal** | R$ 199–499/mês | N análises Pro completas/mês + excedente R$ 49–99 |
| **Créditos avulsos** | R$ 99–199/análise Pro | Para quem usa esporádico, sem assinar |

> Margem bruta no compute: **>90%** em qualquer cenário (COGS R$ 11–25 vs. preço R$ 99–499). O gargalo
> de lucro não é custo — é **CAC e conversão**.

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

**Regra de ouro:** mire **LTV ≥ 3× CAC**. Com COGS de R$ 11–25 e preço de R$ 199–499/mês, o LTV é
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

- **Custo por análise completa:** ~**R$ 11** (município já perfilado) a ~**R$ 17** (1ª vez na cidade);
  teto realista ~R$ 25. Compute é barato.
- **Custo está em 3 features de IA**; o resto é R$ 0 de LLM.
- **Cobrança recomendada:** freemium com **gate por feature** (free = determinístico ilimitado; Pro =
  IA) + assinatura mensal com cota + créditos avulsos.
- **Maior alavanca de custo:** trocar o modelo do Urbanismo IA (Fable 5 → Opus/Sonnet).
- **O que decide o lucro não é o COGS — é o CAC e a conversão free→pago.**
- **Antes de cravar preço:** instrumentar o custo real por análise (§7).
