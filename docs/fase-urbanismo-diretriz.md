# Fase U7 — Urbanismo DIRIGIDO PELA DIRETRIZ (normas urbanísticas por município)

> Fonte da verdade do padrão de urbanismo. Complementa `ARCHITECTURE.md` e `CLAUDE.md`.
> Princípio-mãe (CLAUDE.md §1 e §5): **nenhum parâmetro de urbanismo é inventado.** Todo número
> que molda a massa vem da **diretriz do município carregada** (perfil LUOS, Fase 1.8). Diretriz
> silenciosa → **degrada e ROTULA** (`BASE_FEDERAL` / `PARCIAL_UF` / `COMPLETA`), nunca chuta.
> A aplicação analisa **qualquer cidade do Brasil** — São Roque é só uma amostra.

## 1. O erro que esta fase corrige

O motor tinha `verde_min_pct = 0.20` (e `0.08` no orgânico) **hardcoded** no perfil de estilo.
Isso **sobrepunha a diretriz**. Errado. O piso de área verde — como toda norma urbanística — tem
que **vir da diretriz de cada cidade**. O valor de estilo, quando muito, é **fallback rotulado**
para quando a diretriz é silenciosa (e aí o estudo diz "verificar na prefeitura").

## 2. Doação ≠ Área verde (distinção que o motor tem que respeitar)

São coisas **diferentes**, de artigos diferentes da diretriz:

- **Doação** (ex.: Art. 16 — condomínio ≥ 15.000 m² → **10%** do terreno ao Município): terra
  pública, pode ser **externa** ao condomínio, **institucional**, ou em **pecúnia/obras**
  (Art. 17). NÃO é o verde interno. Já vem de `diretrizes.doacao_pct`.
- **Área verde / APA**: requisito **à parte**, do sistema de áreas verdes/ambiental da diretriz.
  É o que o motor reserva como verde interno preservado. **Não confundir com o `verde` do
  `doacao_split`** (esse é a repartição da doação).

> **RESOLVIDO por exemplo real:** a mesma diretriz exige, além da doação de 10% (Art. 16),
> **"reservar 10% de sua área a título de APA"** (Área de Proteção Ambiental) — um percentual
> **SEPARADO**. Logo, **área verde é campo próprio** (`area_verde_pct` / `apa_pct`), NÃO uma
> linha do `doacao_split`. São, neste município, DOIS 10% distintos:
> **10% doação (externa/pecúnia)** + **10% APA (verde interno preservado)**. O extrator da LUOS
> precisa capturar o APA/área verde como campo próprio (hoje não existe).

## 3. Mapa: Art. 11 (normas urbanísticas) → motor

Exemplo real de diretriz carregada (condomínio de lotes):

| Item da diretriz | O que é | Motor (esquemático) |
|---|---|---|
| I–III — via local **6 / 9 / 11 m** (conforme estacionamento na via) | largura de via condominial | **HONRA**: largura de via = valor da diretriz (não hardcoded) |
| IV — via de pedestres **1,90 m** | acessibilidade | detalhe executivo → **conformidade** (não desenha) |
| V — área de uso comum **≥ 6 m²/unidade** | lazer/comum mínimo | **HONRA**: piso de lazer = `6 m² × nº lotes` (da diretriz) |
| VI — portaria ≤ **10 m²** no recuo | portaria | informativo → conformidade |
| VII — vagas (Quadro V da LC 40/2006) | estacionamento | detalhe executivo → conformidade |
| VIII — visitantes **12% das unidades**, mín. 4 | estacionamento visitante | detalhe executivo → conformidade (sinaliza o nº) |
| IX — **cul-de-sac** em toda via sem saída | geometria viária | **HONRA**: implementa cul-de-sac + **conformidade** |
| Art. 16 — **doação 10%** (≥ 15.000 m²) | doação pública | já lê `doacao_pct` |

**Fronteira (CLAUDE.md §1-A):** o estudo é **massa esquemática, não projeto executivo**. O motor
honra o que molda a massa (larguras de via, % verde, área comum/unidade, cul-de-sac, doação);
vaga de estacionamento, via de pedestre e portaria são **notas de conformidade** (o urbanista
resolve no executivo), não geometria desenhada.

## 4. Modelo de dados — `perfil.normas_urbanisticas` (a construir)

O extrator da LUOS (Fase 1.8) passa a capturar, por município, um bloco de normas urbanísticas
(cada campo com proveniência artigo/página, como os demais parâmetros):

```
normas_urbanisticas:
  via_local_m: {sem_estac: 6.0, estac_1_lado: 9.0, estac_2_lados: 11.0}   # I–III
  via_pedestres_m: 1.90                                                    # IV
  area_comum_m2_por_unidade: 6.0                                           # V
  portaria_max_m2: 10.0                                                    # VI
  vaga_visitante_pct: 0.12   vaga_visitante_min: 4                         # VIII
  cul_de_sac_obrigatorio: true                                            # IX
  area_verde_pct: <da diretriz — ver §2>                                   # sistema de áreas verdes
  doacao_pct: 0.10   doacao_min_area_m2: 15000                             # Art. 16
```

Ausência de qualquer campo → o motor usa o fallback de boas práticas **rotulado** (não trava).

## 5. Fases de implementação (incrementos testáveis, cada um com PNG no dump real)

1. **Verde data-driven** — tira o hardcode; o piso de verde do motor lê a diretriz
   (`doacao_split.verde` ou `area_verde_pct`); estilo vira fallback rotulado. Conformidade:
   "área verde ≥ exigência da diretriz".
2. **Cul-de-sac** (Art. 11 IX) — toda via sem saída ganha bulbo de retorno; é requisito legal
   **e** o lever de eficiência viária (as referências Urbia batem ~15% de viário com cul-de-sac).
   Conformidade: "toda via sem saída tem cul-de-sac".
3. **Larguras de via da diretriz** (Art. 11 I–III) — largura = valor do município conforme a
   política de estacionamento; hoje hardcoded.
4. **Área comum ≥ 6 m²/unidade** (Art. 11 V) — piso de lazer derivado do nº de lotes.
5. **Notas de conformidade** dos itens executivos (vagas, pedestres, portaria).

## 6. O AGENTE EXTRATOR da diretriz (o que lê e traz tudo)

O coração desta fase: um **agente que lê o documento da diretriz** (LUOS / lei de condomínios /
plano diretor, PDF ou texto) e devolve o bloco `normas_urbanisticas` estruturado, **com
proveniência por campo** (artigo + página + trecho citado). Estende o `extrator_luos.py`
(Fase 1.8), que já faz isso para lote/doação/CA.

**Por que é §1-compliant (não viola "número só em Python"):** o LLM **não inventa** número — ele
**lê o que está escrito** e transcreve para campo estruturado ("as vias condominiais sem saída
deverão ser providas de cul de sac" → `cul_de_sac_obrigatorio: true`, Art. 11 IX). O número/regra
**vem da diretriz**, com citação rastreável. O Python valida e usa. É extração de documento, não
geração de dado. Campo sem base no texto → `null` + rótulo "não extraído / verificar na
prefeitura" (degradação honesta, nunca preenchido no chute).

**Contrato de saída do agente** (cada campo é `{valor, artigo, pagina, trecho, confianca}`):
larguras de via (I–III), via de pedestres (IV), área comum/unidade (V), portaria (VI), vagas
(VII–VIII), cul-de-sac (IX), doação % + gatilho de área (Art. 16), **APA/área verde %** (o "10%
a título de APA"), e o que mais a diretriz fixar. Ausente → `null` rotulado.

**Revisão humana:** a extração é **proposta**, não verdade final — o operador confirma/edita no
perfil (como já é o fluxo da LUOS confirmada vs não-confirmada). Só `status=confirmado` entra no
número; senão o estudo roda em `BASE_FEDERAL` e avisa.

## 7. Como isso vira a "skill/padrão por tipo"

O padrão de urbanismo (alto/médio/baixo) tem DOIS componentes, e este doc separa os dois:

- **O que é LEI** (diretriz do município): larguras, % verde, doação, cul-de-sac, área comum.
  Vem do dado, igual para qualquer perfil, muda por cidade. É esta spec.
- **O que é ESTILO** (preferência de composição por padrão): traçado (alto = orgânico de contorno;
  baixo = grelha eficiente), tamanho-alvo de lote, programa de lazer/amenidades. É o
  `urbanismo_estilo.py`, editável por arquivo, calibrado pelas avaliações do operador (memória U5).

A diretriz é o **piso inegociável**; o estilo escolhe **como** compor acima desse piso.
