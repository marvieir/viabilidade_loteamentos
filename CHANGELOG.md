# Changelog

Registro das mudanças relevantes do estudo de massa / urbanismo. Mais recente no topo.
Convenção: cada entrada traz o **problema**, a **correção** e o **efeito medido** (pipeline real
São Roque, salvo nota). A régua continua sendo a dos `CLAUDE.md`/`ARCHITECTURE.md`: cálculo só no
backend, determinismo, proveniência, e valores-ouro por fase passando.

## [não publicado] — 2026-06-21

### Fase 11.11 — validação de tamanho de lote na interface (o app corrige o usuário)
- **Princípio (operador):** o cliente pode errar ao sugerir tamanhos; o papel da app é corrigi-lo —
  (a) corrigir sozinha o que é seguro (já feito no 11.10: janela mínima no default), (b) AVISAR
  quando o usuário força algo ruim (sem bloquear).
- **Correção:** no campo "Lote máx.", quando o valor está perto demais do piso legal da zona (janela
  apertada → sobra), a interface mostra um aviso na hora com o tamanho recomendado (≥ 1,5× piso) ou
  sugere deixar vazio (padrão seguro). Frontend-only; usa o piso que o estudo já devolve.
- Pendente (próximo): alerta de VOCAÇÃO do terreno (topografia/localização → perfil sugerido).

### Fase 11.10 — folga mínima de janela de lote (mata a sobra da baixa renda)
- **Causa raiz:** quando a ZONA força o piso acima do teto de mercado (baixa renda em zona de mín.
  360 vs mercado 250), `[piso, teto]` COLAPSA para ≈ [360, 360] — quase nenhuma faixa cabe num lote
  de área exata → **sobra de 40-49%** (um retângulo limpo de 2.974 m² dava 1 lote só).
- **Correção:** sem `lote_max` do operador, garante `teto ≥ 1,5× piso` de janela p/ a subdivisão
  respirar (operador que fixa `lote_max` assume o aperto).
- **Efeito (baixa, São Roque):** vendável **11% → 38,1%**, lotes **21 → 58**, sobra **40% → 13,4%**.
  Suíte verde.

### Fase 11.8 — campo "lote máx." no menu (#1) + feedback do "Analisar tudo" (#3)
- **#1 — teto de lote pelo operador:** novo campo "Lote máx. (m²)" no menu de urbanismo (4º, ao lado
  de tipo/público/zona). Sobrepõe o teto de MERCADO do perfil (`resolver_diretrizes(..., lote_max_m2)`),
  nunca abaixo do piso legal. Vazio = padrão do perfil. Permite controlar o tamanho máximo de lote por
  estudo sem mexer no código (a generalização do 11.7).
- **#3 — "Analisar tudo" com progresso:** o botão não dava feedback (a prop `analisando` nem era
  passada → parecia que nada acontecia). Agora: botão vira "Analisando…", e cada item do menu lateral
  ganha um ponto âmbar pulsando (analisando) → verde (concluído). Implementado reaproveitando o
  `onData` que cada card já dispara ao concluir (sem editar os cards); timeout de segurança limpa
  estados presos. Suíte backend verde, tsc limpo.

### Fase 11.7 — teto de lote premium (alta renda): +area loteavel, -sobra
- **Descoberta (cobrança do operador):** o teto de 640 m² NÃO é legal (a LUOS São Roque/MUE só fixa
  o PISO de 360 m²; não há teto na diretriz). O 640 era a `faixa` de **referência de MERCADO** do
  perfil 'alta' no código (`PERFIL_LOTE`), uma convenção — não a prefeitura.
- **Correção:** teto de mercado do perfil **alta** 640 → **1.000 m²** (premium). Os lotes maiores
  ABSORVEM o fundo de quadra que virava sobra. Baixa/média mantêm tetos baixos (densidade).
- **Efeito (fixture real):** vendável **34,0% → 41,9%**, sobra **11,6% → 3,9%**, nº de lotes
  praticamente igual (46→45, lotes maiores em vez de sobra), área média 524 → 661 m². Suíte verde.

### Fase 11.6 — corrige `temperature` (quebrava a IA) + 3 verdes distintos no mapa
- **Bug crítico (regressão da 11.5):** `temperature=0.0` causava **400 "temperature is deprecated for
  this model"** (Opus 4.8/Fable 5) → a chamada à IA falhava e caía sempre no preset. Removido o
  parâmetro; a consistência fica com o CAP de lazer/largura (motor é dono da medida) + a regra 5 da
  instrução. A IA volta a propor de fato.
- **Cores (operador):** as áreas verde reservada / verde remanescente / bosque preservado usavam
  tons quase iguais (confundia). Agora 3 cores DISTINTAS: park = verde médio sólido (#22c55e);
  remanescente = lima claro amarelado (#bef264); bosque = floresta bem escuro (#14532d).

### Fase 11.5 — CONSISTÊNCIA: domar a variância da IA (mesma gleba → mesmo resultado)
- **Problema:** regenerar a mesma gleba dava resultados muito diferentes (51 lotes numa rodada, 36
  noutra) e o operador achava que o motor piorava a cada clique. Causa: a chamada ao LLM usava
  `temperature` default (**1.0 = máxima aleatoriedade**) → a IA sorteava lazer/esqueleto diferentes
  toda vez. O motor é determinístico; a borda da IA não era.
- **Correções:** (1) `temperature=0.0` na chamada ao LLM → mesma gleba propõe ~o mesmo programa
  sempre. (2) CAP de lazer no caminho do LLM: a IA pode REDUZIR o lazer (mais lote) mas não exceder
  o padrão do perfil (alta 20%, média 12%, baixa 5%) — não toca override EXPLÍCITO do usuário.
  (3) Regra 5 no `_INSTRUCAO`: consistência + qualidade (use valores-padrão do perfil, esqueleto
  limpo, prefira bons lotes a desenho rebuscado).
- **Efeito:** o resultado para de "pular" entre regenerações; o nº de lotes fica estável (~46) em vez
  de depender de sorte. Suíte verde.

### Fase 11.4 (revertida) — vias locais curvas p/ alta renda: funcionou no São Roque mas crashava em
  glebas sintéticas + conflitava com 2 valores-ouro (grade orientada, convergência lazer). Estética
  pura (não adiciona lote); fica para um esforço dedicado.

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
