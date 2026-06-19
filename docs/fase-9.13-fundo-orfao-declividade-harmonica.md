# Fase 9.13 — Urbanismo: fechar encravados de fundo + suavizar a restrição no mapa (apresentação + ajuste fino)

> Fase curta, dois ajustes: **(1)** fechar os últimos lotes encravados — os de **fundo de
> quadra** (atrás de outro lote, sem lateral com via), que a fusão lateral da 9.12 não resolve, via
> **exceção de fusão frente-fundo**; **(2)** suavizar a **mancha vermelha de declividade** que
> hoje grita no centro do mapa e quebra a leitura do projeto. Referencia `ARCHITECTURE.md`
> (§1-A, §2) e as Fases 9.8/9.12. **Não toca a geração nem o número de lotes além de fechar os
> encravados residuais.** O traçado inteligente (cul-de-sacs, leques) é a **próxima** spec (9.14).

## 1. Objetivo

(1) **Zero lotes encravados** — incluindo os de fundo de quadra, fundindo o fundo órfão com a
frente (exceção à regra lateral), respeitando o piso legal. (2) **Declividade harmônica no mapa**
— a área não-edificável ≥30% aparece de forma discreta (hachura/esmaecido/contorno), não como
bloco vermelho-tijolo sólido competindo com o parcelamento. Continua **ESTUDO DE MASSA
ESQUEMÁTICO** (§1-A).

## 2. O que NÃO muda

- **Geração (9.7-9.12) preservada** — malha, cross-streets, grade adaptativa, todo-lote-com-via,
  reconciliação. A 9.13 só adiciona a **exceção de fusão de fundo** ao passo de frente-via (9.12)
  e mexe na **cor da restrição** (apresentação).
- **Clamp legal (9.4):** preservado — a fusão de fundo respeita `[piso, teto]` (excedente vira
  verde, ver §3).
- **Fronteira §2:** a exceção de fusão é geométrica determinística; nenhuma decisão do LLM.
- Snapshot e contrato do `/medir` preservados.

## 3. Ajuste A — fusão do lote de fundo órfão (fecha os últimos encravados)

A 9.12 funde **lateralmente** (lado a lado). Mas um lote de **fundo de quadra** (atrás de um lote
da frente, numa face de 2 fileiras) tem todos os vizinhos laterais **também** encravados — a
fusão lateral não o recupera. Para esse caso, **exceção**: funde com o lote da **frente** (mesma
coluna).

```
Hierarquia COMPLETA do lote sem via (estende a 9.12):
  1. tem vizinho LATERAL com via?  -> funde/redistribui LATERAL (regra geral, 9.12)
  2. é FUNDO de quadra (atrás de um lote com via), sem lateral com via?
     -> EXCEÇÃO: funde com o lote da FRENTE (mesma coluna), somando profundidade.
        - o lote fundido absorve profundidade ATÉ o teto da faixa; o excedente de
          profundidade (se passar do teto) vira VERDE/não-aproveitável.
        - resultado: lote da frente fica mais profundo (até o teto), sem encravado atrás.
  3. nem frente disponível (face isolada sem via nenhuma) -> vira VERDE (honesto, 9.11/9.12).
```

**Por que frente-fundo só aqui (e não como regra geral):** fusão lateral soma testada (lote mais
largo, normal); fusão frente-fundo soma profundidade (lote mais fundo). Como **regra geral**,
frente-fundo geraria lotes compridos/estreitos (irreal) — por isso a 9.12 a proíbe. Mas para o
**fundo órfão**, é a única solução real (o que está atrás só pode se unir ao que está à frente),
e é o que um urbanista faz com um fundo de quadra sem acesso. **Exceção, não regra.**

**Piso legal preservado (decisão cravada):** a fusão frente-fundo absorve profundidade **até o
teto da faixa**; o que passar do teto vira verde. Assim o lote final respeita `[piso, teto]`
(`fora_da_faixa == 0` mantido); não se cria lote gigante irreal. (Validado: frente 30m + fundo
30m = 60m profundidade / 720m² estouraria 640; então absorve só até 640 e o resto é verde.)

## 4. Ajuste B — declividade harmônica no mapa (apresentação)

Hoje a restrição ≥30% é desenhada como **bloco vermelho-tijolo sólido** que domina o centro do
mapa e compete com o parcelamento (o urbIA não tem essa mancha gritante). Suavizar:

- trocar o **preenchimento sólido** por **hachura diagonal leve** OU **fill esmaecido** (opacidade
  baixa, ~0,2-0,3) OU **só contorno tracejado** com rótulo — escolha de implementação que deixe a
  restrição **legível mas discreta**.
- cor menos agressiva (um vermelho/terracota dessaturado, ou cinza-terra), não o vermelho-tijolo
  saturado atual.
- manter o **rótulo** "Não-edificável (mata/declividade ≥30%)" na legenda — o dado continua
  explícito, só para de gritar visualmente.
- o parcelamento (lotes, vias, áreas públicas) fica em **primeiro plano**; a restrição, ao fundo.

**Não muda o dado:** a área ≥30% continua recortada e medida igual (a geometria não muda); só a
**representação visual** fica harmônica. O usuário ainda vê onde é não-edificável.

## 5. Contrato de API

```jsonc
"viario_diagnostico": { /* … 9.12 … */
  "lotes_fundidos_fundo": 4,        // NOVO: fundos órfãos fundidos com a frente
  "lotes_sem_via_final": 0 },       // invariante: deve ser 0 após 9.13
"geometria": { /* … */
  "restricao_recortada": { /* já existe (9.8) */
    "estilo_sugerido": "hachura_discreta" } }  // dica de apresentação p/ o front
```
`conformidade_legal.todos_lotes_com_frente_via` deve ser `true` (agora sem exceção residual).

## 6. Critérios de aceite

1. **Zero encravados (fecha o ponto 1):** `lotes_sem_via_final == 0`; nenhum lote contado sem
   frente para via, **incluindo** os de fundo de quadra. Teste por lote em São Roque/alta.
2. **Fusão de fundo correta:** lote de fundo órfão funde com a frente (mesma coluna), some
   profundidade até o teto; `lotes_fundidos_fundo` coerente; o lote resultante respeita
   `[piso, teto]` (`fora_da_faixa == 0`).
3. **Excedente vira verde:** quando a fusão frente-fundo passaria do teto, o excedente de
   profundidade é verde/não-aproveitável, não um lote gigante; nenhum lote acima do teto da faixa.
4. **Fusão lateral ainda é a regra:** frente-fundo só ocorre para fundo órfão sem lateral com
   via; a maioria das fusões segue lateral (9.12). Teste: contagem lateral >> contagem fundo.
5. **Declividade discreta (fecha o ponto 3):** a restrição ≥30% é renderizada de forma discreta
   (hachura/esmaecido/contorno), não bloco sólido saturado; o parcelamento fica em primeiro
   plano; o rótulo permanece na legenda. O dado/geometria **não muda**.
6. **§2 + §1-A:** exceção de fusão é determinística (sem LLM); selo "ESQUEMÁTICO"; regex sem
   "aprovado/viável/regular".
7. **Não-regressão:** geração 9.7-9.12, números, viário (~15%), reconciliação — preservados; só
   os encravados de fundo (poucos) mudaram de destino e a cor da restrição mudou.

## 7. Fora de escopo (registrado — vai para a 9.14)

- **Traçado inteligente / heurísticas de valorização:** cul-de-sacs (vias sem saída com bulbo),
  lotes em leque, vias de fundo de vale, maximização de lotes premium — **é a Fase 9.14**, a
  spec grande, **com pesquisa** das melhores práticas de traçado de loteamento premium (como a
  pesquisa de lote da 9.12). É o que aproxima o nosso traçado do urbIA e pode **recuperar lotes**
  (melhor aproveitamento). Não entra aqui.
- **Pórtico, pontes entre ilhas, heatmap (cor):** seguem nas respectivas filas.

## 8. Arquivos esperados (latitude de implementação)

- `core/urbanismo_geom.py` — no passo `garantir_frente_via` (9.12), adicionar a **exceção de
  fundo órfão**: detectar lote de fundo (atrás de lote com via, sem lateral com via), fundir com
  a frente até o teto, excedente → verde. Determinístico.
- `core/urbanismo_medida.py` — `lotes_fundidos_fundo`, `lotes_sem_via_final`;
  `estilo_sugerido` na restrição.
- `models/schemas.py` — campos novos.
- Frontend `MapaLeaflet` — renderizar `restricao_recortada` de forma **discreta** (hachura/
  esmaecido/contorno), parcelamento em primeiro plano; legenda mantém o rótulo.
- Testes: `tests/test_urbanismo_fundo.py` — zero encravados em São Roque (KMZ real), fusão de
  fundo respeita teto (`fora_da_faixa==0`), excedente vira verde, lateral continua sendo a
  maioria; offline onde possível.

A spec fixa **contrato + critérios**. **Ajuste A:** o lote de fundo de quadra órfão (que a fusão
lateral não pega) funde com a frente (exceção), some profundidade até o teto, excedente vira
verde — fechando os **últimos encravados** sem violar a faixa legal. **Ajuste B:** a declividade
≥30% passa a ser mostrada de forma **harmônica** (discreta, ao fundo), não um bloco vermelho que
domina o mapa — o dado continua, só para de competir com o projeto. O **traçado inteligente** (o
salto de qualidade rumo ao urbIA) é a próxima spec, com pesquisa.
