# Fase 9.12 — Urbanismo: todo lote com frente para via (corrige lotes encravados) + parser dos eixos da IA

> **Correção de validade — o bug mais grave do módulo.** O motor conta como "lote" (e soma na
> área vendável) polígonos que **não tocam via nenhuma**: 16 dos 50 lotes de São Roque (~32%) são
> encravados. Pela **definição legal** (Decreto de parcelamento; Lei 6.766), *"lote é a parcela
> em quadra com pelo menos uma divisa lindeira a via oficial"* — logo um polígono sem frente para
> via **não é lote**. O número real de lotes vendáveis cai de 50 para **34** (no app, de 47 para
> ~32) e o vendável de 40,1% para **28,5%**. Esta fase garante que **todo lote tem frente para
> via**, redistribuindo/fundindo lateralmente os encravados, e corrige de quebra o **parser dos
> eixos da IA** (134 eixos descartados por descasamento de aninhamento). Referencia
> `ARCHITECTURE.md` (§1-A, §2) e as Fases 9.4/9.5/9.7/9.11. **Tudo determinístico no Python; o LLM
> não decide geometria (§2).**

## 0. Fontes (parâmetro é lei + prática pesquisada, nunca chute)

| Fonte | Regra extraída |
|---|---|
| Decreto parcelamento (def. legal) | **LOTE = parcela com ≥1 divisa lindeira a via oficial.** Sem via ≠ lote. |
| Lei 6.766 federal | testada mín **5 m**; área mín **125 m²** |
| Lei Rio PLC 29/2013 (escada) | testada × padrão: popular 5-9m, médio 12m, alto 15-20m; **quadra máx 200m**; **remate ≤2 lotes/série −15%**; lote de esquina maior |
| Prática de mercado (consolidada) | popular 125-250m²/testada 5-8m; médio 300-450m²/10-12m; **alto 450-800m²/15-20m** |
| arxiv 2212.06783 (urban design generativo) | pipeline ruas→buffer→`polygonize`→**OBB subdivision** (corte na aresta curta, recursivo) = **o que nosso motor já faz** |
| ABNT 14.653-2 | fatores de valor: testada, profundidade, esquina (−19% a +19%) → base do score |

**Validação de arquitetura:** o algoritmo profissional confirmado pela literatura é exatamente o
nosso (eixos→ruas→faces→subdivisão por bounding box). O que falta **não** é refazer a geração — é
a **regra de validação do lote** (frente para via) que o paper pressupõe e nós não implementamos.

## 1. Objetivo

Garantir que **todo polígono contado como lote tenha frente para via oficial** (testada ≥ mínimo
legal, conexa ao arruamento). Os que não têm são tratados por **fusão/redistribuição lateral**
(prática real de loteamento: lotes enfileirados na via, vizinhos **do lado** se ajustam), e o que
não puder ter acesso vira **verde/não-aproveitável** — nunca "lote fantasma". Resultado: nº de
lotes e área vendável **reais**. Continua **ESTUDO DE MASSA ESQUEMÁTICO** (§1-A).

## 2. O que NÃO muda (não-regressão)

- **Geração (9.7-9.11) preservada:** eixos→ruas→faces→`_subdividir_quadra`→clamp (9.4), grade
  adaptativa (9.11), poda (9.8), sinuosidade (9.9), institucional/clube formados (9.7),
  reconciliação (9.10). A 9.12 **adiciona um passo de validação/ajuste após a subdivisão**, não
  reescreve a geração.
- **Fronteira §2 imóvel:** a regra do encravado é **geométrica determinística** (mede frente,
  funde lateralmente, ou vira verde) — o LLM **não** decide nada disso. (A inteligência de
  urbanismo está nas regras pesquisadas, executadas pelo Python; é a mesma filosofia da IA propor
  eixos e o Python medir.)
- **Clamp legal (9.4):** preservado e **reforçado** — a fusão lateral nunca gera lote fora de
  `[piso, teto]`.
- Snapshot e contrato do `/medir` preservados (os números **mudam de valor** — corrigem para
  baixo —, mas as invariâncias seguem).

## 3. Algoritmo A — todo lote com frente para via (validado na espinha)

```
Após a subdivisão de cada face em lotes (9.4/9.11), ANTES de medir:

1. CLASSIFICAR cada lote: tem frente para via?
   frente = comprimento da interseção entre a borda do lote e o arruamento
   tem_via = frente >= TESTADA_MIN_LEGAL (5 m; ou o mínimo da faixa)
2. Para cada lote SEM via, na ordem:
   a. FUSÃO/REDISTRIBUIÇÃO LATERAL: identificar vizinhos LATERAIS (lado a lado na
      fileira, compartilham divisa lateral) que TÊM via.
      - se um vizinho lateral com via pode absorver o encravado (ou parte dele) sem
        estourar [piso, teto], REDISTRIBUIR a largura: o(s) vizinho(s) com via
        incorpora(m) a área do encravado, somando testada, mantendo profundidade.
      - a fileira de lotes da quadra é re-repartida entre os que têm via (prática real:
        a frente disponível é dividida entre os lotes com acesso).
   b. PROPAGAÇÃO: se o vizinho imediato estoura, tentar o próximo lateral com via na
      mesma fileira (em cadeia), até alguém absorver dentro da faixa.
   c. VERDE: se nenhum vizinho lateral com via pode absorver sem violar a faixa legal,
      o encravado vira VERDE/não-aproveitável (rotulado). NUNCA conta como lote.
3. NUNCA: abrir via nova para servir o encravado (isso é decisão do urbanista, não do
   motor de triagem — reinflaria o viário).
4. RE-MEDIR: nº de lotes, vendável, distribuição — só sobre lotes COM via.
```

**Fusão é LATERAL, não frente-fundo (corrigido):** lotes num loteamento enfileiram-se na via com
a testada na rua; quem se une são vizinhos **do lado**. A fusão lateral **soma testada** (fica
mais largo) e **mantém profundidade** — resultado largo e raso é normal. Fundir frente-fundo
geraria lotes compridos e estreitos (irreal) — **proibido**. Quando a soma de dois lotes inteiros
estoura o teto, o encravado é **redistribuído** (a fileira re-repartida), não simplesmente colado.

**Testada por faixa (preferência suave, da pesquisa):** a subdivisão passa a **preferir** a
testada típica do padrão (alto ≥15m, médio ≥10m, popular ≥5m) — como tendência, não clamp duro
(não rejeita lote por testada; só orienta o corte). Reduz um pouco o nº de lotes no alto padrão,
mas torna o padrão fiel (um "alto padrão" de 450m² com 9m de frente é popular esticado, não alto
padrão). O resultado expõe **testada média** para o usuário comparar.

## 4. Algoritmo B — parser dos eixos da IA (bug dos 134 descartados)

```
CAUSA (diagnosticada): a IA (Opus 4.8) devolve o esqueleto ACHATADO como UMA polilinha
  [[x,y],[x,y],…] (134 pontos), mas o schema/parser espera uma LISTA de polilinhas
  [[[x,y],…],…]. O parser trata cada ponto [x,y] como polilinha, falha ao desempacotar
  -> "coordenadas inválidas" × 134. Traçado atual = 100% fallback (eixos da IA nunca usados).

CORREÇÃO (robustez no parser — aceitar os dois formatos):
  ao ler `esqueleto`:
    - se item[0][0] é número  -> é UMA polilinha achatada -> envolver: [esqueleto]
    - se item[0][0] é lista   -> já é lista de polilinhas -> usar como está
  validar cada vértice (x,y normalizado 0..1) APÓS desaninhar corretamente.
  registrar esqueleto_origem = "llm" quando ≥1 eixo da IA é aceito.
```

Isto **destrava o traçado da IA** (hoje morto). Não muda a geometria de quem já usa fallback; só
passa a aproveitar os eixos que a IA de fato propõe. Independente do Algoritmo A.

## 5. Contrato de API

```jsonc
"viario_diagnostico": { /* … 9.11 … */
  "lotes_sem_via_tratados": 16,        // quantos encravados foram corrigidos
  "lotes_fundidos_lateral": 11,        // viraram parte de vizinho lateral
  "lotes_viraram_verde": 5,            // sem vizinho que absorvesse
  "testada_media_m": 16.2,             // frente média (comparar com a faixa do perfil)
  "esqueleto_origem": "llm",           // agora aceita o formato achatado da IA
  "eixos_ia_aceitos": 1, "eixos_ia_descartados": 0 },
"conformidade_legal": { /* … */
  "todos_lotes_com_frente_via": true } // invariante nova
```
Os campos `n_lotes`, `vendavel`, `area_media`, `distribuicao_tamanhos` passam a refletir **só
lotes com via** (valores corrigidos para baixo).

## 6. Critérios de aceite (testáveis)

1. **Todo lote tem frente para via (a correção):** `todos_lotes_com_frente_via == true`; nenhum
   lote contado tem interseção com arruamento < testada mínima. Teste por lote: frente ≥ 5 m.
2. **Número corrigido (honestidade):** em São Roque/alta, `n_lotes` cai para ~34 (era 50) e
   vendável para ~28,5% (era 40,1%); os 16 encravados **não** contam mais. O número passa a ser
   o real.
3. **Fusão é lateral (corrigido):** os lotes fundidos somam **testada** (ficam mais largos),
   mantêm profundidade; nenhum lote comprido-estreito gerado por fusão frente-fundo. Teste:
   razão profundidade/testada dos fundidos não explode.
4. **Clamp preservado na fusão:** nenhum lote fundido/redistribuído fica fora de `[piso, teto]`
   (`fora_da_faixa == 0`); quando a fusão estouraria, redistribui ou vira verde.
5. **Verde honesto:** encravado sem vizinho lateral que o absorva vira verde/não-aproveitável,
   rotulado; `lotes_viraram_verde` coerente. Nunca conta como lote.
6. **Sem via nova:** nenhuma via é aberta para servir encravado (viário não cresce por causa da
   correção; `viario_pct` estável vs 9.11).
7. **Parser dos eixos (Algoritmo B):** `esqueleto_origem == "llm"` em São Roque/alta;
   `eixos_ia_descartados == 0` (o formato achatado da IA é aceito); o traçado passa a poder usar
   os eixos da IA. Teste com payload achatado `[[x,y],…]` e aninhado `[[[x,y],…],…]` — ambos
   aceitos.
8. **Testada por faixa (preferência suave):** `testada_media_m` tende à faixa do perfil (alto
   ~15m+); mas nenhum lote é **rejeitado** só por testada (é preferência, não clamp). Caixa limpa
   não perde lotes por rigidez.
9. **§2 + §1-A:** a regra do encravado é geométrica determinística (o LLM não decide fusão/verde);
   selo "ESQUEMÁTICO" + "verificar com urbanista"; regex sem "aprovado/viável/regular".
10. **Não-regressão:** geração 9.7-9.11, grade adaptativa, poda, sinuosidade, reconciliação —
    preservadas; o passo novo é validação pós-subdivisão. A reconciliação (9.10) passa a citar o
    nº **corrigido** (~34), fechando o 120→34 com honestidade.

> **Impacto esperado (honesto):** o número de lotes **cai** (de 50 para ~34 em São Roque) — isso
> é a correção de um número que estava **inflado**, não uma perda. O estudo passa a contar só
> lotes que podem ser vendidos. A reconciliação 120→34 fica ainda mais larga, e o texto da 9.10
> deve refletir o número corrigido. É mais honesto, ainda que menos "vendedor".

## 7. Fora de escopo (registrado)

- **Pontes entre ilhas** — fase futura registrada (9.11 §6).
- **Pórtico de entrada** — após o traçado maduro.
- **Heatmap (escala de cor)** — **próxima spec** (vermelho = melhor, gradiente monotônico,
  ancorado na ABNT 14.653-2; legenda "cor = posição, não preço"). Separada desta.
- **Render artístico** — Nível 3.
- **Abrir via nova / otimização de traçado** — do urbanista (§1-A).

## 8. Arquivos esperados (latitude de implementação)

- `core/urbanismo_geom.py`:
  - novo passo `garantir_frente_via(lotes, arruamento, faixa)` após `_subdividir_quadra`:
    classifica frente, **funde/redistribui lateralmente** os sem-via, manda o resto para verde.
  - `_subdividir_quadra` ganha **preferência de testada** por faixa (suave, não clamp).
  - `_eixos` (parser): **desaninhar** o esqueleto da IA aceitando `[[x,y],…]` e `[[[x,y],…],…]`.
- `core/urbanismo_medida.py` — medir só lotes com via; expor `lotes_sem_via_tratados`,
  `lotes_fundidos_lateral`, `lotes_viraram_verde`, `testada_media_m`, `eixos_ia_aceitos`,
  `todos_lotes_com_frente_via`.
- `models/schemas.py` — campos novos no diagnóstico e conformidade.
- `routers/urbanismo.py` — propagar; a reconciliação (9.10) usa o nº corrigido.
- Testes: `tests/test_urbanismo_frente_via.py` — todo lote com frente ≥5m, nº corrigido (~34 em
  São Roque com KMZ real), fusão lateral (não frente-fundo), clamp preservado, verde honesto,
  viário estável, parser aceita ambos os formatos de esqueleto; offline onde possível.

A spec fixa **contrato + critérios + ALGORITMO + FONTES**. **Todo lote passa a ter frente para
via** (definição legal de lote): os encravados são **fundidos/redistribuídos lateralmente** com
vizinhos que têm via — prática real de loteamento, soma testada e mantém profundidade — e o que
não tem acesso vira verde honesto, nunca lote fantasma. O número de lotes corrige para o **real**
(~34 em São Roque), e o parser passa a **aceitar os eixos da IA** (hoje 100% descartados). Tudo
determinístico no Python (§2 intacto); a inteligência de urbanismo vive nas **regras
pesquisadas** (lei + prática + ABNT), não no julgamento do LLM. O heatmap (vermelho = melhor) é a
próxima spec.
