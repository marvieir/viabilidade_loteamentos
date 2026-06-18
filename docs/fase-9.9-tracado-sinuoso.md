# Fase 9.9 — Urbanismo: traçado sinuoso (a IA propõe eixos curvos; o Python materializa contornando o íngreme)

> A fase que dá ao estudo a **cara orgânica do urbIA**. O diagnóstico fechou que a gleba de São
> Roque é **majoritariamente encosta ≥30%** (vegetação é só 7%, 0% dura) — logo **43 lotes é o
> número honesto**, e o parcelamento cabe só nas **pontas loteáveis**. Falta o traçado deixar de
> ser **grade reta** e virar **vias sinuosas** que acompanham o relevo e contornam a mancha
> íngreme. Descoberta-chave da 9.8: **o esqueleto da IA vem VAZIO** → o gerador cai no plano B
> (grade reta). Esta fase ataca as duas metades juntas: (1) garantir que o produto **chama o
> modelo** para propor eixos sinuosos, e (2) **materializar** esses eixos como vias curvas.
> Referencia `ARCHITECTURE.md` (§1-A, §2) e as Fases 9.1/9.7/9.8. **IA propõe a geometria dos
> eixos (curva); Python materializa, recorta à ilha e mede.**

## 0. As duas causas da grade reta (ambas atacadas aqui)

| Causa | Hoje | 9.9 |
|---|---|---|
| **A IA não propõe eixos** | esqueleto vem `[]` → plano B (grade reta) | o produto **chama o modelo** pedindo eixos sinuosos; se vier vazio, é erro registrado, não silêncio |
| **Mesmo com eixo, era reto** | eixo tratado como segmento reto | eixo é **polilinha/curva** (vários vértices), materializada como via curva |

**Por que o esqueleto vinha vazio (a investigar na implementação):** ou o prompt do programa não
pede eixos com vértices suficientes, ou o parser descarta a curva, ou o preset não encaminha o
esqueleto ao gerador. A spec exige que isso seja **diagnosticado e corrigido** — o sintoma
("esqueleto vazio → grade") não pode mais ocorrer silenciosamente.

## 1. Objetivo

Traçado **sinuoso e orgânico** nas pontas loteáveis, acompanhando o relevo e **contornando** a
área não-edificável (≥30%), como o urbIA. Concretamente: a IA propõe uma **via-tronco curva +
ramos** (polilinha com vértices), o Python a materializa com largura legal, **recortada às ilhas
loteáveis** (nunca entra no íngreme), e as quadras/lotes nascem dessa malha curva (reusa
9.7/9.8). Continua **ESTUDO DE MASSA ESQUEMÁTICO** (§1-A) — agora visualmente fiel.

## 2. O que NÃO muda (não-regressão)

- **Toda a maquinaria 9.7/9.8 é preservada:** malha por buffer de eixos, quadras como faces,
  poda de stubs, malha por ilha, institucional/clube formados, `_subdividir_quadra` + clamp
  (9.4), `lotes_features` (9.5), separação verde (9.6), rótulo da restrição (9.8). **A 9.9 só
  troca a FORMA dos eixos (reto → curvo) e garante que eles VÊM da IA.**
- **Fronteira §2 imóvel — e este é o ponto mais delicado da fase:** a IA propõe a **geometria
  dos eixos** (a curva, como intenção de traçado), o Python materializa e **mede**. O eixo é um
  artefato de **intenção** (uma polilinha esquemática), não a via final com coordenadas de
  projeto — o Python a recorta à ilha, aplica largura legal, deriva as faces e mede tudo.
  **Nenhum número (área, nº de lotes, m² de via) vem do LLM** — igual hoje. A curva proposta é
  orientação de desenho; a geometria medida é do motor.
- Os 43 lotes / a área não-edificável **não mudam** por esta fase (é traçado, não recorte).
- Snapshot e contrato do `/medir` preservados.

## 3. O algoritmo (validado na espinha)

```
ENTRADA: ilhas loteáveis (9.8, já contornam o íngreme), perfil, DEM (2.5), diretrizes (9.4)

1. PEDIR EIXOS À IA (corrige o esqueleto vazio):
   - o programa (proposto_llm) deve retornar, POR ILHA loteável, um esqueleto viário como
     POLILINHA com vértices suficientes para curvar (ex.: ≥4 pontos por eixo), em coords
     normalizadas 0..1 da ilha;
   - o prompt instrui: via-tronco SINUOSA acompanhando o eixo maior da ilha + ramos curtos;
     evitar a área íngreme (já recortada); densidade do perfil.
   - VALIDAÇÃO DURA: se o esqueleto vier vazio ou com <2 vértices (degenera em reta), o produto
     REGISTRA o erro (não cai silenciosamente na grade); tenta fallback explícito (curva
     padrão derivada do eixo principal da ilha), nunca a grade reta sem aviso.
2. MATERIALIZAR a curva (Python):
   - normalizado 0..1 → métrico na ilha;
   - eixo = polilinha suavizada (Bézier/Catmull-Rom amostrada nos vértices da IA) → curva real;
   - ruas = buffer(eixo, largura_legal/2) ∩ ILHA  (hierarquia tronco 21 / local 8 da 9.7)
   - CONTORNO POR CONSTRUÇÃO: o ∩ ilha garante que a via nunca invade o íngreme.
3. QUADRAS, LOTES, ÁREAS PÚBLICAS: malha → faces → _subdividir_quadra → institucional/clube
   formados (REUSA 9.7); poda de stubs (REUSA 9.8). Sem mudança — só os eixos agora são curvos.
4. MEDIR: viário, vendável, distribuição, conformidade (REUSA). Sinuosidade é métrica de
   apresentação, não entra no número de área.
SAÍDA: igual 9.8 + eixos curvos; lotes_features, malha curva, áreas formadas, restrição rotulada.
```

**Sinuosidade como intenção, não número (§2):** a curva orienta *onde* a via passa; o Python
mede *quanto* de área ela ocupa. A razão comprimento-curva / distância-reta (sinuosidade) é só
um indicador de apresentação — nenhuma área ou contagem deriva do LLM.

## 4. Contrato de API

`PropostaUrbanisticaOut` (9.8) ganha o estado do esqueleto e a métrica de sinuosidade:
```jsonc
"programa": { /* … proposto_llm … */
  "esqueleto": [ /* POR ILHA: polilinha 0..1 com ≥4 vértices p/ curvar */
    { "ilha": 0, "tipo": "tronco", "pontos": [[0.05,0.5],[0.3,0.7],[0.6,0.45],[0.95,0.55]] },
    { "ilha": 0, "tipo": "ramo",   "pontos": [[0.3,0.7],[0.35,0.95]] } ],
  "esqueleto_origem": "llm" },          // "llm" | "fallback_curva" | (NUNCA "grade_silenciosa")
"viario_diagnostico": { /* … 9.8 … */
  "esqueleto_vazio": false,             // se true, o produto avisou e usou fallback explícito
  "sinuosidade_media": 1.28,            // >1.1 = curvo (1.0 = reto); indicador de apresentação
  "eixos_curvos": true,
  "obs": "eixos sinuosos propostos pela IA, materializados e recortados às ilhas loteáveis" }
```
`/medir` inalterado no contrato de números.

## 5. Critérios de aceite (testáveis)

1. **A IA propõe eixos (resolve a causa raiz):** em São Roque/alta, `esqueleto` vem **não-vazio**
   com ≥1 tronco por ilha loteável e ≥4 vértices por eixo; `esqueleto_origem == "llm"`. O
   sintoma "esqueleto vazio → grade" **não ocorre**; se por algum motivo a IA falhar,
   `esqueleto_vazio == true` **e** usa-se fallback de curva explícito (nunca grade silenciosa).
2. **Traçado curvo (resolve o nº 2 visual):** `sinuosidade_media > 1.1` (vias mensuravelmente
   curvas, não retas); `eixos_curvos == true`. Teste geométrico: o comprimento de cada eixo
   excede a distância reta entre suas pontas em ≥10%.
3. **Contorno do íngreme (por construção):** nenhum trecho de via cai dentro da área
   não-edificável (≥30%); `via ∩ restricao_recortada == vazio`. As curvas ficam nas ilhas
   loteáveis.
4. **Malha ainda enxuta e conexa (não regride a 9.8):** viário continua `≤ ~18%` na gleba real,
   conexo por ilha, stubs podados; os 43 lotes (número honesto) **não caem** por causa do
   traçado curvo (a curva não pode inflar viário acima do teto — se inflar, poda).
5. **Reuso intacto (9.7/9.8):** quadras como faces, institucional/clube formados, clamp legal
   (`fora_da_faixa == 0`), `lotes_features`, separação verde, rótulo da restrição — todos
   preservados sobre a malha curva.
6. **Fronteira §2 + §1-A (o ponto sensível):** o LLM fornece **só a geometria dos eixos** (a
   curva); **nenhuma área, contagem de lotes ou m² de via vem do LLM** — o Python materializa,
   recorta e mede; selo "ESQUEMÁTICO" + "traçado aproximado, verificar com urbanista"; regex sem
   "aprovado/viável/regular".
7. **Número estável:** quadro de áreas, nº de lotes (~43), distribuição — coerentes com a 9.8
   (o traçado mudou de forma, não de quantidade); diferenças só as esperadas por re-loteamento
   das faces curvas, dentro da invariância (retalho ≤1,5%).
8. **Não-regressão:** fases 9.1→9.8 preservadas; suítes verdes (exceto valores de layout, que
   mudam por traçado curvo — invariâncias, clamps e o teto de viário seguem).

> **Expectativa (registrada, honesta):** esta fase deixa o traçado **curvo e orgânico**,
> contornando o íngreme — a cara do urbIA nas pontas loteáveis. Mas é a **primeira versão** da
> sinuosidade: as curvas virão suaves e plausíveis, ainda não necessariamente idênticas ao
> desenho manual de um urbanista (cul-de-sacs, praças de retorno, hierarquia fina de ramos podem
> precisar de iteração). O objetivo é **sinuoso e fiel ao relevo**, não traçado executivo. E
> como metade da gleba é não-edificável, o desenho ocupa só as pontas — isso é o correto, não
> uma limitação.

## 6. Fora de escopo (registrado)

- **Pórtico de entrada** — próxima fase (agora há via-tronco curva onde ancorá-lo).
- **Cul-de-sacs / praças de retorno / hierarquia fina** — refinamento posterior se necessário.
- **Render artístico** (árvores, sombras, ícones) — Nível 3, futuro.
- **Estudo de massa "otimista"** (lotear sobre a mata a-verificar) — descartado para São Roque
  (vegetação é só 7%, irrelevante); fica como possibilidade genérica para glebas onde a mata
  a-verificar seja grande, não aqui.
- **Mudança de recorte / declividade / nº de lotes** — fora; 43 é honesto.

## 7. Arquivos esperados (latitude de implementação)

- `core/urbanismo_programa.py` / prompt do `proposto_llm` — **pedir eixos sinuosos por ilha**
  (polilinha ≥4 vértices, 0..1, tronco curvo + ramos, evitando o íngreme); **diagnosticar e
  corrigir** o esqueleto vazio (causa: prompt? parser? encaminhamento ao gerador?).
- `core/urbanismo_geom.py`:
  - `_eixos` — aceitar polilinha com vértices e **suavizar** (Bézier/Catmull-Rom amostrada) →
    curva real; `construir_malha` usa o eixo curvo (já existe o buffer; muda a forma do eixo).
  - garantir `∩ ilha` (contorno do íngreme por construção) e fallback de curva explícito.
- `core/urbanismo_medida.py` — `sinuosidade_media`, `eixos_curvos`, `esqueleto_vazio`,
  `esqueleto_origem` no diagnóstico. Medição de área reusa.
- `models/schemas.py` — `esqueleto` com `pontos` (polilinha), `esqueleto_origem`, métricas de
  sinuosidade.
- `routers/urbanismo.py` — propagar esqueleto/origem/sinuosidade; resposta com eixos curvos.
- Frontend `MapaLeaflet` — desenhar as **vias curvas** (a malha já vem do back); legenda/nota de
  traçado sinuoso aproximado.
- Testes: `tests/test_urbanismo_sinuoso.py` — esqueleto não-vazio e origem llm, sinuosidade >1.1,
  via ∩ íngreme vazio, viário ≤18% mantido, 43 lotes estáveis, reuso 9.7/9.8; com stub de LLM que
  devolve polilinha curva, offline.

A spec fixa **contrato + critérios + ALGORITMO**. **A IA propõe a via-tronco curva + ramos
(geometria de intenção, por ilha loteável); o Python suaviza, materializa com largura legal,
recorta às ilhas (contornando o íngreme por construção), e mede tudo** — o traçado deixa de ser
grade reta e vira sinuoso como o urbIA, sem que nenhum número venha do LLM (§2) e sem regredir a
malha enxuta da 9.8. O esqueleto vazio é corrigido na raiz (a IA passa a propor de fato os
eixos). É a primeira versão da sinuosidade — orgânica e fiel ao relevo, nas pontas que a gleba
comporta. Depois dela: o pórtico.
