# Pedido de spec — Fase 1.8 (Extração assistida da LUOS)

> Para a sessão de especificação (claude.ai). Contexto: a Fase 2.3 está **concluída e
> validada ao vivo**; a próxima na ordem de execução (ARCHITECTURE §0) é a **1.8**, que
> ainda está só catalogada ("a especificar quando chegar a vez"). Este documento dá o
> contexto para você escrever a spec da 1.8 no mesmo formato da 2.3.

## 1. Estado atual (o que já existe e a 1.8 deve respeitar)
- **Concluídas e validadas:** 1 → 1.5 → 1.7 → 2.1 → 2.2 → 2.3. Branch `claude/eager-dirac-IoO3K`.
  **82+ testes verdes; `tsc` limpo.**
- **Jurisdição (1.7):** detecção de município por malha IBGE + override por nome + divisa;
  cobertura `BASE_FEDERAL`/`PARCIAL_UF`/`COMPLETA`. Hoje o relatório estampa "Lote mínimo
  municipal não considerado / doação não considerada / zoneamento não considerado" quando
  **não há perfil municipal carregado** — exatamente o buraco que a 1.8 preenche.
- **Aproveitável (contrato vigente, §6-A):** `aproveitável = total − UNIÃO(mata ∪ APP ∪
  faixas)`; **vias e doação NÃO entram** hoje. O encadeamento já decidido (§6-A item 5):
  `teto (hoje) → + diretriz 1.8 (doação + lote mínimo legal) → + projeto urbanístico = nº realista`.
  **A 1.8 é quem reintroduz doação e lote mínimo legal no número.**
- **Regime (1.7):** URBANO usa **lote mínimo declarado pelo usuário** (interino, rotulado
  "pendente extração da LUOS — Fase 1.8") e **modalidade é só rótulo**. A 1.8 substitui o
  lote declarado pelo extraído e faz a **modalidade voltar a ter regra** (lote/doação por
  modalidade).
- **Doação (decisão registrada):** é **parâmetro que pode ser 0** (alguns municípios não
  exigem mínimo) — nunca constante no código; só entra no número via perfil municipal.

## 2. O que a 1.8 precisa entregar (esboço — a spec detalha)
- **Entrada:** PDF da LUOS / lei de parcelamento / diretriz municipal (upload do operador).
- **Leitura por LLM** (único uso de LLM no caminho de leitura, ARCHITECTURE §2): extrair, por
  **zona/modalidade**, os parâmetros — lote mínimo legal, frente mínima, % de doação (sistema
  viário / áreas verdes / institucional), taxa de ocupação/CA se houver, recuos.
- **Validação humana OBRIGATÓRIA + proveniência por artigo:** cada número proposto pelo LLM
  vem com a citação (artigo/inciso/página) e **só vira perfil depois que o operador confirma**.
  Nada entra no cálculo sem o "OK" humano. Determinismo do número é preservado: o LLM **lê e
  propõe**, não decide; o cálculo segue no backend.
- **Saída → perfil municipal:** alimenta a jurisdição (eleva a cobertura para `COMPLETA`/zona)
  e **reintroduz doação + lote legal** no aproveitamento (deixa de ser "teto" puro).

## 3. Pontos que a spec precisa fixar (sugestões de contrato/decisões vetáveis)
- **Formato do perfil municipal** (schema): por zona? por modalidade? como casar a zona da
  LUOS com a localização da gleba (ainda não temos zoneamento geométrico municipal)?
- **Fluxo de validação humana:** tela de revisão item-a-item (propor → editar → confirmar),
  com a citação ao lado. Como persistir o perfil confirmado (arquivo/volume, como a malha?).
- **Proveniência:** cada parâmetro carrega artigo + página + "validado por humano em DD/MM".
- **Como o número muda:** com perfil confirmado, `aproveitável` passa a descontar **doação
  (% da modalidade)** e o lote mínimo passa a ser o **legal** (não o declarado). Definir se
  isso troca o headline ou vira um segundo cenário "com diretriz municipal".
- **Degradação:** sem PDF/sem confirmação → comportamento de hoje (lote declarado, sem doação),
  rotulado. Nunca inventar índice de LUOS.
- **Modelo/limites do LLM:** qual provider, como lidar com PDF ruim/escaneado (OCR?), como
  garantir que o LLM não "alucine" um artigo (validação humana é a rede de segurança).
- **Riscos a registrar:** é a fase mais delicada; a spec deve deixar o checklist de aceite
  bem apertado (proveniência por artigo, nada sem confirmação humana, não-regressão das
  fases 1–2.3).

## 4. Restrições inegociáveis herdadas (não contradizer)
- Cálculo numérico só no backend; LLM nunca decide número (ARCHITECTURE §2).
- Todo número com proveniência; determinismo (mesma entrada → mesma saída).
- Frontend só renderiza JSON. Fontes injetáveis; testes offline com stubs.
- Não-regressão: suítes de 1, 1.5, 1.7, 2, 2.1, 2.2, 2.3 continuam verdes.

> Peça à sessão de spec: produzir `docs/fase-1.8-luos.md` no formato da 2.3 (objetivo,
> não-regressão, como funciona, contratos de API, critérios de aceite testáveis, fora de
> escopo, arquivos esperados) — e marcar claramente as **decisões de produto vetáveis**.
