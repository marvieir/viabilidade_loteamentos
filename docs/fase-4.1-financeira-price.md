# Fase 4.1 — Financeira: venda financiada (PRICE) + fluxo de recebimento + correções de UX

> **Corretiva e ampliadora da Fase 4**, motivada por dois achados do teste real:
> (1) o campo `inadimplência=1` zerou todas as receitas sem nenhum aviso (falha de UX/validação
> da spec 4); (2) a planilha **TIV 5.0** (caso real São Roque, 3 matrículas) provou que o
> modelo "à vista / parcelado sem juros" não representa loteamento: a venda real é
> **financiada direto ao comprador em 12–120+ meses com tabela PRICE**, e a **receita
> financeira é ~1/3 do VGV geral** (TIV: nominal R$ 105,7M + juros R$ 35,9M = R$ 141,6M).
> Referencia o `ARCHITECTURE.md` (§1-A, §2) e a spec da Fase 4. **Sem LLM, sem rede.**

## 1. Objetivo

1. **Corrigir as armadilhas de UX/validação** da Fase 4 (a história do −R$ 19M).
2. Introduzir o **modo de venda FINANCIADO**: mesa de vendas com perfis (à vista / N meses com
   taxa), entrada %, **tabela PRICE**, separando **fluxo de vendas** (quando vende) de
   **fluxo de recebimento** (quando o caixa entra) e **VGV nominal** de **receita financeira**.

## 2. O que NÃO muda (não-regressão)

- O Caso Fechado A da Fase 4 (à vista) continua valendo **byte a byte** — o modo financiado é
  **aditivo** (novo `modo: "financiado"`), não substitui à vista/parcelado-sem-juros.
- Fronteira 4×5 intacta: **sem VPL/TIR/payback** (a TIV aba CP 11 vira o gabarito da Fase 5).
- Sem LLM, sem I/O externo. Suítes 1…4 verdes.

## 3. Correções de UX/validação (obrigatórias — a lição do −19M)

1. **`inadimplencia_pct` default 0**, e o formulário deixa de aceitar "1" silenciosamente:
   - valor > 0,30 → **422** com mensagem: *"inadimplência de N% zeraria/derrubaria as
     receitas — confirme explicitamente"* + flag `confirmar_inadimplencia_alta: true` para
     prosseguir (o usuário pode, mas conscientemente).
   - Rótulo do campo muda para **"Inadimplência (%) — 0 = ninguém deixa de pagar"**.
2. **Guard de sanidade do fluxo:** se há vendas configuradas e `Σ entradas == 0` → resposta
   inclui `alerta_critico: "TODAS as entradas são zero — verifique inadimplência/preço/curva"`
   e o front exibe em destaque (vermelho). Nunca entregar um fluxo morto em silêncio.
3. **Escalas distintas nos rótulos:** eficiência exibida como % ("100% = sem perda");
   inadimplência como % ("0% = sem perda"). Acaba o par traiçoeiro `(0–1)` vs `(0–1)`.
4. **Comissão sob inadimplência:** comissão passa a incidir sobre **recebimento** quando
   `modo=financiado` (corretor de loteamento recebe conforme a carteira paga — padrão da
   TIV/mercado) e sobre a venda quando à vista. Parâmetro `comissao_base:
   "recebimento"|"venda"` (default por modo), rotulado.

## 4. Modo FINANCIADO — mesa de vendas (estrutura da TIV, simplificada com honestidade)

### 4.1 Premissas novas
```jsonc
"vendas": {
  "inicio_mes": 18, "duracao_meses": 60, "curva": "linear" | [..],
  "modo": "financiado",
  "entrada_pct": 0.15,                  // no mês da venda (pode ser parcelada: "entrada_parcelas": 1)
  "mesa": [                              // perfis de financiamento (soma participacao = 1, validada)
    { "participacao": 0.05, "prazo_meses": 12,  "taxa_am": 0.0 },
    { "participacao": 0.20, "prazo_meses": 30,  "taxa_am": 0.005 },
    { "participacao": 0.40, "prazo_meses": 60,  "taxa_am": 0.01 },
    { "participacao": 0.35, "prazo_meses": 120, "taxa_am": 0.01 }
  ]                                      // tipo: PRICE (SAC = evolução, vetável)
}
```
Defaults da mesa **rotulados** como *"estrutura típica de mesa de loteamento (referência TIV
5.0) — calibre com sua corretora"*.

### 4.2 Motor (determinístico — `core/financeira.py`)
Para cada **safra** de venda (mês `v`, `q` lotes), distribuída pela mesa:
```
entrada(v)        = q × preço × entrada_pct                       (mês v)
saldo             = preço × (1 − entrada_pct)
para cada perfil p: pmt_p = saldo_p × i_p / (1 − (1+i_p)^−n_p)    (PRICE; i=0 → saldo_p/n_p)
recebimento(m)    = Σ entradas das vendas de m + Σ pmt das safras ativas em m
```
- **`fluxo_vendas[m]`** (valor nominal vendido no mês — informativo) **≠**
  **`fluxo[m].entradas`** (caixa recebido — o que compõe o fluxo).
- **Receita financeira** = Σ recebimentos − VGV nominal, exposta separada (não infla o VGV
  nominal). Permuta `pct_vgv` incide pro-rata sobre **cada recebimento** (como na 4);
  permuta em lotes inalterada. Inadimplência (se > 0) reduz cada recebimento.
- Tributo incide sobre **receita própria recebida** (regime de caixa — inalterado; juros
  tributados junto, com a ressalva de contador).
- Horizonte passa a ser `último mês com recebimento` (ex.: venda no mês 70 com 120x → mês
  190). **Resposta inclui `fluxo_resumo` agregado por ano** além do mensal (o front não vai
  renderizar 190 linhas por padrão; tabela mensal sob expand).

### 4.3 Saída — campos novos em `FinanceiraOut`
```jsonc
"vgv": { "nominal": 10000000, "receita_financeira": 2844668.32, "geral": 12844668.32, ... },
"fluxo_vendas": [ { "mes": 1, "lotes": 10, "valor_nominal": 1000000 }, ... ],
"fluxo": [ ... ],            // entradas agora = recebimento de caixa
"fluxo_resumo_anual": [ { "ano": 1, "entradas": ..., "saidas": ..., "liquido": ..., "acumulado": ... } ],
"avisos": [ ..., "Receita financeira = juros do financiamento direto; tributação sobre juros: confirme com contador." ]
```

## 5. Critérios de aceite (testáveis)

1. **PRICE-ouro unitário:** lote 100.000, entrada 15%, saldo 85.000 em 60× a 1% a.m. →
   `pmt = 1.890,78` (±0,01); 60 parcelas = 113.446,68; **receita financeira do lote =
   28.446,68**; recebimento total do lote = 128.446,68.
2. **Caso Fechado B (agregado):** 100 lotes × 100.000, vendas 10/mês meses 1–10, financiado
   100% num único perfil (60×, 1% a.m., entrada 15%): VGV nominal = 10.000.000; **receita
   financeira = 2.844.668,32** (±0,10); recebimento mês 30 (regime pleno, 10 safras ativas)
   = **189.077,81 de parcelas** + 0 de entradas; última parcela no mês 70; `Σ fluxo.entradas
   = 12.844.668,32` (com permuta 0, inadimplência 0).
3. **Taxa 0 degrada para linear:** perfil com `taxa_am=0` → pmt = saldo/n (sem juros); o modo
   `parcelado` da Fase 4 produz números idênticos ao financiado com taxa 0 e 1 perfil
   (equivalência testada).
4. **Mesa validada:** participações que não somam 1 (±0,001) → 422 diagnóstico; prazo 0 ou
   negativo → 422.
5. **Fluxo de vendas ≠ recebimento:** `fluxo_vendas` soma = VGV nominal; `fluxo.entradas`
   soma = VGV nominal + receita financeira − inadimplência − permuta (consistência ±1 centavo).
6. **Inadimplência segura:** default 0; `0.5` sem flag de confirmação → 422 com a mensagem;
   com `confirmar_inadimplencia_alta: true` → roda e o fluxo carrega o alerta. **Entradas
   totais 0 com vendas configuradas → `alerta_critico` presente** (o caso do print).
7. **Comissão sobre recebimento (financiado):** comissão mensal = % × recebimento bruto do
   mês (testado no Caso B); à vista permanece sobre a venda (Caso A inalterado).
8. **Não-regressão:** Caso Fechado A (Fase 4) byte a byte; suítes 1…4 verdes; nenhum
   VPL/TIR/payback na resposta.
9. **Determinismo + `_fmt` pt-BR no backend** (inalterado); `fluxo_resumo_anual` consistente
   com o mensal (soma bate).
10. **Rótulos de proveniência:** defaults da mesa citam "referência TIV 5.0 — calibre com sua
    corretora"; aviso de tributação sobre juros presente.

## 6. Fora de escopo (da TIV — registrado como evolução, NÃO entra agora)

- **SAC** (a TIV tem PRICE e SAC; MVP = PRICE; SAC é função a mais, vetável incluir).
- **Securitização / antecipação de recebíveis, gestão de carteira** (abas CP 03 Securitizado).
- **Funding**: empréstimos, financiamento de produção, mútuo, crowd, associativo/MCMV (CP 04.2).
- **Sócios/distribuições** (Empreendedor / Sócio 01 / Sócio 02, DRE por participante, CP 06)
  — conecta com o gancho multi-tenant; fase própria futura.
- **Inflação/indexação (8,5% a.a. da TIV) e correção de parcelas** — MVP nominal (mantido).
- **Cenários otimista/provável/pessimista** — evolução (a TIV os tem por curva).
- **Indicadores TIR/MTIR/VPL/ROE/lucratividade/payback/exposição a VP** → **Fase 5**, que
  agora tem gabarito real: a aba **`IND. FINANCEIRO E TECNICO CP 11`** da TIV (TIR 121% a.a.,
  VPL 42,2M, payback 28, exp. máx −6,8M no mês 17 para o caso São Roque) é a referência de
  formato e o candidato a valor-ouro da 5 — **a Fase 5 consumirá o `fluxo` da 4.1.**

## 7. Arquivos esperados (latitude de implementação)

- `core/financeira.py` — `pmt_price(saldo, i, n)` pura; safras × mesa → fluxo de recebimento;
  guards de sanidade; equivalência parcelado≡financiado-taxa-0.
- `routers/financeira.py` — validações 422 (mesa, inadimplência alta), `alerta_critico`.
- `models/schemas.py` — `PerfilMesaIn`, `FluxoVendasOut`, `ResumoAnualOut`, campos novos.
- Frontend: campo inadimplência re-rotulado (%, default 0); seção "Mesa de vendas" (perfis
  com participação/prazo/taxa); KPI "VGV geral (nominal + financeira)"; tabela anual por
  default com expand mensal; banner vermelho para `alerta_critico`.
- Testes: `tests/test_financeira_price.py` (casos-ouro 1–7, offline).

A spec fixa **contrato + critérios**; o resto é latitude. **Sem LLM, sem rede** — PRICE é
aritmética fechada e determinística.
