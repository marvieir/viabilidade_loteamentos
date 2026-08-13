# Fase URB-TERRA — Terraplenagem estimada (corte/aterro) no Custo de Infra (SPEC, AGUARDA APROVAÇÃO)

> Origem: caso #7 do relatório Lotenet (score 4.14) — "estimar volumes de corte/aterro e
> alertar custos ocultos ANTES do projeto urbanístico"; "nenhum produto integra
> topografia→custo". Mockup: `docs/mockups/mockup-urb-terra.png`.

## 1. O que entra (escopo v1)

1. **Motor determinístico `core/terraplenagem.py`**: para o ÚLTIMO layout de Urbanismo,
   estima corte/aterro **POR QUADRA** com **platô balanceado** — a cota de plataforma que
   iguala corte e aterro DENTRO da quadra (minimiza movimentação e zera bota-fora local).
   Volume por pixel do DEM: `|cota − platô| × área do pixel`, somado em corte (cota acima)
   e aterro (cota abaixo).
2. **Fonte de elevação: DEM Copernicus GLO-30** (o mesmo da declividade — nenhuma fonte
   nova). Ressalvas honestas SEMPRE visíveis: é DSM (inclui vegetação — superestima corte
   sob mata) e 30 m é resolução de TRIAGEM, não de projeto executivo. Sem DEM → cobertura
   `INDISPONIVEL` (não inventa; regra 5).
3. **Saída**: por quadra (cota do platô, corte m³, aterro m³, movimentação); totais do
   estudo; **balanço global** (corte − aterro) e **alerta de custo oculto** quando o
   desbalanço passa o limiar (necessidade de bota-fora ou empréstimo — o custo que o
   Lotenet aponta como o "susto" da obra).
4. **Integração no Custo de Infra**: a disciplina *terraplanagem* ganha a base **`por_m3`**
   com a QUANTIDADE vinda da estimativa (movimentação total). O custo unitário R$/m³
   continua sendo do PERFIL do operador (âncora SICRO) — a plataforma estima volume,
   nunca inventa preço. O valor da disciplina pode pré-preencher a linha "Terraplenagem"
   do cronograma físico-financeiro (FIN2-2).
5. **Front**: no card Custo de Infra, botão "Estimar corte/aterro do estudo" → tabela por
   quadra + totais + alerta de desbalanço; na disciplina, a base `por_m3` aparece com a
   quantidade estimada e proveniência. Overlay opcional no mapa (quadra colorida por
   corte/aterro líquido) fica para a fase B se o operador não pedir agora.
6. **Viário fora da v1**: greide de via (corte/aterro do leito) NÃO é modelado — sai
   rotulado no resultado ("estimativa cobre as quadras; viário é fase B").

## 2. Regras da casa aplicadas
- Cálculo só no backend; determinismo (mesmo DEM + mesmo layout → mesmos m³).
- Proveniência em todo número: fonte do DEM + data + método ("platô balanceado por
  quadra, DSM 30 m — triagem").
- Degradação honesta: sem DEM ou sem layout → `INDISPONIVEL` com aviso, nunca zero.
- Nenhum custo unitário inventado (o R$/m³ é do perfil; sem perfil → fica de fora).

## 3. Contrato (esboço)
- `GET /api/analises/{id}/terraplenagem` → `TerraplenagemOut`:
  `{quadras: [{quadra_id, area_m2, plato_m, corte_m3, aterro_m3, movimentacao_m3}],
  corte_total_m3, aterro_total_m3, movimentacao_total_m3, balanco_m3, alerta_desbalanco,
  cobertura, avisos[], proveniencia}` (tudo com `*_fmt` pt-BR onde couber).
- Custo de Infra: base `por_m3` na disciplina terraplanagem; quantidade =
  `movimentacao_total_m3` do último cálculo (persistido por análise, padrão dos stores).

## 4. Testes-ouro
- Plano inclinado sintético (rampa constante) com quadra retangular: platô balanceado =
  cota média; corte = aterro = valor analítico fechado à mão (grid conhecido).
- Quadra plana → 0 m³; duas quadras em cotas diferentes → platôs independentes.
- Sem DEM → `INDISPONIVEL`; sem layout → 404/aviso.
- Integração: disciplina por_m3 multiplica quantidade estimada × custo do perfil.

## 5. Fora da v1 (fase B, se o uso confirmar)
Greide longitudinal de vias por trecho; fatores de empolamento/compactação declaráveis;
bota-fora com DMT (distância de transporte); cotas REAIS do levantamento do agrimensor
(hoje as curvas DXF entram sem cota — extrair a elevação das polylines é evolução);
muros de arrimo/contenção; platô manual por quadra (operador trava a cota).

## 6. Perguntas ao operador
1. Aprova o escopo v1 (corte/aterro por quadra, platô balanceado, DEM 30 m rotulado como
   triagem, viário fora)?
2. Quantidade da disciplina terraplanagem: propomos **corte + aterro somados**
   (movimentação total, o que a máquina de fato move). Alternativa: máx(corte, aterro).
3. Alerta de desbalanço (bota-fora/empréstimo): limiar sugerido de **10% da
   movimentação** — ok, ou prefere outro número?
4. Gratuito ou plano pago? Proposta: **aberto no gratuito** (isca técnica de diferencial
   — "nenhum produto integra topografia→custo"), diferente do FIN2-5 que é pago.
