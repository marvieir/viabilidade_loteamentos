# Fase LAUDO-INV — Relatório do estudo para investidores (SPEC, AGUARDA APROVAÇÃO)

> Pedido do operador (16/08/2026): o export de laudo atual sai só com o semáforo; os
> clientes precisam de um **relatório detalhado da análise da área para mostrar a
> investidores** — com o projeto urbanístico, mapa de calor de lotes, resultados
> financeiros, ambiental e jurídico. Mockup: `docs/mockups/mockup-laudo-inv.png`.

## 1. Formato proposto

**Relatório A4 multi-página, gerado como página de impressão** (HTML print-ready →
o navegador salva em PDF com um clique). Por quê, e não fpdf2 como o laudo atual:
os elementos que o investidor precisa ver — planta do estudo de massa, mapa de calor,
gráficos de fluxo e curva VPL — são vetoriais (SVG desenhado dos GeoJSON/números do
backend), e o navegador imprime isso com qualidade de estúdio, offline, sem nenhuma
dependência nova no backend. O laudo simples (fpdf2) CONTINUA existindo como está.

- Backend: um endpoint **compositor** (`GET /analises/{id}/relatorio`) que agrega os
  snapshots já persistidos de TODAS as dimensões num JSON único (nenhum número novo é
  calculado — só composição + o mesmo guard de linguagem do laudo: nunca "viável",
  nunca "aprovado").
- Front: rota `/app/relatorio/{id}` que RENDERIZA esse JSON em páginas A4 com
  `@media print` (quebras de página, rodapé §1-A em toda página) + botão "Salvar PDF".
- Mapas SEM tiles externos: a planta e o mapa de calor são SVG desenhados dos GeoJSON
  (lotes com a MESMA faixa de score do app — Fase 9.5); o mapa de contexto usa o
  polígono + moldura simples. (Satélite de fundo = fase B, exige proxy de tiles.)

## 2. Estrutura do relatório (páginas)

1. **Capa** — nome do estudo/gleba, município/UF, área em ha, data de geração, quem
   gerou, marca voaz + ressalva §1-A destacada ("pré-análise de triagem; não é laudo
   técnico nem veredito de viabilidade").
2. **Sumário executivo** — semáforo por dimensão (o de hoje) + números-mestre: área
   bruta/aproveitável, lotes do estudo, VGV, resultado nominal, margem, exposição
   máxima, VPL/TIR (se a Econômica rodou). Uma página que o investidor lê em 1 minuto.
3. **A gleba e o contexto** — mapa do polígono; área/perímetro geodésicos; município e
   cobertura da régua legal (BASE_FEDERAL/PARCIAL_UF/COMPLETA); declividade por faixas;
   contexto socioeconômico (Localização, rotulado informativo).
4. **Ambiental** — mapa das restrições (overlays coloridos); tabela camada → área →
   fonte legal → data; severidade do verde (consolidado × a verificar); reconciliação
   de vistoria SE houver (laudo do RT, base × cenário otimista, com as ressalvas).
5. **Aproveitamento** — cascata: bruta − restrições = aproveitável física − doação =
   diretriz; números canônicos, lote mínimo aplicado com base legal citada.
6. **Urbanismo** — **planta do estudo de massa** (SVG: lotes, viário, verde,
   institucional, lazer, lago, pórtico) + quadro de áreas completo (m² e %) +
   indicadores (nº lotes, área média, % viário, lotes/ha) + linha das variantes
   geradas. Selo "estudo ESQUEMÁTICO de triagem — não substitui projeto (art. 6º Lei
   6.766)".
7. **Valorização lote a lote** — **mapa de calor** (score posicional da Fase 9.5, mesma
   escala do app) + distribuição por faixa (n lotes por faixa) + leitura ("faixas
   refletem posição no traçado: esquina/frente-verde/rua interna…"), rotulado como
   régua RELATIVA interna do estudo, não avaliação de mercado.
8. **Financeiro** — premissas declaradas (tabela completa, com origem
   declarado×default), VGV e blocos de custo, **gráfico do fluxo anual** (barras
   entradas/saídas/acumulado), exposição máxima, cenários de venda lado a lado,
   viabilidade estática, comparador tributário (se o plano do usuário incluir FIN2-5).
9. **Econômica** — TMA declarada, VPL, TIR (com status honesto), paybacks, **curva
   VPL×TMA** (SVG), MTIR/ROE quando houver.
10. **Jurídico** — nível de risco consolidado + motivo; resumo das fichas de matrícula
    confirmadas (ônus, áreas × KMZ); status do checklist de diligência. Sem documento →
    "não analisada", explícito.
11. **Premissas, fontes e avisos** — TODA premissa com valor+origem; toda fonte com
    data de referência; TODOS os avisos das dimensões; glossário curto (VGV, TIR,
    diretriz…) para investidor não-técnico.

Dimensão não executada aparece como "NÃO ANALISADA — rode a dimensão no app" (nunca
some em silêncio; ausência de achado ≠ ausência de problema, como no laudo atual).

## 3. Regras da casa aplicadas
- O compositor NÃO recalcula nada: só agrega snapshots persistidos com proveniência.
- Guard de linguagem do laudo reusado no compositor (regex: proíbe "viável"/"aprovado").
- Rodapé §1-A em TODAS as páginas; determinismo (mesmos snapshots → mesmo relatório).
- Front renderiza JSON; SVGs desenhados dos GeoJSON sem geo-matemática nova (projeção
  planar simples de exibição, sem medir nada).

## 4. Testes-ouro
- Compositor: análise com todas as dimensões → JSON com as 11 seções; sem jurídica →
  seção "não analisada"; guard de linguagem dispara em texto proibido.
- Determinismo: duas composições do mesmo estado → JSON idêntico.
- Heat: faixas de score do relatório idênticas às do app (mesma função de faixa).

## 5. Fora da v1 (fase B)
Satélite de fundo nos mapas (proxy de tiles); upload de logo do CLIENTE (white-label);
export .docx editável; envio por e-mail direto ao investidor; kit do corretor (#15 —
mesma infra de render, outro recorte/tonalidade).

## 6. Perguntas ao operador
1. Aprova a estrutura de 11 seções e o formato (página imprimível → PDF pelo navegador,
   mantendo o laudo simples atual como está)?
2. Plano pago (padrão FIN2-5: gate no servidor, bloqueado mostra só o item com convite)
   ou aberto no gratuito?
3. Marca no relatório v1: só voaz, ou já reservamos espaço para o logo/nome do CLIENTE
   na capa (white-label leve — o investidor é cliente do NOSSO cliente)?
