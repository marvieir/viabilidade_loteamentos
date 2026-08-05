# Fase Dashboard-Portfólio — comparador de áreas do cliente (ESPECIFICAÇÃO INICIAL, EM DISCUSSÃO)

> Status: rascunho para discussão com o operador (05/08/2026). Nada aqui está aprovado
> para implementação. A numeração de fase será atribuída quando a spec fechar.

## 1. O problema e o objetivo

O cliente que analisa várias glebas hoje enxerga cada análise isolada. A decisão real dele,
porém, é comparativa: **de todas as áreas que tenho na mesa, qual compro/opciono primeiro?**
O dashboard de portfólio responde isso: um menu novo no app logado que agrega as análises
já feitas pelo cliente e as compara por indicadores — risco (ambiental, jurídico),
aproveitamento (lotes, eficiência) e retorno (VGV, margem, exposição, tempo no negativo).

É também a feature que aumenta o valor da assinatura: quanto mais glebas o cliente analisa,
mais valioso fica o portfólio dele — efeito acumulativo que o plano avulso não entrega.

## 2. Princípios (regras do projeto aplicadas a esta fase)

1. **Todo cálculo no backend.** O dashboard agrega LENDO os resultados salvos das análises
   (stores por dimensão) — não recalcula o motor e o front não soma nada.
2. **Célula vazia é célula honesta.** Dimensão não calculada naquela análise = "não
   calculado" no quadro, nunca zero, nunca estimativa.
3. **Comparabilidade declarada.** TIR/VPL de análises com premissas diferentes (TMA, preço
   do m², prazos) NÃO são comparáveis em silêncio: o quadro mostra as premissas de cada
   linha e avisa quando divergem. Indicadores normalizados (por hectare, por lote) reduzem
   o problema, mas não o eliminam.
4. **Proveniência:** cada indicador aponta a análise/dimensão de origem e a data de
   referência do cálculo.
5. **Score composto só com fórmula declarada e determinística** — e rotulado como régua
   NOSSA (leitura de triagem), nunca como veredito.

## 3. Pesquisa de mercado — o que loteadoras e incorporadoras usam (05/08/2026)

Fontes: materiais técnicos do setor brasileiro de loteamento/incorporação (Portal VGV —
KPIs de incorporação e gestão de landbank; cursos de viabilidade de loteamentos
Sinduscon-MG; Inco/panorama de loteamentos; GRI Institute — indicadores EDLP 2026;
softwares de viabilidade LotePRO, Lotelytics, OfertaTerreno, Gestinc; artigo acadêmico de
viabilidade de loteamento — MIX Sustentável/UFSC) e prática internacional de land
development (Adventures in CRE — residential land development model; REProforma — land
development proforma; LandTech — residual land value; Tactica RES — IRR em development).

Consenso do mercado, agrupado:

**a) Econômicos (retorno sobre capital, fim do ciclo):**
- VGV (Valor Geral de Vendas) — o tamanho do negócio; usado também normalizado (VGV/ha).
- Margem líquida sobre VGV; lucro nominal.
- VPL (à TMA declarada) — filtro de viabilidade econômica; sensível a preço/velocidade.
- TIR (anualizada) — retorno equivalente; sempre lida JUNTO com VPL/payback/exposição.
- Múltiplo de capital (equity multiple): lucro ÷ capital máximo empregado.

**b) Financeiros (comportamento do caixa no tempo):**
- Exposição máxima de caixa ("peak equity"): quanto o empreendedor põe antes de o projeto
  se autofinanciar — o mercado trata como O indicador de risco financeiro de loteamento.
- Tempo de caixa negativo (meses até o fluxo acumulado virar positivo) e payback
  simples/descontado.
- Curva de recebíveis e inadimplência (operacional, pós-lançamento).

**c) Urbanísticos/fundiários ("lot yield"):**
- Nº de lotes e lotes por hectare bruto (rendimento fundiário).
- Eficiência de parcelamento: % de área vendável (benchmark de mercado: ~55-65% da área
  líquida em loteamento aberto; o quadro do nosso motor já mede isso por gleba).
- % de viário (proxy do maior custo de urbanização) e custo de urbanização por lote/por m²
  vendável — pressionado por exigências ambientais crescentes (GRI/EDLP).
- Área média e mix de lotes (aderência ao público-alvo).

**d) Mercado/comercial (exigem dado que NÃO temos hoje):**
- VSO / velocidade de vendas / absorption rate (lotes/mês) — muda a economia do projeto
  inteiro (5→3,5 lotes/mês ≈ +5 meses de juros e overhead, ex. internacional).
- Preço de mercado do lote na região (comparáveis).

**e) Negociação da terra:**
- Valor residual da terra (residual land value): receita total − custos − retorno-alvo =
  máximo pagável pela gleba. É o número que fecha a conversa com o terrenista.
- % do VGV do terrenista na permuta (física, financeira ou híbrida) — nosso motor já
  modela os três modos.
- Prazo/risco de aprovação (planning risk) como desconto sobre o residual.

**f) Portfólio/landbank:**
- Priorização multicritério das áreas (retorno × risco × prazo), ranking do pipeline,
  monitoramento constante — é literalmente o dashboard que esta fase propõe.

## 4. Catálogo de KPIs proposto

Camada **A — já sai das análises existentes** (custo zero de motor; só agregar):

| # | KPI | Dimensão de origem |
|---|---|---|
| A1 | Nº de lotes | urbanismo |
| A2 | Área média e mix de lotes | urbanismo |
| A3 | Eficiência: % vendável sobre área líquida | urbanismo (quadro) |
| A4 | % viário | urbanismo (quadro) |
| A5 | Sobra geométrica % | urbanismo (quadro) |
| A6 | % verde total / doação | urbanismo (quadro) |
| A7 | % restrito da gleba bruta (mata/APP/≥30%) | ambiental+declividade |
| A8 | Alertas por severidade (crítico/atenção) | ambiental |
| A9 | % verde "a verificar" (upside desbloqueável) | área verde |
| A10 | Semáforo jurídico | jurídica |
| A11 | Divergência matrícula × KMZ (%) | jurídica |
| A12 | VGV total (e do próprio × terrenista, com % permuta) | financeira |
| A13 | Margem sobre VGV próprio | financeira |
| A14 | Exposição máxima de caixa (nominal e descontada) + mês | financeira/econômica |
| A15 | VPL (à TMA declarada) | econômica |
| A16 | TIR | econômica |
| A17 | Payback simples e descontado | econômica |
| A18 | Custo de infraestrutura estimado | custo_infra |

Camada **B — deriváveis no backend** (cálculo novo, dados existentes):

| # | KPI | Derivação |
|---|---|---|
| B1 | VGV por hectare bruto | A12 ÷ área bruta |
| B2 | Lotes por hectare bruto | A1 ÷ área bruta |
| B3 | Meses de caixa negativo | fluxo acumulado da financeira: 1º mês ≥ 0 |
| B4 | Lucro nominal (R$) | margem × VGV próprio |
| B5 | Múltiplo de capital | lucro ÷ exposição máxima |
| B6 | Receita média por lote | VGV ÷ nº lotes |
| B7 | m² de viário por lote (proxy custo infra/lote) | área viário ÷ nº lotes |
| B8 | Custo de infra por lote e por m² vendável | A18 ÷ A1 / ÷ área vendável |
| B9 | VPL por hectare | A15 ÷ área bruta |
| B10 | Score de risco por dimensão (0-100, fórmula declarada) | composição determinística de A7-A11 |

Camada **C — futuro, exige dado novo** (registrar, NÃO construir agora):

- C1 Valor residual da terra a TIR-alvo (nova conta sobre o fluxo; candidata forte à fase 2
  — é o número da negociação com o terrenista).
- C2 VSO/velocidade de vendas real e comparáveis de preço de lote na região (dado de
  mercado que não coletamos; entraria como premissa informada + rótulo).
- C3 Prazo de aprovação por município (histórico próprio ao longo do tempo).
- C4 Inadimplência/curva de recebíveis (operacional pós-venda; fora da triagem).

## 5. O dashboard — estágio inicial (MVP da fase)

**Onde:** menu novo no app logado (ex.: "Portfólio"), por usuário — cada cliente vê só as
análises DELE. Não aparece no site público.

**Backend:** `GET /api/portfolio/indicadores` — uma linha por análise salva do usuário:
identificação (título, município/UF, data, tipo), KPIs das camadas A+B calculados no
backend, premissas relevantes (TMA, preço m², modo de permuta) e cobertura (quais dimensões
foram rodadas). Router novo isolado (`portfolio.py`), auth de cliente comum.

**Front (uma tela):**
1. **Cards de destaque** (só entre análises com a dimensão calculada): maior VGV · maior
   VGV/ha · menor exposição máxima · vira positivo mais cedo · mais lotes · menor risco
   ambiental · menor risco jurídico.
2. **Tabela comparativa** ordenável por qualquer coluna, com célula vazia honesta e
   premissas visíveis; aviso quando premissas divergem entre linhas.
3. **Radar por análise** (risco ambiental × jurídico × urbanístico × financeiro) — usa B10.
4. Filtros: município/UF, tipo de loteamento, período.

**Fora do MVP (fase 2 em diante):** score composto com pesos configuráveis pelo cliente,
comparação lado a lado (2-3 áreas em detalhe), valor residual da terra (C1), exportação
PDF/Excel do comparativo, KPIs de mercado (C2).

## 6. Decisões do operador (05/08/2026)

1. **Nome: "AI Portfolio Insights"** — menu no app logado. ✔
2. **Recorte do MVP aprovado** (cards de destaque + tabela comparativa + radar). ✔
3. Colunas da tabela v1 (proposta apresentada em mockup, aguardando ajuste fino do
   operador): Área · ha bruto · Lotes · VGV · VGV/ha · Margem · TIR · Exposição máx. ·
   Meses negativo · Ambiental · Jurídico. Demais KPIs no detalhe da linha.
4. Valor residual da terra (C1): conceito explicado ao operador; decisão de prioridade
   pendente.
5. **Gate comercial: 30 dias de prévia para o plano gratuito**, com CONTADOR visível dos
   dias restantes; depois bloqueia (tela de bloqueio mantém as análises e oferece os
   planos). Planos pagos: acesso pleno. Detalhe a fechar na implementação: o prazo conta
   a partir do primeiro ACESSO ao painel (persistido no backend), não da criação da conta.
6. Score de risco (radar/B10): mockup apresenta com "fórmula aberta"; decisão final
   pendente.

**Mockups aprovação:** imagens em `docs/mockups/` — `mockup-1-painel.png` (painel free com contador) e
`mockup-2-bloqueio.png` (bloqueio pós-30 dias), APROVADAS pelo operador em 05/08; fontes HTML no mesmo diretório para iterar
(dados fictícios, sem código). Iteração de layout acontece sobre elas antes de qualquer
implementação.
