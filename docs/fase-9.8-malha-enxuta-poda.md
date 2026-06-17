# Fase 9.8 — Urbanismo: malha enxuta (poda de stubs + grade por ilha + rótulo da restrição)

> Corrige o que o diagnóstico isolou na 9.7: numa gleba **irregular/recortada**, a malha gerada
> sobre o retângulo envolvente vira **stubs** (cacos de via que não servem lote) → viário inchou
> para 26% e os lotes caíram para 41. A hierarquia (tronco 21 m / local 8 m) está **correta**;
> o problema é a **forma da gleba**. Esta fase **poda os stubs**, gera a malha **por ilha**
> (respeitando a forma e as restrições que partem a gleba) e **rotula a restrição recortada no
> mapa**. Referencia `ARCHITECTURE.md` (§1-A, §2) e a Fase 9.7. **IA propõe eixos; Python poda,
> mede e respeita a forma.** A sinuosidade do traçado é a 9.9 (separada, a seguir).

## 0. A causa-raiz (medida pelo diagnóstico, não suposta)

O Claude Code mediu glebas de formas diferentes com o mesmo perfil (alta/MUE):

| Gleba | viário | vendável | nº lotes | trechos |
|---|---|---|---|---|
| Caixa perfeita 343×172 | **14,9%** | 53,9% | 69 | 1 |
| Partida (2 massas + pescoço) | 18,9% | 48,2% | 48 | 2 |
| Com mata diagonal no meio (≈ a real) | **22,7%** | 47,1% | 81 | 3 |

No último caso, os trechos de via mediram `[149, 7716, 10809] m²` — o **trecho de 149 m² é um
stub** (caco de rua que não serve lote). Quanto mais recortada a gleba, mais stubs entram no
viário e menos faces sobram para lote. **É limitação de design da geração (grade-sobre-bbox), não
calibração de parâmetro.** A malha 9.7, na caixa limpa, dá 15% e conexa — o inchaço é a forma.

Dois achados extras do diagnóstico, que esta spec incorpora:
- O **preset 'alta' veio com esqueleto vazio** → a IA não propôs eixos e o gerador caiu no plano
  B (promover 1 linha central a tronco + grade local). (A proposta de eixos pela IA é tratada a
  fundo na 9.9.)
- A **faixa central clara é restrição recortada** (vegetação e/ou declividade ≥30%; a APP deu
  timeout neste teste) — o motor **corretamente** não loteou sobre ela. Não é bug; falta **rótulo
  no mapa**.

## 1. Objetivo

Tornar a malha **enxuta e fiel à forma da gleba**: remover stubs, gerar a malha **por ilha**
(cada região separada por restrição tem sua própria malha conexa), exigir que cada eixo **sirva
≥1 fileira de lotes**, e **rotular a restrição recortada** no mapa de urbanismo. Meta: viário de
volta a **≤ ~18%** e vendável para perto de **~55%** na gleba real, recuperando os lotes
perdidos. Continua **ESTUDO DE MASSA ESQUEMÁTICO** (§1-A); o traçado segue reto (a curva é 9.9).

## 2. O que NÃO muda (não-regressão)

- **A malha 9.7 (eixos → buffer → faces) é preservada** — ganha **poda** e **geração por ilha**.
  Na caixa limpa, o resultado deve continuar ~15% (a poda não piora o que já estava bom).
- Reusa intacto: `_subdividir_quadra` + clamp/diretrizes (9.4), `lotes_features` (9.5), separação
  verde (9.6), institucional/clube como quadras formadas (9.7), medição.
- **Fronteira §2 imóvel:** IA propõe eixos; Python poda e mede. A poda é **operação geométrica
  determinística** (remover eixo que não serve lote), não decisão de projeto.
- Snapshot e contrato do `/medir` preservados.

## 3. O algoritmo (poda + ilha)

```
1. ILHAS: a área aproveitável já vem recortada das restrições (router). Se a restrição PARTE a
   gleba em regiões desconexas, tratar cada COMPONENTE como uma ILHA independente:
     ilhas = _componentes(aprov)   # cada uma com sua própria malha conexa
   (conexo passa a ser avaliado POR ILHA — duas massas separadas por mata são legitimamente 2)
2. Para cada ilha, gerar a malha 9.7 (eixos da IA ∩ ilha + grade local recortada à ILHA, não ao
   bbox da gleba inteira) → menos stubs já de partida.
3. PODA DE STUBS (a correção central): remover todo eixo/segmento de via que NÃO sirva lote:
     • um eixo "serve" se há quadra loteável (área ≥ ~1 lote) de pelo menos um lado da sua faixa
       E o eixo tem comprimento ≥ ~25 m (não é cotovelo/caco);
     • segmento que não serve → removido; a área dele volta a lote (re-loteia a face) ou a verde.
     • repetir até estabilizar (a remoção de um stub pode expor outro).
4. CONECTIVIDADE por ilha: após a poda, cada ilha deve ter malha conexa (1 peça) ligando seus
   lotes ao tronco; se a poda desconectar um grupo de lotes, manter o menor eixo que o reconecta.
5. Re-medir: viário (área da malha podada), vendável, nº de lotes, distribuição (reusa).
6. RÓTULO DA RESTRIÇÃO (apresentação): desenhar no mapa de urbanismo a restrição recortada
   (vegetação/declividade/APP) como camada própria rotulada — não deixá-la como "clarão".
```

**Regra de poda (determinística, §2):** "um eixo de via só existe se serve lote". Isso é
mensurável (quadra loteável adjacente + comprimento mínimo) e auditável — não é o Python
"projetando", é removendo via que não cumpre função. O que sobra de área vira lote ou verde
(nunca retalho — 9.4 preservado).

## 4. Contrato de API

`PropostaUrbanisticaOut` (9.7) ganha o diagnóstico de poda/ilha e a restrição rotulada:
```jsonc
"geometria": { /* … 9.7 … */
  "restricao_recortada": {            // NOVO: a restrição que o motor não loteou (p/ rótulo)
    "type": "MultiPolygon", "coordinates": [...],
    "origem": ["vegetacao","declividade_30"],   // de onde veio (APP se disponível)
    "rotulo": "Área não-edificável (mata/declividade) — ver cards Ambiental/Vegetação/Declividade" } },
"viario_diagnostico": {
  "ilhas": 2,                          // nº de regiões separadas por restrição
  "conexo_por_ilha": true,             // cada ilha tem malha conexa
  "stubs_podados": 3,                  // quantos cacos de via foram removidos
  "viario_pct": 0.17, "vendavel_pct": 0.55,
  "obs": "malha por ilha; eixos que não servem lote foram podados; área recuperada virou lote/verde" }
```
`/medir` inalterado no contrato.

## 5. Critérios de aceite (testáveis — ancorados no experimento do diagnóstico)

1. **Viário enxuto (resolve o nº 1):** na gleba real recortada (tipo São Roque com mata
   central), `viario_pct ≤ ~18%` (a 9.7 dava 22-26%); vendável sobe para **~55%** (era 47-35%);
   nº de lotes **sobe** vs. os 41 atuais. Calibrado contra o experimento (caixa limpa = 15%).
2. **Stubs podados:** nenhum trecho de via menor que ~1 lote sem quadra loteável adjacente
   sobrevive; `stubs_podados ≥ 1` na gleba recortada; o trecho de 149 m² do diagnóstico **não**
   existe mais.
3. **Cada eixo serve lote:** teste — todo segmento de via tem ≥1 quadra loteável adjacente e
   comprimento ≥ ~25 m; cotovelos/cacos foram removidos.
4. **Malha por ilha (resolve parte do nº 2):** gleba partida por restrição → `ilhas ≥ 2`,
   `conexo_por_ilha == true` (cada região é conexa internamente); a malha **não** tenta cruzar a
   restrição. Caixa não-partida → 1 ilha, conexa.
5. **Não piora a caixa limpa:** gleba retangular continua viário ~15%, conexa, ~69 lotes (a poda
   não degrada o que já estava bom).
6. **Restrição rotulada (resolve o nº 3):** `restricao_recortada` presente quando há restrição
   que o motor recortou; o mapa de urbanismo a desenha como camada rotulada (não mais "clarão");
   o texto remete aos cards Ambiental/Vegetação/Declividade. Sem restrição → campo ausente, sem
   inventar.
7. **Área recuperada vira lote/verde:** a área dos stubs removidos é reincorporada a lote ou
   verde; `retalho_perdido ≤ 1,5%` (9.4 preservado); invariância viário+quadras ≈ aproveitável.
8. **Reuso + §2 + §1-A:** clamp legal (`fora_da_faixa == 0`), `lotes_features`, institucional/
   clube formados (9.7) preservados; stub fornece eixos, Python poda e mede (nenhuma decisão do
   LLM); selo "ESQUEMÁTICO" + "verificar com urbanista"; regex sem "aprovado/viável/regular".
9. **Não-regressão:** fases 9.1/9.3/9.4/9.5/9.6/9.7 preservadas no que vale; suítes verdes
   (exceto valores de layout, que mudam por ser malha podada — invariâncias e clamps seguem).

> **Expectativa (registrada):** esta fase deixa a malha **enxuta e correta** (números de volta ao
> razoável, sem stubs, fiel à forma da gleba), mas o traçado **continua reto/angular**. A
> **sinuosidade** (vias curvas acompanhando o relevo, como o urbIA) é a **Fase 9.9**, a seguir —
> e dependerá de a IA propor de fato uma via-tronco sinuosa + ramos (hoje o esqueleto vem vazio e
> cai na grade). Separamos de propósito: primeiro enxugar e corrigir, depois curvar.

## 6. Fora de escopo (registrado)

- **Sinuosidade / traçado orgânico** — Fase 9.9 (a IA propõe via-tronco curva + ramos; verificar
  que o produto chama o modelo para o esqueleto em vez de cair na grade).
- **Pórtico de entrada** — depois da 9.9 (precisa da via principal madura).
- **Render artístico** — Nível 3, futuro.
- **Otimização do traçado, técnicos, custos** — mantidos fora.

## 7. Arquivos esperados (latitude de implementação)

- `core/urbanismo_geom.py`:
  - `_componentes(aprov)` → ilhas; gerar malha **por ilha** (grade recortada à ilha, não ao bbox).
  - `podar_stubs(eixos, quadras, ruas)` → remove eixo sem quadra loteável adjacente / comprimento
    < mínimo; itera até estabilizar; reconecta se a poda isolar lotes. **Python puro.**
  - área dos stubs removidos → re-loteia a face ou vira verde (não retalho).
- `core/urbanismo_medida.py` — `viario_diagnostico` com `ilhas`/`conexo_por_ilha`/`stubs_podados`;
  expõe `restricao_recortada` (a restrição que o router já subtraiu) para o mapa.
- `routers/urbanismo.py` — passar a geometria da restrição recortada (já calculada em
  `_aproveitavel_wgs`) para a resposta, para o rótulo no mapa.
- `models/schemas.py` — `restricao_recortada`, campos de diagnóstico de poda/ilha.
- Frontend `MapaLeaflet`/`CardUrbanismo` — desenhar `restricao_recortada` como camada rotulada
  (ex.: hachura/verde-escuro "não-edificável"); legenda atualizada. Malha podada já vem do back.
- Testes: `tests/test_urbanismo_poda.py` — viário ≤18% na gleba recortada, caixa limpa ~15%
  intacta, stubs removidos, ilhas conexas, restrição exposta; reusa o experimento do diagnóstico,
  offline.

A spec fixa **contrato + critérios + ALGORITMO**. **A IA propõe os eixos; o Python gera a malha
por ilha, poda todo segmento que não serve lote, e rotula a restrição** — viário volta ao
razoável (~15-18%), os lotes perdidos voltam, a gleba partida é tratada como ilhas conexas, e o
"clarão" vira restrição demarcada. Fronteira do §2 intacta (§1-A). O traçado fica enxuto e
correto aqui; **orgânico/sinuoso é a 9.9**, a seguir.
