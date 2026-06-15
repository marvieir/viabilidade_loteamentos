# Fase 9.2 — Urbanismo: lotes heterogêneos guiados por valorização

> Corrige o defeito que o teste real expôs: o gerador aplicava **um lote-alvo uniforme** (800 m²
> para todo mundo), inflando o viário (37%) e deixando **retalhos perdidos** nas bordas.
> Loteamento real tem **mix de tamanhos**, e o tamanho é **consequência da qualidade da
> posição**. Esta fase faz a IA propor a **estratégia de mix + heurísticas de valorização**, e
> o Python **zoneia por qualidade, dimensiona cada lote conforme a zona e fecha as quadras sem
> sobra**. Referencia `ARCHITECTURE.md` (§1-A, §2, §7) e as Fases 9/9.1. **IA propõe a política;
> Python produz polígonos e números.** Pressupõe a 9.1 (traçado por arquétipo + topografia).

## 1. Objetivo e a distinção que protege a fase

Substituir o lote uniforme por um **mix heterogêneo** em que lotes premium (cota alta, fundo
para verde, frente para lazer, sossego) são maiores e melhor pontuados, e os comuns completam a
quadra — eliminando o retalho perdido e devolvendo o viário à faixa realista.

**A linha que mantém a fase honesta (decidida com o operador):**
- **NÃO é otimização** ("ache o melhor traçado que maximiza lotes quentes"). Otimização de
  layout urbano é problema de pesquisa em aberto e é o **"quebrar a cabeça" do urbanista** —
  insubstituível (§1-A). O tool não persegue uma distribuição-meta.
- **É aplicação de heurísticas conhecidas de valorização** (conhecimento estável de urbanismo):
  lote grande na cota alta, fundo para mata, frente para água/lazer, longe do ruído da via
  principal, sossego em cul-de-sac. A IA **propõe onde aplicá-las nesta gleba**; o Python
  materializa; o heatmap **mede se funcionou**.
- A distribuição de score do urbIA (maioria 7-8, ~17% em 9-10, média ~9) é **referência de
  calibração e sanidade de validação — NUNCA meta**. O heatmap reporta a **consequência medida**
  da estratégia, com a ressalva de que o urbanista, quebrando a cabeça (lago, remembramento,
  traçado), extrai mais.

## 2. O que NÃO muda (não-regressão)

- **Fronteira do §2 imóvel:** o LLM propõe **estratégia de mix + heurísticas** (política,
  texto/estrutura); o Python dimensiona, posiciona, fecha quadra e mede. **Nenhum tamanho/
  coordenada/score final vem do LLM.**
- **A peça que resolve isso já existe — o `score()` da Fase 9** — só muda de lugar na cadeia:
  era "gera lote uniforme → pontua"; passa a "**zoneia por score → dimensiona conforme a zona →
  re-pontua**". A fórmula do score não muda; agora ela **informa** o tamanho, além de medir.
- Snapshot versionado (9 §7) e `/medir` (sem LLM) intactos; ouros de quadro de áreas de São Roque
  permanecem válidos. Cenário aditivo (9 §8). Fases 1–8 byte a byte. Suítes 1…9.1 verdes.

## 3. A régua da fronteira (o que o Python pode, sem otimizar)

| Python PODE (determinístico, auditável) | Python NÃO faz (é projeto/otimização — do urbanista) |
|---|---|
| Zonear a gleba em faixas de qualidade pelo `score()` geométrico (cota/verde/lazer/ruído) | Buscar o arranjo que maximiza nº de lotes quentes (otimização) |
| Dimensionar cada lote dentro da faixa de tamanho da sua zona (premium maior) | Inventar feição nova (lago artificial) para criar premium |
| Ajustar testada/profundidade **dentro da faixa** para fechar a quadra sem sobra | Remembrar/redesenhar quarteirões buscando valor (projeto) |
| Posicionar a faixa premium onde a heurística da IA indicou (cota alta, fundo verde) | Decidir a estratégia de valorização por critério próprio (é da IA/urbanista) |
| Medir correlação tamanho×score, sobra, % viário, distribuição | Afirmar que a distribuição é "ótima"/"ideal" |

**Regra-mestre:** a IA dá a **política de mix + as heurísticas georreferenciadas**; o Python faz
**operações geométricas determinísticas** (zonear por score, dimensionar na faixa, fechar quadra,
medir). Se uma operação não dá para escrever como função geométrica determinística e auditável,
é projeto — fora.

## 4. Como funciona (pipeline, sobre o traçado da 9.1)

1. **Programa (borda, LLM):** além do que a 9.1 já traz, o programa ganha:
   - **`estrategia_mix`**: faixas de tamanho + proporção-alvo (default por perfil, calibrado pela
     referência; editável). Ex. `alta`:
     `[{premium: 700–900, prop: 0.25}, {padrao: 450–600, prop: 0.55}, {compacto: 350–450, prop: 0.20}]`.
   - **`heuristicas_valorizacao`**: lista georreferenciada de onde aplicar valor — `premium_em:
     ["cota_alta","fundo_mata","frente_lazer"]`, `penalizar: ["via_principal","entrada"]` — com
     justificativa e proveniência ("proposto por IA; táticas de valorização urbanística").
2. **Zoneamento de qualidade (núcleo, determinístico):** o Python pontua o **espaço da quadra**
   (não o lote ainda) pelos atributos geométricos que já temos — cota (DEM 2.5), proximidade de
   verde/mata (2.2), proximidade da área de lazer (materializada na 9.1), afastamento da via
   principal/entrada — e zoneia em faixas (premium/padrão/compacto) conforme as heurísticas.
3. **Dimensionamento conforme a zona (determinístico):** cada lote nasce na faixa de tamanho da
   sua zona; o Python **ajusta a testada dentro da faixa para fechar a quadra sem retalho**
   (validado: sobra → ~0%). Recorte contra a área aproveitável (restrições) inalterado.
4. **Re-pontuação (determinístico):** o `score()` da Fase 9 roda sobre os lotes finais → heatmap.
   Agora há **correlação positiva tamanho×score** (lote grande caiu na zona boa) — é o sinal de
   que a estratégia foi aplicada, não de que é ótima.
5. **Degradação honesta:** gleba que não comporta a proporção premium pedida (pouca cota alta/
   pouco fundo de verde) → materializa o máximo viável e rotula *"posições premium limitadas
   pela geometria da gleba — proporção reduzida; o urbanista pode criar valor com recursos de
   projeto (ex.: lago, terraplenagem) fora desta triagem"*. **Nunca força a distribuição.**

## 5. Contrato de API

Sem endpoint novo. `PropostaUrbanisticaOut` (Fases 9/9.1) ganha:
```jsonc
"programa": { /* … 9/9.1 … */
  "estrategia_mix": [ { "faixa": "premium", "min_m2": 700, "max_m2": 900, "prop_alvo": 0.25 },
                      { "faixa": "padrao", "min_m2": 450, "max_m2": 600, "prop_alvo": 0.55 },
                      { "faixa": "compacto", "min_m2": 350, "max_m2": 450, "prop_alvo": 0.20 } ],
  "heuristicas_valorizacao": { "premium_em": ["cota_alta","fundo_mata"], "penalizar": ["via_principal"],
                               "origem": "proposto_llm", "justificativa": "…" } },
"lotes": [ { "lote_id": "L001", "area_m2": 812.4, "faixa": "premium", "score": 9.1,
             "zona_motivo": ["cota_alta","fundo_mata"] }, /* … */ ],   // tamanho+score MEDIDOS
"mix_medido": {
  "distribuicao": [ { "faixa": "premium", "n": 18, "pct": 0.26, "area_media_m2": 783 },
                    { "faixa": "padrao", "n": 39, "pct": 0.56, "area_media_m2": 512 },
                    { "faixa": "compacto", "n": 13, "pct": 0.18, "area_media_m2": 398 } ],
  "correlacao_tamanho_score": 0.74,
  "sobra_retalho_m2": 120.5, "sobra_retalho_pct": 0.002,
  "arruamento_pct": 0.17 },
"heatmap": { /* 9: faixas de score + por_lote; agora reflete o mix */ },
"avisos": [ /* … 9/9.1 … */,
  "Mix e posicionamento são ESTRATÉGIA aplicada, não otimização: a distribuição é a consequência medida; o urbanista extrai mais valor com recursos de projeto (lago, traçado, remembramento) — fora desta triagem." ]
```
`/medir` inalterado (mede qualquer layout, incl. com lotes de tamanhos variados).

## 6. Critérios de aceite (testáveis — estruturais, NÃO a distribuição-meta)

**Sobre snapshots fixos** (a política/heurística da IA é fixada; o teste mede o motor).

1. **Mix de fato (acaba o uniforme):** dado um programa com 3 faixas, os lotes gerados têm
   tamanhos em ≥2 faixas distintas; **não existe tamanho único** (a v1 com 800 uniforme falha
   este critério).
2. **Sobra minimizada:** numa quadra-ouro de 6.000 m², o mix fecha com **sobra ≤ 1%** (vs. ~6,7%
   do uniforme de 800) — o retalho perdido some.
3. **Viário realista:** sobre a gleba de São Roque, `arruamento_pct` volta para faixa
   plausível (**≤ ~20%**, não os 37% da v1) — teste relativo (cai vs. a Fase 9.1 sem mix).
4. **Correlação tamanho×score positiva:** `correlacao_tamanho_score > 0` (lotes maiores nas
   zonas melhores) — prova de que a heurística foi aplicada. **Não** se exige um valor-meta.
5. **Heurística georreferenciada respeitada:** lotes da faixa premium caem majoritariamente nas
   zonas que a heurística marcou (cota alta/fundo mata) — teste: ≥X% dos premium em zona-alvo;
   premium **não** cai na zona penalizada (via principal) salvo esgotamento, então rotulado.
6. **Proporção dentro da tolerância OU degradada:** `pct` por faixa converge para `prop_alvo`
   (tol ~5 p.p.) quando a gleba comporta; quando não (pouca cota alta), **degrada rotulado**,
   nunca força.
7. **Fronteira §2:** gerador-stub fornece estratégia+heurística; **nenhum tamanho/score vem do
   stub** — Python dimensiona e pontua. Programa sem estratégia premium → sem premium inventado.
8. **Score é consequência, não meta:** **regex/asserção: a resposta NÃO afirma distribuição
   "ótima/ideal"**; o aviso de "estratégia, não otimização" presente; a referência urbIA não
   aparece como alvo no código (só na calibração dos defaults).
9. **Determinismo + §1-A:** mesmo snapshot → mesmo mix/heatmap; rótulo "ESTUDO DE MASSA
   ESQUEMÁTICO" + "verificar com urbanista"; regex sem "aprovado/viável/regular".
10. **Não-regressão:** `/medir` e ouros de quadro de áreas (Fase 9) inalterados; fases 1–8 byte a
    byte; suítes 1…9.1 verdes; zoneamento/dimensionamento testados isolados, offline.

> **Validação (não valor-ouro cravado):** quando o layout real do urbIA chegar como geometria, a
> distribuição de score/tamanhos dele vira **sanidade de validação** — confere-se que o motor,
> medindo o traçado real, dá distribuição compatível. **Não** se crava a distribuição como meta.

## 7. Fora de escopo (registrado — não inflar)

- **Otimização do traçado/lotes** (maximizar valor automaticamente) — é o "quebrar a cabeça" do
  urbanista; o tool aplica estratégia, não busca o ótimo.
- **Lago artificial / feições de água novas** — ato de projeto mais forte e mistura com APP;
  **evolução, conversa própria** (decidido com o operador).
- **Remembramento/redesenho de quarteirões buscando valor** — projeto do urbanista.
- **Pesquisa web ao vivo de táticas de valorização** — o LLM já as conhece (conhecimento
  estável) e as aplica no programa; busca é evolução (Mercadológica).
- **Projeto aprovável, técnicos (água/esgoto/energia/drenagem), terraplenagem, custos
  (SINAPI/SICRO), edição interativa/3D/render** — mantidos fora (Fases 9/9.1).
- **Preço absoluto do lote** — o heatmap ordena qualidade; R$/m² por faixa é input do usuário.

## 8. Arquivos esperados (latitude de implementação)

- `core/urbanismo_geom.py` — zoneamento de qualidade da quadra (reusa atributos do `score()`);
  dimensionamento por faixa com **fechamento de quadra sem sobra**; posicionamento da faixa
  premium pelas heurísticas. **Python puro.**
- `core/urbanismo_medida.py` — `mix_medido` (distribuição, correlação tamanho×score, sobra,
  %viário); `score()` re-rodado sobre os lotes finais.
- `core/urbanismo_programa.py` — prompt do LLM ganha `estrategia_mix` + `heuristicas_valorizacao`
  (defaults por perfil calibrados pela referência; anti-alucinação; stub offline).
- `routers/urbanismo.py` — resposta estendida; `/medir` inalterado.
- `models/schemas.py` — `FaixaMixOut`, `LoteOut` (com faixa/zona_motivo), `MixMedidoOut`.
- Frontend: `CardUrbanismo` mostra a **distribuição de tamanhos** (não um número só), o heatmap
  refletindo o mix, a correlação tamanho×score como leitura, e o aviso "estratégia, não
  otimização"; selo ESQUEMÁTICO e §1-A mantidos. Front só renderiza.
- Testes: `tests/test_urbanismo_mix.py` (mix, sobra, viário, correlação, heurística, degradação,
  fronteira-stub, determinismo — casos sintéticos, offline).

A spec fixa **contrato + critérios**; o resto é latitude. **A IA propõe a estratégia de
valorização; o Python zoneia, dimensiona, fecha a quadra e mede** — a fronteira do §2 intacta, o
heatmap vira consequência medida de uma estratégia, e o urbanista (que quebra a cabeça e extrai
mais) segue insubstituível (§1-A).
