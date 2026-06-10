# Pedido de spec — Fase 4 (Financeira)

> Para a sessão de especificação (claude.ai). Contexto: **1 → 1.5 → 1.7 → 1.8 → 2 → 2.1 →
> 2.2 → 2.3 → 2.5 → 3 → 3.5 concluídas e validadas** (148 testes; dashboard profissional no
> ar; jurídico documental testado com matrícula real). A próxima do roadmap (ARCHITECTURE
> §0) é a **Fase 4 — Financeira**: o fluxo de caixa do empreendimento — **é onde a planilha
> do curso finalmente entra**, com as correções já registradas na §9. Este documento dá o
> contexto para você escrever `docs/fase-4-financeira.md` no formato das specs anteriores
> (2.3/3 são os melhores exemplos).

## 1. Estado atual (o que já existe e a 4 deve consumir)

- **O motor já produz os lotes** — o insumo central da financeira. `POST
  /analises/{id}/aproveitamento` devolve três números de lotes, em ordem de autoridade:
  1. **`cenario_diretriz.n_lotes`** — com doação municipal + lote legal da zona confirmada
     (headline urbano quando há perfil 1.8 confirmado). Ex. real São Roque/MUE: **120 lotes**.
  2. `n_lotes_teto` — teto físico (aproveitável ÷ lote declarado), sem doação/vias.
  3. `cenario_otimista.n_lotes_teto` — hipotético (verde a verificar liberado).
  A spec deve fixar **qual alimenta o caso-base** (sugestão: diretriz quando existe, senão
  teto **com aviso de que superestima**) e se os outros viram cenários.
- **Vias NÃO estão descontadas** em nenhum número (decisão §6-A: vias/doação reais dependem
  do projeto). A financeira precisa tratar isso como **premissa declarada** (ex.: % de
  eficiência do projeto urbano) — nunca como fato.
- **Toda dimensão = um router + um card** (encaixe pronto: sidebar `secoes.tsx`, `onData`
  para KPIs). Frontend **só renderiza JSON** (§2) — **nenhuma conta no front**, nem juros.
- **Áreas/contexto disponíveis por análise:** área total, aproveitável, doação m² (cenário
  diretriz), município/UF, restrições (ambiental/declividade/jurídico) — úteis para compor
  premissas e ressalvas, não para inventar preço.

## 2. Correções da §9 que a spec DEVE incorporar (erros conhecidos da planilha do curso)

1. **RET 1%/4% NÃO se aplica a loteamento** (é de incorporação). O `5,93%` da planilha é
   incorporação no lucro presumido (art. 4º Lei 10.931/2004). Loteamento → **Lucro
   Presumido ou Lucro Real**, e **tributação é PARÂMETRO validável, nunca constante** —
   cada alíquota com proveniência ("declarado pelo usuário" / "default rotulado, confirme
   com contador").
2. **"Aproveitamento 74%/60%" não tem âncora legal** — é regra de mercado; se a spec usar
   um % de eficiência de projeto como default, deve ser **editável e rotulado**.
3. Todo default herdado da planilha entra como **premissa editável com aviso**, jamais
   número escondido na fórmula.

## 3. O que a Fase 4 precisa entregar (esboço — a spec detalha e decide)

Fronteira já fixada no roadmap: **a 4 monta o FLUXO; a 5 (Econômica) avalia o fluxo**
(VPL/TIR/payback ficam para a 5 — não antecipar).

- **Entradas (todas declaradas, com defaults rotulados):** preço médio do lote (R$ ou
  R$/m²) — *a precificação de mercado é dimensão futura; aqui é input*; custo de
  urbanização (R$/m² ou R$/lote); curva/prazo de vendas e de obra; comissão; aquisição da
  gleba (compra à vista/parcelada/**permuta** % do VGV ou em lotes); regime tributário +
  alíquotas; despesas (projetos/aprovação, marketing, administração); inadimplência
  opcional.
- **Saídas (determinísticas):** VGV; custos por bloco; impostos; resultado nominal e
  margem; **fluxo de caixa por período** (insumo da Fase 5); exposição máxima de caixa.
  Cada linha com proveniência da premissa que a gerou.
- **Cenários:** ao menos caso-base (lotes da diretriz) e, se barato, teto/otimista como
  variantes informativas — espelhando o padrão aditivo das fases 2.3/1.8.

## 4. Pontos que a spec precisa fixar (decisões vetáveis)

- **Origem dos lotes do caso-base** e rotulagem quando cair no teto físico (§1).
- **Contrato**: `POST /analises/{id}/financeira` (params no corpo, como o aproveitamento)
  — shape do fluxo (granularidade mensal? trimestral? parametrizada?).
- **Persistência das premissas** por análise (padrão volume da 1.8/3) — o operador não
  deve redigitar tudo a cada sessão; premissas confirmadas com `validado_por`?
- **Modelo tributário**: quais regimes oferecer (Presumido/Real), o que é calculado × o
  que é só parâmetro multiplicado; ressalva "confirme com contador" obrigatória.
- **Permuta**: % do VGV vs lotes físicos — como entra no fluxo e no VGV líquido.
- **Sem dado externo, sem LLM, sem índice de inflação automático** no MVP (valores
  nominais; indexação é evolução) — confirmar/vetar.
- **A planilha do curso é o material de referência da sessão de spec** — o operador a
  fornece; a spec extrai a estrutura dela (blocos de custo, curva) e **descarta os erros
  da §9**. Valores-ouro dos testes devem vir de um caso fechado na planilha corrigida.

## 5. Restrições inegociáveis herdadas (não contradizer)

- Cálculo numérico só no backend; **LLM em lugar nenhum desta fase** (é aritmética pura).
- Determinismo: mesmas premissas → mesmo fluxo, sempre. Testes com **valores-ouro**.
- Toda premissa com proveniência (declarada × default rotulado); todo número auditável.
- Frontend só renderiza JSON (inclusive formatação de moeda — backend manda string pt-BR,
  padrão da 3.5, ou number + máscara fixa: a spec decide e fixa o contrato).
- Degradação honesta: sem premissa essencial → pede, não chuta. Não-regressão 1…3.5.

> Peça à sessão de spec: produzir `docs/fase-4-financeira.md` no formato das anteriores
> (objetivo, não-regressão, como funciona, contrato de API, critérios de aceite com
> valores-ouro da planilha corrigida, fora de escopo, arquivos esperados), marcando as
> **decisões vetáveis** — sobretudo a origem dos lotes do caso-base, o modelo tributário
> e a fronteira 4×5 (fluxo × avaliação).
