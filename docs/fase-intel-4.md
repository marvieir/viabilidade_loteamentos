# Fase INTEL-4 — Calibração do estilo pelos projetos importados

**Data:** 28/07/2026 · **Sequência do operador:** INTEL-1 ✓ → INTEL-2 ✓ → **INTEL-4 (esta)**
**Base:** `docs/fase-motor-intel.md` §INTEL-4 · **Juiz da mudança:** placar do INTEL-1.

## O problema

Os alvos do perfil de estilo (`urbanismo_estilo.ESTILO_DEFAULT`) foram escritos por
inferência nossa a partir de referências de mercado. Eles nunca foram confrontados com o
que um urbanista real desenha. Cada DWG que um cliente importa (URB-IMPORT) É esse
confronto: um projeto pronto, aprovado ou em aprovação, com decisões tomadas por quem
assina o projeto.

Hoje esse material entra, é medido, é auditado — e morre ali. Nenhuma métrica dele volta
para o motor.

## O que esta fase faz

Extrai as métricas dos projetos importados, agrega por padrão, e **propõe** ajustes nos
alvos do estilo. A proposta é um artefato que o operador lê, compara com o vigente e
aceita ou recusa. **Nada muda sozinho** — o estilo continua versionado e a aceitação é
manual, igual ao gate da LUOS.

```
projetos importados  →  métricas por projeto  →  agregação por padrão  →  PROPOSTA
   (já no store)         (determinístico)         (mediana, n≥mínimo)     (operador aceita)
                                                                              ↓
                                                            {estilo-urbanismo}/{perfil}.json
                                                                              ↓
                                                            placar do INTEL-1 mede antes×depois
```

## Métricas extraídas de cada projeto importado

Todas por cálculo geodésico no backend, sobre a geometria já fechada da importação — nada
de número vindo de IA, nada recalculado no front (§1, §2).

| Métrica | Como sai da geometria |
|---|---|
| `lote_area_mediana_m2` | mediana da área medida dos lotes |
| `lote_testada_mediana_m` | menor lado do retângulo mínimo rotacionado de cada lote |
| `lote_prof_mediana_m` | maior lado do mesmo retângulo |
| `lote_razao_prof_testada` | mediana da razão — o "formato" do lote do projetista |
| `quadra_area_mediana_m2` | mediana da área das quadras (agrupamento por `quadra_id`) |
| `quadra_lotes_mediana` | mediana de lotes por quadra |
| `verde_frac`, `institucional_frac`, `lazer_frac`, `viario_frac`, `vendavel_frac`, `agua_frac` | do `quadro_areas` já medido |

Métrica ausente nunca vira zero — vira "não medido", e a agregação a ignora.

**Largura de via ficou de fora** (estava prevista no rascunho desta spec). Ela sairia de
área do viário ÷ comprimento dos eixos, mas a camada de via do CAD do cliente costuma trazer
as **duas guias** (meios-fios), não o eixo — o comprimento viria dobrado e a largura pela
metade, sem como distinguir automaticamente. Número que não se sustenta não entra (§verdade
antes de resposta). Volta quando houver como separar eixo de guia com confiança.

## Classificação por padrão (decisão de design)

Os projetos importados não carregavam público-alvo: o `perfil` do snapshot é `{}` (a
importação não passa pelo gerador). Sem essa etiqueta não há como agregar por padrão.

**Decisão do operador (28/07): QUEM CARREGA declara o padrão, num campo do wizard.** Quem
sobe o DWG conhece o empreendimento. A alternativa — inferir pela mediana de área de lote —
erra justamente no caso que mais aparece: gleba mista, com quadras econômicas e nobres no
mesmo projeto, cuja mediana cai num padrão que o projeto inteiro não é. Errar a etiqueta
contamina a mediana daquele padrão, que é exatamente o que a calibração não pode fazer.

O campo é **opcional** (não trava a importação de quem só quer conferir o desenho) e diz na
própria tela para que serve: aprender com projetos reais, sem alterar nada na medição
daquele projeto.

A inferência pela área de lote **continua no código como fallback rotulado**, para os
projetos importados antes do campo existir. Toda proposta mostra quantos projetos são
`declarado` e quantos são `inferido`, para o operador saber em que confiar. Mediana fora de
qualquer faixa conhecida → `indefinido`, fora da agregação: não empurramos para a faixa mais
próxima.

## Agregação e o piso de evidência

- Agrega por padrão com **mediana** (robusta a um projeto atípico), não média.
- **Mínimo de projetos por padrão para propor qualquer coisa: 3.** Com 1 ou 2, o relatório
  mostra as métricas mas **não** propõe alteração — dizer "seu alvo está errado" com base
  em um projeto seria exatamente o tipo de chute que o CLAUDE.md proíbe.
- Toda proposta carrega: valor vigente, valor proposto, `n` projetos, dispersão
  (mín–máx) e a lista dos projetos que sustentam o número. Proveniência, como todo
  número do produto.

## Quais knobs a calibração pode propor

Só os que têm correspondência direta e honesta com o que se mede num projeto pronto:

| Knob do estilo | Métrica que o sustenta |
|---|---|
| `verde_min_pct` | `verde_frac` mediano |
| `lazer_pct_organico` | `lazer_frac` mediano |
| `verde_min_pct_organico` | `verde_frac` mediano |
| `lago_frac_aproveitavel` | fração de lâmina d'água, quando houver |

`prompt_regras`, `tracado`, `gramatica` e `arquetipo` **ficam de fora**: são escolhas de
composição, não medidas — nenhum número de projeto pronto justifica mudá-las.

A faixa de lote (`PERFIL_LOTE`) **não** é calibrada aqui. Ela orienta a mira, e mexer nela
sem base legal foi exatamente o erro de 27/07. O relatório mostra as medianas reais de
testada/profundidade dos projetos como **informação para o operador**, sem propor troca.

## Entregáveis

1. `backend/app/core/urbanismo_calibracao.py` — extração + agregação + proposta (puro,
   determinístico, testável sem rede).
2. `backend/scripts/calibrar_estilo.py` — CLI: varre o store de urbanismo, imprime o
   relatório e grava `proposta_estilo.json` no diretório de estilo. Não escreve o
   `{perfil}.json` — quem promove é o operador, com um comando explícito `--aplicar`.
3. Testes-ouro: métricas de um projeto sintético conhecido; agregação com n<3 não propõe;
   inferência de padrão nas três faixas; determinismo (mesma entrada → mesma proposta).
4. Registro no placar: rodar o placar antes e depois de aplicar, e anexar o diff à decisão.

## Fora do escopo

- Aplicar calibração automaticamente (quebra o gate humano).
- Calibrar piso de lote ou qualquer parâmetro com natureza legal.
- Ler o DWG de novo: a calibração usa a geometria JÁ fechada e medida no store.
