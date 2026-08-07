# Fase FIN-2 — Financeira avançada (ESPECIFICAÇÃO INICIAL, EM DISCUSSÃO)

> Status: rascunho para discussão com o operador (06/08/2026). Origem: análise minuciosa da
> planilha **TIV 5.0 — Técnica Inteligente de Viabilidade** (modelo profissional do setor,
> 103 abas, capítulos CP 01-11) fornecida pelo operador, comparada com nossa Financeira
> (fase 4) + Econômica (fase 5). Nada aqui está aprovado para implementação.

## 1. Posicionamento (o que copiar e o que NÃO copiar)

A TIV é ferramenta de **estruturação profunda** (pós-decisão de compra): 4 atores com matriz
de rateio, 5 instrumentos de funding, securitização, 3 regimes tributários. Nós somos
**triagem pré-viabilidade**: o objetivo da FIN-2 é fechar os gaps que hoje fazem nossa
exposição/retorno saírem otimistas ou incompletos aos olhos de quem usa a TIV — SEM virar
um Excel na web. Critério de corte: entra o que muda a DECISÃO de triagem; fica fora o que
só interessa depois da compra.

Nossos diferenciais preservados em tudo: lotes e quadro vêm do MOTOR real da gleba (não
digitados), proveniência em cada número, leituras "sob as premissas declaradas", motor
determinístico testado (a TIV depende de fórmula não travada e disciplina do usuário).

## 2. Escopo proposto (6 itens, em 2 ondas)

### Onda A — realismo do fluxo (maior impacto de credibilidade)

**FIN2-1 · Curva de vendas + 3 cenários.**
- Hoje: venda distribuída uniformemente no período declarado.
- Proposta: presets de curva ("rampa de lançamento" — forte nos 1ºs meses, cauda longa —,
  "linear", "manual" mês a mês) + três cenários nomeados (otimista/base/conservador), cada
  um com sua curva/período. Resultado: indicadores dos 3 cenários LADO A LADO (VGV igual;
  mudam exposição, payback, VPL/TIR). Referência TIV: PREMISSA D CP-03 (curvas mensais por
  cenário, seleção de cenário ativo).
- Contrato: `PremissasFinanceiraIn.cenarios[]` (nome, curva, periodo); `FinanceiraOut`
  ganha `cenarios[]` resumidos; a Econômica avalia o cenário ativo. Front: seletor +
  comparativo. Determinístico; curva soma 100% (validação com aviso, não silêncio).

**FIN2-2 · Obra no tempo (cronograma físico-financeiro).**
- Hoje: o custo de infra (RF-URB-8, paramétrico POR DISCIPLINA com BDI) entra no fluxo sem
  cronograma próprio por disciplina.
- Proposta: cada disciplina ganha mês de início + duração + curva (linear/frente carregada/
  manual) — default sensato por disciplina (ex.: terraplenagem no início, pavimentação no
  fim). O desembolso mensal da obra passa a ser a soma das curvas. Referência TIV: CP 02
  (curvas de engenharia por disciplina).
- Efeito esperado: exposição máxima de caixa mais realista (hoje tende a subestimar o pico).

**FIN2-3 · Indicadores adicionais (barato, alta percepção).**
- MTIR (taxa de reinvestimento = TMA declarada), ROE nominal e anualizado, exposição média
  mensal e tempo médio de exposição — todos já calculáveis do fluxo existente. Entram na
  EconomicaOut com proveniência e leituras "sob premissas". Referência TIV: CP 11.
- Aproveitar e expor o quadro ESTÁTICO consolidado (CP 07): VGV, custos por bloco em % do
  VGV, resultado — números que já temos, só falta a moldura "viabilidade estática".

### Onda B — capital de terceiros e régua de decisão

**FIN2-4 · Financiamento à produção + da exposição (com gatilhos).**
- Modelo TIV (CP 04.2): adesão SIM/NÃO; produção → % financiado do custo de obra, liberação
  quando % mínimo de OBRA e % mínimo de VENDAS são atingidos (o motor calcula o mês do
  gatilho a partir das curvas FIN2-1/FIN2-2), juros, prazo; exposição → cobre o vale do
  caixa com taxa própria. Saída: fluxo com e sem funding, e o efeito no VPL/TIR/exposição.
- Escopo contido: SÓ esses dois instrumentos (mútuo/crowdfunding/associativo ficam fora da
  triagem; registrar como futuro).

**FIN2-5 · Tributos por regime — EXIGE VERIFICAÇÃO LEGAL PRÉVIA.**
- A TIV modela RET, lucro presumido e lucro real. Para LOTEAMENTO a régua tributária tem
  pegadinhas (RET é regime de INCORPORAÇÃO — Lei 10.931/2004; a aplicabilidade a loteamento
  e o RET-Loteamento precisam ser verificados na fonte; presumido com bases 8%/12% é o
  usual do setor). REGRA DA CASA: nada vira produto sem base legal citada.
- Caminho: sessão de pesquisa legal dedicada (Planalto/RFB + doutrina) → spec do cálculo
  com artigos → só então implementação, com regime declarado como premissa visível.

**FIN2-6 · Score GO/NO-GO multicritério (evolução do Comparar áreas).**
- A "Definição das Métricas" da TIV valida a direção que já planejamos para a fase 2 do
  Comparar áreas: métricas com 5 FAIXAS calibráveis (ameaça −5 … oportunidade +5) e PESO
  por métrica → score de priorização entre áreas.
- Proposta: faixas/pesos default nossos (rotulados como régua de triagem, fórmula aberta,
  editáveis por perfil sem rebuild — padrão INTEL-2), aplicados às linhas do Comparar
  áreas. NUNCA "aprovado/viável": o rótulo é oportunidade/atenção/ameaça por métrica.

## 3. Fora de escopo (registrado, não construir)

- Matriz de rateio 4 atores (nosso incorporador × terrenista cobre a triagem; 3º sócio é
  estruturação).
- Securitização de recebíveis e gestão de carteira detalhada (pós-venda; hoje temos
  inadimplência % — suficiente para triagem).
- Permuta externa (unidades de outro empreendimento), empréstimo ao dono do terreno,
  mútuo/crowdfunding/associativo-MCMV, taxa TAO.
- Correção monetária/INCC no fluxo (nossa Econômica é em MOEDA CONSTANTE por decisão da
  fase 5 — misturar nominal e real é fonte clássica de erro; reavaliar só com demanda).
- SAC como tabela de venda (Price cobre o padrão do setor de lotes; registrar demanda).
- WACC/CAPM como calculadora de TMA (bonito, mas a TMA declarada é mais honesta para
  triagem; pode virar "ajuda" informativa um dia).

## 4. Perguntas abertas para o operador

1. Ordem: concorda com Onda A (FIN2-1/2/3) primeiro? É a que muda a cara da triagem.
2. FIN2-1: três cenários bastam? Nomes "otimista/base/conservador" ou outros?
3. FIN2-2: defaults de cronograma por disciplina — você tem referências de obra reais para
   calibrar (mês de início típico por disciplina), ou usamos rateio uniforme rotulado até
   colhermos dados?
4. FIN2-4: os bancos/fundos que teus contatos usam trabalham com quais gatilhos típicos
   (% obra / % vendas)? Números reais calibram os defaults.
5. FIN2-5: autoriza a sessão de pesquisa legal tributária antes de qualquer spec de cálculo?
6. Gate comercial: FIN2 inteira é feature de plano pago, ou o gratuito vê a Onda A na tela
   (sem PDF), no padrão do que já fazemos?
