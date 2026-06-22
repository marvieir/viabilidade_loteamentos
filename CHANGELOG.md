# Changelog

Registro das mudanças relevantes do estudo de massa / urbanismo. Mais recente no topo.
Convenção: cada entrada traz o **problema**, a **correção** e o **efeito medido** (pipeline real
São Roque, salvo nota). A régua continua sendo a dos `CLAUDE.md`/`ARCHITECTURE.md`: cálculo só no
backend, determinismo, proveniência, e valores-ouro por fase passando.

## [não publicado] — 2026-06-21

### Fase 11.4 — vias locais CURVAS para ALTA RENDA (beleza por perfil)
- **Princípio (operador):** alta renda → beleza é fundamental (traçado curvo, estilo URBIA);
  média/baixa → prioridade é densidade (grade reta). Encoda o §3.6 do `boas-praticas-loteamento.md`.
- **Correção:** `_via_ondulada` transforma a via local reta numa CURVA suave (onda perpendicular
  tapered nas pontas, amplitude ≤18% do bloco p/ não cruzar a paralela). Gated em `quer_curva`
  (arquétipo sinuoso = alta renda); na grelha (baixa/média) as vias seguem RETAS (densidade intacta).
- **Medido:** o protótipo provou que LOOP reduz lote (pior); a curva SUAVE (mantém a grade, só
  ondula) **preservou** o lote (n 46→47) e não mexeu na grelha — beleza sem custo de densidade.

### Fase 11.3b — pórtico na ENTRADA real (onde a via toca a borda) + marcador magenta achável.

### Fase 11.3 — PÓRTICO/entrada visível no mapa
- **Problema:** o motor já calculava a entrada única (ponto do arruamento junto à borda de acesso) e
  contava `pórtico=1`, mas era só diagnóstico — **não aparecia** como componente no mapa.
- **Correção:** `Layout.portico` (disco no acesso, sobre a via-tronco) emitido no GeoJSON; frontend
  renderiza o overlay `urb_portico` (marcador laranja forte) + legenda "Pórtico / entrada".
- Pendente (componentes nomeados — mirante/quiosque/lago): amenidades ainda agrupadas como
  lazer/verde; nomeá-las é evolução futura.

### Fase 11.2 — verde na TERRA MARGINAL (boas práticas §3.4)
- **Problema:** `_selecionar_verde` reservava as MAIORES faces como verde → tomava a parcela nobre
  (o platô), que então virava sobra; as faces irregulares (que lotam mal) viravam lote ruim.
- **Correção (Unwin/Alexander, `boas-praticas-loteamento.md` §3.4):** reserva primeiro as faces
  MENOS aptas a lote (mais irregulares/côncavas), deixando as REGULARES e cheias para virar lote.
- **Efeito (fixture real):** vendável **29,9% → 34,0%**, **n 40 → 46 (+6 lotes)**, sobra cai. Suíte
  verde (2 valores-ouro de recuperação recalibrados: a recuperação/fusão viraram OPCIONAIS porque o
  layout §3.4 reduz a necessidade — os invariantes reais seguem: zero órfão p/ verde, clamp, n_lotes
  não regride).

### Fase 11.1 — subdivisão no EIXO PRÓPRIO da parcela (Lynch/Hack)
- A quadra se orienta à FORMA do sítio (menor retângulo rotacionado), não ao eixo global — recupera
  parcela oblíqua/irregular que a grelha global desperdiçava. Never-worse (compara e escolhe). +3
  lotes, invariância preservada.

### Fase 10.8b — ≥30% é verde preservado, não "sobra"
- **Problema:** o quadro contabilizava a faixa de declividade ≥30% (não-edificável por lei) como
  "sobra geométrica a reduzir", inflando a sobra para ~39% e assustando a leitura.
- **Correção:** as faces ≥30% vão para um balde próprio (`nao_edif_reg`) que soma ao **verde
  reservado/preservado**, fora da sobra — e fora da recuperação aditiva (que poderia tentar lotear
  o ≥30%, ilegal).
- **Efeito:** sobra geométrica **30,4% → 15,5%** (só a fragmentação real); verde
  reserva/preservada **14% → ~29%** (mesma faixa de áreas verdes da referência URBIA). Vendável
  inalterado (rótulo não cria lote).

### Fase 10.8 — A gleba vira UMA (≥30% veda LOTE, não VIA)
- **Problema:** o motor recortava a faixa ≥30% **inteira** do aproveitável (tirava via *e* lote),
  deixando a gleba partida em duas porções ligadas só por uma via diagonal em "dente de serra" que
  cruzava o meio. Era o "loteamento partido" reclamado.
- **Base legal:** Lei 6.766/79 art. 3º, parág. único, III — veda **parcelamento** (lote) em ≥30%,
  **não a via** (estrada é regida por greide/corte-aterro). Vedação relativa a lote.
- **Correção:** o ≥30% **não sai mais do domínio das vias** — a malha viária atravessa a faixa e
  junta a gleba num loteamento só; só os **lotes** a evitam (a parte ≥30% vira verde preservado).
  Mata/APP seguem bloqueando via + lote.
- **Efeito:** malha **conecta as duas metades** (antes saía em 7 componentes soltos);
  viário **24,5% → 17,1%**; **0 m² de lote no ≥30%**. Com a gleba conexa, a travessia diagonal
  deixa de ser necessária.

### Fase 10.6 — Corte de viário (largura de via)
- **Correção:** cap da largura de via em **11 m** na fronteira do programa (condomínio de lotes =
  vias privadas, coletora de pista única; engine é dono da medida, §2). Independe do que a IA
  proponha. `CAIXA_TRONCO_M` (conexão) 14 → 11.
- **Efeito (sintético comparável):** viário **31,4% → 28,0%**; vendável **36,4% → 37,4%**.

### Fase 10.5 — Backstop de densidade (acesso interno em faces fundas)
- **Problema:** faces muito fundas (profundidade ≥ ~4·prof) só loteavam 2 fileiras na frente e o
  miolo virava sobra.
- **Correção:** `_adensar_face` injeta vias locais internas que cortam a face funda em bandas
  rasas, dando frente ao miolo; a via é clipada à face (não vaza para a restrição).
- **Efeito (sintético):** vendável **32,6% → 36,4%**; sobra **20,5% → 15,0%**.

### Modelo de IA
- Cadeia de modelos para `/propor`: usa **Opus 4.8** hoje (melhor disponível); **Fable 5** atrás de
  flag para o futuro.

### Revertido / descartado (não está no código)
- **Fase 10.7** — tratar as metades como núcleos independentes (sem travessia quando há acesso
  externo): descartada. Deixava a gleba partida em loteamentos soltos (7 componentes), o oposto do
  desejado. A 10.8 resolve juntando de verdade.
- **Recuperação por "eixo próprio"** — relotear blocos de sobra no eixo do próprio bloco: descartada.
  Ganho mínimo (+2 lotes; o `garantir_frente_via` dropava as fileiras sem frente) e quebrava testes
  de invariância de área.

### Pendências
- Recuperar a sobra restante (~15%, concentrada em poucos blocos que precisam de acesso interno
  próprio, com conservação de área garantida).
- Inteligência de subdivisão **por perfil**: alta renda = posicionar **valor** (cul-de-sac premium,
  lote grande em cota alta/fundo de mata); baixa/média = **densidade máxima** (mini-malha).
- Apresentação da base do percentual (área líquida) quando o ≥30% entra no domínio das vias.
