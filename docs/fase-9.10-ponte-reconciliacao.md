# Fase 9.10 — Ponte de reconciliação: teto teórico (Aproveitamento) × estudo realista (Urbanismo)

> **Não é urbanismo nem é bug — é coerência entre abas.** O mesmo sistema mostra **120 lotes** na
> aba Aproveitamento e **51 lotes** na aba Urbanismo para a mesma gleba. Os dois números estão
> **corretos**, mas medem perguntas diferentes; mostrados isolados, parecem contradição e minam a
> confiança do usuário. Esta fase faz **cada card citar o outro** e rotular o seu número — **puro
> texto/apresentação, zero mudança de cálculo**. Referencia `ARCHITECTURE.md` (§1-A) e as abas
> Aproveitamento e Urbanismo (9.x).

## 0. Por que 120 e 51 divergem (diagnosticado, não suposto)

Os dois partem da **mesma base física** (≈58.920 m² = gleba − APP − declividade ≥30% − mata).
A divergência são **duas premissas concretas + a geometria**:

| | Aproveitamento (teto) | Urbanismo (desenho) |
|---|---|---|
| **Doação** | 20% (piso legal) → sobra ~80% | 46,7% (desenhada: viário + verde + lazer + inst) → sobra ~53% |
| **Lote** | ÷ 360 m² (mínimo legal da zona) | ~500 m² (perfil alto real; mediana ~498) |
| **Método** | `floor((físico − doação) / lote_mín)` | desenha malha → faces → lotes, contorna o íngreme |
| **Lotes** | **120** | **51** |

**Decomposição validada:** 120 × (360/500) × (53%/80%) ≈ 62 lotes teóricos com as premissas do
desenho; de 62 para 51 é a **perda geométrica real** (~18%: faces curvas, perímetro, clamp legal,
retalho do traçado sinuoso da 9.9). Plausível para um traçado que contorna metade da gleba
non-aedificandi.

**Os nomes no código já entregam a natureza de cada um:**
- `lotes_teto` (Aproveitamento) = **teto regulatório**: "no máximo isto, se cada lote fosse o
  mínimo legal (360) e você doasse só o mínimo (20%)". Limite superior, não o desenhável.
- Urbanismo = **estudo de massa geométrico**: "isto é o que de fato cabe com lotes do padrão alto
  (~500), vias conectadas e áreas públicas materializadas". O número realista para o incorporador.

## 1. Objetivo

Eliminar a estranheza da divergência **sem mudar nenhum cálculo**: apresentar os dois números
como uma **faixa honesta** (teto teórico → estudo realista), com cada card **rotulando o seu
número e citando o outro**. Isso é *mais* informativo que um número só — entrega a dupla-visão
(teto possível + piso realista) que dá valor a uma ferramenta de triagem, e respeita o §1-A
(mostra o range e manda verificar, não promete nem força número).

## 2. O que NÃO muda (crítico)

- **Zero mudança de cálculo.** `lotes_teto` continua `floor((físico − doação_mín) / lote_legal)`;
  o Urbanismo continua medindo 51 sobre o traçado. **Nenhum número se move.**
- Nenhuma aba passa a depender da outra para *calcular* — a referência é só **textual** (o card
  exibe o número do outro como contexto, não o usa em conta própria).
- Fronteira §2 e §1-A intactas; nenhum número vem do LLM.
- Não toca geometria, traçado, recorte, declividade.

## 3. A ponte (texto em cada card)

**Na aba Aproveitamento**, junto ao "120 lotes", uma linha de contexto:
> *"Teto teórico — lote mínimo legal (360 m²) e doação mínima (20%). É o limite superior da zona,
> não o que cabe desenhado. O estudo de massa (aba Urbanismo) mede ~51 lotes com lotes do perfil
> (~500 m²) e vias/áreas reais."*

**Na aba Urbanismo**, junto ao "51 lotes", a contrapartida:
> *"Estudo de massa geométrico — lotes do perfil (~500 m²), doação desenhada (~47%), vias
> conectadas e áreas públicas materializadas, contornando a área não-edificável. Teto regulatório
> da zona: ~120 lotes (aba Aproveitamento), assumindo lote mínimo e doação mínima."*

**Opcional (se couber sem poluir):** um micro-resumo de faixa, do tipo *"~120 (teto legal) → ~51
(estudo realista)"*, em um dos cards, deixando claro que a verdade comercial está perto do
geométrico.

**Diretrizes do texto:**
- Os números (120, 51, 360, 500, 20%, 47%) devem ser **lidos das respostas reais**, não
  hardcoded — se a gleba muda, os números do texto mudam junto (são interpolados dos campos que
  cada aba já calcula).
- Linguagem §1-A: "teto", "estimativa", "estudo de massa", "verificar com urbanista" — nunca
  "cabem 120" ou "serão 51" como promessa.
- O texto explica a **razão** da diferença (lote menor + doação menor na fórmula), não só
  constata que diferem.

## 4. Contrato de API

Cada aba já tem o seu número; a ponte só exige que **cada resposta exponha os campos que o texto
da outra precisa** (para interpolação, sem recálculo):

```jsonc
// resposta do Aproveitamento (já tem lotes_teto; expor as premissas p/ o texto)
"reconciliacao": {
  "lotes_teto": 120, "lote_base_m2": 360, "doacao_base_pct": 0.20,
  "ref_estudo_massa": { "fonte": "urbanismo", "lotes_estimados": 51 }  // citação textual
}

// resposta do Urbanismo (já tem n_lotes; expor as premissas p/ o texto)
"reconciliacao": {
  "lotes_estudo": 51, "lote_mediano_m2": 498, "doacao_desenhada_pct": 0.467,
  "ref_teto_regulatorio": { "fonte": "aproveitamento", "lotes_teto": 120 }  // citação textual
}
```

`ref_*` é **só para exibição** — o card mostra o número do outro como contexto. Se a outra aba
não foi computada nesta sessão (ex.: usuário não rodou o estudo de massa), o card mostra o seu
número e um convite ("rode o estudo de massa para ver o número realista"), sem inventar.

## 5. Critérios de aceite (testáveis)

1. **Zero mudança de número:** `lotes_teto` (120) e `n_lotes` do Urbanismo (51) **idênticos** ao
   atual; nenhuma conta alterada. Suítes de Aproveitamento e Urbanismo verdes sem mudança de
   valor.
2. **Aproveitamento cita o estudo:** o card do teto exibe, junto aos 120, o rótulo "teto teórico"
   + a premissa (lote 360, doação 20%) + a referência ao estudo de massa (~51). Texto presente e
   correto.
3. **Urbanismo cita o teto:** o card do estudo exibe, junto aos 51, o rótulo "estudo geométrico"
   + a premissa (lote ~500, doação ~47%) + a referência ao teto regulatório (~120).
4. **Números interpolados, não hardcoded:** mudar a gleba (ou o perfil) muda os números do texto
   coerentemente; um teste com gleba diferente mostra o texto refletindo os novos valores.
5. **Degradação honesta:** se só uma aba foi computada, o card mostra o seu número + convite a
   rodar a outra, **sem inventar** o número ausente.
6. **§1-A preservado:** linguagem de "teto/estimativa/estudo de massa/verificar", sem promessa;
   regex sem "cabem N"/"serão N"/"garantido".
7. **Explica a razão:** o texto diz *por que* diferem (lote menor + doação menor na fórmula), não
   só que diferem.
8. **Sem acoplamento de cálculo:** nenhuma aba usa o número da outra em conta própria; a
   referência é puramente textual/exibição.

## 6. Fora de escopo (registrado)

- **Mudar a fórmula do teto** (descontar perda de traçado para aproximar de 51) — descartado: a
  fórmula é um teto regulatório legítimo; aproximá-la mascararia a diferença conceitual real.
- **Aposentar o número do teto e usar o geométrico em todo lugar** — descartado: o teto rápido
  por área tem valor próprio (instantâneo, não exige rodar o estudo de massa).
- **Pórtico de entrada** — próxima fase, depois desta.
- **Qualquer mudança de geometria, traçado, recorte** — fora.

## 7. Arquivos esperados (latitude de implementação)

- `core/aproveitamento.py` — expor `reconciliacao` com `lotes_teto`, `lote_base_m2`,
  `doacao_base_pct` (já calculados; só serializar) e, quando o estudo de massa existir na sessão,
  `ref_estudo_massa.lotes_estimados`.
- `core/urbanismo_medida.py` — expor `reconciliacao` com `lotes_estudo`, `lote_mediano_m2`,
  `doacao_desenhada_pct` (já calculados) e `ref_teto_regulatorio.lotes_teto`.
- `models/schemas.py` — bloco `reconciliacao` em ambas as respostas (campos de exibição).
- `routers/` — quando ambas as análises existem para a mesma gleba/sessão, preencher as
  referências cruzadas; senão, deixar a referência nula (o front mostra o convite).
- Frontend (cards Aproveitamento e Urbanismo) — renderizar o texto da ponte com os números
  interpolados; rótulos "teto teórico" / "estudo geométrico"; o micro-resumo de faixa opcional.
- Testes: `tests/test_reconciliacao.py` — números idênticos ao atual, textos presentes e
  interpolados, degradação honesta quando uma aba falta, sem acoplamento de cálculo, offline.

A spec fixa **contrato + critérios**. **Puro texto/apresentação:** cada card rotula o seu número
(teto teórico vs estudo geométrico) e cita o outro, explicando que a diferença vem de duas
premissas (lote 360 vs ~500; doação 20% vs ~47%) mais a perda geométrica do desenho — os dois
números **corretos**, mostrados como faixa honesta (teto possível → realista), sem mover nenhum
cálculo e sem acoplar as abas. Mata a estranheza da divergência e, de quebra, dá ao usuário a
dupla-visão que uma ferramenta de triagem deve ter (§1-A). Depois desta: o pórtico.
