# Fase UX — Onboarding e experiência guiada (spec por fases)

**Data:** 21/07/2026 · **Decisões do operador:** trilha SUGERIDA (nunca trava); diretrizes do
município com WARNING de cobertura (não bloqueia); gleba-exemplo curada pelo operador (não
consome quota); trilha mora numa barra compacta no topo + painel expansível (híbrido).

**Problema:** o momento mágico (KMZ → mapa medido) acontece em 30 s, mas depois a plataforma
abre as 8 dimensões de uma vez, sem ordem, sem dizer pré-requisitos nem o que cada análise
entrega. Só o card Financeira tem trilho (wizard) — e é o único sem reclamação de UX.

**Base de pesquisa (jul/2026):** checklist persistente de 3–6 passos > tour de tooltips;
estados vazios orientados (+30–45% de conclusão de tarefa, NN/g); revelação progressiva;
tempo-até-valor como métrica-mãe; quem completa onboarding retém ~3,4× mais em 90 dias.

## Fases (uma por vez; o operador testa entre elas)

| Fase | Entrega | Status |
|---|---|---|
| UX-1 | Trilha da Análise (endpoint + barra + painel) | ESTA FASE |
| UX-2 | Estados vazios orientados em cada card | — |
| UX-3 | Wizards de pré-requisitos: Urbanismo (#17) e Jurídico | — |
| UX-4 | Gleba-exemplo (análise curada, clone leitura, sem quota) | — |
| UX-5 | Evento de ativação medido (junto da MKT-4) | — |

---

## Fase UX-1 — Trilha da Análise

### Contrato (backend decide, frontend renderiza — regra inegociável)

`GET /api/analises/{analise_id}/trilha` (autenticado, dono) →

```json
{
  "passo_atual": "diretrizes",
  "passos": [
    {"id": "gleba",      "titulo": "Gleba carregada",            "estado": "concluido",
     "motivo": "18,71 ha medidos por cálculo geodésico."},
    {"id": "diretrizes", "titulo": "Município e diretrizes",     "estado": "atencao",
     "motivo": "Sem o plano diretor/LUOS a análise roda no nível federal: lote mínimo municipal, doação e zoneamento não são considerados. Envie o PDF no card Aproveitamento para a cobertura completa.",
     "cobertura": "BASE_FEDERAL"},
    {"id": "ambiental",  "titulo": "Pré-análise ambiental",      "estado": "disponivel",
     "motivo": "Cruza APP, vegetação, declividade, UCs e mineração — cada alerta com fonte e data."},
    {"id": "urbanismo",  "titulo": "Pré-projeto urbanístico",    "estado": "disponivel", ...},
    {"id": "juridico",   "titulo": "Pré-análise jurídica",       "estado": "pendente",
     "motivo": "Envie a matrícula (PDF) para extrair a ficha e os ônus."},
    {"id": "financeira", "titulo": "Análise financeira e laudo", "estado": "pendente", ...}
  ]
}
```

- **Estados:** `concluido` | `disponivel` (dá para rodar já) | `atencao` (funciona, mas com
  limitação declarada — o warning âmbar) | `pendente` (falta insumo do usuário).
- **Derivação determinística no backend** (mesma entrada → mesma trilha):
  - `gleba`: sempre `concluido` (a análise existe).
  - `diretrizes`: `concluido` se perfil municipal confirmado (cobertura COMPLETA);
    `atencao` com o texto de cobertura caso contrário; município nulo → `pendente`.
  - `ambiental`: `concluido` se há resultado ambiental no snapshot salvo; senão `disponivel`.
  - `urbanismo`: `concluido` se há proposta no store de urbanismo; senão `disponivel`.
  - `juridico`: `concluido` se há ficha confirmada; `disponivel` se há ficha proposta;
    `pendente` sem documento.
  - `financeira`: `concluido` se há fluxo salvo; `disponivel` se urbanismo concluído
    (tem lotes para precificar); senão `pendente` (motivo aponta o urbanismo).
  - `passo_atual` = primeiro não-`concluido` na ordem.
- A trilha é SUGERIDA: nenhum endpoint passa a exigir passo anterior.

### Frontend

- **Barra compacta** no workspace, sob a TopBar, só com análise aberta: título curto +
  "passo N de 6" + bolinhas de progresso (âmbar para `atencao`). Clique expande.
- **Painel expansível** (dropdown da barra): lista dos 6 passos com estado, motivo e ação
  ("Ir para o card" — rola até o card correspondente). Fecha ao clicar fora.
- **Auto-expandido nas 2 primeiras análises** da conta (contador em localStorage;
  heurística de front, não de negócio).
- **Mobile:** a barra colapsa para um botão flutuante com "N/6".
- Refetch da trilha: ao carregar a análise, ao fechar o painel de qualquer card de dimensão
  e após "Analisar tudo". Sem polling.

### Testes-ouro (backend)

Cenários: análise recém-criada (gleba concluído, diretrizes atenção, ambiental/urbanismo
disponíveis, jurídico/financeira pendentes); com perfil municipal confirmado (diretrizes
concluído); com proposta de urbanismo (urbanismo concluído + financeira disponível);
com ficha jurídica; 401 sem login; 404 de análise alheia.
