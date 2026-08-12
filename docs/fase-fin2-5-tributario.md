# Fase FIN2-5 — Comparador tributário do loteamento (IMPLEMENTADA 11/08/2026)

> **Decisões do operador (11/08):** (1) escopo v1 APROVADO; (2) comparador como painel
> ADICIONAL, mantendo o passo Tributos atual; (3) recurso de PLANO PAGO — bloqueado,
> mostra apenas o item bloqueado (com convite aos planos).
> **Notas de implementação:** a "carga atual" do cenário A é o próprio campo
> `aliquota_pct` do passo Tributos (fonte única; default 5,93% rotulado preservado —
> compat total; 6,73% é o típico COM adicional de IRPJ, o usuário declara). O campo
> `regime` do contrato virou `cenario_fluxo` ("atual" | "ibs_cbs") para não colidir com
> o `regime` fiscal já existente. Correção IPCA = campo `correcao_acumulada_pct`
> declarável (determinismo). Código: `core/tributario.py`, gate `FIN25_GATE_DIR`,
> testes `test_tributario.py` (valores-ouro fechados à mão no docstring).

> Base: `docs/pesquisa-legal-tributaria.md` (10/08/2026, fontes primárias + doutrina).
> Janela de mercado validada pelo relatório Lotenet (caso #5, score 4.15): "o loteador
> precisa recalcular viabilidades agora e não há ferramenta". Mockup:
> `docs/mockups/mockup-fin25-tributario.png`.

## 1. O que entra (escopo v1)

Um **comparador de regimes** dentro da Financeira (nova sub-seção do passo Tributos), com
premissas declaradas e conta POR LOTE:

1. **Regime atual / transição (art. 486 LC 214/2025):** carga % sobre receita bruta —
   default 6,73% (presumido típico: IRPJ 8%×15% + adicional + CSLL 12%×9% + PIS/COFINS
   3,65%), editável; rotulado "válido para loteamento com REGISTRO PROTOCOLADO até
   31/12/2028 que optar pela transição (CBS 3,65% definitiva; IBS na transição — ver
   pendência de regulamentação)".
2. **Regime novo (IBS/CBS, regime específico de imóveis):** por lote —
   `base = preço_lote − redutor_ajuste_lote − redutor_social` onde:
   - `redutor_ajuste_lote` = rateio por lote de (valor de aquisição do terreno + ITBI +
     contrapartidas urbanísticas/ambientais), corrigidos por IPCA (premissas: campos que a
     Financeira já tem — aquisição — + 2 campos novos: ITBI/laudêmio e contrapartidas);
     rateio proporcional à área vendável (rotulado; leitura fina do rateio é pendência);
   - `redutor_social` = R$ 30.000/lote residencial (art. 259; IPCA; 1ª alienação; nunca
     negativa a base);
   - `alíquota = alíquota_padrão_referência × 50%` (campo premissa, default 28% rotulado
     "referência — regulamentação em evolução").
3. **Saída:** carga total e por lote nos dois cenários; diferença em R$ e p.p.; breakeven
   (preço de lote em que os regimes se igualam); alerta de decisão: "registro até
   31/12/2028 preserva a opção da transição — [art. 486]".
4. **RET:** NÃO calculado (elegibilidade é jurídica — lote vinculado a construção +
   afetação); vira NOTA informativa quando tipo=condomínio de lotes ("possível RET 4% —
   verificar elegibilidade com tributarista; Lei 14.382/2022").

## 2. Regras da casa aplicadas
- Cálculo determinístico no backend (novo `core/tributario.py`); front renderiza.
- Proveniência POR LINHA (artigo da LC 214 em cada componente); leituras "sob as premissas
  declaradas"; ressalva fixa "não é parecer tributário — validar com contador/tributarista".
- Nenhuma alíquota municipal inventada: ITBI/contrapartidas são premissas declaradas.
- Integra a Econômica: o cenário tributário escolhido alimenta o fluxo (linha de tributos),
  como a aliquota_pct de hoje — compatibilidade total (default = comportamento atual).

## 3. Contrato (esboço)
- `PremissasFinanceiraIn.tributos` ganha: `regime` ("atual_transicao" | "ibs_cbs"),
  `itbi_laudemio_r$`, `contrapartidas_r$`, `aliquota_padrao_ref_pct` (default 28),
  `lotes_residenciais` (default: todos).
- `FinanceiraOut` ganha `comparativo_tributario`: por regime {carga_total, carga_por_lote,
  pct_efetivo_vgv, componentes[] com base_legal}, breakeven, avisos.
- Testes-ouro: lote popular (R$ 100k — redutor social corta ~30% da base) × alto padrão
  (R$ 400k), breakeven, base nunca negativa, IPCA como premissa fixa de referência
  (determinismo: sem consulta de índice ao vivo — campo "correção acumulada %" declarável).

## 4. Fora da v1
Créditos de insumos no regime regular, split payment, permuta/SPE, cálculo RET, IBS
municipal/estadual detalhado na janela 2029-2032 (pendência de regulamentação — rotulado).

## 5. Perguntas ao operador
1. Aprova o escopo v1 (comparador 2 regimes + breakeven + alerta 2028)?
2. Tributos hoje é % única sobre receita — manter esse campo como "cenário atual" e o
   comparador como painel adicional (recomendado), ou substituir o passo Tributos?
3. Feature de plano pago (padrão da casa) ou aberta no gratuito como isca?
