# Fase 9.7 — Urbanismo: traçado de verdade (viário-malha + quadras como faces + áreas públicas formadas)

> **A fase grande, e a que ataca a dor de raiz.** Até aqui o sistema **nunca teve um traçado de
> ruas**: o viário é "espaço negativo" (aproveitável − lotes − reservas), a quadra é uma faixa
> de grade, o institucional é um disco de canto e o clube é um círculo central. Tudo o que o
> operador aponta há várias telas — vias desconexas, lazer no círculo, áreas mal demarcadas —
> decorre disso. Esta fase **inverte a geração**: as ruas vêm primeiro (malha conectada a partir
> do esqueleto da IA), as quadras são os miolos cercados pelas ruas (faces da malha), e as áreas
> públicas (institucional, clube) viram **quadras formadas com frente para via**. Referencia
> `ARCHITECTURE.md` (§1-A, §2) e as Fases 9.1/9.3/9.4/9.5/9.6. **IA propõe os eixos; Python
> constrói a malha, deriva as quadras e mede.**

## 0. A inversão (o que muda na raiz)

| Hoje (errado) | 9.7 (correto) |
|---|---|
| Viário = aproveitável − lotes − reservas (sobra desconexa) | Viário = **malha de ruas conectada** (eixos da IA → buffer com largura legal) |
| Quadra = faixa horizontal de uma grade | Quadra = **face da malha** (miolo cercado por ruas) |
| Institucional = disco crescido num canto (sem frente) | Institucional = **quadra com frente para via** (critérios legais) |
| Clube = disco central (placeholder) | Clube = **quadra/figura com frente** (não círculo) |
| Sobra → slivers anexados ao verde (picotado) | Sobra → **quadra verde formada** (face pequena) |

**A fronteira do §2 não se move:** a IA já entrega a intenção (esqueleto de eixos + arquétipo +
percentuais — Fase 9.1). O Python transforma esses eixos em **grafo de ruas conectado**, deriva
as quadras como **faces** da malha, e mede tudo. Nenhum número/coordenada final vem do LLM.

## 1. Objetivo

Gerar um **parcelamento legível como projeto**: ruas que conectam, quadras de verdade, lotes
dentro das quadras, e áreas públicas (lazer, institucional, verde) como **figuras formadas com
frente para via** — não sobra, não círculo, não blob. Continua **ESTUDO DE MASSA ESQUEMÁTICO**
(§1-A): é uma **aproximação** de malha real — melhor que a sobra de hoje, ainda não o traçado
executivo do urbanista. O ganho é traçado conectado + áreas formadas; o refino orgânico é
iterativo.

## 2. O que NÃO muda (não-regressão)

- **Reaproveita tudo que já funciona:** `_subdividir_quadra` (loteia um polígono com clamp
  legal — agnóstico à origem da quadra), o clamp/diretrizes (9.3/9.4), a medição
  (`distribuicao_tamanhos`, `conformidade_legal`, heatmap), `lotes_features` (9.5), a separação
  verde reservado/sobra e a estilização (9.6). **Esses não se reescrevem.**
- **Fronteira §2 imóvel:** IA propõe eixos/percentuais; Python materializa e mede.
- Snapshot versionado e contrato de números do `/medir` preservados (os números podem mudar de
  valor — o layout é outro —, mas a **forma** do contrato e as invariâncias se mantêm).
- Os princípios (clamp legal `[piso,teto]`, doação ≥ mínimo, §1-A) continuam valendo sobre o
  novo layout.

## 3. O algoritmo (validado na espinha)

```
ENTRADA: área aproveitável, esqueleto de eixos da IA (9.1), arquétipo, perfil, diretrizes (9.4), DEM (2.5)

1. MALHA VIÁRIA (nova — o coração):
   a. eixos = esqueleto da IA (normalizado→métrico, validado) + conexões à divisa/entrada
   b. hierarquia: tronco/coletora (≥21 m) vs. ramos/local (12–14 m)  [larguras legais]
   c. ruas = unary_union( buffer(cada eixo, largura/2) ) ∩ aproveitável
   d. GARANTIR CONECTIVIDADE: a malha é uma peça só; trechos soltos do esqueleto são
      conectados ao tronco mais próximo ou descartados (registrado). Sem ilhas de via.
2. QUADRAS = FACES da malha (nova):
   a. linhas = bordas da gleba ∪ eixos das ruas
   b. faces = polygonize(linhas)              # os polígonos que as ruas cercam
   c. quadra = face − ruas                     # miolo, descontada a largura da via
   d. (cada quadra herda a orientação/declividade da 2.5 para o lote)
3. LOTES: para cada quadra, _subdividir_quadra(quadra, perfil, clamp)   # REUSA 9.3/9.4
4. ÁREAS PÚBLICAS como QUADRAS FORMADAS (nova):
   a. INSTITUCIONAL: escolher/recortar UMA quadra que toque via oficial, com
      frente ≥10 m, relação frente/prof ≤1/3, círculo inscrito ⌀≥10 m, declividade ≤15% (DEM)
      — dimensionada ao alvo da doação; NÃO um disco de canto.
   b. CLUBE/LAZER: uma quadra/figura com frente para via (não círculo central);
      o verde de lazer ao redor é quadra(s) verde(s), não anel de placeholder.
   c. SOBRA: faces pequenas/residuais viram QUADRAS VERDES formadas (não slivers no verde).
5. MEDIR: quadro de áreas, distribuição, conformidade, heatmap — tudo como já mede (reusa).
   Viário agora é a área da MALHA (medida), não a sobra.
SAÍDA: lotes_features (9.5) + ruas (malha) + quadras públicas formadas, todos GeoJSON separados.
```

**Critérios legais do institucional (pesquisados — Lei municipal/6.766):** área pública com
**frente ≥10 m para via oficial**, **relação frente/profundidade ≤1/3**, **círculo inscrito de
⌀≥10 m**, **declividade ≤15%**. Por isso precisa ser uma **quadra formada com acesso por rua** —
e tipicamente **na borda com acesso pela via principal**, não encravada. (A localização final é
da Prefeitura nas Diretrizes — §1-A: "verificar na prefeitura".)

## 4. Contrato de API

`PropostaUrbanisticaOut` ganha o viário como **malha** e as áreas públicas **formadas**:
```jsonc
"geometria": {
  "rotulo": "esquemático",
  "lotes_features": { "type": "FeatureCollection", "features": [ /* 9.5, por lote */ ] },
  "viario": {                                   // AGORA malha conectada (não sobra)
    "type": "MultiPolygon", "coordinates": [...],
    "conexo": true, "trechos": 1, "hierarquia": { "tronco_m": 21, "local_m": 12 } },
  "quadras": { "type": "FeatureCollection", "features": [ /* cada quadra como face */ ] },
  "sistema_lazer": { "type": "Polygon", "frente_via_m": 14, "forma": "quadra" },   // não círculo
  "institucional": { "type": "Polygon", "frente_via_m": 12, "circulo_inscrito_m": 11,
                     "declividade_pct": 8, "qualifica_legal": true },              // quadra formada
  "areas_verdes_reservada": {...}, "areas_verdes_sobra": {...}   // 9.6, sobra agora = quadras verdes
},
"viario_diagnostico": { "conexo": true, "trechos_descartados": 0,
                        "obs": "malha a partir dos eixos da IA; trechos soltos conectados ao tronco" },
"institucional_diagnostico": { "qualifica_legal": true,
   "checks": { "frente_min_10m": true, "frente_prof_1_3": true, "circulo_10m": true, "decliv_15": true },
   "obs": "quadra com frente para via; localização final definida pela Prefeitura nas Diretrizes" },
"avisos": [ /* … 9/9.4 … */,
  "Viário é malha esquemática a partir dos eixos propostos pela IA; o traçado executivo é do urbanista.",
  "Áreas públicas (institucional/lazer) são quadras formadas com frente para via — localização e forma finais com a Prefeitura/urbanista (art. 6º Lei 6.766)." ]
```

## 5. Critérios de aceite (testáveis — mordem os 3 problemas apontados)

1. **Viário conectado (resolve "vias desconexas"):** a malha viária é **uma peça conexa**
   (`viario.conexo == true`); não há ilhas de via soltas (a tela com trechos que "somem e
   reaparecem" **falha** este critério). Teste de conectividade do grafo.
2. **Quadras são faces da malha (resolve "grade de faixas"):** cada quadra é um polígono
   **cercado por vias** (face da malha), não uma faixa horizontal; `quadras` é uma
   FeatureCollection com ≥2 faces; viário **não** é mais subtração (é a área da malha medida).
3. **Institucional é quadra formada (resolve "blob de canto"):** `institucional.qualifica_legal
   == true` com os 4 checks (frente ≥10 m, frente/prof ≤1/3, círculo ⌀≥10 m, declividade ≤15%);
   **não** é um disco de canto; toca via oficial. Se nenhuma quadra qualifica, rotula
   "institucional não encaixa nos critérios — definir com a Prefeitura" (degradação honesta).
4. **Clube não é círculo (resolve "lazer no círculo"):** `sistema_lazer.forma == "quadra"` com
   frente para via; teste geométrico rejeita círculo (ex.: razão área/perímetro² fora da de um
   disco) — a figura tem cantos/frente, não é um disco central.
5. **Verde não picotado (resolve "verde em retalhos"):** a sobra vira **quadras verdes formadas**
   (faces), não slivers; `areas_verdes_sobra` tem nº de peças baixo e cada uma com área mínima
   (não dezenas de cacos).
6. **Invariância de áreas:** viário(malha) + Σ quadras (lotes + públicas) ≈ aproveitável (±1%);
   `retalho_perdido ≤ 1,5%` (9.4 preservado).
7. **Reuso intacto:** lotes saem de `_subdividir_quadra` com clamp legal `[piso,teto]`
   (`fora_da_faixa == 0`, 9.4); distribuição/conformidade/heatmap/`lotes_features` (9.3/9.4/9.5)
   funcionam sobre o novo layout sem reescrita.
8. **Fronteira §2 + §1-A:** stub fornece eixos; **nenhuma coordenada final vem do stub** — Python
   constrói a malha e mede; selo "ESQUEMÁTICO" + "verificar com urbanista"; regex sem
   "aprovado/viável/regular".
9. **IA propõe, Python materializa:** os eixos da IA são a semente; trechos inválidos são
   conectados ou descartados com registro (`viario_diagnostico`), nunca propagados como ilha.
10. **Não-regressão do que vale:** clamp/diretrizes (9.4), separação verde (9.6), `lotes_features`
    (9.5) preservados; suítes dessas fases verdes no que não for o layout em si. (Os
    valores-ouro de quadro de áreas mudam de número — o layout é outro —, mas as **invariâncias**
    e os **clamps** seguem.)

> **Expectativa honesta (registrada):** esta é a primeira versão de uma malha real. Espera-se
> ruas conectadas, quadras de verdade e áreas públicas formadas — uma aproximação **melhor que a
> sobra de hoje**, porém **ainda não o traçado orgânico do urbanista** (curvas finas, encaixe
> perfeito ao relevo). O refino do traçado (mais orgânico) é iterativo, em fases seguintes. O
> pórtico de entrada entra **depois** desta (agora há via principal onde ancorá-lo).

## 6. Fora de escopo (registrado)

- **Traçado orgânico de qualidade executiva** (a beleza do urbIA) — refino iterativo posterior;
  aqui a malha é conectada mas esquemática.
- **Pórtico de entrada** — próxima fase (depende da via principal desta).
- **Render artístico / árvores / ícones** — Nível 3, futuro.
- **Otimização do traçado** (maximizar valor/lotes) — é o "quebrar a cabeça" do urbanista (§1-A).
- **Projeto aprovável, técnicos, terraplenagem, custos (SINAPI/SICRO)** — mantidos fora.

## 7. Arquivos esperados (latitude de implementação)

- `core/urbanismo_geom.py` — **reescrita do traçado** (a parte central):
  - `construir_malha(eixos_ia, arquetipo, larguras, aprov)` → malha viária **conexa** (grafo de
    ruas; reusa `centerline.buffer(largura/2)` que já existe; garante conectividade).
  - `quadras_por_faces(malha, aprov)` → quadras como faces (`shapely.ops.polygonize`), descontada
    a via. **Substitui** `_linhas_de_quadra` (grade).
  - `_subdividir_quadra` — **reusado sem mudança** para lotear cada face.
  - `institucional_como_quadra(quadras, ruas, dem, alvo)` → escolhe/recorta quadra com frente
    para via + critérios legais (frente ≥10 m, frente/prof ≤1/3, círculo ⌀10 m, declividade
    ≤15%). **Substitui** `_reservar_institucional` (disco de canto).
  - `clube_como_quadra(...)` → figura com frente para via. **Substitui** `_reservar_lazer`
    (disco central).
  - sobra → `quadras_verdes_formadas` (faces pequenas), não slivers.
- `core/urbanismo_medida.py` — `viario` = área da malha; `quadras` FeatureCollection;
  `*_diagnostico` (conectividade, qualificação legal do institucional). Medição reusa o resto.
- `models/schemas.py` — `viario` com `conexo`/`hierarquia`; `quadras` FC; `institucional`/
  `sistema_lazer` com `frente_via_m`/`forma`/`qualifica_legal`; diagnósticos.
- `routers/urbanismo.py` — resposta com malha + quadras + áreas formadas + diagnósticos.
- Frontend `MapaLeaflet`/`CardUrbanismo` — desenhar a **malha viária** (faixas de rua conectadas,
  cinza forte), as **quadras** (contorno), os **lotes** por face (9.5, cor por score), e as
  **áreas públicas formadas** (institucional/clube/verde com forma e rótulo — 9.6); legenda.
- Testes: `tests/test_urbanismo_malha.py` — conectividade do viário (1 peça), quadras como faces,
  institucional qualifica_legal (4 checks), clube não-círculo, verde não picotado, invariância de
  área, reuso do clamp; calibrado no São Roque, offline.

A spec fixa **contrato + critérios + ALGORITMO + FONTES**. **A IA propõe os eixos; o Python
constrói a malha de ruas conectada, deriva as quadras como os miolos que as ruas cercam, loteia
cada quadra (reusando o que já existe), e forma o institucional e o clube como quadras com frente
para via** — viário deixa de ser sobra, quadra deixa de ser faixa, institucional deixa de ser
blob, clube deixa de ser círculo. A fronteira do §2 fica imóvel, e o urbanista segue
insubstituível (§1-A). É a primeira versão de uma malha real — conectada e formada, ainda
esquemática; o refino orgânico vem depois.
