# Fase 4 — Financeira (fluxo de caixa do empreendimento)

> É onde a planilha do curso entra — **a estrutura dela, sem os erros da §9**. Referencia o
> `ARCHITECTURE.md` (§1-A, §2, §6, §9) e **não o contradiz**. **Aritmética pura: sem LLM,
> sem dado externo, sem rede.** Fronteira fixada no roadmap: **a Fase 4 MONTA o fluxo de
> caixa por período; a Fase 5 (Econômica) AVALIA o fluxo** (VPL/TIR/payback ficam para a 5).

## 1. Objetivo

Dado o **nº de lotes** que o motor já produz e um conjunto de **premissas declaradas** (todas
com proveniência), montar o **fluxo de caixa mensal** do loteamento e devolver: VGV bruto e
próprio, custos por bloco, impostos, **fluxo por mês + acumulado**, **exposição máxima de
caixa**, resultado nominal e margem. Cada linha rastreável à premissa que a gerou.

**Espelha a planilha do curso** (Dados do Parcelamento → Tabela de Preço → Custo → Carteira →
EVE), com as correções obrigatórias da §9:
- **Tributação é PARÂMETRO, nunca constante.** Sem RET (não se aplica a loteamento). Default
  rotulado *"Lucro Presumido — alíquota efetiva sobre receita; CONFIRME COM CONTADOR"*.
- **Nenhum % de mercado escondido em fórmula** — todo default herdado da planilha é premissa
  **editável e rotulada** (`origem: "default_rotulado"` até o usuário tocar).

## 2. O que NÃO muda (não-regressão)

- **Não altera o aproveitamento** — a 4 **consome** lotes; nunca recalcula geometria/doação.
- **Sem VPL/TIR/payback/desconto** — é a Fase 5. A 4 entrega o fluxo que a 5 vai descontar.
- Sem LLM, sem I/O externo, sem credencial. Suítes 1…3.5 continuam verdes.
- Front **só renderiza JSON** (§2) — **nenhuma conta no front, nem juros, nem formatação de
  moeda calculada**: o backend manda `valor` (number) **e** `valor_fmt` (string pt-BR),
  padrão da 3.5.

## 3. Como funciona (determinístico, cálculo só no backend)

### 3.1 Origem dos lotes do caso-base (decisão vetável A — recomendação do handoff endossada)
```
se cenario_diretriz disponível  → lotes = cenario_diretriz.n_lotes   (origem: "diretriz")
senão                           → lotes = n_lotes_teto               (origem: "teto_fisico")
                                  + aviso OBRIGATÓRIO: "teto físico SEM doação/vias —
                                  tende a SUPERESTIMAR receita; confirme a diretriz municipal"
```
O usuário pode **sobrescrever** (`origem: "declarado"`). Rural usa `n_parcelas` com o mesmo
padrão. Os outros números (teto/otimista) **não viram fluxos paralelos** no MVP — só o
caso-base (cenários múltiplos = evolução; vetável).

### 3.2 Vias e eficiência de projeto (correção §9 nº 2)
Vias **não estão descontadas** em nenhum lote do motor (§6-A). A financeira oferece o
parâmetro opcional **`eficiencia_projeto_pct`** (reduz os lotes vendáveis: `lotes_vendaveis =
floor(lotes × eficiência)`), **default 1.0 (sem redução), editável e rotulado** — *"% dos
lotes do caso-base efetivamente vendáveis após viário/lazer do projeto; regra de mercado SEM
âncora legal; defina com o urbanista"*. Nunca um 74%/60% escondido.

### 3.3 Blocos do modelo (estrutura da planilha, corrigida)
**Receita** — `vgv_bruto = lotes_vendaveis × preço_lote`. Vendas com **curva**: início, duração
(meses), distribuição `linear` (default) ou lista custom de % por mês (soma=1, validada).
Modo **à vista** (recebe no mês da venda) ou **parcelado** (entrada % no mês da venda +
N parcelas mensais iguais, **sem juros no MVP** — valores nominais; tabela com juros é
evolução, vetável). Inadimplência opcional: % simples reduzindo cada recebimento (default 0).

**Permuta (aquisição da gleba)** — três modos, um por análise:
- `permuta_vgv`: terrenista recebe `pct` de **cada recebimento** (pro-rata); receita própria
  = `(1−pct)` de cada entrada de caixa. `vgv_proprio = vgv_bruto × (1−pct)`.
- `permuta_lotes`: `n` lotes ao terrenista → saem de `lotes_vendaveis` antes do VGV próprio
  (equivalente físico; convertido e exibido como % para conferência).
- `compra`: valor + condição (à vista no mês 0 ou parcelado início/n meses) → linhas de saída.

**Custos** — cada um com curva própria (mês início, duração, linear/custom):
urbanização/infra (R$/lote **ou** R$/m² de área aproveitável — um dos dois);
projetos+aprovação (default rotulado R$ 280.000 — *da planilha do curso, confirme*);
topografia/georreferenciamento (default rotulado R$ 100.000);
SPE/ITBI/cartório (valor declarado; ITBI só no modo `compra`);
marketing (% do VGV próprio, curva); administração (fixo mensal, do mês 0 ao fim);
comissão de vendas (% sobre o **valor bruto** de cada venda, no mês da venda — vetável:
sobre recebimento, para vendas parceladas com comissão diluída).

**Tributos** — `aliquota_pct` × **receita própria recebida no mês** (regime de caixa).
Default rotulado **5,93%** com proveniência: *"alíquota efetiva típica de Lucro Presumido
imobiliário (PIS 0,65 + COFINS 3,00 + IRPJ 1,20 + CSLL 1,08); NÃO é RET; ignora adicional de
IRPJ; CONFIRME COM CONTADOR"*. Campo `regime: "presumido"|"real"|"outro"` é **rótulo de
proveniência** — o motor sempre multiplica a alíquota informada (não apura imposto real;
fora de escopo).

### 3.4 Montagem do fluxo (motor puro)
`core/financeira.py` — `montar_fluxo(premissas) -> FluxoOut`. Horizonte = último mês com
movimento (derivado das curvas). Para cada mês: `entradas − saídas`; acumulado; **exposição
máxima = mínimo do acumulado** (com o mês em que ocorre); resultado nominal = acumulado
final; margem = resultado ÷ VGV próprio. Toda linha do fluxo referencia o bloco/premissa
(`origem_linha`). Arredondamento: centavos (2 casas), `floor` só em contagem de lotes.

## 4. Contrato de API

### 4.1 `POST /api/analises/{id}/financeira` (premissas no corpo) → `FinanceiraOut`
Ver `models/schemas.py` (`PremissasFinanceiraIn` → `FinanceiraOut`). Resumo dos campos:
`caso_base` (lotes/origem/aviso) · `vgv` (bruto/proprio/permuta, com `_fmt`) · `blocos`
(total + proveniência por premissa) · `fluxo` (por mês: entradas/saidas/liquido/acumulado +
`_fmt`) · `indicadores` (resultado_nominal, margem_sobre_vgv_proprio, exposicao_maxima
{valor, mes}, horizonte_meses) · `proveniencia` · `avisos`.

Sem premissa essencial (`preco_lote`) → **422 pedindo o campo** (degradação honesta — não
chuta preço). `GET` devolve a última execução persistida (premissas + resultado).

### 4.2 Persistência (decisão vetável B)
Premissas persistem **por análise** em volume (padrão 1.8/3). `origem` por premissa:
`declarado` × `default_rotulado`. **Sem gate `proposto→confirmado`** — a origem já é o humano;
proveniência basta.

## 5. Critérios de aceite (Caso Fechado A — valores-ouro)

**Caso Fechado A:** 100 lotes × R$ 100.000; permuta_vgv 20%; vendas 10/mês meses 1–10 à
vista; comissão 5% s/ bruto; tributo 5,93% s/ receita própria; urbanização R$ 30.000/lote
linear meses 1–6; projetos 280.000 + topografia 100.000 no mês 0; administração 10.000/mês
(0–10); marketing 2% do VGV próprio linear meses 1–4.

1. VGV: bruto 10.000.000; próprio 8.000.000; permuta 2.000.000.
2. Fluxo-ouro: mês 0 = −390.000; meses 1–4 = +152.560; meses 5–6 = +192.560; meses 7–10 =
   +692.560 (exatos, 2 casas).
3. Acumulado final = **3.375.600,00** = resultado nominal; **exposição = −390.000 no mês 0**;
   margem = **42,1950%**; horizonte = 10. Consistência: `Σ liquido == VGV próprio − Σ saídas`.
4. Origem dos lotes (§3.1): diretriz sem aviso; teto com aviso de superestimação; declarado
   sobrepõe.
5. Tributação = parâmetro: alíquota 0 → resultado 3.850.000; proveniência "confirme com
   contador" e **não menciona RET como aplicável**.
6. Parcelado desloca o caixa; exposição **piora** vs à vista.
7. Permuta por lotes `n=20` → `lotes_vendaveis=80`, VGV próprio 8.000.000 (≈20%).
8. Eficiência 0.9 → 90 lotes vendáveis (rótulo "regra de mercado sem âncora legal").
9. Degradação: sem `preco_lote` → 422 nomeando o campo; curva custom que não soma 1 → 422.
10. Determinismo + `_fmt` pt-BR no backend; **nenhum** VPL/TIR/payback nos indicadores;
    não-regressão 1…3.5.

## 6. Fora de escopo (registrado)

- VPL/TIR/TMA/payback/sensibilidade → **Fase 5 (Econômica)**.
- Precificação de mercado → dimensão Mercadológica (aqui preço é input).
- Indexação/inflação, juros de tabela, financiamento → evolução (MVP nominal).
- Apuração tributária real → contador; o motor multiplica a alíquota informada.
- Cotas/captação e carteira avançada → evolução pós-Fase 5.

## 7. Arquivos (implementados)

- `core/financeira.py` — `montar_fluxo(premissas, ctx)` puro + formatador `brl`.
- `core/financeira_store.py` — persistência por análise (volume).
- `routers/financeira.py` — `POST`/`GET /analises/{id}/financeira`; resolve lotes (§3.1).
- `models/schemas.py` — `PremissasFinanceiraIn`, `BlocoOut`, `LinhaFluxoOut`,
  `IndicadoresOut`, `FinanceiraOut`.
- Frontend: item "Financeira" + `CardFinanceira` (premissas com defaults rotulados;
  tabela do fluxo; KPIs VGV/resultado/exposição).
- Testes: `tests/test_financeira.py` (Caso Fechado A + variações, offline).
