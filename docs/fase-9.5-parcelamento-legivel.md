# Fase 9.5 — Urbanismo: parcelamento legível (desenhar lote a lote)

> Puramente de **apresentação da geometria que o motor já mede**. Hoje o backend gera um
> `Polygon` por lote, mas **funde tudo com `unary_union` na serialização** → o mapa mostra uma
> "mancha" translúcida (a união dos lotes) em vez do parcelamento. Esta fase para de fundir,
> expõe **cada lote como uma Feature GeoJSON** e desenha **lote a lote** — vias, lazer,
> institucional e verde como camadas distintas. Referencia `ARCHITECTURE.md` (§1-A, §2) e as
> Fases 9/9.1/9.4. **Não muda nenhum número, não muda o gerador, não toca a fronteira do §2.**

## 1. Objetivo

Tornar o estudo de massa **legível como um parcelamento**: cada lote desenhado como seu
polígono (com borda), as vias como faixas próprias, as áreas de lazer/verde/institucional como
figuras delimitadas — em vez da mancha de região atual. A geometria **já existe** em
`layout.lotes: list[Polygon]`; o trabalho é **expô-la lote a lote** (backend) e **renderizá-la
lote a lote** (frontend).

**O que isto NÃO é (escopo honesto):** não é o gerador de vias sinuosas (Nível 2) nem o render
artístico (Nível 3). É a correção de que o desenho **mostre o que o motor mede**. Continua
"ESTUDO DE MASSA ESQUEMÁTICO" — o traçado segue esquemático; o ganho é **legibilidade** (lotes
individuais), não fidelidade de traçado nem acabamento pictórico.

## 2. O que NÃO muda (não-regressão — crítico)

- **Zero mudança de número.** A serialização lote a lote é a **mesma geometria**, só não
  fundida: a **soma das áreas das Features == área do MultiPolygon de hoje** (validado). Quadro
  de áreas, `distribuicao_tamanhos`, `n_lotes`, heatmap, conformidade — **idênticos**.
- **Gerador intocado** (`_subdividir_quadra`, clamp, remate, diretrizes da 9.4). Só muda
  `geojson_do_layout` (serialização) e o `CardUrbanismo`/`MapaLeaflet` (render).
- **Fronteira do §2 imóvel:** continua só renderizar o GeoJSON que o motor mediu; nenhum número
  vem do LLM, nenhuma geometria nova é criada — a existente deixa de ser fundida.
- Snapshot versionado e `/medir` inalterados no contrato de números. Suítes 1…9.4 verdes.

## 3. Backend — parar de fundir, expor cada lote como Feature

Em `core/urbanismo_medida.py::geojson_do_layout`, **substituir o `unary_union(layout.lotes)`**
por uma **FeatureCollection** com uma Feature por lote, casando geometria + atributos **por
índice** (o modelo atual: geometria em `layout.lotes[i]`, atributos em listas paralelas e na
medição — `med.heatmap["por_lote"][i]`, `layout.lote_quadra[i]`, `_lados_mrr(layout.lotes[i])`):

```python
def geojson_do_layout(layout, to_wgs, por_lote) -> dict:
    def _gj(geom):
        if geom is None or geom.is_empty: return None
        return mapping(transform(to_wgs, geom))

    # NOVO: cada lote = 1 Feature (geometria + props que já existem), casado por índice
    feats = []
    for i, geom in enumerate(layout.lotes):
        if geom is None or geom.is_empty: continue
        t, p = _lados_mrr(geom)                      # testada/profundidade já calculadas assim
        pl = por_lote[i] if i < len(por_lote) else {}
        feats.append({
            "type": "Feature",
            "geometry": mapping(transform(to_wgs, geom)),
            "properties": {
                "lote_id": pl.get("lote_id", f"L{i+1:03d}"),
                "area_m2": pl.get("area_m2"), "score": pl.get("score"),
                "testada_m": t, "profundidade_m": p,
                "quadra_id": layout.lote_quadra[i] if i < len(layout.lote_quadra) else None,
                "faixa_score": _faixa(pl.get("score")),   # p/ colorir heatmap no mapa
            },
        })
    return {
        "rotulo": "esquemático",
        "lotes_features": {"type": "FeatureCollection", "features": feats},  # <-- NOVO
        "lotes": _gj(unary_union(layout.lotes)) if layout.lotes else None,    # mantido p/ compat
        "arruamento": _gj(layout.arruamento),
        "areas_verdes": _gj(layout.areas_verdes),
        "sistema_lazer": _gj(layout.sistema_lazer),
        "institucional": _gj(layout.institucional),
    }
```

- **`lotes_features`** (FeatureCollection) é o campo novo — uma Feature por lote, com as
  propriedades que **já existem** (sem recalcular nada).
- **`lotes`** (MultiPolygon fundido) **permanece** por compatibilidade — o front passa a usar
  `lotes_features`; o fundido fica como fallback.
- `viario`/`verde`/`lazer`/`institucional` já vêm separados — mantêm-se; lazer e verde podem
  ganhar `rotulo` nas props para legenda.
- Schema (`models/schemas.py`): `geometria.lotes_features: FeatureCollection`; cada Feature com
  as props do `LoteOut` **+ a geometria** (o `LoteOut` numérico em `distribuicao_tamanhos`
  continua como está).

## 4. Frontend — desenhar lote a lote

Em `MapaLeaflet`/`CardUrbanismo`: **iterar a FeatureCollection** em vez de empurrar um polígono
único de lotes.

```tsx
// CardUrbanismo: usa lotes_features (cai p/ lotes fundido se ausente)
const lotesFC = proposta?.geometria?.lotes_features;
// MapaLeaflet: uma camada de lotes que itera as Features
<GeoJSON
  data={lotesFC}
  style={(f) => ({
    color: "#374151", weight: 0.8,                 // BORDA visível por lote
    fillColor: CORES_FAIXA[f.properties.faixa_score] ?? "#9CA3AF",
    fillOpacity: 0.45,                               // sólido, não a mancha translúcida
  })}
  onEachFeature={(f, layer) =>
    layer.bindPopup(
      `Lote ${f.properties.lote_id} · ${f.properties.area_m2?.toFixed(0)} m² · ` +
      `score ${f.properties.score?.toFixed(1)} · quadra ${f.properties.quadra_id ?? "-"}`
    )
  }
/>
```

- **Cada lote com sua borda** (`weight` visível) — é o que separa o parcelamento da mancha.
- **`fillOpacity` maior** (~0.45) e **cor por faixa de score** → o heatmap vira o próprio mapa
  (lotes quentes/frios visíveis, como no urbIA), com a legenda de faixas que já existe.
- **Popup por lote** (área, score, quadra) — usa as props da Feature.
- Vias (faixa cinza), lazer/clube, verde e institucional com **estilos distintos** (cores e
  rótulos próprios) — camadas separadas, cada uma legível.
- Mantém o selo **ESQUEMÁTICO** e a nota "eixos de via aproximados; o valor é o quadro de áreas,
  não a precisão do desenho" (§1-A) — o traçado segue esquemático.

## 5. Critérios de aceite (testáveis)

1. **Invariância de área (o número não muda):** `Σ área das Features de lotes_features` ==
   área do `lotes` (MultiPolygon de hoje), ±0,5 m²; `len(features)` == `n_lotes` ==
   `len(distribuicao_tamanhos.lotes)`. **Prova de que serializar lote a lote não altera nada.**
2. **Uma Feature por lote, com geometria + props:** cada Feature tem `geometry` (Polygon) e
   `properties` com `lote_id`, `area_m2`, `score`, `testada_m`, `profundidade_m`, `quadra_id`,
   `faixa_score`; os valores **batem** com `distribuicao_tamanhos.lotes` e `heatmap.por_lote`
   (mesmo `lote_id` → mesmos números). Casamento por índice correto.
3. **Camadas separadas:** `arruamento`, `areas_verdes`, `sistema_lazer`, `institucional` saem
   como geometrias distintas (já saem) — render com estilos distintos; nenhuma fundida com lotes.
4. **Frontend desenha lote a lote:** o componente itera `lotes_features` (há `features.map`/
   `GeoJSON` sobre a coleção), cada lote com **borda visível**; não há mais um único polígono de
   lotes translúcido. Popup por lote funciona.
5. **Heatmap no mapa:** lotes coloridos por `faixa_score` (a legenda de faixas casa com as cores
   do mapa). (Opcional, mas recomendado — é o que aproxima do urbIA.)
6. **Compatibilidade:** `lotes` (fundido) ainda presente; se `lotes_features` ausente, o front
   cai para o fundido sem quebrar.
7. **§1-A preservado:** selo "ESQUEMÁTICO" + nota de traçado aproximado + avisos da 9/9.4
   presentes; **regex sem "aprovado/viável/regular"**. O ganho é legibilidade, não aprovação.
8. **Não-regressão total:** quadro de áreas, distribuição, conformidade, heatmap (números),
   `/medir` — **idênticos** ao atual; gerador intocado; suítes 1…9.4 verdes; só serialização e
   render mudaram.

## 6. Fora de escopo (registrado)

- **Vias sinuosas / quadras orgânicas / lotes em leque** (qualidade do traçado) — é o **Nível 2**,
  brainstorm seguinte; aqui o traçado segue esquemático, só fica legível lote a lote.
- **Render artístico / árvores / ícones de lazer / textura** (acabamento pictórico) — é o
  **Nível 3** (peça ilustrativa, com a trava "geometria manda na imagem"); fora.
- **Edição interativa do parcelamento na tela** — evolução.
- **Mudança de qualquer número ou do gerador** — proibido nesta fase (é só apresentação).

## 7. Arquivos esperados (latitude de implementação)

- `core/urbanismo_medida.py` — `geojson_do_layout` passa a montar `lotes_features`
  (FeatureCollection, 1 Feature/lote, props por índice); mantém `lotes` fundido p/ compat.
  Recebe `por_lote` (já calculado) para as props.
- `models/schemas.py` — `geometria.lotes_features: FeatureCollection`; Feature com props do lote
  + geometria.
- `routers/urbanismo.py` — passa `por_lote` ao serializador; resposta ganha `lotes_features`.
  `/medir` idem.
- Frontend `MapaLeaflet`/`CardUrbanismo` — iterar `lotes_features`, borda por lote, cor por
  `faixa_score`, popup por lote; estilos distintos para via/verde/lazer/institucional; selo e
  notas §1-A mantidos.
- Testes: `tests/test_urbanismo_features.py` — invariância de área (Σ features == fundido),
  contagem == n_lotes, props batem com `distribuicao_tamanhos.lotes`/`heatmap`, offline.

A spec fixa **contrato + critérios**. **O motor já mede lote a lote; esta fase apenas para de
fundir e desenha cada lote** — parcelamento legível (lotes, vias, lazer, institucional
individuais), número nenhum alterado, fronteira do §2 intacta, traçado ainda esquemático (§1-A).
A qualidade do traçado (vias orgânicas) é o **Nível 2**, a próxima conversa.
