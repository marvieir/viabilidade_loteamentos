# Pedido de spec — Fase 3 (Jurídica)

> Para a sessão de especificação (claude.ai). Contexto: as fases **1 → 1.5 → 1.7 → 1.8 →
> 2 → 2.1 → 2.2 → 2.3 → 2.5** estão **concluídas e validadas ao vivo** (a 2.5 em São Roque,
> com egress keyless do Copernicus confirmado no container). A interface passou por um
> **redesign** (dashboard profissional — ver §1.5 abaixo). A próxima na ordem de execução
> (ARCHITECTURE §0, item 11) é a **Fase 3 — Jurídica**, ainda só catalogada ("perfil
> municipal/estadual; consome o que a 1.8 extraiu"). Este documento dá o contexto para você
> escrever `docs/fase-3-juridica.md` no mesmo formato da 1.8/2.3.

## 1. Estado atual (o que já existe e a 3 deve respeitar)
- **Concluídas e validadas:** 1 → 1.5 → 1.7 → 1.8 → 2 → 2.1 → 2.2 → 2.3 → 2.5.
  Branch `claude/eager-dirac-IoO3K`. **120 testes + 3 skip; `tsc` limpo; `next build` ok.**
- **Jurisdição (1.7):** detecção de município (malha IBGE) + override por nome + divisa;
  cobertura `BASE_FEDERAL`/`PARCIAL_UF`/`COMPLETA`. Hoje, sem perfil municipal, o relatório
  estampa "lote/doação/zoneamento municipal não considerado" e degrada para nível federal.
- **Perfil municipal (1.8) — JÁ EXTRAI MAIS DO QUE ENTRA NO NÚMERO.** A 1.8 lê a LUOS por
  LLM (na borda: lê e **propõe** com citação por artigo) e produz um `PerfilMunicipal`
  (`backend/app/models/schemas.py`) que só vira utilizável com `status=confirmado` (PUT com
  `validado_por` + `data_referencia`). Esse perfil já carrega, **por zona e por modalidade**:
  - `lote_min_m2`, `doacao_pct` → **únicos que entram no aproveitável** hoje (via
    `CenarioDiretrizOut`, aditivo ao headline físico-ambiental).
  - `frente_min_m`, `ca`, `taxa_ocupacao`, `doacao_split` (viário/verde/institucional) →
    **extraídos com proveniência, mas hoje NÃO usados em lugar nenhum.** Os comentários do
    schema dizem literalmente "persiste p/ a dimensão Jurídica (Fase 3)". **Esse é o material
    que a Fase 3 vem consumir.**
- **Aproveitável (contrato vigente):** `aproveitável = total − UNIÃO(mata ∪ APP ∪ faixas ∪
  declividade ≥30%)`; cenário "com diretriz" desconta doação e usa lote legal. A Fase 3
  **não deve mexer no número do aproveitável** (é dimensão de conformidade/triagem legal,
  não de cálculo de lotes) — salvo decisão explícita da spec.
- **Camadas de perfil (`backend/app/perfis/`):** hoje só `fmp_municipios.json` (FMP rural por
  município, INCRA) e `lista_municipios.json` (malha). **Não há ainda camada estadual nem o
  layering federal/estadual/municipal** que o ARCHITECTURE prevê — definir se a 3 o cria.

### 1.5. Frontend já está pronto para receber a dimensão (pós-redesign)
A UI virou um **dashboard** (app shell). Adicionar a dimensão Jurídica é encaixe, não reforma:
- **Sidebar** (`components/shell/secoes.tsx`): cada dimensão é um item `{ id, rotulo, Icone }`.
  A Fase 3 adiciona **um item** ("Jurídico") + ícone inline em `components/Icons.tsx`.
- **Seção/painel** (`app/page.tsx`): cada dimensão é um `<Card*>` montado e exibido quando
  ativo; reporta resultado via `onData` (alimenta os **KPIs** do topo) e overlays via
  `onOverlays*` (alimenta o **mapa-herói**, com toggle de camadas central).
- **Mapa-herói + camadas:** cores/rótulos em `components/mapa/overlays.ts`. Se a Jurídica
  tiver geometria (ex.: faixa non-aedificandi de rodovia/ferrovia), entra como novo overlay.
- **Regra preservada:** o front **só renderiza JSON** — KPIs e cards não recalculam nada.

## 2. O que a Fase 3 precisa entregar (esboço — a spec detalha e decide o escopo)
A tensão central a resolver na spec: **a 1.8 já fez a "leitura municipal".** O que sobra para
a "Jurídica" é **consolidar a conformidade legal** sobre os parâmetros já extraídos + os
níveis federal/estadual. Candidatos de escopo (a spec escolhe/recorta — decisão de produto):
- **(A) Checklist de conformidade municipal** sobre o perfil 1.8 confirmado: confronta a gleba
  e o cenário com `frente_min_m`, `ca`, `taxa_ocupacao`, `doacao_split` (viário/verde/
  institucional), recuos — sinalizando o que é exigência legal vs. o que depende de projeto.
  Cada item com proveniência por artigo (herda da 1.8).
- **(B) Camada federal/estadual** (o "perfil estadual" do nome): exigências da Lei 6.766/79
  **não-geométricas** (já cobrimos APP e ≥30% nas fases 2.x), faixas non-aedificandi de
  rodovia/ferrovia/dutos, legislação estadual de parcelamento, eventuais restrições de uso.
  Definir o **layering** `BASE_FEDERAL → PARCIAL_UF → COMPLETA` e como ele eleva a cobertura.
- **(C) Síntese jurídica da triagem:** um "card Jurídico" que junta os alertas legais já
  dispersos (mineração ANM da 2.1, verde-em-APP da 2.3, vedação ≥30% da 2.5) numa leitura de
  **risco jurídico** rotulada — sem decidir aprovação (continua triagem).

## 3. Pontos que a spec precisa fixar (contratos/decisões vetáveis)
- **Recorte de escopo:** A, B, C ou combinação? O nome no roadmap é "perfil municipal/estadual
  (consome o que a 1.8 extraiu)" — a spec confirma se a 3 é **consumo/conformidade** (não
  cria novo dado pesado) ou se também **cria a camada estadual** (dado novo, fontes, egress).
- **Contrato de API:** `GET /analises/{id}/juridico` devolvendo o quê? (lista de itens
  legais com `status` conforme/atenção/vedado + proveniência + ressalva). Espelhar o formato
  de `AmbientalOut`/`DeclividadeOut` (alertas + proveniência + avisos).
- **Relação com o aproveitável:** confirmar que a 3 **não altera** o número (só sinaliza), ou
  definir exatamente o que entraria (ex.: faixa non-aedificandi vira desconto? — provavelmente
  já é geométrico e caberia nas 2.x, não aqui).
- **Layering de cobertura:** como `frente_min`/`ca`/`taxa_ocupacao` (municipais) e as
  exigências federais/estaduais se combinam e elevam `BASE_FEDERAL → PARCIAL_UF → COMPLETA`.
- **Fontes e determinismo:** se a 3 trouxer dado novo (B), fonte **injetável** + testes
  offline com stub (padrão 2.1/2.2/2.5); se for só consumo (A/C), nada de I/O novo.
- **Degradação honesta:** sem perfil 1.8 confirmado → a 3 mostra o que dá no nível federal e
  **rotula a cobertura** (nunca inventar índice municipal ausente).
- **Proveniência:** cada item jurídico carrega artigo/lei + data + ressalva "triagem, não
  decide aprovação" (herda a disciplina das fases anteriores).

## 4. Restrições inegociáveis herdadas (não contradizer)
- Cálculo numérico só no backend; LLM nunca decide número (ARCHITECTURE §2).
- Todo número/alerta com proveniência; determinismo (mesma entrada → mesma saída).
- Frontend só renderiza JSON; fontes injetáveis; testes offline com stubs.
- Não inventar dado de jurisdição ausente → degradar para federal e rotular cobertura.
- **Não-regressão:** as suítes de 1, 1.5, 1.7, 1.8, 2, 2.1, 2.2, 2.3, 2.5 continuam verdes.

> Peça à sessão de spec: produzir `docs/fase-3-juridica.md` no formato da 1.8/2.3 (objetivo,
> não-regressão, como funciona, contratos de API, critérios de aceite testáveis com
> valores-ouro, fora de escopo, arquivos esperados) — marcando claramente as **decisões de
> produto vetáveis** (sobretudo o recorte de escopo do §2 e se cria ou não a camada estadual).
