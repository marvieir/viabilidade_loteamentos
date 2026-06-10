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
```jsonc
// REQUEST (tudo opcional tem default rotulado; essenciais sem default → 422 pedindo)
{
  "lotes": { "origem": "auto" },            // auto = regra §3.1; ou {"origem":"declarado","n":120}
  "eficiencia_projeto_pct": 1.0,
  "preco_lote": 100000,                      // essencial (ou preco_m2 + area média) — sem default
  "vendas": { "inicio_mes": 1, "duracao_meses": 10, "curva": "linear",
              "modo": "avista" },            // ou {"modo":"parcelado","entrada_pct":0.2,"n_parcelas":36}
  "inadimplencia_pct": 0.0,
  "aquisicao": { "modo": "permuta_vgv", "pct": 0.20 },
  "custos": {
    "urbanizacao": { "base": "por_lote", "valor": 30000, "inicio_mes": 1, "duracao_meses": 6 },
    "projetos_aprovacao": { "valor": 280000, "mes": 0 },
    "topografia": { "valor": 100000, "mes": 0 },
    "administracao_mensal": 10000,
    "marketing": { "pct_vgv_proprio": 0.02, "inicio_mes": 1, "duracao_meses": 4 },
    "comissao_pct": 0.05
  },
  "tributos": { "regime": "presumido", "aliquota_pct": 0.0593 }
}

// RESPONSE
{
  "caso_base": { "lotes": 100, "origem_lotes": "diretriz|teto_fisico|declarado",
                 "aviso_lotes": null | "teto físico SEM doação/vias — tende a SUPERESTIMAR…" },
  "vgv": { "bruto": 10000000, "bruto_fmt": "R$ 10.000.000,00",
           "proprio": 8000000, "proprio_fmt": "R$ 8.000.000,00",
           "permuta": { "modo": "permuta_vgv", "pct": 0.20, "valor": 2000000 } },
  "blocos": [   // totais por bloco, com proveniência da premissa
    { "bloco": "urbanizacao", "total": 3000000, "total_fmt": "…",
      "proveniencia": "R$ 30.000/lote × 100 — declarado pelo usuário" },
    { "bloco": "tributos", "total": 474400,
      "proveniencia": "5,93% s/ receita própria — DEFAULT ROTULADO; confirme com contador" }
    // … projetos, topografia, administracao, marketing, comissao …
  ],
  "fluxo": [    // POR MÊS — o insumo da Fase 5
    { "mes": 0, "entradas": 0, "saidas": 390000, "liquido": -390000,
      "liquido_fmt": "−R$ 390.000,00", "acumulado": -390000 },
    { "mes": 1, "entradas": 800000, "saidas": 647440, "liquido": 152560, "acumulado": -237440 }
    // … até o último mês com movimento …
  ],
  "indicadores": {
    "resultado_nominal": 3375600, "resultado_nominal_fmt": "R$ 3.375.600,00",
    "margem_sobre_vgv_proprio": 0.421950,
    "exposicao_maxima": { "valor": -390000, "mes": 0 },
    "horizonte_meses": 10
  },
  "proveniencia": "Premissas declaradas/defaults rotulados desta análise · lotes do cenário diretriz (São Roque/MUE)",
  "avisos": [
    "Fluxo NOMINAL (sem inflação/indexação) — avaliação (VPL/TIR) é a dimensão Econômica.",
    "Tributação simplificada por alíquota efetiva — NÃO substitui apuração contábil; confirme com contador.",
    "Pré-análise financeira (§1-A): premissas do usuário; não é recomendação de investimento."
  ]
}
```
Sem premissa essencial (`preco_lote`) → **422 pedindo o campo** (degradação honesta — não
chuta preço). `GET` devolve a última execução persistida (premissas + resultado).

### 4.2 Persistência (decisão vetável B)
Premissas persistem **por análise** em volume (padrão 1.8/3) — o operador não redigita.
`origem` por premissa: `declarado` (com data) | `default_rotulado`. **Sem gate
`proposto→confirmado`**: o gate da 1.8 protege contra o LLM; aqui a origem **já é o humano** —
proveniência basta. (Vetável: exigir confirmação formal com `validado_por`.)

## 5. Critérios de aceite (testáveis — valores-ouro do Caso Fechado A)

**Caso Fechado A** (aritmética verificável à mão; substitui números da planilha com erros):
100 lotes × R$ 100.000; permuta_vgv 20%; vendas 10/mês meses 1–10 à vista; comissão 5%
s/ bruto; tributo 5,93% s/ receita própria; urbanização R$ 30.000/lote linear meses 1–6;
projetos 280.000 + topografia 100.000 no mês 0; administração 10.000/mês (0–10);
marketing 2% do VGV próprio linear meses 1–4.

1. **VGV:** bruto = 10.000.000; próprio = 8.000.000; permuta = 2.000.000.
2. **Fluxo-ouro por mês:** mês 0 = −390.000; meses 1–4 = +152.560; meses 5–6 = +192.560;
   meses 7–10 = +692.560 (cada um exato, 2 casas).
3. **Acumulado e indicadores:** acumulado final = **3.375.600,00** = resultado nominal;
   **exposição máxima = −390.000 no mês 0**; margem = **42,1950%** (±0,0001);
   horizonte = 10. Consistência interna: `Σ liquido == acumulado final == VGV próprio −
   Σ blocos de saída` (tolerância 1 centavo).
4. **Origem dos lotes (§3.1):** com `cenario_diretriz` no contexto → `origem_lotes="diretriz"`,
   sem aviso; sem diretriz → `"teto_fisico"` **com** o aviso de superestimação; declarado
   sobrepõe ambos.
5. **Tributação = parâmetro:** mudar `aliquota_pct` para 0 muda só o bloco tributos
   (resultado = 3.850.000,00); a proveniência do default contém "confirme com contador" e
   **não menciona RET como aplicável**.
6. **Parcelado:** vendas `entrada 20% + 4 parcelas` → recebimentos redistribuídos (mesma
   receita total, caixa deslocado); exposição máxima **piora** vs à vista (teste relativo).
7. **Permuta por lotes:** `permuta_lotes n=20` → `lotes_vendaveis=80`, VGV próprio =
   8.000.000 (equivalência com o caso A exibida como 20%).
8. **Eficiência de projeto:** `0.9` → 90 lotes vendáveis; proveniência rotula "regra de
   mercado sem âncora legal".
9. **Degradação honesta:** sem `preco_lote` → 422 nomeando o campo; curva custom que não
   soma 1 → 422 diagnóstico. Nunca inventa premissa.
10. **Determinismo + formatação no backend:** mesmas premissas → mesmo fluxo byte-a-byte;
    todo valor monetário acompanha `_fmt` pt-BR gerado no backend; **nenhum** VPL/TIR/payback
    na resposta (fronteira 4×5). Não-regressão: suítes 1…3.5 verdes.

## 6. Fora de escopo (registrado)

- **VPL / TIR / TMA / payback / sensibilidade** → **Fase 5 (Econômica)**, que consome `fluxo`.
- **Precificação de mercado** (quanto vale o lote ali) → dimensão Mercadológica; aqui preço
  é **input**.
- **Indexação/inflação (INCC/IPCA), juros de tabela em vendas parceladas, financiamento
  bancário** → evolução (MVP nominal).
- **Apuração tributária real** (Lucro Real, adicional IRPJ, reforma IBS/CBS — nota da §9)
  → contador; o motor multiplica alíquota informada.
- **Cotas/captação de investidores** (aba Cotas da planilha) e **ponto de equilíbrio/análise
  de carteira avançada** → evolução pós-Fase 5.

## 7. Arquivos esperados (latitude de implementação)

- `core/financeira.py` — `montar_fluxo(premissas)` **puro** (validação + curvas + blocos +
  fluxo + indicadores); formatador pt-BR no backend.
- `routers/financeira.py` — `POST`/`GET /analises/{id}/financeira`; resolve lotes via
  aproveitamento da análise (§3.1); persiste premissas+resultado em volume.
- `models/schemas.py` — `PremissasFinanceiraIn`, `BlocoOut`, `LinhaFluxoOut`,
  `IndicadoresOut`, `FinanceiraOut`.
- Frontend: item "Financeira" na sidebar + `CardFinanceira` (formulário de premissas com
  defaults rotulados e badges de origem; tabela do fluxo; KPIs VGV/resultado/exposição via
  `onData`). Sem conta no front.
- Testes: `tests/test_financeira.py` (Caso Fechado A + variações, offline, determinísticos).

A spec fixa **contrato + critérios**; o resto é latitude. **Sem LLM, sem rede, sem
credencial** — aritmética determinística sobre premissas declaradas, com proveniência.
