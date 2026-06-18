# Fase 9.11 — Urbanismo: grade adaptativa por ilha (corrige o viário que colapsa em gleba estilhaçada)

> **Correção de regressão, cirúrgica.** Numa gleba alongada e recortada, a declividade ≥30%
> **estilhaça** o aproveitável em ilhas pequenas/tortas (7 ilhas só com a declividade, 32 com a
> mata). A malha 9.7 usa uma **grade grossa fixa** (quarteirão ≈84×50 m); recortada numa ilha
> pequena, ela rende **pouquíssimas faces** (a ilha de 37.988 m² gerou só 2 faces). Como o viário
> **É a fronteira interna compartilhada entre faces**, poucas faces ⇒ quase nenhuma fronteira ⇒
> **viário colapsa para ~5%**, os lotes ficam colados num quarteirão único e o verde de lazer
> pousa numa face superdimensionada. Esta fase torna **o tamanho do quarteirão função do tamanho
> da ilha** (grade adaptativa), respeitando o **piso legal de lote**. Referencia
> `ARCHITECTURE.md` (§1-A, §2) e as Fases 9.4/9.5/9.7/9.8/9.9. **Não toca poda, sinuosidade nem
> recorte — todos inocentados com log real.**

## 0. A causa, provada com log (não suposta)

O Claude Code rodou o pipeline com a gleba e a declividade **reais** e falsificou as hipóteses
anteriores:

| Hipótese | Veredito (com dado real) |
|---|---|
| Poda remove via demais | **Falso** — a poda só conta cacos; não subtrai área de rua |
| Eixos curvos (9.9) inflam cacos | **Falso** — medido reta×curva: curva não estoura a poda |
| `:388` degenera ilha em "quadra sem via" | **Falso** — 0 de 7 ilhas caíram nesse ramo |
| **Grade grossa rende poucas faces por ilha** | **VERDADEIRO** — log abaixo |

```
ilha area=37988 bbox=233×299  eixos_grade=5  faces=2  via=3515 m²  ← ilha grande, só 2 faces!
ilha area=24541 bbox=315×158  eixos_grade=3  faces=3  via=3831 m²
ilha area=47    bbox=10×14    eixos_grade=1  faces=1  via=0 m²      (×5 slivers)
```

**A cadeia:** declividade estilhaça → ilhas pequenas/tortas → grade grossa (≈84×50 m) rende 1–2
faces por ilha → poucas/nenhuma fronteira interna → **viário ≈ 0** + lotes colados + verde grande
numa face superdimensionada. O sistema já sinaliza o sintoma: `conexo_por_ilha = False`.

Reprodução do colapso (DEM + WorldCover reais): aproveitável 58.523 m² (≈ os 58.920 do app);
viário despenca para 7,0% com 32 ilhas — a vizinhança do 4,7% do print.

## 1. Objetivo

Fazer a malha gerar **faces suficientes em cada ilha**, adaptando o tamanho do quarteirão ao
tamanho da ilha — **sem violar o piso legal de lote**. Em ilha pequena/torta, o quarteirão afina
(mais faces → mais fronteira interna → viário real → lotes deixam de ficar colados). O afinamento
**para no piso legal**: nunca gera lote abaixo do mínimo (360 m², Lei 6.766). Ilha pequena demais
para conter lotes legais vira **verde/não-aproveitável honestamente**, não bloco forçado.

## 2. O que NÃO muda (inocentado com log — não tocar)

- **Poda de stubs (9.8):** correta — só conta cacos, não remove via. **Intacta.**
- **Sinuosidade (9.9):** correta — eixos curvos não inflam cacos. **Intacta.**
- **`:388` / degradação de ilha:** não é a causa. **Intacto.**
- **Recorte (declividade/mata/APP), ponte de reconciliação (9.10):** **intactos.**
- **Clamp legal de lote (9.4), `lotes_features` (9.5), institucional/clube formados (9.7):**
  preservados — a grade adaptativa **alimenta** o mesmo `_subdividir_quadra`, não o substitui.
- **Fronteira §2:** a IA propõe eixos/percentuais; o tamanho do quarteirão é **decisão
  geométrica determinística** do Python (função do tamanho da ilha + piso legal), não vem do LLM.

## 3. O algoritmo (validado na espinha)

```
Para CADA ilha loteável (após recorte e contorno do íngreme — 9.8):

1. MEDIR a ilha: área, bbox (largura × altura), forma.
2. ESCOLHER o lado do quarteirão ADAPTATIVO:
   lado_quadra = clamp( f(tamanho_da_ilha), PISO_LEGAL, TETO_PERFIL )
   - ilha grande  → quarteirão maior (até o teto do perfil; preserva o desenho atual onde já
     funciona — caixa limpa segue ~15%);
   - ilha pequena → quarteirão menor (afina até gerar faces adjacentes), MAS:
   - PISO_LEGAL = lado mínimo que ainda comporta lote ≥ lote_mín do clamp (9.4). Tipicamente
     ~2×prof_mín (duas fileiras costas-com-costas) p/ lote ≥ 360 m². NUNCA afina abaixo disso.
3. GERAR a grade adaptada na ilha → faces (quadras), como na 9.7 (polygonize).
4. SE, mesmo no PISO, a ilha rende 0 face loteável (sliver minúsculo, ex.: 47 m²):
   a ilha NÃO vira bloco forçado — vira verde/não-aproveitável (honesto), rotulada.
5. LOTEAR cada face com _subdividir_quadra + clamp (REUSA 9.4 sem mudança).
6. Viário = fronteiras internas (REUSA 9.7); poda (REUSA 9.8); medir (REUSA).
```

**O piso legal é inviolável (§ do clamp, herdado da 9.4):** a grade afina para gerar faces, mas
**o lote resultante nunca fica abaixo do mínimo legal**. Se afinar o quarteirão empurraria o lote
para < 360 m², o afinamento para — e se a ilha não comporta nem isso, ela é honestamente
classificada como verde/não-aproveitável, jamais loteada fora da lei. Isto **estende**, não
contradiz, o `fora_da_faixa == 0` das fases anteriores.

## 4. Contrato de API

`PropostaUrbanisticaOut` (9.10) ganha o diagnóstico de adaptação por ilha:
```jsonc
"viario_diagnostico": { /* … 9.8/9.9 … */
  "ilhas_detalhe": [
    { "ilha": 0, "area_m2": 37988, "bbox_m": [233,299],
      "lado_quadra_m": 62, "faces": 9, "motivo": "adaptado: ilha média" },
    { "ilha": 5, "area_m2": 47, "bbox_m": [10,14],
      "lado_quadra_m": null, "faces": 0, "motivo": "sub-lote: vira verde/não-aproveitável" } ],
  "grade_adaptativa": true,
  "viario_pct": 0.16, "conexo_por_ilha": true,
  "obs": "quarteirão dimensionado por ilha, com piso legal de lote; faces e fronteiras internas recuperadas" }
```
`/medir` inalterado no contrato.

## 5. Critérios de aceite (testáveis — ancorados no log do diagnóstico)

1. **Viário recuperado (resolve a regressão):** na gleba real estilhaçada (São Roque/alta com
   declividade real), `viario_pct` volta a `~15%` (era ~5–7%); os lotes **deixam de ficar
   colados** (cada quadra tem fronteira/via). A vizinhança 4,7–7% **não** se repete.
2. **Mais faces por ilha (a correção direta):** a ilha grande (~38.000 m²) que rendia **2 faces**
   passa a render várias (ex.: ≥6); `ilhas_detalhe[].faces` cresce coerentemente; a fronteira
   interna (= viário) cresce junto.
3. **Piso legal respeitado (inviolável):** nenhum lote abaixo do mínimo (360 m²);
   `fora_da_faixa == 0` (clamp da 9.4 preservado). A grade afina **só até** onde o lote ainda é
   legal; teste confirma que o `lado_quadra_m` nunca produz lote < 360 m².
4. **Sliver vira verde, não bloco (degradação honesta):** ilha pequena demais para conter lote
   legal (ex.: 47 m²) é classificada verde/não-aproveitável, **não** loteada nem forçada a bloco;
   `motivo == "sub-lote: vira verde/não-aproveitável"`.
5. **Caixa limpa não regride:** gleba retangular grande continua viário ~15%, ~69 lotes (a
   adaptação só age onde a ilha é pequena; em ilha grande, o quarteirão segue no teto do perfil).
6. **Não mexe no inocentado:** poda (9.8), sinuosidade (9.9), `:388`, recorte, ponte (9.10) —
   **idênticos**; suítes dessas fases verdes. Só a escolha do lado do quarteirão mudou.
7. **§2 + §1-A:** o tamanho do quarteirão é decisão geométrica do Python (não do LLM); selo
   "ESQUEMÁTICO" + "verificar com urbanista"; regex sem "aprovado/viável/regular".
8. **Conectividade melhora:** `conexo_por_ilha` passa a `true` nas ilhas que comportam malha (as
   que viravam 1 face e davam viário 0 agora geram fronteira interna). Ilhas legitimamente
   separadas pela declividade seguem desconexas entre si (correto — pontes são fase futura).

> **Expectativa (registrada):** esta fase recupera o viário e descola os lotes na gleba
> estilhaçada, fazendo a malha funcionar na ilha torta como já funciona na caixa limpa. Não é um
> traçado executivo — segue esquemático (§1-A). Ilhas separadas por faixa fina de declividade
> continuam **desconexas entre si** nesta fase; **reconectá-las (pontes) é a fase futura
> registrada** abaixo.

## 6. Fora de escopo (registrado)

- **Pontes entre ilhas vizinhas separadas por declividade fina** — **FASE FUTURA** (reconectar o
  que a declividade separou; melhoria real, mas é outra fase — não empilhar aqui). Quando a ilha
  A e a ilha B estão a poucos metros, separadas só por uma fresta de declividade, uma via-ponte
  poderia uni-las; fica para depois desta.
- **Pórtico de entrada** — depois das pontes/maturação do viário.
- **Render artístico** — Nível 3, futuro.
- **Mexer em poda, sinuosidade, recorte, clamp** — proibido (inocentados/corretos).

## 7. Arquivos esperados (latitude de implementação)

- `core/urbanismo_geom.py`:
  - na geração por ilha (9.7/9.8), trocar o **lado do quarteirão fixo** por
    `lado_quadra_adaptativo(ilha, perfil, clamp)` → função do tamanho da ilha, com `clamp(piso_legal,
    teto_perfil)`; o piso deriva do lote mínimo do clamp (9.4).
  - ramo de **sliver**: ilha que não rende face loteável nem no piso → verde/não-aproveitável
    (rotulada), nunca bloco forçado.
  - `_subdividir_quadra` (9.4), fronteiras internas/viário (9.7), poda (9.8) — **reusados sem
    mudança**.
- `core/urbanismo_medida.py` — `ilhas_detalhe` (área, bbox, lado_quadra, faces, motivo);
  `grade_adaptativa`. Medição reusa.
- `models/schemas.py` — `ilhas_detalhe`, `grade_adaptativa` no diagnóstico.
- `routers/urbanismo.py` — propagar o diagnóstico de adaptação.
- Frontend — sem mudança obrigatória (a malha já vem do back mais densa); opcional: nota "grade
  adaptada ao terreno" quando `grade_adaptativa` agir.
- Testes: `tests/test_urbanismo_grade_adaptativa.py` — viário ~15% na gleba estilhaçada real,
  faces por ilha crescem, **piso legal respeitado (`fora_da_faixa == 0`)**, sliver vira verde,
  caixa limpa intacta, poda/sinuosidade não tocadas; usa o KMZ real de São Roque e a vizinhança
  do log (38k m² → ≥6 faces), offline onde possível.

A spec fixa **contrato + critérios + ALGORITMO**. **A grade do quarteirão passa a ser função do
tamanho da ilha, com piso legal inviolável** — ilha pequena afina até gerar faces (recuperando
fronteira interna e, com ela, o viário e a separação dos lotes), mas nunca abaixo do lote mínimo;
ilha pequena demais vira verde honesto. Corrige a regressão (viário colapsado) atacando a causa
que o log provou — poucas faces por ilha — **sem tocar na poda, na sinuosidade nem no recorte,
todos inocentados**. As pontes entre ilhas ficam como fase futura registrada.
