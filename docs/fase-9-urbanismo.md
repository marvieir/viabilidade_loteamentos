# Fase 9 — Urbanismo (estudo de massa urbanística proposto por IA)

> Primeiro módulo em que a IA toca o **desenho**. Por isso a fronteira do §2 é o coração da
> spec: **a IA propõe o PROGRAMA na borda; o Python gera a geometria e mede TODOS os
> números.** O artefato que cruza a fronteira é um programa estruturado (JSON) — **nunca o
> polígono final do lote**. Referencia `ARCHITECTURE.md` (§1-A, §2, §6-A item 5, §7). Reusa a
> infra de LLM da 1.8 (sem credencial nova). Fecha o último degrau do nº de lotes
> (teto → + diretriz → **+ projeto urbanístico**).

## 1. Objetivo e fronteira de produto (§1-A — ler primeiro)

Produzir um **estudo de massa de pré-análise**: dado o KMZ (ou a união da Fase 8), as
restrições que o motor já computou, e um **perfil** (tipo de loteamento + público-alvo), a IA
propõe um programa urbanístico e o Python gera+mede um **layout esquemático** com quadro de
áreas, nº de lotes e heatmap de valorização.

**Não é o projeto urbanístico.** É a pré-análise que o *antecede*:
- O tool entrega "sob o perfil escolhido, esta gleba **comporta da ordem de** X lotes de ~Y m²
  com Z% de lazer" — **estudo de massa esquemático**, não traçado executivo.
- O **urbanista é insubstituível** (art. 6º/7º Lei 6.766: traçado viário definitivo,
  diretrizes da gleba, projeto aprovável). O tool **nunca** diz "projeto aprovado/viável/
  regular"; diz "estudo de massa — **verificar com urbanista**".
- A geometria gerada é rotulada **"ESQUEMÁTICA"** em toda saída; o valor é o quadro de áreas,
  o trade-off de densidade por perfil e o heatmap — não a precisão do eixo de via.

## 2. O que NÃO muda (não-regressão)

- **As fases 1–8 permanecem determinísticas e intactas.** O estudo de massa é uma **camada
  criativa separada e versionada** (§7); o laudo determinístico (Fase 7) **não** o consome no
  caminho crítico — ele entra como **cenário aditivo** (§8), nunca troca o headline em silêncio.
- A IA fica **na borda** (propõe programa) — **nenhum número** vem do LLM (§2). O Python gera a
  geometria e calcula 100% das medidas.
- Reusa a infra da 1.8: `ANTHROPIC_API_KEY` gated + TLS corporativa + gerador injetável + flag
  de desligar + **stub offline** (testes 100% sem rede), `claude-opus-4-8` com tool use forçado.
  **Sem credencial nova.**
- Suítes 1…8 verdes; o gerador geométrico é **Python puro (shapely/pyproj)**, separável e
  testável offline.

## 3. A fronteira LLM ↔ Python (o núcleo — onde um para e o outro começa)

```
   BORDA (LLM, não-determinístico)              NÚCLEO (Python, determinístico)
   ────────────────────────────────             ──────────────────────────────────
   lê: aproveitável + restrições (1,2,2.x,3)     recebe o PROGRAMA (snapshot)
       + perfil (tipo + público-alvo)            gera: viário snapado a partir do
   PROPÕE um PROGRAMA estruturado:                  esqueleto + quadras + LOTES
     • faixa de lote-alvo (m²)                       (subdivisão paramétrica)
     • hierarquia viária (larguras)               mede: quadro de áreas, nº de lotes,
     • % e lista de amenidades de lazer                área média, testada/profundidade
     • arquétipo de traçado                       pontua: heatmap de valorização por lote
     • densidade-alvo                             valida: NADA loteado sobre APP/≥30%/
     • esqueleto grosseiro (polilinhas das             verde-dura/faixa/servidão (recorta
       vias principais; zonas de amenidade)            contra a área aproveitável)
              │                                            ▲
              └──────── artefato = PROGRAMA JSON ──────────┘
                        (NUNCA polígono final de lote)
```

**Princípios invioláveis da fronteira:**
1. O LLM emite **intenção/programa + esqueleto**; **jamais** o polígono final de um lote ou o
   nº de lotes. Todo número da resposta é **medido pelo Python**.
2. O nº de lotes **emerge** da geração determinística dado o programa — a IA muda a densidade
   mudando o **programa** (lote maior → menos lotes), o Python conta. Satisfaz "a IA muda para
   mais/menos lotes" **sem** a IA cravar o número.
3. **A área aproveitável é a tela**: o gerador recorta tudo contra a união de restrições já
   computada (não loteia sobre APP, declividade ≥30%, verde-dura, faixa não-edificável,
   servidão de LT). Restrição violada → o lote não existe (recorte geométrico), não um aviso.
4. Esqueleto do LLM é **sugestão**: o Python **snapa/valida/regulariza**; se inviável
   (auto-intersecta, sai da gleba), o Python corrige ou ignora aquele trecho e **registra** —
   nunca aceita geometria crua do LLM como verdade.

## 4. Entradas

- **Da análise (já prontas):** geometria da gleba (1/8), área aproveitável + união de
  restrições (2/2.x), perfil municipal confirmado se houver (1.8: lote legal da zona, doação).
- **Do usuário (novas, declaradas):**
  - **`tipo_loteamento`**: `aberto` | `fechado` | `condominio_lotes` | `desmembramento` |
    `loteamento_rural`. (Afeta exigência de muro/pórtico, viário interno vs. oficial, e os
    mínimos legais aplicáveis.)
  - **`publico_alvo`**: `baixa` | `media` | `alta` — seleciona o **preset de perfil** (§5) e
    **condiciona o programa** que o LLM propõe.
  - Overrides opcionais (lote-alvo, % lazer, lista de amenidades) — todos com default do preset,
    rotulados, editáveis.

## 5. Perfis de público-alvo (PRESETS EMBARCADOS — não pesquisa ao vivo)

Decisão vetável (recomendada): as características de cada faixa são **conhecimento estável** →
**presets embarcados** (padrão "dado estável é pipeline, não agente"), editáveis e rotulados
*"perfil de referência de mercado — calibre com seu urbanista/corretor"*. O LLM **contextualiza
qualitativamente** o programa por perfil (sabe que alta renda é diferente), mas os **guard-rails
numéricos são determinísticos**. **Pesquisa web ao vivo** das características fica como evolução
(conecta com a futura Mercadológica).

| Parâmetro (preset) | `baixa` | `media` | `alta` |
|---|---|---|---|
| Lote-alvo (m²) | 125–250 | 250–450 | 600–1000+ |
| Densidade | alta (maximiza lotes) | média | baixa (exclusividade) |
| % lazer além da doação | mínimo (só obrigatório) | bom, sem luxo | alto (15–25%+) |
| Amenidades típicas | institucional básico | playground, quadra, salão | clube, lago, tênis, mirante, paisagismo |
| Viário | grelha eficiente | misto | sinuoso, lotes com fundo contra verde |
| Fechamento/pórtico | normalmente aberto | aberto ou fechado | fechado, pórtico elaborado |
| Trade-off | + lotes | equilíbrio | sacrifica lotes por R$/m² |

O preset é **entrada do programa**, não veredito — o motor mede o que sai e o usuário ajusta.

## 6. Como funciona (pipeline)

1. **Programa (borda):** `GeradorPrograma` (injetável; real = Claude API gated; stub offline)
   recebe restrições+perfil → propõe o **programa JSON** (§3) com justificativa por item e
   **proveniência** ("proposto por IA sob perfil alta renda; valide com urbanista").
2. **Geração (núcleo, determinístico):** `core/urbanismo_geom.py` (Python puro) toma o programa
   → gera viário (do esqueleto, snapado) → quadras → **lotes** (subdivisão paramétrica:
   testada-alvo × profundidade na faixa do perfil) → **recorta contra a área aproveitável**
   (nada sobre restrição). v1 deliberadamente **esquemática** (ex.: vias-espinha + fileiras de
   lotes perpendiculares; cul-de-sacs onde o perfil pede) — qualidade evolui por iteração.
3. **Medição (determinística):** quadro de áreas (vendável, áreas verdes, sistema de lazer,
   institucional, arruamento) + indicadores (comprimento de vias, leito carroçável, calçadas,
   testada/profundidade média, área média) + **nº de lotes**. Espelha o quadro do exemplo
   (imagem "Implantação"): Vendável / Verdes / Lazer / Institucional / Arruamento sobre a
   Área Líquida.
4. **Conformidade do programa:** confronta o quadro medido com os **% legais do perfil
   municipal** (doação, lote legal da zona — da 1.8/3.5): "lazer 8% < mínimo X% da zona —
   ajustar" (`atencao`), sem decidir aprovação.
5. **Heatmap de valorização (determinístico):** `score()` por lote (§ abaixo) → faixas + %;
   o **R$/m² diferenciado é multiplicador por faixa definido pelo usuário** (não preço
   inventado).

### Heatmap — scoring determinístico por lote
Score 0–10 por atributos **geométricos/medíveis** do lote (pesos do preset, editáveis):
fundo contra área verde/mata (privacidade — peso alto em `alta`), esquina, lote em cul-de-sac,
declividade média do lote (suave melhor), testada (maior melhor), proximidade de amenidade,
afastamento de via principal/entrada (ruído). Saída: score por lote + distribuição em faixas
(como a "Análise de Lotes"/"Heatmap de Score" do exemplo). **Sem preço absoluto** — o tool
ordena qualidade relativa; o R$/m² por faixa é input do usuário.

## 7. Determinismo & snapshot versionado

- A proposta do LLM é **não-determinística** → ao gerar, persiste-se um **snapshot versionado**
  (`proposta_id`, timestamp, perfil, programa completo, seed). **Toda medição/score roda sobre o
  snapshot** → "mesmo snapshot → mesma medição/heatmap" (determinístico e testável offline).
- Várias propostas coexistem (o usuário compara perfis/versões); cada uma é imutável. Regenerar
  cria nova versão — **não** sobrescreve.
- O **laudo determinístico (Fase 7) não muda**: o estudo de massa entra como **anexo/cenário
  rotulado**, com a ressalva §1-A; não contamina o caminho 1–8.

## 8. Integração (cenário aditivo — padrão 1.8/2.3)

O nº de lotes do estudo entra como **`cenario_urbanistico`** ao lado de teto/diretriz/otimista —
**não troca o headline em silêncio**. É, conceitualmente, o lote-count mais realista (fecha o
degrau do §6-A), então o front **pode** destacá-lo quando há proposta aceita — mas é **escolha
explícita de apresentação**, e o backend devolve todos os cenários (front não recalcula, §2).

## 9. Contrato de API

### 9.1 `POST /api/analises/{id}/urbanismo/propor` (perfil no corpo) → `PropostaUrbanisticaOut`
```jsonc
// REQUEST
{ "tipo_loteamento": "fechado", "publico_alvo": "alta",
  "overrides": { "lote_alvo_m2": 700, "pct_lazer": 0.20 } }   // opcional, default do preset

// RESPONSE (snapshot versionado)
{
  "proposta_id": "u_3550605_001", "versao": 1, "rotulo": "ESTUDO DE MASSA ESQUEMÁTICO",
  "perfil": { "tipo": "fechado", "publico_alvo": "alta" },
  "programa": {                                   // o que o LLM PROPÔS (proveniência)
    "lote_alvo_m2": 700, "densidade": "baixa", "pct_lazer": 0.20,
    "amenidades": ["clube","lago_app","tenis","mirante"],
    "arquetipo_viario": "sinuoso_fundo_verde",
    "origem": "proposto_llm", "justificativa": "perfil alta renda prioriza exclusividade…" },
  "geometria": { "tipo": "GeoJSON", "rotulo": "esquemático",
                 "viario": {…}, "quadras": {…}, "lotes": {…}, "areas_verdes": {…},
                 "lazer": {…}, "institucional": {…} },   // tudo gerado/medido pelo Python
  "quadro_areas": {
    "area_liquida_m2": 131433.75,
    "vendavel": { "m2": 74644.40, "pct_apo": 0.5679 },
    "areas_verdes": { "m2": 36686.92, "pct_apo": 0.2791 },
    "sistema_lazer": { "m2": 0.0, "pct_apo": 0.0 },
    "institucional": { "m2": 0.0, "pct_apo": 0.0 },
    "arruamento": { "m2": 20102.43, "pct_apo": 0.1529 }
  },
  "indicadores": { "n_lotes": 167, "area_media_m2": 446.97, "testada_media_m": 17.94,
                   "profundidade_media_m": 24.91, "comprimento_vias_m": 2635.47,
                   "leito_carrocavel_m2": 14984.98, "calcadas_m2": 10612.28 },
  "heatmap": { "score_medio": 8.97,
               "faixas": [ { "faixa": "9-10", "n": 29, "pct": 0.1736 }, /* … */ ],
               "por_lote": [ { "lote_id": "L001", "score": 9.2, "area_m2": 612 }, /* … */ ] },
  "conformidade_programa": [
    { "item": "lote_alvo", "status": "considerado", "leitura": "700 m² ≥ lote legal da zona (360 m²)" },
    { "item": "lazer", "status": "atencao", "leitura": "verificar mínimo da zona com urbanista" } ],
  "proveniencia": "Programa proposto por IA (perfil) + geometria e medidas geradas/medidas em Python sobre a área aproveitável da análise",
  "avisos": [
    "ESTUDO DE MASSA ESQUEMÁTICO — pré-análise (§1-A); NÃO é projeto urbanístico nem traçado executivo; o projeto e as diretrizes da gleba são do urbanista (art. 6º Lei 6.766).",
    "Nº de lotes e quadro de áreas MEDIDOS pelo motor sobre a proposta; a IA propôs o programa, não os números.",
    "Não contempla projetos técnicos (água, esgoto, energia, drenagem) nem custos de obra."
  ]
}
```
Sem `ANTHROPIC_API_KEY` → 503 honesto (gerador desligado). `GET .../urbanismo` lista as
propostas (snapshots) da análise; `GET .../urbanismo/{proposta_id}` devolve uma.

### 9.2 Medição independente do gerador (testabilidade)
`POST .../urbanismo/medir` recebe uma **geometria de layout** (GeoJSON de lotes/vias/verde) e
devolve **só** o quadro de áreas + indicadores + heatmap (determinístico, **sem LLM**). É o
endpoint que os valores-ouro aferem (mede o layout REAL de São Roque sem depender do LLM).

## 10. Critérios de aceite (testáveis)

**Princípio (do handoff):** os testes aferem que o **MOTOR MEDE** um layout e reproduz o
quadro, **não** que o LLM adivinhe o traçado.

1. **Quadro de áreas-ouro (São Roque / TIV 5.0)** — alimentando `/medir` com o layout real:
   `area_liquida = 131.433,75 m²`; **vendável 74.644,40 (56,79%)**; **verdes 36.686,92
   (27,91%)**; **arruamento 20.102,43 (15,29%)**; e a soma vendável+verdes+arruamento =
   **área líquida** (±0,5 m²). *(Requer o layout real como geometria — ver nota.)*
2. **Indicadores-ouro:** `n_lotes = 167`; `area_media = 446,97 m²` (e 167 × 446,97 ≈ vendável,
   ±0,5%); testada média 17,94 m; profundidade 24,91 m; comprimento de vias 2.635,47 m.
3. **Recorte contra restrições:** nenhum lote gerado intersecta APP/≥30%/verde-dura/faixa/
   servidão (teste geométrico: `Σ área de interseção lote∩restrição = 0`).
4. **Fronteira LLM↔Python:** com gerador-stub que devolve um **programa**, o Python gera e mede;
   **nenhum número da resposta vem do stub** (teste: stub não fornece n_lotes/áreas — eles são
   computados). Esqueleto inválido do stub (polilinha que auto-intersecta) → Python corrige/
   ignora e registra, **não** propaga geometria crua.
5. **Determinismo por snapshot:** medir/pontuar o mesmo snapshot duas vezes → resultado
   idêntico; regerar cria nova versão sem sobrescrever.
6. **Heatmap determinístico (2ª geração):** dado um conjunto de lotes, `score()` produz faixas
   estáveis; a distribuição por faixa e o `score_medio` são **cravados na 1ª geração validada**
   contra o projeto real (padrão "ouro de 2ª geração"); **nenhum preço absoluto** na saída.
7. **Presets de perfil:** `alta` produz programa com lote-alvo ≥ `media` ≥ `baixa` e %lazer
   `alta` ≥ `media` ≥ `baixa` (monotonicidade testável do guard-rail); overrides sobrepõem com
   proveniência.
8. **Aditivo, não headline:** `cenario_urbanistico` aparece ao lado dos demais; aproveitamento/
   financeira/laudo (1–8) **byte a byte** sem a Fase 9; o estudo entra no laudo só como anexo
   rotulado.
9. **§1-A:** rótulo "ESTUDO DE MASSA ESQUEMÁTICO" e os 3 avisos sempre presentes; **regex: sem
   "aprovado/viável/regular"**; "verificar com urbanista" presente.
10. **Offline + 503 + não-regressão:** `/medir` e `score()` rodam sem rede; propor sem chave →
    503; mesma entrada → mesma saída; suítes 1…8 verdes; gerador geométrico testado isolado.

> **Nota de dado de teste:** o critério 1–2 exige o **layout real de São Roque como geometria**
> (polígonos de lotes/vias/verde) — as imagens dão o quadro-alvo, mas o teste de medição precisa
> dos polígonos. Marco exporta do projeto/urbIA (KMZ/DWG/GeoJSON) ou, na falta, monta-se um
> layout sintético cujo quadro reproduz os números, e o São Roque real vira teste de validação
> quando a geometria chegar.

## 11. Fora de escopo (registrado)

- **Projeto urbanístico aprovável / diretrizes da gleba** (art. 6º/7º Lei 6.766) — do urbanista.
- **Projetos técnicos** (água, esgoto, energia, drenagem, pavimentação, terraplenagem) — fora;
  é a "Estimativa de Infraestrutura" do exemplo, **não** entra.
- **Custos de obra** — evolução. *(Referência para a fase futura: **SINAPI** (Caixa/IBGE) para
  custos unitários de edificação e **SICRO** (DNIT) para infra/viário — é a fonte oficial que
  faltava; ancora a tabela de custos sem inventar valor.)*
- **Otimização do traçado** (maximizar lotes/valor automaticamente) — o tool propõe um estudo,
  não otimiza; comparar versões é manual.
- **Edição interativa do traçado na tela / 3D / render** — evolução; o MVP gera e mede.
- **Pesquisa web ao vivo do perfil de mercado** — presets no MVP; pesquisa é evolução
  (Mercadológica).
- **Preço absoluto do lote / avaliação imobiliária** — o heatmap ordena qualidade; preço é input.

## 12. Arquivos esperados (latitude de implementação)

- `core/urbanismo_programa.py` — `GeradorPrograma` (interface injetável + real Claude API,
  prompts por perfil, anti-alucinação; stub offline). Emite **programa**, não geometria.
- `core/urbanismo_geom.py` — **Python puro**: viário (do esqueleto, snapado) + quadras + lotes
  (subdivisão paramétrica) + **recorte contra aproveitável**; gerador esquemático v1, separável.
- `core/urbanismo_medida.py` — quadro de áreas + indicadores + `score()` do heatmap (**puros**).
- `routers/urbanismo.py` — `propor` (503), `GET` lista/uma, **`medir`** (sem LLM).
- `models/schemas.py` — `ProgramaIn/Out`, `QuadroAreasOut`, `HeatmapOut`, `PropostaUrbanisticaOut`.
- Persistência: snapshots versionados por análise (volume, padrão 1.8/3).
- Frontend: item "Urbanismo" na sidebar + `CardUrbanismo` (seleção tipo+público-alvo; render do
  GeoJSON esquemático com **selo "ESQUEMÁTICO"**; quadro de áreas; heatmap de lotes com legenda
  de faixas + input de R$/m² por faixa; lista de versões; avisos §1-A). Front só renderiza
  GeoJSON/JSON — zero geo-matemática em JS.
- Testes: `tests/test_urbanismo_medida.py` (quadro/indicadores/heatmap-ouro, offline) +
  `tests/test_urbanismo_fronteira.py` (stub-programa → Python mede; recorte; determinismo).

A spec fixa **contrato + critérios**; o resto é latitude. **IA na borda propõe o programa;
Python puro gera e mede toda a geometria e todos os números** — a fronteira do §2 intacta, e o
urbanista insubstituível (§1-A).
