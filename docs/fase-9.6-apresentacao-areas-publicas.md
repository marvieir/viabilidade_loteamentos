# Fase 9.6 — Urbanismo: apresentação das áreas públicas (legibilidade, sem tocar número nem traçado)

> Fase curta de **apresentação**. O diagnóstico revelou que verde/lazer/institucional **vão ao
> mapa, mas aparecem apagados** (opacidade 0,3, borda única, verde sobre satélite verde), e que
> o verde virou **picotado** (na 9.4, `areas_verdes = verde_reservado ∪ sobra_de_ponta`). Esta
> fase estiliza as áreas públicas com destaque, **separa o verde-bloco da sobra de ponta** em
> campos distintos, e aumenta o mapa. **Não muda número, não muda o gerador, não toca o
> viário** (o viário-malha é a Fase 9.7, o Nível 2). Referencia `ARCHITECTURE.md` (§1-A, §2) e
> as Fases 9.4/9.5.

## 1. Objetivo

Tornar as áreas públicas **legíveis no mapa**: o verde central como bloco limpo e destacado, o
lazer/clube com cor de equipamento, o institucional visível, a sobra de ponta como "verde
remanescente" discreto — em vez do verde picotado e apagado atual. Aumentar a área do mapa para
análise. **Puramente apresentação + um ajuste de serialização que não altera totais.**

**O que isto NÃO é:** não é o viário-malha (Fase 9.7 / Nível 2) — o viário continua como está
(será refeito na próxima fase). Não é o pórtico (depende do viário, fica para depois). Não é
render artístico (Nível 3).

## 2. O que NÃO muda (não-regressão — crítico)

- **Zero mudança de número.** Separar `areas_verdes` em reservado + sobra é a **mesma
  geometria** — a soma continua idêntica (validado: 1488 == 1488). Quadro de áreas,
  `distribuicao_tamanhos`, conformidade (verde total), heatmap — **idênticos**.
- **Gerador intocado** (subdivisão, clamp, remate, diretrizes). **Viário intocado** (segue como
  sobra; a Fase 9.7 o refaz). Só muda a **separação do verde na serialização** e a
  **estilização no front**.
- **Fronteira do §2 imóvel:** só apresentação; nenhum número vem do LLM.
- `/medir` e snapshot inalterados no contrato de números. Suítes 1…9.5 verdes.

## 3. Backend — separar verde reservado de sobra de ponta

Na 9.4 (passo 4), a sobra de ponta foi anexada a `areas_verdes`, misturando o bloco central com
retalhos espalhados. Separar em **dois campos** (sem mudar o total):

```python
# core/urbanismo_geom.py — manter os dois separados ao reservar/devolver
verde_reservado = ...        # o bloco limpo (clube/verde central planejado)
sobra_ponta     = ...        # a sobra de ponta devolvida ao verde (9.4 passo 4)

# core/urbanismo_medida.py — geojson_do_layout: expor separado
"areas_verdes_reservada": _gj(verde_reservado),   # bloco limpo (destaque forte)
"areas_verdes_sobra":     _gj(sobra_ponta),        # retalho remanescente (discreto)
"areas_verdes":           _gj(unary_union([verde_reservado, sobra_ponta])),  # mantido p/ compat e quadro
```

- O **quadro de áreas e a conformidade continuam usando o verde total** (`areas_verdes` =
  reservado ∪ sobra) — número idêntico ao de hoje.
- Os dois campos novos são **só para o mapa** distinguir bloco (destaque) de retalho (discreto).
- `sistema_lazer`, `institucional`, `arruamento` seguem como hoje (o viário será refeito na 9.7).

## 4. Frontend — estilizar com destaque e contraste

Em `MapaLeaflet`/`CardUrbanismo`, dar a cada camada **estilo próprio com contraste sobre
satélite**, borda visível, e ordem de desenho que não deixe as áreas públicas serem encobertas:

| Camada | Estilo proposto (ajustável) | Observação |
|---|---|---|
| `areas_verdes_reservada` | verde escuro, borda forte, fill ~0,5 | o "verde de verdade" — destaque |
| `areas_verdes_sobra` | verde claro/hachura, fill ~0,25, rótulo "remanescente" | discreto, não compete |
| `sistema_lazer` | cor de equipamento (ex.: azul/ciano), borda, rótulo "lazer/clube" | distinto do verde |
| `institucional` | laranja/roxo, borda, rótulo "institucional" | sempre desenhar se > 0 |
| `arruamento` | cinza mais forte (ex.: #64748b), fill ~0,4 | provisório (9.7 refaz) |
| lotes (9.5) | cor por faixa de score (como está) | — |

- **Contraste sobre satélite:** verde puro sobre vegetação some — usar verde escuro saturado +
  borda branca/escura, ou padrão de hachura, para destacar do fundo.
- **Legenda no mapa:** uma legenda clara das camadas (verde reservado, remanescente, lazer,
  institucional, viário, + a faixa de score dos lotes que já existe).
- **Ordem de desenho:** áreas públicas com borda visível **por cima o suficiente** para serem
  lidas (não encobertas pelos lotes); ou borda destacada que apareça mesmo sob os lotes.
- **Mapa maior (comentário 1):** aumentar a altura do `MapaLeaflet` e/ou botão expandir/tela
  cheia; zoom inicial mais fechado na gleba.
- **Texto do "não avaliado" (comentário 5):** trocar "mínimo não confirmado" por algo como *"a
  LUOS confirma a doação total (20%), mas não detalha o split verde/institucional — verificar na
  prefeitura"*. (Só texto; a lógica "não avaliado" está correta e **não muda**.)

## 5. Critérios de aceite (testáveis)

1. **Invariância (número não muda):** `area(areas_verdes_reservada) + area(areas_verdes_sobra)`
   == `area(areas_verdes)` de hoje, ±0,5 m²; quadro de áreas, conformidade (verde total),
   distribuição e heatmap **idênticos** ao atual.
2. **Verde separado:** resposta traz `areas_verdes_reservada` (bloco) e `areas_verdes_sobra`
   (retalho) como geometrias distintas; `areas_verdes` (total) mantido para compat/quadro.
3. **Áreas públicas legíveis no mapa:** verde reservado, lazer, institucional renderizados com
   **cor e borda distintas e com contraste sobre satélite**; institucional desenhado sempre que
   > 0; legenda presente.
4. **Verde deixa de picotar:** o bloco reservado aparece como figura limpa destacada; a sobra
   aparece discreta/rotulada — não mais "retalhos verdes espalhados competindo".
5. **Mapa maior:** altura aumentada e/ou expandir; a gleba ocupa a área útil.
6. **Texto do "não avaliado" melhorado:** explica que a LUOS confirma a doação total mas não o
   split (a lógica permanece "não avaliado" — correta).
7. **§1-A preservado:** selo "ESQUEMÁTICO", nota de traçado aproximado, avisos — presentes;
   regex sem "aprovado/viável/regular".
8. **Não-regressão total:** gerador, viário, números — intactos; suítes 1…9.5 verdes; só
   serialização do verde (split) e estilo/UX do front mudaram.

## 6. Fora de escopo (registrado)

- **Viário como malha conectada / eixos de rua reais** — é a **Fase 9.7 (Nível 2)**, a próxima e
  grande; aqui o viário segue como está (sobra), só com cor um pouco mais forte.
- **Pórtico de entrada** — depende de via principal real; fica para depois da 9.7.
- **Render artístico / árvores / ícones / forma de equipamento do clube** — Nível 3, futuro.
- **Mudança de número, gerador ou traçado** — proibido nesta fase.

## 7. Arquivos esperados (latitude de implementação)

- `core/urbanismo_geom.py` — manter `verde_reservado` e `sobra_ponta` como referências separadas
  ao montar o layout (já existem internamente; só não descartar a distinção).
- `core/urbanismo_medida.py` — `geojson_do_layout` expõe `areas_verdes_reservada` e
  `areas_verdes_sobra`; mantém `areas_verdes` total para o quadro/conformidade.
- `models/schemas.py` — dois campos novos de geometria; total mantido.
- `routers/urbanismo.py` — resposta com os campos novos; `/medir` idem.
- Frontend `MapaLeaflet`/`CardUrbanismo` — estilos distintos com contraste, legenda, mapa maior,
  texto do "não avaliado"; ordem de desenho que torne as áreas públicas legíveis.
- Testes: `tests/test_urbanismo_apresentacao.py` — invariância (verde reservado + sobra ==
  total), campos presentes, número idêntico ao atual, offline.

A spec fixa **contrato + critérios**. **Só apresentação:** separa o verde-bloco da sobra,
estiliza as áreas públicas com destaque, aumenta o mapa — número nenhum muda, o viário segue
intocado (será refeito na 9.7), a fronteira do §2 fica imóvel. A legibilidade da **malha de
ruas** é a próxima fase (Nível 2), que é a grande.
