# Fase 2.3 — Severidade do verde (restrição dura × a verificar)

> Refinamento da dimensão **Área verde (2.2)**. Referencia o `ARCHITECTURE.md`
> (seções 2, 4, 6-A) e **não o contradiz**. Próxima na ordem de execução (seção 0).

## 1. Objetivo

Hoje a 2.2 desconta **todo** o verde do aproveitável e trata uma APP de rio e um pasto
arborizado **igual**. Esta fase **decompõe o verde em dois baldes por severidade legal**,
sem mudar o número conservador de triagem:

- **`verde_restricao_dura`** — verde que cai em **APP (curso ou massa d'água) ou Unidade de
  Conservação**. Vegetação legalmente protegida; supressão em geral **proibida**.
- **`verde_a_verificar`** — verde **fora** dessas zonas de proteção de vegetação. Supressão
  **pode** ser autorizada mediante **laudo de engenheiro ambiental + licença** — não é
  proibição, é "a verificar".

Isso responde diretamente à pergunta que justifica o produto: *"vale a pena gastar com due
diligence nesta gleba?"* — mostrando quanto da mata é intocável vs. quanto poderia ser
destravado por um laudo.

**Fronteira mantida (no relatório):** classificar mata como nativa / Mata Atlântica /
suprimível é **laudo de engenheiro em campo, fora do escopo**. Nenhum dado de satélite faz
isso com segurança jurídica. Esta fase **não** emite parecer de supressão — só separa o que
está em zona de proteção legal do que não está.

## 2. O que NÃO muda (não-regressão)

- **O aproveitável de triagem (headline) continua descontando TODO o verde** (conservador).
  O `area_aproveitavel_m2` e o `n_lotes_teto` da 2.2 **não mudam**.
- A união de restrições da seção 6-A (sem dupla contagem) **não muda**.
- A 2.1 (ambiental) e a 2.2 (verde total) permanecem intactas.
- **Sem dado externo novo e sem credencial.** Reusa `get_fonte_vegetacao` (2.2) e
  `get_fonte_camadas` (2.1). Pura geometria, 100% offline-testável.

## 3. Como funciona (determinístico, cálculo só no backend)

Novo módulo `core/severidade_verde.py` — função pura, CRS métrico local (AEQD, igual 2.2):

```
classificar_severidade_verde(verde_geom, camadas) -> SeveridadeVerde
```

Onde `camadas` são as geometrias que a 2.1 já produz (`app`, `app_massa_dagua`, `uc`,
`faixa_nao_edificavel`, `linhas_transmissao`). Lógica:

```
zona_protecao_vegetacao = UNIÃO(app ∪ app_massa_dagua ∪ uc)     # protege a MATA
verde_restricao_dura    = verde_geom ∩ zona_protecao_vegetacao
verde_a_verificar       = verde_geom − zona_protecao_vegetacao
# invariante: restricao_dura + a_verificar = verde_total (tolerância pequena)

zona_nao_edificavel     = UNIÃO(faixa_nao_edificavel ∪ linhas_transmissao)  # impede CONSTRUIR
potencial_desbloqueavel = (verde_a_verificar − zona_nao_edificavel).area    # clamp >= 0
```

**Por que `potencial_desbloqueavel` desconta também faixa/servidão:** suprimir mata sob um
linhão ou na faixa non aedificandi **não** libera área construível — você ainda não pode
construir ali. Só vira área útil potencial o verde a verificar que está **fora** de toda
zona não-edificável.

Tudo por interseção/diferença geométrica (`shapely`), sem LLM, sem agente.

## 4. Contratos de API

### 4.1 `GET /api/analises/{id}/vegetacao` — estende `VegetacaoOut`
Acrescenta o bloco `severidade` (os campos da 2.2 permanecem):

```jsonc
{
  // ... campos existentes da 2.2 (area_total, verde, liquida, percentual,
  //     geojson_verde, proveniencia, avisos, consultada) ...
  "severidade": {                        // null se vegetação OU camadas não consultadas
    "verde_total_m2": 137700,
    "restricao_dura": {
      "area_m2": 19400,
      "pct_do_verde": 0.1409,
      "fontes": ["app", "app_massa_dagua"],   // quais camadas incidiram (uc se houver)
      "geojson": { /* overlay cor "proibido" */ }
    },
    "a_verificar": {
      "area_m2": 118300,
      "pct_do_verde": 0.8591,
      "geojson": { /* overlay cor "atenção" */ }
    },
    "potencial_desbloqueavel_m2": 118300,    // a_verificar − (faixa ∪ servidão); clamp>=0
    "composicao_classes": {                  // opcional; dado já existe na 2.2
      "arvores": 0.90, "arbustiva": 0.10, "umida": 0.0, "mangue": 0.0
    },
    "proveniencia": "verde WorldCover 2021 × APP/UC (ANA/ICMBio, DD/MM); CRS AEQD local",
    "ressalva": "Verde fora de APP/UC PODE ser suprimível mediante laudo de engenheiro ambiental e licença do órgão competente. Triagem, não parecer. Classificação de mata nativa/suprimível exige campo."
  }
}
```

### 4.2 `POST /api/analises/{id}/aproveitamento` — acrescenta `cenario_otimista`
**Headline inalterado.** Adiciona um cenário **informativo e separado**:

```jsonc
{
  // ... saída da 2.2 inalterada (area_aproveitavel_m2, pct_sobre_total, n_lotes_teto...) ...
  "cenario_otimista": {                    // null se severidade indisponível; INFORMATIVO
    "premissa": "supressão autorizada do verde a verificar fora de zonas não-edificáveis",
    "area_aproveitavel_m2": /* aproveitável_conservador + potencial_desbloqueavel */,
    "pct_sobre_total": 0.xx,
    "n_lotes_teto": /* recalculado */,
    "ressalva": "Cenário HIPOTÉTICO. Depende de laudo + licença ambiental. NÃO é o número de triagem (headline) — é o teto se a vegetação a verificar for liberada."
  }
}
```

> **⚠ Única decisão de produto vetoável desta fase:** mostrar o `cenario_otimista` (um
> segundo número no relatório). Minha recomendação é **incluir**, porque é exatamente a
> informação que decide se contratar o engenheiro vale a pena — e ele fica claramente
> rotulado como hipotético, sem virar o headline. Se você preferir relatório de um número
> só, é só vetar e o backend calcula mas o front não exibe.

## 5. Critérios de aceite (testáveis)

1. **Severidade só com ambas as fontes.** `severidade` só é preenchida se vegetação **e**
   camadas ambientais foram consultadas; senão `severidade=null` + aviso honesto
   ("camadas ambientais não consultadas; severidade do verde indisponível"). Nunca inventa.
2. **`verde_restricao_dura` = verde ∩ união(APP ∪ APP_massa ∪ UC)**, em CRS métrico; `fontes`
   lista quais camadas de fato incidiram.
3. **Conservação de área:** `restricao_dura.area_m2 + a_verificar.area_m2 = verde_total_m2`
   (tolerância ≤ 0,5%). Sem dupla contagem (verde em APP **e** UC conta uma vez na dura).
4. **`potencial_desbloqueavel_m2` = a_verificar − união(faixa_não_edif ∪ servidão_LT)**,
   nunca negativo (clamp em 0).
5. **Valor-ouro — Terreno_Cachoeira** (24,08 ha; verde 13,77 ha): a `restricao_dura` deve
   bater com a **sobreposição mata∩APP que a 2.2 já computa (1,94 ha)**, sem UC incidente →
   `restricao_dura ≈ 1,94 ha`, `a_verificar ≈ 11,83 ha` (±0,5%). (Confirmar contra as
   camadas reais; se houver UC/faixa/servidão incidente, ajustar e registrar.)
6. **Headline inalterado (não-regressão da 2.2):** `area_aproveitavel_m2` e `n_lotes_teto`
   do aproveitamento permanecem os mesmos (todo o verde segue descontado). O
   `cenario_otimista` é aditivo e nunca substitui o headline.
7. **`cenario_otimista` coerente:** `area_aproveitavel_otimista = aproveitável_conservador +
   potencial_desbloqueavel`; `n_lotes_teto` recalculado pelo mesmo lote mínimo; ressalva
   presente. (Sujeito ao veto da seção 4.2 — se vetado, calcula mas não expõe no front.)
8. **Overlay em duas cores no mapa:** `restricao_dura` (cor "proibido") e `a_verificar`
   (cor "atenção"), cada um com seu GeoJSON. O overlay verde total da 2.2 segue disponível.
9. **Degradação honesta por fonte:** se só a vegetação foi consultada (sem ambiental),
   `severidade=null` e o verde total continua descontado normalmente (comportamento 2.2).
10. **Determinismo + proveniência + não-regressão:** fontes **injetáveis** (reusa
    `get_fonte_vegetacao` e `get_fonte_camadas`); testes **offline** com stubs (gleba + verde
    stub + camadas stub); cálculo só no backend; proveniência declara quais camadas entraram
    e a data; ressalva de laudo de campo presente. **Suítes das Fases 1, 1.5, 1.7, 2, 2.1 e
    2.2 continuam verdes.**

## 6. Fora de escopo (registrado)

- **Classificação de mata** (nativa / Mata Atlântica / regeneração / suprimível) — laudo de
  campo. A 2.3 só separa "em zona de proteção legal" de "fora dela".
- **Persistência temporal** do verde (mata antiga × recente, Aula 06) — exigiria outra fonte
  (WorldCover é snapshot 2021). Gancho para futuro, não entra aqui.
- **Declividade** (≥30%) continua na Fase 2.5 (DEM, exige chave OpenTopography).

## 7. Arquivos esperados (latitude de implementação)

- `core/severidade_verde.py` — função pura de classificação (novo).
- `routers/vegetacao.py` — injeta também as camadas ambientais e popula `severidade`.
- `routers/analises.py` — acrescenta `cenario_otimista` ao aproveitamento.
- Frontend: `CardVegetacao` (overlay duas cores + breakdown dura/a verificar);
  `CardAproveitamento` (cenário otimista rotulado, se não vetado).

A spec fixa **contrato + critérios**; o resto é latitude. **Sem agente, sem LLM, sem dado
externo novo** — é geometria sobre o que 2.1 e 2.2 já produzem.
