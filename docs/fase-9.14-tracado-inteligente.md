# Fase 9.14 — Urbanismo: traçado inteligente (contorno da restrição, conectividade, cul-de-sacs de bulbo)

> **O salto de qualidade do módulo — do traçado funcional ao traçado de projeto.** Hoje as vias
> correm até a borda da área de declividade ≥30% e **simplesmente somem** (legenda atual: "viário
> em 0 trechos · 12 cacos podados"; fidelidade: "esqueleto[0]/[3] descartado: fora da área
> aproveitável"). O loteamento fica **partido em duas porções que não se conectam**, com vias
> mortas apontando uma para a outra. Em projeto de urbanismo real isso **não ocorre**: uma via ou
> **contorna** o obstáculo e reconecta, ou **termina em cul-de-sac de bulbo** (retorno) — nunca
> morre numa ponta solta. Esta fase faz o traçado: **(A)** contornar a área não-edificável em vez
> de cortar a via; **(B)** garantir conectividade (toda porção loteável liga à entrada);
> **(C)** fechar ramos em **cul-de-sac de bulbo** (exclusividade premium, lotes em leque nos
> fundos de mata); **(D)** ao dar acesso às porções hoje órfãs, **recuperar lotes** que viravam
> "verde remanescente" (sobra geométrica), elevando o aproveitamento e baixando o verde-sobra.
> Referencia `ARCHITECTURE.md` (§1-A, §2) e as Fases 9.7/9.9/9.11/9.12/9.13. **Tudo determinístico
> no Python; a IA propõe o programa de traçado, o Python materializa e mede toda a geometria (§2).**

## 0. Fontes (traçado é norma técnica + boas práticas PESQUISADAS, nunca chute)

| Fonte | Regra extraída |
|---|---|
| **SIURB/SP — Instrução de Projeto Geométrico (IP-03)** | **Acima de 15% de declividade NÃO se projeta pavimentação, mas escadaria** (estudo específico). São Roque tem ≥30% no miolo → **via NÃO atravessa a restrição; contorna pela borda.** Âncora da regra A. |
| **VTPI / Sustainable City Code — connectivity index** | Conectividade = links ÷ (interseções + culs-de-sac). Índice ≥1,4 é o mínimo p/ malha caminhável. **Dead-ends reduzem o índice — usar com parcimônia, sempre projetados.** Âncora da regra B. |
| **ACCESS Magazine / Wharton — "Reconsidering the cul-de-sac"** | Padrão **loops-and-lollipops** (curvilíneo, ruas curtas, cul-de-sacs, T-intersections) é o do loteamento premium em relevo; **mas carece de interconexão se não houver coletora-tronco costurando tudo** → exigir tronco conectora. |
| **J. Urban Planning & Dev. (Hochschild 2015) / arxiv 2305.08186** | **Cul-de-sac de BULBO** dá a maior coesão/privacidade; comunidades premium se organizam em ruas sem saída e junções em T p/ reduzir tráfego. **O bulbo é a ferramenta de exclusividade** (lotes em leque, fundo de mata). Âncora da regra C. |
| **Cul-de-Sac Design Standards (Scribd/PA)** | Cul-de-sac: comprimento máx ~300 m (1000 ft) **ou** limite de unidades por acesso único; bulbo com **ilha central** (reduz pavimento, drenagem); turnaround dimensionado p/ veículo de serviço (raio ~9–12 m). Parâmetros da regra C. |
| **Lei 6.766 / LUOS (já no motor)** | quadra máx 200 m; via local caixa ≥ ~11 m; lote em `[piso, teto]`; todo lote com frente para via (9.12/9.13). Invariâncias preservadas. |
| **arxiv 2212.06783 (já validado)** | pipeline ruas→buffer→polygonize→OBB subdivision = o motor atual. A 9.14 enriquece o **traçado das ruas** (entrada do pipeline), não o método de subdivisão. |

**Validação de arquitetura:** o que muda é o **programa de traçado** (a IA propõe vias mais ricas)
e a **materialização do viário** (o Python roteia pela borda, conecta, fecha bulbos). O método de
subdivisão de face em lote (9.4/9.11) e o filtro frente-via (9.12/9.13) **não mudam** — recebem
quadras melhores e medem do mesmo jeito.

## 1. Objetivo

Traçado **conectado, sem vias mortas, contornando a restrição, com cul-de-sacs de bulbo onde há
exclusividade** — aproximando o estudo de um projeto de loteamento real e **recuperando lotes**
hoje perdidos como sobra-verde por falta de acesso. Continua **ESTUDO DE MASSA ESQUEMÁTICO**
(§1-A): o traçado é de triagem, **não** o projeto executivo do urbanista (vias, raios, greides,
drenagem são dele).

## 2. O que NÃO muda (não-regressão — crítico)

- **Subdivisão de face em lote (9.4/9.11)** e **filtro frente-via (9.12/9.13):** preservados. A
  9.14 muda o **traçado do viário** (entrada do pipeline) e a **recuperação de faces órfãs**; a
  subdivisão e a validação de lote rodam depois, iguais.
- **Clamp legal (9.4):** todo lote em `[piso, teto]`, `fora_da_faixa == 0`. Os lotes recuperados
  (regra D) também passam pelo clamp e pelo filtro frente-via.
- **Todo lote com frente para via (9.12/9.13):** invariante mantida — inclusive os lotes em leque
  do bulbo (frente para a curva do bulbo) e os recuperados (frente para a via de contorno).
- **Fronteira §2 imóvel:** a IA propõe o **programa de traçado** (esqueleto de eixos, hierarquia,
  onde fazer cul-de-sac); o **Python materializa e mede** (roteia pela borda, conecta, fecha
  bulbos, subdivide, mede). **Nenhum número vem da IA.** As regras de contorno/conectividade/bulbo
  são **geométricas determinísticas**.
- **§1-A:** selo "ESQUEMÁTICO"; "verificar com urbanista (art. 6º Lei 6.766)"; regex sem
  "aprovado/viável/regular". A via de contorno é **traçado de triagem**, não greide executivo.
- **Reconciliação (9.10), grade adaptativa (9.11), poda (9.8):** preservadas; recebem o traçado
  novo.

## 3. Regra A — contorno da restrição (via não cruza ≥30%, contorna pela borda)

**O conserto do defeito central.** Hoje, quando um eixo proposto cruza a área não-edificável, o
Python **corta** o trecho (vira "caco podado") e a via some. Pela norma (SIURB: >15% = escadaria,
não via pavimentada; São Roque ≥30%), a via **não pode** cruzar a restrição — mas em vez de
**cortar**, deve **contornar**.

```
Para cada eixo de via que intersecta a área não-edificável (≥30% / mata / APP):
  1. NÃO descartar o trecho. ROTEAR pela BORDA da restrição:
     a. buffer de afastamento na restrição (AFAST_VIA, ex. 6–8 m da área vedada).
     b. traçar o eixo contornando o buffer (seguir o contorno externo da restrição
        do ponto de entrada ao ponto de saída), mantendo a via fora da área vedada.
     c. o contorno reconecta as duas porções que a restrição separava.
  2. Se o contorno for inviável (restrição encosta na divisa, sem passagem):
     a porção do outro lado é tratada como ILHA SEPARADA (regra B decide se vira
     acesso próprio ou verde) — mas NUNCA se deixa uma via morta apontando para ela.
  3. NENHUMA via termina dentro/na borda da restrição como ponta solta:
     ou contorna (reconecta), ou vira cul-de-sac de bulbo (regra C).
```

Validado: via reta E-W que cruzaria a restrição → reroteada pela borda inferior do buffer,
**não invade** a área vedada e **conecta** as porções oeste e leste por uma via só.

## 4. Regra B — conectividade (toda porção loteável liga à entrada; sem ilha órfã)

```
Após o traçado (com contornos da regra A):
  1. Montar o GRAFO de vias (nós = interseções/pontas; arestas = trechos).
  2. Identificar o nó de ENTRADA (acesso da gleba à via pública).
  3. Para cada PORÇÃO loteável, verificar caminho viário até a entrada:
     - conectada -> ok.
     - isolada   -> ESTENDER a tronco coletora (contornando a restrição, regra A)
                    até conectá-la; se geometricamente impossível, a porção vira
                    VERDE (honesto) — nunca uma quadra sem acesso nem uma via morta.
  4. Índice de conectividade (links / (interseções + culs-de-sac)) reportado como
     diagnóstico. Não é trava (é triagem), mas porção isolada É falha.
```

**Hierarquia (da pesquisa):** uma **via-tronco coletora** costura as porções (entrada → contorno
→ porções); **vias locais** servem as quadras; **cul-de-sacs** (regra C) são ramos terminais de
exclusividade. A tronco é o que impede o "loteamento partido em duas ilhas".

## 5. Regra C — cul-de-sac de bulbo (ponta vira retorno; exclusividade premium)

```
Um ramo terminal (que não reconecta) NÃO fica como ponta solta. Vira cul-de-sac de bulbo:
  1. No fim do ramo, adicionar BULBO de retorno: círculo de raio RAIO_BULBO
     (ex. 9–12 m, giro de veículo de serviço). Opcional: ilha central (reduz
     pavimento/drenagem) — registrada como área verde interna do bulbo.
  2. Comprimento do ramo <= CULDESAC_MAX (ex. ~300 m / 1000 ft) OU limite de lotes
     servidos por acesso único; acima disso, exige reconexão (regra B) ou segundo acesso.
  3. LOTES EM LEQUE ao redor do bulbo: frente para a curva do bulbo, fundo para a mata
     -> são os lotes de EXCLUSIVIDADE (privacidade, fundo verde). Passam pelo clamp e
     pelo filtro frente-via como qualquer lote (frente = arco do bulbo).
  4. Onde a IA propõe (no programa) "cul-de-sac / fundo de mata / exclusividade",
     o Python materializa o bulbo. A DECISÃO de onde é programa (IA, borda);
     a GEOMETRIA do bulbo é Python (número).
```

Validado: ramo terminando perto da mata → bulbo raio 9 m (área ~254 m²), ~4 lotes em leque com
testada ~14 m no arco. É a ferramenta de valorização que o urbIA usa nos fundos.

## 6. Regra D — recuperação de lotes da sobra-verde (o ganho de aproveitamento)

```
Hoje, porções sem acesso viram "verde remanescente" (sobra geométrica, NÃO reserva proposital).
Com o contorno (A) e a conectividade (B) dando acesso:
  1. Reclassificar faces antes órfãs: se passaram a ter frente para via (contorno/tronco),
     entram na SUBDIVISÃO (9.4/9.11) -> viram LOTES (com clamp e filtro frente-via).
  2. DISTINGUIR no quadro de áreas:
     - VERDE-RESERVA: mata/lazer proposital (parte do programa, fica verde de propósito).
     - VERDE-SOBRA: o que sobrou por geometria (deve CAIR com o traçado melhor).
  3. Métrica de ganho: vendável SOBE, verde-sobra CAI. (Em São Roque, o verde de 32,7%
     deve baixar; o vendável de 36,8% deve subir — quanto, o motor mede.)
```

**Importante (§1-A):** recuperar lote é **dar acesso geométrico**, não forçar número. Uma face só
vira lote se, com a via de contorno, **de fato** ganha frente para via e cabe no clamp. O verde
que for **reserva** (mata/lazer do programa) permanece verde — não se "loteia a mata" para inflar
o vendável. A distinção reserva × sobra é o que mantém a honestidade.

## 7. A fronteira §2 nesta fase (explícita, porque a IA toca mais o traçado)

| Quem | Faz o quê |
|---|---|
| **IA (Opus 4.8) — BORDA** | Propõe o **programa de traçado**: esqueleto de eixos mais rico, **hierarquia** (tronco coletora vs locais), **onde** fazer cul-de-sac (fundos de mata/exclusividade), intenção de contornar a restrição. Texto + eixos normalizados. **Nenhum número, nenhuma medida.** |
| **Python — NÚMERO** | **Materializa**: roteia a tronco pela **borda** da restrição (regra A), monta o grafo e **garante conectividade** (regra B), **fecha ramos em bulbo** (regra C), **recupera faces órfãs** (regra D), **subdivide** (9.4/9.11), **filtra frente-via** (9.12/9.13), **mede TUDO**. As regras A–D são **algoritmos determinísticos**. |

Se a IA propuser um traçado que cruza a restrição, o Python **não** o descarta nem o obedece cego:
**contorna** (regra A). A IA sugere a intenção; o Python faz a geometria legal e medível.

## 8. Contrato de API

```jsonc
"viario_diagnostico": { /* … 9.13 … */
  "trechos_contornando_restricao": 2,    // vias que contornam a ≥30% (antes: cortadas)
  "vias_mortas": 0,                      // INVARIANTE: nenhuma ponta solta
  "culdesacs_bulbo": 3,                  // ramos terminados em bulbo de retorno
  "indice_conectividade": 1.5,           // links / (interseções + culs-de-sac)
  "porcoes_loteaveis": 2,                // porções separadas pela restrição
  "porcoes_conectadas": 2,               // INVARIANTE: == porcoes_loteaveis (ou resto é verde)
  "porcoes_isoladas_viraram_verde": 0 },
"quadro_areas": { /* … */
  "verde_reserva_m2": 12000,             // mata/lazer proposital (programa)
  "verde_sobra_m2": 3500,                // sobra geométrica (deve CAIR vs 9.13)
  "lotes_recuperados_de_sobra": 6 },     // faces antes órfãs que viraram lote
"tracado": {
  "esqueleto_origem": "llm",             // eixos da IA (parser 9.12)
  "hierarquia": ["tronco_coletora","locais","culdesacs"] }
```
`conformidade_legal.todos_lotes_com_frente_via` continua `true` (inclui leque do bulbo e
recuperados). `n_lotes` e `vendavel` **sobem** vs 9.13 (recuperação); `verde_sobra` **cai**.

## 9. Critérios de aceite (testáveis)

1. **Sem vias mortas (fecha o ponto que o Marco viu):** `vias_mortas == 0`. Nenhuma via termina
   numa ponta solta; toda via ou reconecta (contorno) ou fecha em bulbo. Teste em São Roque/alta.
2. **Contorno da restrição (regra A):** `trechos_contornando_restricao >= 1`; nenhuma via cruza a
   área ≥30% (interseção via × restrição = ∅); as vias que antes eram "cacos podados" por cruzar a
   restrição agora **contornam**. O "viário em 0 trechos" da tela atual deve sumir.
3. **Conectividade (regra B):** `porcoes_conectadas == porcoes_loteaveis` (ou as não-conectadas
   viraram verde, `porcoes_isoladas_viraram_verde` coerente); **nenhuma quadra sem acesso à
   entrada**; `indice_conectividade` reportado. O "loteamento partido em duas ilhas" desaparece.
4. **Cul-de-sac de bulbo (regra C):** `culdesacs_bulbo >= 1` onde há ramo terminal; cada bulbo tem
   raio ≥ RAIO_BULBO; ramos ≤ CULDESAC_MAX; lotes em leque do bulbo têm frente para a curva
   (frente-via ok) e passam pelo clamp.
5. **Recuperação de lote (regra D):** `lotes_recuperados_de_sobra >= 1` em São Roque;
   `verde_sobra_m2` **menor** que o verde-remanescente da 9.13; `n_lotes` e `vendavel`
   **maiores** que a 9.13. O verde de 32,7% **cai**; o vendável de 36,8% **sobe**.
6. **Reserva × sobra honesta:** `verde_reserva_m2` (mata/lazer do programa) permanece verde —
   não é loteado; só o `verde_sobra` (geométrico) é convertido onde ganha acesso real. Teste:
   a mata proposital não vira lote.
7. **Clamp + frente-via preservados:** `fora_da_faixa == 0`; `todos_lotes_com_frente_via == true`
   (inclui leque e recuperados). Nenhum lote novo viola a faixa legal nem fica sem frente.
8. **§2 + §1-A:** regras A–D são determinísticas (a IA propõe programa, não geometria/número);
   se a IA propõe traçado cruzando a restrição, o Python contorna (não descarta nem obedece);
   selo "ESQUEMÁTICO"; "verificar com urbanista"; regex limpo.
9. **Não-regressão:** subdivisão (9.4/9.11), filtro frente-via (9.12/9.13), reconciliação (9.10),
   poda (9.8), grade adaptativa (9.11), clamp (9.4) — preservados. A reconciliação passa a citar o
   `n_lotes` novo (recuperado).
10. **Caixa limpa (sanidade):** numa gleba retangular sem restrição, o traçado continua são (sem
    bulbos desnecessários, sem contornos espúrios, conectividade alta, `verde_sobra ≈ 0`); a 9.14
    não deve degradar o caso fácil.

> **Impacto esperado (honesto):** o `n_lotes` e o vendável **sobem** (recuperação de sobra-verde
> via acesso), o verde-sobra **cai**, e o traçado vira **conectado e legível** (sem vias mortas,
> sem loteamento partido). É um ganho real de aproveitamento — mas vem de **dar acesso
> geométrico**, não de forçar número: a mata-reserva permanece verde. Aproxima o estudo do padrão
> urbIA (vias definidas, cul-de-sacs de exclusividade) **sem** virar projeto executivo (§1-A).

## 10. Fora de escopo (registrado)

- **Greide, raios de curva, drenagem, perfis longitudinais** — projeto executivo do urbanista
  (§1-A). A 9.14 é traçado de triagem em planta, não projeto geométrico.
- **Pórtico de entrada** — fase futura (após o traçado maduro).
- **Pontes entre ilhas separadas por restrição fina** — registrado (9.11 §6); aqui só se
  contorna, não se faz ponte.
- **Heatmap (escala de cor: vermelho = melhor)** — spec separada, depois desta.
- **Render artístico (Nível 3)** — com trava de arquitetura (ilustração nunca define número).

## 11. Arquivos esperados (latitude de implementação)

- `core/urbanismo_traçado.py` (ou no `urbanismo_geom.py`):
  - `rotear_contornando_restricao(eixo, restricao, afast)` — regra A (buffer + contorno).
  - `garantir_conectividade(grafo_vias, entrada, porcoes)` — regra B (estende tronco / vira verde).
  - `fechar_culdesac_bulbo(ramo, raio, max_len)` — regra C (bulbo + leque).
  - `recuperar_faces_orfas(faces, vias)` — regra D (face com acesso novo → subdivisão).
- `core/urbanismo_medida.py` — expor `trechos_contornando_restricao`, `vias_mortas`,
  `culdesacs_bulbo`, `indice_conectividade`, `porcoes_*`, `verde_reserva_m2`, `verde_sobra_m2`,
  `lotes_recuperados_de_sobra`.
- `core/urbanismo_llm.py` (prompt do programa) — pedir ao Opus 4.8 um **programa de traçado** com
  hierarquia (tronco/locais/cul-de-sacs) e **onde** fazer cul-de-sac (exclusividade/fundo de mata)
  e a intenção de contornar a restrição. **Sem números.**
- `models/schemas.py` — campos novos.
- Frontend `MapaLeaflet` — render do contorno, bulbos (com ilha central se houver), tronco vs
  locais (hierarquia visual leve); legenda distingue verde-reserva de verde-sobra.
- Testes: `tests/test_urbanismo_traçado.py` — São Roque (KMZ real): vias_mortas==0, contorno não
  cruza restrição, porções conectadas, bulbo com raio/leque, lotes recuperados, verde-sobra cai,
  clamp e frente-via preservados; **caixa limpa**: traçado são, sem bulbos espúrios. Offline onde
  possível.

A spec fixa **contrato + critérios + ALGORITMO + FONTES**. **Regra A:** a via **contorna** a área
≥30% pela borda em vez de morrer nela (âncora SIURB: >15% não é via pavimentada) — conecta as
porções, acaba o "loteamento partido". **Regra B:** toda porção loteável **liga à entrada** (ou o
resto vira verde honesto) — sem ilhas órfãs, sem vias mortas. **Regra C:** ramos terminais fecham
em **cul-de-sac de bulbo** (retorno + lotes em leque) — a exclusividade premium do urbIA. **Regra
D:** ao dar acesso, **recupera lotes** que eram sobra-verde — vendável sobe, verde-sobra cai, sem
lotear a mata-reserva. A IA propõe o **programa de traçado**; o **Python materializa e mede toda a
geometria** (§2 intacto). É o salto rumo ao urbIA, mantendo a honestidade da triagem (§1-A). O
**heatmap** (vermelho = melhor) é a próxima spec.
