# Pedido de spec — Fase 5 (Econômica)

> Para a sessão de especificação (claude.ai). Contexto: **1 → … → 4 → 4.1 → 4.2 concluídas e
> validadas** (195 testes + 4 skip). A Fase 4 (e os incrementos 4.1 PRICE / 4.2 wizard +
> parceria) **padronizou o fluxo de caixa mensal** — a Fase 5 é **curta a partir daqui**: ela
> só **AVALIA** esse fluxo (VPL/TIR/TMA/payback/sensibilidade). Este documento dá o contexto
> para escrever `docs/fase-5-economica.md` no formato das specs anteriores (a 4 é o melhor
> exemplo, mesma família). O `CardFinanceira` já deixou os **slots `vpl`/`tir`/`payback` com
> status `pendente`** no semáforo — a 5 só os preenche.

## 0. Decisões já tomadas pelo OPERADOR (2026-06-12) — a spec parte daqui

1. **TMA em termos de IPCA (taxa REAL).** Decisão do operador: *"loteamento não usa PRICE,
   coloque IPCA."* Recebível de loteamento é **corrigido por IPCA** — logo a TMA da Fase 5 é
   uma **taxa real (spread acima do IPCA)**, não uma taxa nominal solta. **A spec PRECISA
   resolver a consistência nominal × real** entre o fluxo que a Fase 4 entrega e o desconto da
   Fase 5 (ver §3, item TMA — agora o ponto central). A Fase 4 está **travada/validada**: a 5
   não a reescreve; ela decide como tratar (descontar em real sobre fluxo já indexado, ou
   deflacionar, etc.) — mas **explicitamente e com proveniência**, nunca escondido.
2. **Sensibilidade no MVP = só curva VPL × TMA.** Sem ±% em preço/custo nesta fase (fica para
   evolução). Responde "a que taxa o VPL zera" (≈ TIR) de forma barata e determinística.
3. **A spec será escrita na sessão de especificação (claude.ai)**, não na sessão de
   implementação — este handoff é o insumo. (Implementação só começa com a
   `docs/fase-5-economica.md` em mãos.)

## 1. Estado atual (o que a 5 consome — já pronto)

- **A Fase 4 entrega o `fluxo` mês a mês** (`GET /analises/{id}/financeira` → `FinanceiraOut`):
  cada linha `{mes, entradas, saidas, liquido, acumulado}` + `_fmt` pt-BR. Já há
  `indicadores` **nominais** (resultado_nominal, margem, exposição máxima, horizonte). A 5
  **não recalcula o fluxo** — recebe/lê o mesmo `fluxo` e aplica desconto temporal.
- **Fronteira já fixada (4×5):** a 4 é nominal; **VPL/TIR/TMA/payback são EXCLUSIVOS da 5**
  (os testes da 4 garantem que nenhum desses aparece lá). A 5 não muda a 4.
- **Padrões herdados (obrigatórios):** aritmética pura (sem LLM/rede/credencial);
  determinismo + valores-ouro; toda saída com `_fmt` no backend (§2, front não calcula);
  premissa com proveniência (declarado × default rotulado); degradação honesta.
- **Encaixe pronto no front:** dimensão = um router + um card (sidebar `secoes.tsx`,
  `onData` para KPIs). O `CardFinanceira` já mostra o fluxo; a 5 vira um card "Econômica"
  que consome o mesmo resultado.

## 2. O que a Fase 5 precisa entregar (esboço — a spec detalha e decide)

- **Entradas:** o `fluxo` da 4 (lido da análise) + **TMA real** (taxa mínima de atratividade
  **acima do IPCA** — ver §0.1; declarada com proveniência, sem default escondido; decidir
  unidade e conversão para descontar o fluxo mensal) + opcionais (data-base, expectativa de
  IPCA se o tratamento nominal×real exigir, periodicidade).
- **Saídas (determinísticas) sobre o fluxo:**
  - **VPL** à TMA (e talvez uma curva VPL × taxa para leitura);
  - **TIR** (mensal e anualizada) — método numérico robusto (bissecção/Newton com
    fallback), tratando o caso **sem raiz real / múltiplas trocas de sinal** com honestidade
    (não inventar TIR; rotular "indefinida/múltipla");
  - **payback simples** e **payback descontado** (mês em que o acumulado/descontado vira ≥0;
    "não recuperado no horizonte" se não ocorrer);
  - **exposição máxima descontada** (opcional); **índice de lucratividade** (VPL/investimento)
    se fizer sentido.
- **Sensibilidade (MVP — decidido em §0.2):** **só a curva VPL × TMA** para um range de taxa
  (ex.: deflator real de X% a Y%). **Sem** ±% em preço/custo nesta fase (evolução).
- **Leitura/veredito de triagem:** texto rotulado ("VPL>0 à TMA X% → cria valor"; "TIR < TMA
  → destrói"), **sempre com a ressalva** §1-A (premissas do usuário; não é recomendação de
  investimento).

## 3. Pontos que a spec precisa fixar (decisões vetáveis)

- **Contrato:** `POST /analises/{id}/economica` (TMA + opções no corpo) vs `GET`. Como obtém o
  fluxo — relê a persistência da 4 (recomendado) ou recebe o fluxo no corpo? (Reler garante
  consistência e evita o front mandar números.)
- **TMA real × IPCA (PONTO CENTRAL — §0.1):** o operador fixou que loteamento é corrigido por
  **IPCA**, logo a TMA é **real**. A spec deve decidir e deixar EXPLÍCITO: (a) o fluxo da Fase 4
  é nominal ou já em termos reais? (b) descontamos o fluxo por uma **taxa real** direto, ou
  deflacionamos por IPCA e depois descontamos? (c) unidade da TMA real (mensal/anual) e
  conversão; **sem default escondido** (no máximo um "exemplo, defina sua TMA"). É a premissa
  que decide o veredito — e a relação nominal×real não pode ficar implícita.
- **TIR degenerada:** convenção para fluxo sem investimento inicial, sem troca de sinal, ou
  com múltiplas raízes — rótulo honesto, nunca um número arbitrário.
- **Periodicidade:** o fluxo da 4 é mensal; VPL/TIR mensais com anualização exibida — confirmar.
- ~~**Escopo de sensibilidade** no MVP~~ → **decidido (§0.2): só VPL×TMA.**
- **Persistência** das premissas econômicas por análise (padrão 1.8/3/4).

## 4. Restrições inegociáveis herdadas (não contradizer)

- Cálculo só no backend; **sem LLM nesta fase** (matemática financeira pura).
- Determinismo + valores-ouro (um "Caso Fechado B": pegar o fluxo do Caso Fechado A da 4 e
  fixar VPL/TIR/payback à mão para uma TMA dada).
- Toda saída com `_fmt`; toda premissa com proveniência; ressalva §1-A presente.
- Não-regressão 1…4; a 4 permanece **nominal** (a 5 não escreve na 4).

> Peça à sessão de spec: produzir `docs/fase-5-economica.md` no formato da 4 (objetivo,
> não-regressão, como funciona, contrato de API, critérios de aceite com **valores-ouro
> calculados sobre o fluxo do Caso Fechado A**, fora de escopo, arquivos esperados),
> marcando as **decisões vetáveis** — sobretudo a unidade da TMA, o tratamento da TIR
> degenerada e o escopo da sensibilidade.
