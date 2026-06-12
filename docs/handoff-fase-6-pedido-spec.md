# Pedido de spec — Fase 6 (Localização — enriquecimento socioeconômico IBGE)

> Para a sessão de especificação (claude.ai). Contexto: **1 → … → 4.2 → 5 concluídas e
> validadas** (215 testes backend + 4 front). A espinha dorsal KMZ → geometria → ambiental →
> jurídico → financeiro → econômico está fechada. A Fase 6 é a **primeira de
> ENRIQUECIMENTO**: não decide nada, contextualiza a **demanda** (tamanho, dinâmica e poder
> de compra do mercado local) a partir de dados oficiais do município já resolvido. Este
> documento é o insumo para escrever `docs/fase-6-localizacao.md` no formato das specs
> anteriores (a 4 e a 5 são os melhores exemplos).

## 0. Decisões já tomadas pelo OPERADOR (2026-06-12) — a spec parte daqui

1. **Indicadores do MVP (todos os quatro):**
   - **População + densidade + crescimento** (Censo 2010 → 2022): tamanho e dinâmica do mercado.
   - **Renda / PIB per capita**: poder de compra do comprador-alvo.
   - **Déficit / domicílios**: nº de domicílios e, se disponível, sinal de déficit habitacional
     — proxy direto de demanda por lotes (pode exigir fonte além do Censo; ver §3).
   - **Faixa etária / pirâmide**: perfil etário do comprador (mais visual que decisório).
2. **A spec será escrita na sessão de especificação (claude.ai)**, não aqui — este handoff é
   o insumo. Implementação só começa com a `docs/fase-6-localizacao.md` em mãos.

## 1. Decisões de arquitetura já fixadas (regra do projeto — a spec respeita, não revota)

- **Granularidade = município** (`cod_ibge`). A Fase 1.7 já resolve município/UF/IBGE da gleba
  (detecção + override por nome + divisa); a 6 **consome** esse `cod_ibge`. Setor censitário é
  evolução.
- **Puramente informativo (§1-A):** a Localização **não decide viabilidade nem entra em cálculo**
  de nenhuma outra fase. Enriquece o laudo de triagem; nunca vira veredito.
- **Offline / determinístico via arquivo EMBARCADO** (pipeline download+cache, no padrão da
  **lista leve IBGE** `lista_municipios.json` já no repo — "aquisição de dado oficial é pipeline,
  não agente"). **Sem LLM, sem rede em runtime/testes.** Sem dado para o município → **degrada
  honesto** e rotula a cobertura (faltou indicador X), nunca inventa (não-regressão da regra 5).
- **Proveniência obrigatória** por indicador: fonte (Censo 2022, PIB Municipal IBGE, etc.) e
  **ano de referência**. `_fmt` pt-BR no backend (§2): o front só renderiza.

## 2. O que a Fase 6 precisa entregar (esboço — a spec detalha e decide)

- **Entrada:** o `cod_ibge` da análise (já resolvido). Nada vindo do front além disso.
- **Saída (`LocalizacaoOut`, determinística):** os quatro blocos de indicadores acima, cada
  número com `_fmt` e proveniência; um rótulo de **cobertura** (quais indicadores existem para
  aquele município) no espírito `BASE_FEDERAL`/`PARCIAL`/`COMPLETA`; ressalva §1-A
  ("enriquecimento, não recomendação").
- **Contrato:** `GET /api/analises/{id}/localizacao` (sem corpo — o dado é do município, não do
  usuário; é auto-enriquecimento). Persistência opcional (o dado é estável; talvez nem precise).
- **Front:** item "Localização" na sidebar + `CardLocalizacao` — cards/KPIs dos quatro blocos,
  pirâmide etária como gráfico simples (plotagem dos números do backend, zero cálculo no front),
  proveniência visível. Comparação com média da UF/Brasil é desejável se barata (vetável).

## 3. Pontos que a spec precisa fixar (decisões vetáveis)

- **Fonte exata de cada indicador e o recorte embarcado:** população/densidade/idade saem do
  **Censo 2022**; renda do Censo ou PNAD; **PIB per capita** é a série *PIB dos Municípios*
  (IBGE); **déficit habitacional** normalmente é **Fundação João Pinheiro / MUNIC**, não Censo
  direto — a spec decide se entra no MVP como "déficit" ou degrada para "nº de domicílios"
  (proxy) quando a fonte de déficit não cobrir o município. **Não inventar déficit ausente.**
- **Formato do arquivo embarcado:** um JSON por indicador ou um consolidado `socioeco_ibge.json`
  (cod_ibge → indicadores). Tamanho: se ficar grande (~5.570 municípios × vários campos), avaliar
  se vai embarcado (como a lista leve) ou em volume (como a malha geométrica) — decisão de §4 da
  ARCHITECTURE.
- **Crescimento populacional:** método (Censo 2010→2022, % total ou taxa a.a. composta) e como
  exibir.
- **Cobertura/degradação:** rótulos quando faltam indicadores; o que aparece quando o município
  só tem parte dos dados.
- **Valores-ouro:** fixar **São Roque/SP (3550605)** como caso fechado, com os quatro blocos
  conferidos contra a fonte (população 2022, densidade, crescimento 2010→2022, renda/PIB,
  domicílios, faixas etárias) — o teste offline compara contra esses números.
- **Comparação com UF/Brasil** no MVP (sim/não) e **persistência** (precisa? ou recalcula do
  arquivo a cada GET, já que é determinístico).

## 4. Restrições inegociáveis herdadas (não contradizer)

- **Sem LLM, sem rede** nesta fase (dado estruturado oficial = pipeline, não agente).
- **Determinismo + valores-ouro** (Caso Fechado São Roque); testes 100% offline.
- **Não inventar dado de jurisdição/indicador ausente** (regra 5) — degradar e rotular cobertura.
- Toda saída com `_fmt` no backend; toda premissa/indicador com proveniência (fonte + ano).
- **Enriquecimento puro:** não-regressão 1…5; a 6 não escreve em nenhuma fase anterior e não
  participa de cálculo de viabilidade.

> Peça à sessão de spec: produzir `docs/fase-6-localizacao.md` no formato da 4/5 (objetivo,
> não-regressão, como funciona, contrato de API, **critérios de aceite com valores-ouro do
> Caso Fechado São Roque**, fora de escopo, arquivos esperados), marcando as **decisões
> vetáveis** — sobretudo a fonte do **déficit habitacional** (e o fallback para nº de domicílios),
> o formato/local do arquivo embarcado e se há comparação com UF/Brasil no MVP.
