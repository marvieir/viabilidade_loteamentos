# Fase 7 — Consolidação (laudo de triagem em PDF)

> Fecha o laço do MVP: une o **subconjunto executivo** das dimensões já implementadas num
> **PDF exportável**, com o disclaimer-mestre do §1-A e um **semáforo consolidado** no topo.
> Referencia `ARCHITECTURE.md` (§1-A, §2). **Sem LLM, sem rede, sem cálculo novo** — é
> composição + apresentação do que cada dimensão já devolve com proveniência.

## 1. Objetivo

Gerar, sob demanda, um **laudo de pré-análise** da gleba (ou do conjunto agrupado — Fase 8)
em PDF, reunindo os achados das dimensões num documento que o incorporador leva para
advogado/urbanista/sócio. **Não calcula nada de novo**: lê os JSONs das dimensões já
executadas na análise e os apresenta. O headline é um **painel de semáforo** (favorável /
atenção / restrição por dimensão, na linguagem §1-A), seguido do detalhe executivo.

## 2. O que NÃO muda (não-regressão)

- **Zero cálculo novo** — consome `aproveitamento`, `ambiental`+`vegetacao`+`declividade`,
  `juridico`, `financeira`, `economica`, `localizacao` exatamente como já vêm. Nenhum número
  é recalculado; se diverge, é bug da dimensão, não daqui.
- Sem LLM, sem rede, sem credencial. Suítes 1…6 verdes; nenhuma dimensão é alterada.
- `_fmt` pt-BR já vem das dimensões; o laudo **não reformata número** (§2) — só dispõe.

## 3. Escopo do laudo (subconjunto executivo — decisão do operador)

Cobre as dimensões que mais pesam na triagem (não as 12 — decisão do operador):

| Seção do laudo | Fonte (dimensão) | O que entra |
|---|---|---|
| **Identificação** | análise + 1.7 | gleba, área/perímetro, município/UF, cobertura de jurisdição, data |
| **Aproveitamento** | aproveitamento | headline (diretriz/teto), área aproveitável, nº de lotes, restrições na união |
| **Ambiental** | ambiental + vegetação + declividade | APP/UC/mineração/servidão, verde (dura×a verificar), declividade ≥30% |
| **Jurídico** | juridico | ônus/averbações/indisponibilidade + cross-check área matrícula×KMZ + síntese de risco |
| **Financeiro-econômico** | financeira + economica | VGV (nominal+financeira), resultado, exposição máx, VPL, TIR, paybacks |
| **Localização** | localizacao | os 4 indicadores socioeconômicos (informativo) |

Cada seção: os números-chave com proveniência (fonte+ano/artigo) + os **avisos §1-A** da
própria dimensão. Conformidade (3.5) e os blocos completos ficam na tela; o laudo é o
executivo. **Dimensão não executada → seção marcada "não analisada"** (não inventa, não omite
em silêncio).

## 4. Headline — semáforo consolidado (regra fixa, determinística)

No topo do laudo, um quadro com uma luz por dimensão, derivada **do que a dimensão já
reporta** (não é juízo novo):

| Luz | Critério (exemplos por dimensão) |
|---|---|
| 🔴 **restrição** | ANM/declividade ≥30% vedada · ônus que trava transação · divergência de área · resultado nominal < 0 |
| 🟡 **atenção** | verde a verificar relevante · margem < referência · exposição > capital · déficit/demografia fracos |
| 🟢 **favorável** | sem restrição dura na dimensão · indicadores positivos sob as premissas |
| ⚪ **não analisada** | dimensão sem execução na análise |

**Linguagem §1-A inegociável:** o semáforo é "leitura de triagem **sob os dados/premissas
informados**", **nunca veredito de viabilidade**. O laudo **não tem um "VIÁVEL/INVIÁVEL"
geral** — tem luzes por dimensão e a ressalva-mestre. Regra fixa no backend (`semaforo()`),
auditável; reusa os `status`/`nivel`/`leituras` que as dimensões já emitem.

## 5. Como funciona

`POST /api/analises/{id}/laudo` → gera o PDF e devolve referência para download.
- Backend monta um **modelo de dados do laudo** (`LaudoData`) lendo as dimensões executadas
  + o `semaforo()` consolidado; renderiza via a **skill de PDF** do ambiente (HTML→PDF ou
  ReportLab — latitude de implementação), com cabeçalho/rodapé, número de página e a
  **ressalva §1-A em toda página** (rodapé fixo).
- **Capa**: identificação + semáforo. **Miolo**: uma página/bloco por seção do §3.
  **Rodapé fixo**: *"Pré-análise de triagem — não substitui parecer de advogado, levantamento
  de agrimensor/engenheiro, projeto de urbanista nem aprovação da prefeitura (§1-A)."*
- **Proveniência consolidada** no fim: lista as fontes/datas de cada dimensão (de onde cada
  número veio) — é o que torna o laudo auditável.

## 6. Critérios de aceite (testáveis)

1. **Composição sem recálculo:** os números do laudo são **idênticos** aos dos endpoints das
   dimensões (teste compara campo a campo — VGV, VPL, nº de lotes, áreas); nenhuma conta no
   gerador.
2. **Semáforo determinístico:** dado um conjunto fixo de saídas de dimensão (fixtures), o
   `semaforo()` produz as luzes esperadas — ANM→🔴, verde-a-verificar→🟡, etc.; mesma entrada
   → mesmas luzes.
3. **Sem veredito global:** **regex no texto do laudo: nenhuma string "viável"/"inviável"**
   como conclusão; a ressalva §1-A aparece na capa **e** no rodapé de toda página.
4. **Dimensão ausente:** análise sem financeira executada → seção "Financeiro" = "não
   analisada" + luz ⚪; o PDF gera mesmo assim (degradação honesta, nunca trava).
5. **Proveniência presente:** cada seção carrega fonte+ano/artigo; a lista consolidada de
   fontes fecha o documento.
6. **PDF válido:** arquivo abre, tem capa + seções + numeração; texto pt-BR (`_fmt` das
   dimensões preservado, sem reformatação).
7. **Subconjunto executivo:** o laudo cobre as 6 seções do §3 (não as 12 dimensões);
   Conformidade e blocos completos **não** entram no PDF (ficam na tela).
8. **Determinismo + não-regressão:** mesma análise → PDF equivalente (mesmo conteúdo);
   suítes 1…6 verdes; nenhuma dimensão tocada.

## 7. Fora de escopo (registrado)

- **Personalização do laudo** (logo do incorporador, seções ligáveis/desligáveis, marca
  branca) — evolução.
- **As 12 dimensões completas no PDF** — o MVP é executivo; um "laudo completo" é evolução.
- **Narração em prosa por LLM** (resumo executivo escrito) — possível evolução §2(b)
  (opcional, desligável), **fora do MVP** (laudo é composição determinística).
- **Assinatura digital / verificação** — externo.
- **Exportar em DOCX/HTML** — o operador pediu PDF; outros formatos são evolução.

## 8. Arquivos esperados (latitude de implementação)

- `core/laudo.py` — `montar_laudo_data(analise)` (lê dimensões executadas) + `semaforo()`
  (regra fixa) — **puros**, sem I/O de rede.
- `routers/laudo.py` — `POST /analises/{id}/laudo` → gera PDF (skill de PDF), devolve
  referência de download.
- `models/schemas.py` — `LaudoData`, `LuzSemaforo`, `SecaoLaudo`.
- Template do PDF (HTML+CSS de impressão **ou** ReportLab) com capa, seções, rodapé §1-A
  fixo, numeração.
- Frontend: botão **"Gerar laudo (PDF)"** no topo da análise (ou na sidebar) → chama o
  endpoint, oferece o download; estado de carregando.
- Testes: `tests/test_laudo.py` (fixtures de dimensões → semáforo + composição + regex
  anti-"viável" + degradação, offline).

A spec fixa **contrato + critérios**; o resto é latitude. **Sem LLM, sem rede, sem cálculo
novo** — é a vitrine do que as 12 dimensões já produziram, com a fronteira §1-A carimbada em
toda página.
