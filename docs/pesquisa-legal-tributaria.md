# Pesquisa legal — tributação do loteamento (FIN2-5)

> Sessão autorizada pelo operador em 10/08/2026 (sequência pós-relatório Lotenet — a Reforma
> Tributária foi apontada pelo mercado como janela de urgência: "o loteador precisa recalcular
> viabilidades agora e não há ferramenta"). Fontes: LC 214/2025, Lei 10.931/2004, Lei
> 14.382/2022, IN RFB 2179/2024, doutrina tributária especializada (Conjur, Tozzini, Mariz de
> Oliveira, notas técnicas CNM/Sinduscon). **Status: 1ª rodada — números e artigos abaixo
> verificados por múltiplas fontes secundárias; leitura fina do texto legal antes de
> implementar (pendências no §5).**

## 1. Regime ATUAL do loteamento (o baseline que a Financeira modela hoje)

- **Lucro presumido** (o padrão do setor): base presumida de **8% (IRPJ)** e **12% (CSLL)**
  sobre a receita bruta da venda de lotes (estoque imobiliário) → IRPJ 15% × 8% = 1,2% +
  adicional 10% sobre o que excede R$ 60 mil/trimestre de base + CSLL 9% × 12% = 1,08% +
  **PIS/COFINS cumulativo 3,65%** → carga total típica **≈ 5,93% a 6,73% da receita bruta**
  (o "6,73%" citado no relatório Lotenet).
- **RET 4%** (Lei 10.931/2004): regime da INCORPORAÇÃO com patrimônio de afetação. Desde a
  **Lei 14.382/2022** (+ IN RFB 2.179/2024), a alienação de lotes de loteamento PODE
  caracterizar incorporação e aderir ao RET **se** vinculada à construção de casas
  isoladas/geminadas pelo empreendedor **e** com patrimônio de afetação registrado na
  matrícula; **condomínio de lotes** foi equiparado a condomínio edilício (RET acessível).
  Loteamento puro (venda de lote sem construção) segue FORA do RET.
- IRPJ/CSLL **não mudam com a Reforma** (ela reestrutura o consumo); o presumido continua
  como régua de renda.

## 2. Reforma Tributária (EC 132/2023 + LC 214/2025) — o que muda para o loteador

### 2.1 Regime específico de bens imóveis
- IBS/CBS incidem sobre alienação de imóveis por contribuinte do regime regular, com
  **redução de 50% da alíquota padrão** na alienação (locação: redução de 70%).
- Alíquota padrão de referência estimada em ~26,5-28% → **alíquota efetiva de alienação
  ~13-14%, sobre base REDUZIDA pelos redutores** (abaixo) — não comparável diretamente aos
  6,73% atuais sem simular os redutores.

### 2.2 Redutor de AJUSTE (arts. 257-258)
- Valor vinculado a cada imóvel que ABATE a base de cálculo na alienação: valor de
  aquisição/referência do imóvel (terreno) + **ITBI e laudêmio pagos na aquisição** +
  **contrapartidas urbanísticas e AMBIENTAIS pagas ao poder público** para viabilizar o
  empreendimento — tudo **corrigido pelo IPCA** desde o pagamento (art. 258, §6º).
- Racional: evitar bitributação de quem adquiriu no regime antigo. Para o loteamento, é o
  mecanismo que reconhece terreno + contrapartidas no cálculo POR LOTE (o "redutor
  proporcional por lote" citado no relatório; atenção do mercado ao risco de dupla contagem
  em doações de área pública).

### 2.3 Redutor SOCIAL (art. 259)
- **R$ 30.000 por LOTE residencial** (expressamente: unidade resultante de parcelamento da
  **Lei 6.766/79** ou condomínio de lotes) e R$ 100.000 por imóvel residencial novo —
  abatidos da base **após** o redutor de ajuste, **uma única vez por imóvel** (1ª alienação),
  atualizados pelo IPCA, sem gerar base negativa.
- Efeito prático: em lote popular (ex.: R$ 90-120 mil), o redutor social corta 25-33% da
  base — a alíquota EFETIVA por lote despenca; em lote de alto padrão o efeito relativo é
  menor. **A conta é por lote — exatamente o que a plataforma sabe fazer.**

### 2.4 Regime de TRANSIÇÃO do loteamento (art. 486)
- Loteamento com **registro protocolado até 31/12/2028**: opção por recolher **CBS a 3,65%
  sobre a receita bruta, em caráter definitivo**, SEM apropriação de créditos e sem os
  redutores — replicando a lógica cumulativa atual. (Incorporação no RET, art. 485: CBS
  2,08%, ou 0,53% interesse social.)
- É a decisão estratégica central do loteador em 2026-2028: **registrar até 2028 e travar o
  regime antigo × cair no regime novo com redutores** — depende do mix de lotes, do valor do
  terreno/contrapartidas e do perfil (popular × alto padrão). NÃO tem resposta única: é
  simulação caso a caso — o produto.

### 2.5 Cronograma
- **2026**: ano-teste (CBS 0,9% + IBS 0,1%, compensáveis com PIS/COFINS);
- **2027**: CBS plena substitui PIS/COFINS;
- **2029-2032**: transição gradual do IBS (substituindo ISS/ICMS);
- **2033**: regime pleno. IRPJ/CSLL inalterados ao longo de todo o período.

## 3. O que isso significa para o produto (esboço do FIN2-5)

A Financeira ganha um **comparador tributário por regime**, com premissa declarada e
proveniência por artigo:

1. **Cenário presumido/atual**: 6,73% sobre receita (comportamento de hoje, já parametrizado
   na aba Tributos) — válido na prática até 2026 e, via art. 486, congelável para
   loteamentos registrados até 2028 (CBS 3,65% + observação sobre o IBS na transição).
2. **Cenário regime novo (IBS/CBS)**: por lote — base = preço − redutor de ajuste
   proporcional (terreno + ITBI + contrapartidas, IPCA) − redutor social (R$ 30 mil, lote
   residencial, 1ª alienação); alíquota = padrão × 50%. A plataforma tem n_lotes, preço por
   lote e o custo do terreno (aquisição) — insumos completos.
3. **Saída**: carga total e POR LOTE em cada cenário, breakeven ("a partir de qual preço de
   lote o regime novo fica pior?"), e o alerta de decisão: "registrar até 31/12/2028 trava a
   opção do art. 486".
4. Rotulagem inegociável: leituras "sob as premissas declaradas", artigo citado por linha,
   ressalva "não é parecer tributário — validar com contador/tributarista".

## 4. Fora de escopo do FIN2-5
Créditos de IBS/CBS de insumos de obra (regime regular pleno), split payment, ITBI municipal
(alíquotas variam — campo declarável), permuta/SPE (estruturas — FIN2-4/consultoria), RET
passo a passo (elegibilidade é jurídica; a plataforma informa a condição e rotula).

## 5. Pendências de leitura fina (antes da implementação)
- Texto integral dos arts. 254-260 (regime específico) e 485-486 (transição) da LC 214/2025 —
  em especial: como o IBS se comporta para quem optou pelo art. 486 na janela 2029-2032;
  base exata do redutor de ajuste para LOTE (rateio por m² vendável? por lote?); regras de
  atualização e da 1ª alienação no redutor social.
- Regulamentação infralegal pendente (atos do Comitê Gestor do IBS/RFB) — marcar
  proveniência "conforme LC 214/2025, regulamentação em evolução" nos resultados.
- Alíquota padrão de referência (26,5%? 28%?) — usar campo premissa com default rotulado.

## 6. Fontes (verificadas em 10/08/2026)
- LC 214/2025, arts. 257-259 (redutores) e 485-486 (transição) — via normas.leg.br e doutrina.
- Lei 10.931/2004 (RET); Lei 14.382/2022 + IN RFB 2.179/2024 (RET para lotes/condomínio de lotes).
- Conjur — "CBS/IBS nas operações com bens imóveis" (21/07/2025); "O que muda no RET" (16/07/2025).
- Tozzini Freire — "IBS e CBS nas atividades imobiliárias LC 214/2025"; Nota Técnica CNM
  "Bens imóveis à luz da LC 214/2025"; Mariz de Oliveira — "Regime específico: redutor de ajuste".
- Regime atual: Contábeis — "Tributação da atividade de loteamento"; Turivius — "Venda de
  imóveis no lucro presumido".
