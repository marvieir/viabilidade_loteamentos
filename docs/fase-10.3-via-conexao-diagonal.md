# Fase 10.3 — Urbanismo: via de conexão DIAGONAL cruzando a faixa ≥30%

> **Correção conceitual.** Até a 10.1 o motor tratava a faixa de declividade **≥30% como barreira
> absoluta para a via** (REGRA A da 9.14: "a via NÃO atravessa a restrição; contorna pela borda"),
> e media a travessia entre porções por um **cruzamento RETO** (vão mais curto, ≤80 m, greide só
> entre as duas pontas). Resultado em São Roque: o cruzamento reto dava **~20–26%** → veredicto
> **inviável** → **loteamento partido** em duas porções que não se ligam. Mas isso confunde **dois
> conceitos diferentes**: a faixa ≥30% veda **LOTE** (Lei 6.766 art. 3º, parág. único, III), **não
> via**; e o que decide a travessia é o **greide da VIA**, não a **declividade do terreno**. Uma via
> cruza terreno de 30% **na diagonal**, com corte/aterro, mantendo greide ≤15% (`greide_via = s·sen θ`
> — a ~25° do contorno, 30% de terreno vira ~13% de via). Esta fase faz o motor **achar o traçado
> diagonal de menor greide** (busca minimax sobre o DEM), **permitir a via cruzar o ≥30%**, medir o
> **greide da via** ao longo do traçado e **sinalizar a exigência geotécnica**. Referencia
> `ARCHITECTURE.md` (§1-A, §2) e as Fases 9.14/10/10.1. **Determinístico: a IA não entra; o Python
> acha o corredor ótimo e mede (§1/§2).**

## 0. Fontes (a distinção terreno × via é geometria + norma, nunca chute)

| Fonte | Regra extraída |
|---|---|
| **Lei 6.766/79, art. 3º, parág. único, III** | Proíbe **parcelar (LOTEAR)** em terreno com declividade ≥30%, **"salvo se atendidas exigências específicas das autoridades competentes"**. A vedação é de **lote** (risco de deslizamento/edificação), **não de via**. |
| **Greide de via (ex.: Indaiatuba, Cód. de Obras art. 58; SIURB/IP-03)** | A via tem limite **próprio** — o **greide** (rampa longitudinal), ~**15%** máx; **>15% = escadaria, não via**. Greide ≠ declividade do terreno. |
| **Geometria de estrada de montanha (switchback/banqueta)** | Uma via que cruza um talude de declividade `s` formando ângulo `θ` com a curva de nível tem **greide = s·sen θ**. Atravessar 30% a 25° do contorno ⇒ greide ≈ 13% (≤15%). É o que permite a via subir o morro **diagonal**, não de frente. |
| **9.14 (REGRA A) — permanece p/ a REDE LOCAL** | As vias **locais** que servem as quadras continuam **contornando** o ≥30% (não se loteia/serve mata íngreme; o miolo vira bosque preservado). A 10.3 é a **exceção da via-TRONCO de conexão**, a única que cruza, com laudo. |

**Validação de arquitetura:** muda só o **modelo da travessia de conexão** (`conexao.py`) e como o
router a invoca. A subdivisão de face→lote, o filtro frente-via e o contorno da rede local (9.14)
**não mudam**. Lote no ≥30% **segue vedado**; só a via-tronco de conexão atravessa.

## 1. Objetivo

Conectar porções separadas por relevo num **loteamento único**, medindo o **greide da via** no
**melhor traçado diagonal** (que pode cruzar o ≥30%), em vez de declarar o loteamento partido por
ler a declividade do terreno como barreira. Continua **ESTUDO DE MASSA ESQUEMÁTICO** (§1-A): o
greide vem de **DEM público 30 m** (interpolado) → **indicativo de triagem**; topografia de campo
(curvas 1 m) e laudo geotécnico fecham o greide executivo e validam o corte/aterro.

## 2. Contrato (o que mudou)

- **`conexao.travessia_diagonal(porcao_a, porcao_b, amostrar_cota, dominio, restricao, passo)`** —
  pathfinder **minimax** sobre o DEM: grade fina (passo adaptativo, alvo ≤5000 nós) sobre o
  `dominio` (a gleba inteira, **incluindo o ≥30%**), vizinhança **16-direções** (diagonais rasas até
  ~26°), arestas com peso = **greide da via** entre nós. Acha o caminho A→B de **menor greide-MÁXIMO
  (gargalo)** por união-find (Kruskal), reconstrói o eixo (polilinha), mede greide/extensão/desnível
  e marca **`cruza_restricao`** se o eixo intersecta o ≥30%/mata. **Degrada** para `travessia_otima`
  (reto) sem DEM ou se a grade não resolve as duas porções.
- **`Travessia`**: novos campos `cruza_restricao: bool` e `terreno_max_pct: Optional[float]`;
  `proposta_por` admite `"diagonal"`.
- **`router._travessia_conexao`**: com DEM, usa `travessia_diagonal` (domínio = `aprov ∪ restrição`);
  sem DEM, mantém o modelo reto (não inventa diagonal sobre relevo ausente). Emite no diagnóstico:
  `modelo` (`"diagonal_minimax"`/`"reto"`), `cruza_restricao`, `exigencia_geotecnica` e
  **`nota_geotecnica`** (art. 3º Lei 6.766) quando a via cruza ≥30%.
- **Front** (`api.ts` + `CardUrbanismo.tsx`): badge "via diagonal" + greide; **selo âmbar** da
  exigência geotécnica ("via cruza ≥30% em corte/aterro — exige projeto geométrico + laudo; nenhum
  lote na faixa, só a via atravessa").

## 3. Valores-ouro

**Sintético** (`tests/test_conexao_diagonal.py`) — terreno-rampa `cota = 0,30·x` (30%), duas porções
separadas por faixa de 120 m:

| Modelo | greide da via | veredicto |
|---|---|---|
| reto (`travessia_otima`) | ≥25% | **inviável** |
| diagonal (`travessia_diagonal`) | ≤15% (≈13,4%) | **não inviável**, `cruza_restricao=True`, eixo > vão reto |

**Gleba real (São Roque)** — verificação end-to-end pela função do motor, DEM Copernicus 30 m:

| Modelo | greide da via | veredicto |
|---|---|---|
| reto (antigo) | **19,8%** | inviável → partia o loteamento |
| **diagonal (10.3)** | **9,7%** | **via_normal** → conecta; via 184 m, cruza ≥30% (laudo) |

## 4. Ressalvas honestas (§1-A)

- Greide de **DEM 30 m interpolado** → **indicativo**; o badge diz "confirmar com topografia". Laudo
  geotécnico de campo valida greide executivo e o corte/aterro no ≥30%.
- A via cruza terreno ≥30% → **art. 3º Lei 6.766** ("exigências das autoridades competentes"):
  projeto geométrico + laudo. **Nenhum lote** na faixa; só a via.
- O miolo ≥30%/mata que **não** vira via segue **bosque/área verde preservada** (Fase 10.2).
