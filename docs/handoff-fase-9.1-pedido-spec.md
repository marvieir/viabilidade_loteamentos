# Pedido de spec — Fase 9.1 (Urbanismo — refino de fidelidade do traçado)

> Para a sessão de especificação (claude.ai). Contexto: a **Fase 9 — Urbanismo (estudo de
> massa esquemático por IA)** foi implementada e validada conforme `docs/fase-9-urbanismo.md`.
> A fronteira do §2 está intacta: a IA propõe o **programa** (lote-alvo, densidade, %lazer,
> arquétipo viário, esqueleto); o **Python gera e mede** toda a geometria e todos os números.
> Os 10 critérios passaram (valores-ouro de São Roque batem no `/medir`), suíte 273 testes,
> regressão 1…8 zero. Esta é uma fase de **EVOLUÇÃO** (refino de fidelidade do traçado) — o
> que a própria spec da 9 listou como "fora de escopo / evolução". O MVP (parcelamento
> completo + áreas obrigatórias, medido) **já está entregue**; aqui melhoramos o **realismo do
> desenho**, sem tocar na fronteira §2 nem na linguagem §1-A. Produza
> `docs/fase-9.1-urbanismo-tracado.md` no formato das specs anteriores (a 9, a 1.8, a 4/5 são
> os melhores exemplos).

## 0. O que já existe (ponto de partida — não revota)

- **Borda (LLM):** `core/urbanismo_programa.py` — `GeradorPrograma` injetável (real
  `GeradorProgramaClaude` gated por `ANTHROPIC_API_KEY`, tool use forçado; stub offline).
  Presets de público-alvo embarcados (baixa/média/alta, monotônicos). O LLM já propõe
  `pct_lazer`, `arquetipo_viario`, `amenidades` e um `esqueleto` (polilinhas de eixos).
- **Núcleo (Python puro):** `core/urbanismo_geom.py` (grelha axial v1; recorta contra a área
  aproveitável; loteia **todas** as ilhas buildáveis) + `core/urbanismo_medida.py` (quadro de
  áreas + indicadores + heatmap, CRS métrico AEQD) + `core/urbanismo_store.py` (snapshots
  versionados).
- **Contrato:** `POST .../urbanismo/medir` (determinístico, SEM LLM — afere os ouros) ·
  `POST .../urbanismo/propor` (IA→programa→Python gera/mede; 503 sem credencial) · `GET`.
- **Front:** card "Urbanismo (IA)" renderizando o GeoJSON esquemático + quadro + heatmap.

## 1. Resultado ao vivo (São Roque/SP, 7,81 ha — condomínio de lotes, alta renda)

Área líquida **58.678,16 m²** → vendável **40.010,52 (68,2%)** · áreas verdes **1.462,25
(2,5%)** · institucional **284,26 (0,5%)** · arruamento **16.921,13 (28,8%)**; **70 lotes**,
área média 571,58 m² (testada 20,71 / profundidade 28,16). Heatmap médio 7,53. Programa
proposto pela IA: lote-alvo 600 m², densidade baixa, **lazer 25%**, viário "orgânico sinuoso",
amenidades clube/áreas verdes preservadas.

## 2. Gaps de FIDELIDADE observados (o alvo desta fase)

1. **O quadro de áreas não converge para o programa.** A IA pediu **25%** de lazer (clube
   central + áreas verdes preservadas); o motor mediu **2,5%** — a grelha v1 só reserva uma
   faixa fina de verde no topo de cada ilha. O número é honesto (mede o que a grelha fez), mas
   está longe da intenção. **Mesmo para institucional** (0,5% medido).
2. **Viário é grelha axial**, não o "orgânico sinuoso acompanhando curvas de nível" do
   programa; o **esqueleto** sugerido pela IA é **validado e descartado** (não vira traçado).
3. **A topografia não entra no traçado.** Já temos a declividade por DEM (Fase 2.5); o traçado
   ignora curvas de nível, faixas íngremes intra-aproveitável, fundos de vale.

## 3. Decisões que a spec PRECISA fixar (vetáveis)

> **Inviolável (herdado, a spec respeita e demonstra):** fronteira §2 (nenhum número nem
> coordenada FINAL de lote vem do LLM — o Python materializa e mede); §1-A (rótulo "ESTUDO DE
> MASSA ESQUEMÁTICO", avisos, "verificar com urbanista", regex sem "aprovado/viável/regular");
> determinismo por snapshot; front só renderiza GeoJSON; **não-regressão 1…9** (a 9.1 não
> reescreve dimensão anterior; `/medir` e os valores-ouro do quadro **continuam válidos**).

### 3.1 Materializar o programa de áreas (lazer/verde + institucional)
O gerador passa a **reservar de fato** o `pct_lazer` proposto como **lazer/clube central +
áreas verdes**, e a doação **institucional**, de forma que o quadro **convirja** para o
programa (com tolerância). Definir: como posicionar (clube central vs. faixas; preferir
encostar o verde em mata/APP existente para casar com o §1-A); o que fazer quando a gleba
**não comporta** o %lazer pedido — **degradar e rotular** ("lazer alvo 25% não cabe na área
aproveitável; materializado X% — verificar com urbanista"), **nunca** inflar nem inventar.

### 3.2 Viário por arquétipo + consumo do esqueleto da IA
O gerador passa a **honrar o `arquetipo_viario`** (grelha eficiente × sinuoso de fundo de
vale) e a **consumir o esqueleto** validado da IA como **eixos-base** (hoje só registra e
descarta). Cravar **onde fica a fronteira**: a IA **sugere** eixos (polilinhas); o Python
**valida, snapa à gleba, regulariza larguras e MEDE** — o que conta como "regularizar" sem o
Python virar projetista? (Recomendação: o Python nunca cria um eixo que a IA não sugeriu além
da malha-base determinística; e nunca aceita geometria crua sem validar — mantém o invariante
da 9 de "esqueleto inviável é ignorado e registrado".)

### 3.3 Topografia no traçado (reuso da 2.5)
Usar a **declividade (DEM, Fase 2.5)** para orientar quarteirões/vias como **triagem** (ex.:
vias tendendo a acompanhar curvas de nível; lotes com fundo para verde/vista; evitar cravar
fileira em faixa mais íngreme dentro do aproveitável) — **não** é projeto de terraplenagem nem
drenagem. Definir a fonte/contrato (reusar `get_fonte_dem`/`FonteDEM` da 2.5, degradável
quando o DEM não está disponível — o traçado cai no modo sem-topografia, rotulado).

### 3.4 Valores-ouro (como aferir um traçado mais "orgânico" de forma determinística)
A parte criativa (programa) é não-determinística; o teste continua medindo o **motor sobre um
snapshot fixo**. Recomendação: (a) cravar, num **caso sintético**, que o quadro de áreas
**converge para o programa** (lazer medido ≈ `pct_lazer` ±tolerância; institucional idem);
(b) que o traçado **respeita o esqueleto** (eixos sugeridos aparecem como vias, ±snap) e a
**topografia** (nenhum lote na faixa mais íngreme reservada); (c) **São Roque real** vira
validação quando a geometria do projeto chegar. Os **valores-ouro do `/medir` da Fase 9
permanecem** (não-regressão da medição pura).

## 4. Fora de escopo (registrar — não inflar a fase)

- Projeto aprovável / diretrizes da gleba (art. 6º/7º Lei 6.766) — do urbanista.
- Projetos técnicos (água, esgoto, energia, drenagem, pavimentação, terraplenagem).
- **Custos de obra** (SINAPI/SICRO) — fase de custos própria, futura.
- Edição interativa do traçado na tela / 3D / render.
- Otimização multiobjetivo (maximizar lotes/valor automaticamente).
- Pesquisa de mercado ao vivo do perfil (presets seguem embarcados).
- Preço absoluto do lote (o heatmap ordena qualidade; R$/m² é input do usuário).

> Peça à sessão de spec: produzir `docs/fase-9.1-urbanismo-tracado.md` no formato da 9/1.8/4
> (objetivo, não-regressão, como funciona — **com a fronteira §2 redesenhada para o consumo do
> esqueleto e a materialização do lazer**, contrato/schema das mudanças, critérios de aceite
> com valores-ouro, fora de escopo, arquivos esperados), cravando as decisões vetáveis (3.1
> materialização do lazer/verde/institucional, 3.2 viário por arquétipo + esqueleto, 3.3
> topografia, 3.4 valores-ouro). O resultado é um estudo de massa **mais fiel ao programa**,
> sem nunca virar projeto aprovável nem cruzar a fronteira do §2.
