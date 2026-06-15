# Pedido de spec — Fase 9 (Urbanismo — projeto urbanístico proposto por IA)

> Para a sessão de especificação (claude.ai). Contexto: **fases 1 → … → 6 + 7 (laudo) + 8
> (agrupamento) concluídas e validadas** (255 testes backend + 4 front; `tsc`/`next build`/
> vitest limpos). A espinha dorsal KMZ → geometria → ambiental → jurídico → financeiro →
> econômico → localização → laudo está fechada. A Fase 9 é a **primeira que produz um
> TRAÇADO**: uma proposta de parcelamento (malha viária + quadras + lotes + áreas
> obrigatórias) **sugerida por um modelo de IA** e **medida/validada pelo motor
> determinístico**. Este documento é o insumo para escrever `docs/fase-9-urbanismo.md` no
> formato das specs anteriores (a 1.8, a 4 e a 5 são os melhores exemplos: a 1.8 porque é a
> referência de **IA na borda + gate humano**; a 4/5 pelo rigor de contrato + valores-ouro).

## 0. Por que esta fase já estava prevista

O `ARCHITECTURE.md` **anteviu** esta fase em dois pontos — ela fecha uma lacuna desenhada,
não é terreno novo:

- **§6-A, item 5 (encadeamento do nº de lotes):**
  `teto físico → + diretriz 1.8 (doação + lote legal) → + PROJETO URBANÍSTICO (% vias + % lazer) = nº de lotes realista`.
  Hoje o produto para no penúltimo degrau. A Fase 9 entrega o último: **% de vias e % de
  lazer deixam de ser desconhecidos** porque passam a vir de um traçado concreto.
- **§7 (tabela de dimensões) e §1-A (profissionais insubstituíveis):** o **urbanista** é quem
  faz o projeto + as diretrizes da gleba (art. 6º da Lei 6.766/79). O tool **calcula o teto
  físico**; "vias/lazer/doação real são do projeto". A Fase 9 não troca o urbanista — produz
  uma **proposta de triagem** para orientar onde ele vai mexer e quanto a gleba comporta.

## 1. Decisão já tomada pelo OPERADOR — a spec parte daqui

1. **Escopo do MVP = parcelamento completo + áreas obrigatórias.** A proposta da IA já entrega,
   no primeiro incremento testável: **malha viária + quadras + lotes + áreas públicas
   (institucional + verde/lazer)**, com o **quadro de áreas medido contra os % legais** que o
   perfil municipal (1.8) já fornece (doação, lote legal da zona). Não começar por "só
   esqueleto".
2. **A IA entra no projeto** (o operador quer a IA propondo o traçado) — *como* ela entra (que
   papel exato, em que formato de saída) é a **primeira decisão de design** que esta spec
   resolve (§3.1). O operador não fixou o mecanismo; pediu que a sessão de spec decida com os
   trade-offs à vista.
3. **A spec será escrita na sessão de especificação (claude.ai)**, não aqui. Implementação só
   começa com `docs/fase-9-urbanismo.md` em mãos.

## 2. Restrições inegociáveis herdadas (a spec respeita, não revota)

Esta é a fase de **maior tensão com as regras do projeto** — por isso o cuidado. Nenhuma das
abaixo pode ser quebrada; a spec precisa mostrar **explicitamente** como cada uma é honrada.

- **Regra 1 / §2 — o número mora no Python, nunca no LLM; a IA fica na BORDA.** A fronteira do
  projeto é entre *propor um desenho* (onde IA é bem-vinda, como já é em 1.8/3 para ler
  documento) e *medir/decidir o número* (área, %, nº de lotes — determinístico, Python, sem
  LLM, jamais). **Nenhum número que aparece no laudo pode ter sido calculado pelo LLM.** O
  padrão já existe no projeto: `ExtratorLUOS`/`ExtratorDocumento` — o LLM **lê e propõe**, o
  humano confirma, o Python calcula. A Fase 9 é a versão geométrica disso: o LLM **propõe um
  traçado**, o motor **mede**.
- **Regra 4 — determinismo (mesma entrada → mesma saída).** Um LLM é não-determinístico por
  natureza. A spec precisa reconciliar isso sem contaminar o caminho determinístico do laudo
  (ver §3.2).
- **Regra 5 — não inventar dado ausente.** A proposta respeita o que o motor já sabe da gleba:
  não loteia sobre APP, declividade ≥30%, verde-dura, faixa não-edificável, servidão de LT
  (tudo já computado nas fases 2.x). A **área aproveitável** é a tela; o resto é restrição.
- **§1-A — pré-análise e alertas, não laudo; linguagem.** A proposta é **triagem**, **não
  projeto aprovável**: não substitui o urbanista nem as diretrizes da gleba (art. 6º Lei
  6.766). O texto **nunca** diz "projeto aprovado/viável/regular"; sempre "proposta de
  triagem — submeter a projeto de urbanista e às diretrizes da prefeitura". Ausência de
  conflito ≠ ausência do problema.
- **§2 (front) — o front só renderiza JSON.** O traçado vem como **GeoJSON do backend**
  (mesmo canal do polígono/buffers, já desenhado no mapa Leaflet). Zero geo-matemática em JS;
  o front não recalcula área nem nº de lotes — exibe o que o backend mediu.
- **Não-regressão 1…8.** A Fase 9 **não reescreve** nenhuma dimensão anterior. O aproveitável,
  o financeiro, o jurídico continuam idênticos com/sem a proposta (critério-coração, no espírito
  do nº 8 das fases 6/7).

## 3. Decisões que a spec PRECISA fixar (vetáveis)

### 3.1 Papel da IA — a decisão central (define toda a arquitetura)

Três caminhos, com o trade-off. **Recomendação para a sessão de spec: caminho A** (mantém a IA
mais longe do número e é o mais robusto, porque LLM erra geometria fina).

- **(A) IA propõe PARÂMETROS, o Python desenha e mede.** O LLM escolhe a *estratégia* de projeto
  (orientação/dimensão das quadras, largura de via, frente/profundidade de lote, onde concentrar
  verde/institucional, padrão de malha) a partir do contexto da gleba; um **gerador
  determinístico em Python** materializa a geometria (quadras/lotes/vias) dentro da área
  aproveitável e mede tudo. **Nenhum número e nenhuma coordenada vêm do LLM.** É a leitura mais
  fiel ao §2 (IA na borda escolhendo estratégia; geometria e número no Python). Custo: precisa de
  um gerador geométrico determinístico (a peça mais pesada de engenharia da fase).
- **(B) IA desenha a geometria (GeoJSON), o Python só valida.** O LLM devolve o traçado já como
  coordenadas; o Python mede e valida contra a lei e as restrições. Mais livre visualmente, mas
  (i) LLM erra geometria precisa (lotes que não fecham, sobreposição), (ii) o resultado vira
  não-determinístico de ponta a ponta, e (iii) aproxima perigosamente o LLM do número. **Maior
  risco de regressão de princípio.**
- **(C) IA faz zoneamento ESQUEMÁTICO, o Python detalha.** Meio-termo: o LLM marca regiões grossas
  (eixo da via principal, mancha de verde, lote institucional); o Python encaixa a malha e loteia
  dentro delas e mede. Equilíbrio entre liberdade de projeto e controle do número.

**A spec precisa cravar um caminho e justificar**, mostrando onde exatamente o LLM para e o
Python começa, e qual o **artefato que cruza essa fronteira** (parâmetros JSON? regiões GeoJSON
grosseiras? traçado completo?).

### 3.2 Determinismo (regra 4) — como reconciliar com um LLM

Recomendação: **camada criativa separada, rotulada e versionada** (não forçar o LLM a ser
determinístico). O laudo/análise determinístico das fases 1…8 **continua intocado**. A proposta
urbanística é uma **camada explicitamente não-determinística**: gera-se a proposta, **salva-se o
snapshot** (parâmetros + GeoJSON resultante), e o motor **mede sobre o snapshot de forma
determinística** — "mesmo snapshot → mesma medição, sempre". O usuário pode pedir "nova proposta"
(gera outra, versionada). Assim a regra 4 vale onde importa (o número medido é reproduzível dado o
snapshot) sem fingir que o LLM é determinístico. Alternativas a considerar/descartar: forçar
seed/temperatura 0 + cache (reduz mas não garante; mistura IA no caminho determinístico); ou
gerar o traçado por heurística pura sem IA (cumpre a regra 4 trivialmente, mas abre mão da IA que
o operador pediu).

### 3.3 Como o resultado se conecta às outras dimensões (sem regressão)

- **Aproveitável (§6-A item 5):** a proposta fecha o último degrau — `% vias` e `% lazer` deixam
  de ser desconhecidos. A spec decide se isso entra como **mais um cenário aditivo** (padrão da
  "decisão A": não troca o headline silenciosamente; o front escolhe qual destacar) ou se passa a
  ser o headline quando há proposta. **Recomendação: aditivo** (coerente com `cenario_diretriz` e
  `cenario_otimista`), com o nº de lotes da proposta rotulado "realista — sob o traçado proposto".
- **Financeira (4.x):** hoje o nº de lotes do caso-base é `diretriz > teto > declarado` (§3.1 da
  Fase 4, repassado pelo front). A spec decide se a proposta vira **mais uma origem** de nº de
  lotes (ex.: `proposta > diretriz > teto`), sempre **repassada pelo front** (§2, o front não
  recalcula). Não mudar o motor financeiro além de aceitar essa origem.
- **Laudo (Fase 7):** a proposta deve poder virar uma seção do laudo (quadro de áreas + nº de
  lotes realista + a ressalva §1-A). A Fase 7 recebe as dimensões no corpo — encaixe natural.

### 3.4 Contrato de API e schema de saída

- **Entrada:** o `analise_id` (geometria + restrições já computadas), a **zona/perfil confirmado**
  (1.8, para lote legal + doação), e parâmetros do operador (ex.: alvo de lote, preferências).
  Avaliar se aceita o operador **fixar/editar** alguns parâmetros antes de gerar.
- **Saída (`UrbanismoOut`, medida no backend):** **GeoJSON** das camadas (lotes, quadras, vias,
  áreas institucional/verde) + **quadro de áreas** (área de cada uso, % sobre a gleba, nº de lotes)
  + **conformidade** com os % legais do perfil (doação atendida? lote ≥ legal da zona?) + a
  **proveniência da proposta** (qual modelo, qual snapshot/versão, que parâmetros, que data) +
  ressalva §1-A. Todo número com `_fmt` pt-BR no backend.
- **Endpoints:** algo como `POST /api/analises/{id}/urbanismo` (gera/regenera a proposta) +
  `GET` (relê o snapshot persistido). Persistência por análise em volume (padrão das fases 4/5,
  gitignored). **Gate humano?** Decidir se a proposta nasce `proposto` e só `confirmado` entra no
  número (padrão 1.8/3) — recomendado pelo §1-A (o traçado é julgamento de urbanista), pelo menos
  como rótulo "proposta não validada por urbanista".
- **Degradação honesta:** sem área aproveitável suficiente, sem perfil de zona, egress/credencial
  de LLM ausente → mensagem acionável, nunca traçado inventado.

### 3.5 Infra de LLM (reusar o que já existe)

Não é credencial nova. O projeto já tem o padrão desde a 1.8/3:

- `ANTHROPIC_API_KEY` (gated; ausência → 503 acionável, não quebra o resto), **TLS corporativa**
  (`LUOS_CA_BUNDLE` / `LUOS_TLS_INSECURE`), `load_dotenv`, **gerador injetável** (à la
  `ExtratorLUOS`/`get_extrator_documento`) + **flag de desligar** + **stub offline** para os
  testes rodarem 100% sem rede. Modelo: o mesmo `claude-opus-4-8` já usado, com **structured
  outputs / tool use forçado** (não parsear prosa) para a proposta de parâmetros.
- **Decisão de design:** o gerador geométrico determinístico (caminho A) é **Python puro**
  (shapely/pyproj), separável e testável offline — espelhar a separação `FonteDEM` (I/O) ×
  `analisar_declividade` (puro) da 2.5: a parte com LLM/rede fica isolada da parte que mede.

### 3.6 Valores-ouro

A spec precisa de um **caso fechado** com o quadro de áreas conferido. O candidato natural é o
**projeto real do operador** (o "modelo de projeto urbanístico de exemplo" que ele vai fornecer à
sessão de spec) — provavelmente **São Roque / TIV 5.0** (gleba 181.991 m², **167 lotes** de ~447
m², **vias 15,3%**, **verdes 28%**), que o `ARCHITECTURE.md` já cita como referência. Os testes
aferem que **o motor mede** esse traçado e reproduz o quadro de áreas/nº de lotes — não que o LLM
adivinhe o traçado (a parte criativa é não-determinística; o teste trava a **medição** sobre um
snapshot fixo, e o stub do gerador devolve um traçado canônico).

## 4. O que o OPERADOR precisa fornecer à sessão de spec

- **O modelo de projeto urbanístico de exemplo** (KMZ/DWG/PDF/print do parcelamento-referência —
  idealmente o de São Roque/TIV 5.0). Ele ancora: o formato de saída esperado, o que conta como
  lote/quadra/via/área institucional, e o **quadro de áreas-ouro**. Sem ele a spec fica no
  genérico.

## 5. Fora de escopo (registrar para não inflar a fase)

- Projeto aprovável / diretrizes da gleba (art. 6º Lei 6.766) — é do urbanista; o tool faz
  triagem. Otimização multi-objetivo do traçado (maximizar lotes), terraplenagem/drenagem/redes,
  3D, exportação para CAD — evolução. Edição interativa do traçado na tela (arrastar lotes) —
  evolução; o MVP gera e mede, a edição fina é do projeto real.

> Peça à sessão de spec: produzir `docs/fase-9-urbanismo.md` no formato da 1.8/4/5 (objetivo,
> não-regressão, como funciona — **com a fronteira §2 desenhada explicitamente: onde o LLM para,
> onde o Python mede**, a estratégia de determinismo da §3.2, contrato de API + schema GeoJSON,
> **critérios de aceite com os valores-ouro do projeto-exemplo**, fora de escopo, arquivos
> esperados), cravando as **decisões vetáveis** — sobretudo (1) o **papel da IA** (§3.1), (2) o
> tratamento do **determinismo** (§3.2) e (3) se a proposta é **cenário aditivo** ou vira headline
> no aproveitável/financeira (§3.3).
