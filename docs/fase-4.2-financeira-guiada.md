# Fase 4.2 — Financeira guiada: wizard + parceria (incorporador/terrenista) + dashboard

> Motivada pelo feedback do operador sobre a Fase 4: *"campos vagos, não intuitivos, sem
> ordem de preenchimento"* → a financeira vira um **wizard passo a passo**; e a planilha do
> curso mostrou a peça que faltava no motor: **expor o VGV/fluxo dos DOIS lados da parceria**
> (incorporador E terrenista). Pressupõe a **Fase 4.1** (PRICE + correções de UX) — as duas
> podem ser implementadas na mesma leva. Referencia `ARCHITECTURE.md` (§1-A, §2).
> **Sem LLM, sem rede.**

## 1. Objetivo

1. **Wizard**: o card Financeira deixa de ser um formulário plano e vira um fluxo guiado de
   6 passos — cada passo com poucos campos, defaults rotulados pré-preenchidos, validação
   imediata e um resultado parcial visível ("o que isso já me diz").
2. **Parceria**: o motor passa a devolver `participantes` — VGV, recebimento e fluxo do
   **incorporador** e do **terrenista**, qualquer que seja o modo de aquisição.
3. **Dashboard de resultado**: leitura consolidada com semáforo de indicadores **sob as
   premissas declaradas** (§1-A: nunca a palavra "viável" como veredito).

## 2. O que NÃO muda (não-regressão)

- **Contrato de cálculo intacto**: continua um `POST /analises/{id}/financeira` com as
  premissas completas — o wizard é estado do **frontend** que acumula passos; o backend não
  vira máquina de estados. Casos-ouro A (Fase 4) e B (4.1) **byte a byte**.
- Fronteira 4×5 (sem VPL/TIR — o dashboard reserva os slots para a Fase 5).
- Sem LLM, sem I/O externo. Suítes 1…4.1 verdes.

## 3. O wizard (frontend — ordem natural de preenchimento)

Princípio: **um passo = uma pergunta de negócio**. Barra de progresso; voltar livre; próximo
só habilita com o passo válido; cada passo mostra um **resultado parcial** que dá sentido ao
que acabou de ser preenchido. Premissas persistem por análise (padrão da Fase 4) — reabrir o
wizard recupera onde parou.

| Passo | Pergunta de negócio | Campos | Resultado parcial exibido |
|---|---|---|---|
| 1. Lotes & Preço | "Quantos lotes e a quanto?" | lotes (auto: diretriz > teto, badge de origem + aviso; sobrescrevível), preço por **R$/m² × área do lote** (como o curso: 350 × 263 = 92.122) **ou** R$/lote | **VGV bruto** na hora |
| 2. Parceria | "Como o terreno é pago e como divide?" | modo: `parceria %` (incorporador/terrenista, soma=100) \| `permuta em lotes` \| `compra` (valor+condição) | **VGV de cada parte** |
| 3. Venda | "Como você vende?" | curva (início, duração), modo: à vista \| parcelado \| **financiado** (mesa PRICE da 4.1, default rotulado) | **VGV geral** (nominal + receita financeira) |
| 4. Custos | "Quanto custa fazer?" | urbanização (R$/lote ou R$/m²), projetos, topografia, marketing %, comissão %, admin mensal — defaults rotulados pré-preenchidos | **total de custos** + custo/lote |
| 5. Tributos | "Qual regime?" | regime + alíquota (default 5,93% rotulado "confirme com contador"), inadimplência % (default 0, guard da 4.1) | imposto estimado |
| 6. Resultado | — | — | **Dashboard** (§5) |

Microcopy obrigatória: cada campo tem uma linha de ajuda em linguagem de incorporador
("Entrada (%): quanto o comprador paga no ato"), e todo default rotulado mostra o badge
`default — edite` com a proveniência no hover. **É a resposta direta ao feedback "campos
vagos"** — nenhum campo sem explicação de uma linha.

## 4. Parceria — `participantes` no motor (backend)

O split do curso (`incorporador % × receita; terrenista = resto`) **é matematicamente a
nossa `permuta_vgv`** — a mudança é **expor os dois lados** em toda saída:

```jsonc
"participantes": {
  "incorporador": {
    "pct": 0.80,
    "vgv": { "nominal": 8000000, "receita_financeira": ..., "geral": ... },
    "recebimento_total": ...,
    "custos_total": ...,            // MVP: 100% dos custos no incorporador (rotulado)
    "resultado_nominal": ..., "margem": ..., "exposicao_maxima": {...},
    "fluxo": [ ... ]                 // o fluxo da Fase 4 atual É o do incorporador
  },
  "terrenista": {
    "pct": 0.20, "modo": "parceria_vgv" | "permuta_lotes" | null,   // null se compra
    "vgv": { "nominal": 2000000, ... },
    "recebimento_total": ...,
    "fluxo": [ { "mes": 1, "entradas": 200000 }, ... ]   // só recebe; sem custos no MVP
  }
}
```
- `parceria %` ≡ `permuta_vgv` (pro-rata em cada recebimento). `permuta_lotes`: o fluxo do
  terrenista é o recebimento dos lotes dele (vendidos pela mesma curva/mesa, rotulado como
  premissa). `compra`: terrenista = null; o vendedor não participa do fluxo.
- **Custos 100% no incorporador no MVP** (rotulado: *"split de custos entre sócios é
  evolução — TIV trata; aqui o terrenista só recebe"*). Tributo de cada parte sobre a
  receita da parte, mesma alíquota (rotulado "cada parte apura seu imposto; confirme").

## 5. Dashboard (passo 6) — leitura sob premissas, nunca veredito

Layout em três blocos (a "aba dashboard" que o operador pediu):

1. **Números-mestre**: VGV geral (nominal + financeira) · resultado nominal · margem ·
   exposição máxima (valor + mês) · horizonte. Cards grandes, `_fmt` pt-BR do backend.
2. **Semáforo de indicadores — calculado no backend** (`leituras[]`), com regra fixa e
   auditável; **linguagem §1-A**:
   - resultado nominal > 0 → `favoravel` ("resultado positivo sob as premissas declaradas");
     < 0 → `desfavoravel`;
   - margem vs `margem_referencia_pct` (premissa editável, default rotulado 0,20 — *"prática
     de mercado; defina a sua"*) → `favoravel`/`atencao`;
   - exposição máxima vs `capital_disponivel` (premissa **opcional**) → `favoravel` se
     |exposição| ≤ capital; `atencao` se excede ("exposição supera o capital informado —
     estruturar funding"); omitida se capital não informado;
   - **slots da Fase 5** (`vpl`, `tir`, `payback`): presentes com `status: "pendente"` e
     rótulo "disponível na dimensão Econômica" — o dashboard nasce pronto para recebê-los.
3. **Parceria**: VGV e resultado por participante (gráfico de composição) + tabela
   comparativa de recebimento incorporador × terrenista por ano.

**Ressalva fixa no rodapé do dashboard:** *"Indicadores condicionados às premissas
informadas — pré-análise (§1-A), não recomendação de investimento nem garantia de
resultado."* A palavra **"viável" não aparece** como veredito do sistema.

## 6. Critérios de aceite (testáveis)

1. **Split-ouro (Caso A + terrenista 20%)**: incorporador VGV 8.000.000 / terrenista
   2.000.000; fluxo do terrenista = 200.000/mês nos meses 1–10; `Σ` dos dois fluxos de
   entradas = recebimento total do empreendimento (±1 centavo); resultado do incorporador
   = Caso A (custos 100% nele).
2. **Split no financiado (Caso B + 20%)**: terrenista recebe 20% de cada recebimento
   (entrada e parcelas), incluindo pro-rata da receita financeira.
3. **`permuta_lotes`**: 20 lotes → fluxo do terrenista = recebimento de 20 lotes pela
   mesma mesa/curva, rotulado como premissa; equivalência de VGV com 20% exibida.
4. **`compra`**: `participantes.terrenista = null`; pagamento do terreno nas saídas.
5. **Preço por m²**: `350 × 263,21 = 92.123,50/lote` (2 casas) — paridade com o exemplo do
   curso; R$/lote direto produz o mesmo VGV.
6. **`leituras[]` determinísticas**: resultado>0 → `favoravel`; margem < referência →
   `atencao`; exposição > capital informado → `atencao` com a frase de funding; capital
   ausente → leitura omitida; slots VPL/TIR/payback com `status="pendente"`. **Nenhuma
   string "viável"/"inviável" na resposta do backend** (teste de regex).
7. **Wizard (frontend)**: 6 passos na ordem da tabela; próximo desabilitado com passo
   inválido; todo campo com microcopy de uma linha; defaults com badge `default — edite`;
   reabrir a análise recupera os passos preenchidos; resultado parcial visível em cada passo.
8. **Contrato preservado**: um único `POST` com premissas completas (wizard é estado do
   front); Casos A e B byte a byte; sem VPL/TIR calculados; suítes 1…4.1 verdes.
9. **Rotulagem da parceria**: custos 100% incorporador rotulado; tributo por parte rotulado
   "confirme com contador".
10. **Determinismo + `_fmt` pt-BR backend** (inalterado).

## 7. Fora de escopo (registrado)

- **Split de custos entre sócios / múltiplos sócios / distribuições** (TIV CP 06) — junto
  do gancho multi-tenant; evolução.
- **Reajuste/indexação da carteira (IGPM + juros do curso; multiplicador 1,37114)** — o
  multiplicador do curso é **constante hardcoded sem fórmula**; nosso PRICE com taxa cobre o
  efeito de juros de forma auditável. Indexação inflacionária = evolução (MVP nominal). Se o
  usuário quiser aproximar o reajuste, a taxa da mesa pode embutir a expectativa (rotulado).
- **"Tudo vendido no mês 1" (aba Carteira do curso)** — simplificação que infla a arrecadação;
  **não copiar**: nosso motor mantém curva de vendas e safras.
- **VPL/TIR/MTIR/ROE/payback/exposição a VP** → Fase 5 (gabarito: TIV CP 11). O dashboard
  já reserva os slots.
- **Comparador de prazos** (tabela 36/60/…/240 do curso) — vira um botão "comparar prazos"
  futuro; o motor já permite (rodar N vezes); UI de comparação é evolução.

## 8. Arquivos esperados (latitude de implementação)

- `core/financeira.py` — split por participante (função pura sobre o fluxo já montado);
  `leituras()` do semáforo (regras fixas).
- `models/schemas.py` — `ParticipanteOut`, `LeituraOut`, campos novos em `FinanceiraOut`.
- `routers/financeira.py` — inalterado no contrato; resposta estendida.
- Frontend: `WizardFinanceira` (6 passos, estado local + persistência por análise),
  microcopy por campo, `DashboardFinanceira` (números-mestre + semáforo + parceria + slots
  Fase 5), banner de ressalva §1-A.
- Testes: `tests/test_financeira_participantes.py` + teste de regex anti-"viável".

A spec fixa **contrato + critérios**; o resto é latitude. **Sem LLM, sem rede** — split e
leituras são aritmética determinística; o wizard é organização de UI sobre o mesmo contrato.
