# Fase 8 — Agrupamento de glebas vizinhas (análise unificada multi-KMZ)

> Permite subir **2+ KMZ de glebas vizinhas** e analisá-las como **um único projeto**. A
> regra é a mais simples possível: **o número de arquivos é a intenção** — 1 KMZ = uma
> gleba (fluxo de hoje, intacto); 2+ KMZ = projeto unificado. Referencia `ARCHITECTURE.md`
> (§2, §4, §4-A) e respeita a ingestão existente ("nunca agrupar em silêncio"). **Sem LLM,
> sem rede** — união geométrica determinística.

## 1. Objetivo

Na **criação** da análise, aceitar 1 ou N arquivos KMZ. Com 1, nada muda. Com 2+, validar
que as glebas **se tocam** (fronteira compartilhada, mesmo município) e produzir a **união
geométrica** como a geometria da análise — daí todo o pipeline (geometria, ambiental,
aproveitamento, financeira, econômica, localização) roda sobre a união, **sem precisar saber
que veio de vários arquivos**.

**Premissas fixadas pelo operador (escopo enxuto):**
- **Mesmo município sempre** — não tratamos glebas em municípios diferentes (a análise usa
  um `cod_ibge`). Se a detecção indicar municípios distintos → recusa com diagnóstico.
- **Só agrupa se forem vizinhas com limite entre elas** — vão entre as glebas, toque só em
  ponto (canto) ou sobreposição → **recusa**, nunca força.
- **Matrículas distintas → adiante** — o jurídico-documental multi-matrícula fica para fase
  futura; na análise agrupada o jurídico opera como hoje (uma matrícula por vez ou pulado).
- **Agrupou = uma análise só** (a união). Não mantém as individuais em paralelo, não há
  "juntar análises existentes" (quem quer individual sobe 1 KMZ).

## 2. O que NÃO muda (não-regressão)

- **1 KMZ = comportamento idêntico ao atual**, byte a byte (o caminho de upload único não é
  tocado; a união de 1 elemento é a própria geometria).
- O **motor de geometria permanece puro** (`Polygon` entra → medidas saem); o agrupamento é
  um **adaptador a montante**, no espírito da camada de ingestão (§4-A). As dimensões a
  jusante não sabem da origem múltipla.
- Sem LLM, sem rede. Suítes 1…7 verdes.

## 3. A regra de contiguidade (núcleo determinístico — validada)

Para um conjunto de geometrias já parseadas (cada uma pela ingestão existente — inclusive
linha-fechável/reparo de polígono):

```
1. cada arquivo → polígono válido (reusa core/ingestao; arquivo inválido → recusa diagnóstica)
2. detectar município de cada um (1.7); divergiu → RECUSA "glebas em municípios diferentes"
3. sobreposição? para qualquer par g_i.overlaps(g_j) == True → RECUSA
   "glebas se sobrepõem (área em duplicidade) — verifique os arquivos"
4. união = unary_union(geoms); SE união.geom_type for MultiPolygon (desconexo) → RECUSA
   "glebas não são contíguas (há vão ou apenas tocam em um ponto) — só agrupamos áreas com
    fronteira comum"
5. união é Polygon único → ACEITA: vira a geometria da análise
```

Fundamento geométrico (verificado): vizinhos de verdade compartilham uma **fronteira-linha**
→ `unary_union` devolve **Polygon** simples; vão ou toque em ponto → **MultiPolygon**
(desconexo) → recusa; sobreposição → `overlaps=True` → recusa. A regra é, portanto, "a união
é um polígono único e os interiores não se sobrepõem". Tolerância de encosto: usa a **mesma
tolerância de fechamento** da ingestão (gap ≤ tolerância conta como tocando — evita recusar
por folga milimétrica de digitalização), declarada na proveniência.

## 4. Como funciona

- **Criação da análise** aceita `kmz[]` (1..N). Backend:
  parseia cada um → detecta municípios → roda a regra §3 → em sucesso, persiste a análise com
  a **geometria-união** + um bloco `agrupamento` de proveniência (quantos arquivos, nome de
  cada, fronteira detectada, tolerância, município comum).
- **Daí em diante é uma análise normal** — área/perímetro são os da união; ambiental,
  aproveitamento, financeira etc. consomem a união sem ramo especial.
- **Recusa é sempre diagnóstica** (qual regra falhou, com números) e **não cria análise
  parcial** — o usuário corrige os arquivos e tenta de novo.

### Contrato
`POST /api/analises` (criação) passa a aceitar **múltiplos KMZ**. A resposta inclui, quando
N>1:
```jsonc
"agrupamento": {
  "n_glebas": 2,
  "arquivos": ["terreno_a.kmz", "terreno_b.kmz"],
  "municipio_comum": { "cod_ibge": "3550605", "nome": "São Roque", "uf": "SP" },
  "fronteira": "compartilhada",            // sempre 'compartilhada' quando aceito
  "tolerancia_encosto_m": 1.0,
  "area_total_m2": 200000,                  // = área da união (sem dupla contagem)
  "proveniencia": "União geométrica de 2 KMZ contíguos (fronteira comum) — mesmo município"
}
```
Erros (sempre diagnósticos, sem criar análise):
- `422 GLEBAS_NAO_CONTIGUAS` — vão/ponto entre elas (inclui a distância do vão, se houver).
- `422 GLEBAS_SOBREPOSTAS` — interiores se cruzam (inclui a área de sobreposição).
- `422 MUNICIPIOS_DIFERENTES` — detecção divergente (lista os municípios).
- `422` da ingestão para qualquer arquivo inválido (reusa o diagnóstico existente).

## 5. Critérios de aceite (testáveis — valores-ouro geométricos)

1. **1 KMZ inalterado:** upload único produz **exatamente** a análise de hoje (byte a byte);
   nenhum bloco `agrupamento`.
2. **Contíguos → união-ouro:** duas glebas quadradas de 100 (lado 10) compartilhando a aresta
   `x=10` → união **Polygon**, **área 200**, perímetro da borda externa (sem a linha interna);
   `agrupamento.n_glebas=2`, `fronteira="compartilhada"`.
3. **Vão → recusa:** mesma A e uma B deslocada 0,5 (gap) → `422 GLEBAS_NAO_CONTIGUAS`;
   **nenhuma análise criada**.
4. **Toque em ponto → recusa:** B que encosta só no vértice `(10,10)` → união MultiPolygon →
   `422 GLEBAS_NAO_CONTIGUAS` ("apenas tocam em um ponto").
5. **Sobreposição → recusa:** B que invade A → `overlaps=True` → `422 GLEBAS_SOBREPOSTAS`
   com a área de sobreposição.
6. **Municípios diferentes → recusa:** detecção devolve 2 `cod_ibge` → `422
   MUNICIPIOS_DIFERENTES`.
7. **Tolerância de encosto:** gap ≤ tolerância da ingestão → aceita como contíguo (não recusa
   por folga milimétrica), com a tolerância na proveniência.
8. **A jusante é cego à origem:** dada a união, aproveitamento/ambiental produzem o mesmo que
   produziriam para uma gleba única daquela forma (a dimensão não tem ramo "agrupado").
9. **3+ glebas:** A|B|C em fila contígua → união Polygon única, área somada; uma delas solta
   → recusa.
10. **Determinismo + não-regressão:** mesma entrada → mesma união/recusa; suítes 1…7 verdes;
    caminho de 1 KMZ intacto.

## 6. Fora de escopo (registrado)

- **Glebas em municípios diferentes** — fixado fora pelo operador (regra do mesmo município).
- **Multi-matrícula no jurídico-documental** — adiante; na análise agrupada o jurídico opera
  como hoje.
- **"Juntar análises já existentes"** (botão na lista) — fora; o agrupamento é na criação,
  por número de arquivos.
- **Glebas separadas como "portfólio"** (não contíguas analisadas juntas) — não é este
  recurso; aqui exige-se fronteira comum. Portfólio é outra ideia, futura.
- **Recorte/edição de geometria na tela** (ajustar fronteira manualmente) — evolução; o MVP
  aceita ou recusa o que veio nos arquivos.
- **Doação/vias do conjunto vs. das partes** — o aproveitável da união segue o §6-A normal
  (vias/doação são do projeto); o agrupamento não muda essa regra.

## 7. Arquivos esperados (latitude de implementação)

- `core/agrupamento.py` — `agrupar(geoms, municipios, tolerancia)` → união válida **ou**
  recusa diagnóstica (puro, sobre geometrias já parseadas); reusa `unary_union` + `overlaps`
  + `touches`.
- `core/ingestao.py` — passa a aceitar lista de fontes (cada uma pelo parser atual);
  inalterado para 1 arquivo.
- `routers/analises.py` (criação) — aceita `kmz[]`; chama ingestão por arquivo → agrupamento
  → persiste união + bloco `agrupamento`; erros 422 diagnósticos.
- `models/schemas.py` — `AgrupamentoOut`, erros nomeados.
- Frontend: tela de **nova análise** aceita múltiplos arquivos (drag de N KMZ); com N>1,
  mostra o resultado do agrupamento (glebas, fronteira, área da união) **ou** o erro
  diagnóstico; com 1, fluxo atual. Mapa mostra a união (e, se útil, as bordas originais).
- Testes: `tests/test_agrupamento.py` (ouros geométricos 1–10, offline, com shapely).

A spec fixa **contrato + critérios**; o resto é latitude. **Sem LLM, sem rede** — é geometria
determinística (união + contiguidade) a montante de um pipeline que nem percebe a diferença.
