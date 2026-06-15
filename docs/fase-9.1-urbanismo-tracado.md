# Fase 9.1 — Urbanismo: fidelidade do traçado (programa materializado + viário por arquétipo + topografia)

> Corretiva/refinadora da Fase 9. A v1 gerou um quadro de áreas **honesto** mas **distante da
> intenção do programa**: a IA pediu 25% de lazer + viário orgânico, o motor materializou 2,5%
> e uma grelha axial, descartando o esqueleto da IA. Esta fase faz a geometria **convergir para
> o programa** — sem mover um milímetro da fronteira do §2. Referencia `ARCHITECTURE.md`
> (§1-A, §2, §6-A, §7) e a Fase 9. **IA propõe; Python materializa e mede.**

## 1. Objetivo

Elevar a **fidelidade** do estudo de massa em três frentes, mantendo-o esquemático e §1-A:
1. **Materializar o programa de áreas** — reservar de fato o `%lazer` (clube/lazer central +
   áreas verdes) e a doação institucional **antes** de lotear, com o quadro de áreas medido
   **convergindo** para o programa (com tolerância) ou **degradando rotulado** quando a gleba
   não comporta.
2. **Viário por arquétipo** — o gerador passa a honrar o `arquetipo_viario` e a **consumir o
   esqueleto da IA como eixos-base** (regularizando/snapando), em vez de só registrar e descartar.
3. **Topografia no traçado** — usar a declividade (DEM da 2.5, já disponível) para **orientar**
   quarteirões/vias (acompanhar curvas de nível; fundo de lote para o verde/vista) — como
   triagem, não terraplenagem.

**Continua ESTUDO DE MASSA ESQUEMÁTICO** — o traçado executivo e as diretrizes da gleba são do
urbanista (§1-A). A melhora é de *plausibilidade*, não de *aprovabilidade*.

## 2. O que NÃO muda (não-regressão)

- **A fronteira do §2 é inviolável e não se mexe:** nenhuma coordenada/número final vem do LLM.
  O LLM continua propondo **programa + esqueleto** (intenção); o Python materializa toda a
  geometria e mede todos os números. O que muda é **o quanto o Python honra o programa**, não
  quem desenha.
- **Snapshot versionado (Fase 9 §7) intacto:** "mesmo snapshot → mesma medição". A parte criativa
  (programa/esqueleto) segue não-determinística; a materialização+medição segue determinística.
- **Cenário aditivo (Fase 9 §8):** não troca o headline. Fases 1–8 byte a byte. Suítes 1…9 verdes.
- `/medir` (sem LLM) continua existindo e medindo qualquer layout — os ouros de São Roque do
  quadro de áreas **permanecem válidos**.

## 3. A régua da fronteira (o ponto crítico — "regularizar" sem virar projetista)

O risco desta fase é o Python "melhorar" o traçado a ponto de **projetar**. A linha:

| O Python PODE (materializar/regularizar — determinístico) | O Python NÃO faz (é projeto — do urbanista) |
|---|---|
| Snapar os eixos da IA à gleba; fechar gaps; remover auto-interseção; impor largura/raio mínimos | Inventar um traçado "melhor" que o programa não pediu; otimizar |
| Reservar polígonos de lazer/institucional na posição que o esqueleto/zonas da IA indicam | Decidir onde fica o clube por critério próprio (isso é da IA/urbanista) |
| Orientar fileiras de lote perpendiculares ao eixo; girar quarteirões para acompanhar a curva de nível | Dimensionar greide, corte/aterro, drenagem |
| Recortar tudo contra a área aproveitável (restrições) | Liberar restrição para "caber" o programa |
| Medir e **reportar divergência** entre programa e resultado | Esconder a divergência ou forçar o número |

**Regra-mestre:** a IA dá **intenção georreferenciada** (eixos, zonas); o Python faz
**operações geométricas determinísticas e auditáveis** (snap, buffer, offset, recorte, rotação
de quarteirão por aspecto de declividade) para **materializar essa intenção** e medir. Toda
operação é nominável e testável — se não dá para escrever como função geométrica determinística,
é projeto, e não entra.

## 4. Como funciona

### 4.1 (a) Materialização do programa de áreas — reservar antes de lotear
Ordem nova do gerador (`core/urbanismo_geom.py`):
```
1. área aproveitável (restrições já recortadas — Fase 2.x)
2. RESERVAR lazer central + áreas verdes (alvo = pct_lazer × aproveitável) nas zonas que a IA
   indicou; RESERVAR institucional (doação da 1.8/perfil)
3. lotear o RESTANTE (viário + quadras + lotes)
4. medir o quadro; comparar com o programa → convergência OU degradação rotulada
```
**Convergência:** `|pct_medido − pct_programa| ≤ tol` (default 3 p.p. para lazer/verde; doação
institucional segue o mínimo legal da zona, sem tolerância para baixo). Dentro da tolerância →
`status: "atendido"`.
**Degradação honesta (gleba não comporta):** se o `%lazer` pedido não cabe preservando lote
mínimo viável, materializa o **máximo físico** e rotula *"lazer reduzido de 25% para 18% — a
gleba não comporta o programa pedido preservando lotes; verificar prioridades com urbanista"*.
**Nunca** infla o número nem ignora o pedido em silêncio.

### 4.2 (b) Viário por arquétipo — consumir o esqueleto da IA
- O programa traz `arquetipo_viario` (`grelha_eficiente` | `sinuoso_fundo_vale` | …) e o
  **esqueleto** (polilinhas dos eixos principais). O gerador passa a usar o esqueleto como
  **eixos-base**: snapa à gleba, regulariza (largura da hierarquia, raio mínimo de curva,
  conexão), e gera as vias locais conforme o arquétipo (grelha → fileiras ortogonais; sinuoso →
  vias acompanhando o esqueleto/curvas, lotes perpendiculares).
- Esqueleto inválido (sai da gleba, auto-intersecta) → o Python **regulariza ou descarta o
  trecho e registra** (como hoje), mas o caminho feliz passa a **honrar** o que é válido.
- A medição (comprimento de vias, leito, calçadas, testada/profundidade) é a mesma — só o
  traçado de entrada muda.

### 4.3 (c) Topografia no traçado (DEM da 2.5 como orientação)
- Reusa a malha de declividade já computada (Fase 2.5). O gerador usa o **aspecto/curvas de
  nível** para **orientar** quarteirões: girar a fileira de lotes para que as vias acompanhem a
  curva de nível (menos rampa transversal) e o **fundo do lote** aponte para o verde/cota alta
  (privacidade/vista — peso do perfil alta renda). É **orientação geométrica**, não greide.
- Onde a declividade ≥30% (vedada) já está fora (recorte da Fase 2.5); aqui a declividade
  **suave/média** apenas **orienta**, não veta. Rótulo: *"orientação por declividade —
  triagem; o projeto geométrico/terraplenagem é do urbanista/engenheiro"*.

### 4.4 Heatmap (Fase 9) ganha sinal melhor
Com lazer central materializado e fundo-para-verde, o `score()` por lote passa a refletir
proximidade real do lazer e privacidade de fundo — sem mudar a fórmula (os atributos já
existem; agora a geometria os alimenta de verdade).

## 5. Contrato de API

Sem endpoint novo. `POST /api/analises/{id}/urbanismo/propor` ganha campos de **fidelidade** na
resposta (a proposta/`PropostaUrbanisticaOut` da Fase 9 é estendida):
```jsonc
"programa": { /* … Fase 9 … */ "arquetipo_viario": "sinuoso_fundo_vale",
              "esqueleto": { "tipo": "GeoJSON", "eixos": [...] } },   // intenção da IA
"fidelidade": {
  "areas": [
    { "item": "lazer", "alvo_pct": 0.25, "medido_pct": 0.241, "status": "atendido", "tol_pp": 3 },
    { "item": "institucional", "alvo_pct": 0.05, "medido_pct": 0.05, "status": "atendido" },
    { "item": "lazer", "status": "degradado",
      "leitura": "reduzido de 25% para 18% — gleba não comporta preservando lotes; ver urbanista" }
  ],
  "viario": { "arquetipo": "sinuoso_fundo_vale", "esqueleto_usado": true,
              "trechos_descartados": 1, "obs": "1 trecho do esqueleto saía da gleba — descartado" },
  "topografia": { "orientacao_por_declividade": true,
                  "obs": "quarteirões orientados às curvas de nível (DEM 2.5) — triagem, não terraplenagem" }
},
"avisos": [ /* … os 3 da Fase 9 … */,
  "Fidelidade: o quadro de áreas converge para o programa quando a gleba comporta; divergências são rotuladas, nunca forçadas." ]
```
Degradação: programa sem zonas de lazer indicadas → reserva no melhor encaixe geométrico e
rotula "posição do lazer inferida — confirme com urbanista". `/medir` inalterado.

## 6. Critérios de aceite (testáveis)

**Sobre snapshots fixos** (a parte criativa é não-determinística; o teste mede o motor sobre um
programa/esqueleto fixo — padrão Fase 9).

1. **Convergência de áreas (caso sintético-ouro):** gleba aproveitável retangular de 58.682 m²,
   programa lazer 25% + institucional 5% → após materializar, `lazer_medido ∈ [22%, 28%]`
   (`status="atendido"`), `institucional ≥ 5%`, e a v1 (2,5%) **falha** o critério (prova de
   que o critério morde).
2. **Reserva antes de lotear:** a soma vendável + verdes + lazer + institucional + arruamento =
   área aproveitável (±0,5 m²); o lazer/institucional **não** intersectam lotes.
3. **Degradação honesta:** programa lazer 25% numa gleba que só comporta 18% preservando lote
   mínimo → `status="degradado"`, `medido ≈ 18%`, leitura presente; **nunca** infla para 25%
   nem zera o pedido.
4. **Esqueleto consumido:** com esqueleto fixo válido, as vias geradas seguem os eixos
   (teste: distância de Hausdorff entre eixo-base e via gerada ≤ tolerância de regularização);
   `esqueleto_usado=true`. Trecho inválido → descartado e contado, resto honrado.
5. **Arquétipo aplicado:** `grelha_eficiente` produz vias predominantemente ortogonais;
   `sinuoso_fundo_vale` produz vias acompanhando o esqueleto/curvas — testável por métrica de
   orientação (variância angular das vias) distinta entre os dois sobre a mesma gleba.
6. **Topografia orienta, não veta:** com DEM fixo, os quarteirões giram para acompanhar a curva
   de nível (teste: ângulo médio via × gradiente dentro de faixa); declividade ≥30% continua
   **fora** (recorte 2.5 inalterado); rótulo "triagem, não terraplenagem" presente.
7. **Fronteira §2 intacta:** gerador-stub fornece programa+esqueleto; **nenhum número/coordenada
   final vem do stub** — o Python materializa e mede. O Python **não** gera lazer/viário que o
   programa não pediu (teste: programa sem lazer → sem lazer materializado, não um default
   inventado).
8. **Determinismo por snapshot:** materializar+medir o mesmo snapshot 2× → idêntico; regerar =
   nova versão.
9. **§1-A:** rótulo "ESTUDO DE MASSA ESQUEMÁTICO" + avisos (Fase 9 + o de fidelidade); **regex:
   sem "aprovado/viável/regular"**; "verificar com urbanista" presente; rótulos de degradação/
   orientação presentes.
10. **Não-regressão:** `/medir` e os ouros de quadro de áreas de São Roque (Fase 9) **inalterados**;
    fases 1–8 byte a byte; suítes 1…9 verdes; gerador geométrico testado isolado, offline.

> **Nota de dado de teste:** os critérios usam **casos sintéticos** (geometria controlada) para
> cravar convergência/arquétipo/topografia de forma determinística. O **São Roque real** entra
> como **validação** quando o layout chegar como geometria (KMZ/DWG/GeoJSON) — aí confere-se que
> o motor mede o traçado real reproduzindo o quadro, como na Fase 9.

## 7. Fora de escopo (registrado — não inflar)

- **Projeto urbanístico aprovável / diretrizes da gleba** (art. 6º/7º Lei 6.766) — do urbanista.
- **Projetos técnicos** (água, esgoto, energia, drenagem) e **terraplenagem/greide/corte-aterro**
  — fora; topografia aqui só **orienta** o traçado, não dimensiona.
- **Custos de obra** (SINAPI/SICRO) — fase de custos futura.
- **Otimização multiobjetivo do traçado** (maximizar lotes/valor/declividade automaticamente) —
  o tool materializa o programa proposto; não busca o ótimo.
- **Edição interativa na tela / 3D / render fotorrealista** — evolução; o MVP gera e mede.
- **Geometria orgânica de qualidade executiva** (a beleza do render do urbanista) — continua
  esquemático; o ganho é convergência ao programa + viário plausível, não arte final.

## 8. Arquivos esperados (latitude de implementação)

- `core/urbanismo_geom.py` — nova ordem (reservar lazer/institucional → lotear restante);
  consumo do esqueleto (snap/regularização); orientação de quarteirão por declividade (DEM 2.5).
  **Python puro.**
- `core/urbanismo_medida.py` — bloco `fidelidade` (convergência por item, degradação rotulada).
- `routers/urbanismo.py` — resposta estendida (`fidelidade`); `/medir` inalterado.
- `models/schemas.py` — `FidelidadeOut`, campos de esqueleto/arquétipo na proposta.
- Frontend: `CardUrbanismo` mostra a **convergência programa × medido** (barras alvo vs medido),
  o arquétipo viário e a nota de topografia; selo "ESQUEMÁTICO" e avisos §1-A mantidos; render do
  GeoJSON já honra lazer central + viário do arquétipo. Front só renderiza.
- Testes: `tests/test_urbanismo_fidelidade.py` (convergência, degradação, esqueleto, arquétipo,
  topografia, fronteira-stub, determinismo — casos sintéticos, offline).

A spec fixa **contrato + critérios**; o resto é latitude. **A IA propõe a intenção; o Python
materializa por operações geométricas determinísticas e mede** — a fidelidade sobe, a fronteira
do §2 não se move, e o urbanista segue insubstituível (§1-A).
