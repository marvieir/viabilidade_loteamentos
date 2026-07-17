# Visuais das páginas de marketing

## Pranchas SVG (geradas pelo MOTOR REAL — não editar à mão)

`plano-masterplan.svg`, `plano-ambiental.svg` e `plano-heatmap.svg` são saída do replay
determinístico do estudo real de São Roque (dump 031: 154 lotes, score médio 5,72). O heatmap
usa o score v2 verdadeiro, lote a lote. Para regenerar (da raiz do repo, com o dump desejado):

```bash
python3 scripts/gerar_pranchas_marketing.py caminho/do/dump.json
```

Regra de honestidade dos blueprints: mockup inventado é proibido; estas pranchas são a
alternativa correta enquanto não há prints (é o desenho verdadeiro do motor).

## Prints reais de interface (tour tela a tela da /loteadores)

Capturados pelo operador (PNG largo, ~1600 px+). Nomes EXATOS que a página espera; enquanto um
arquivo não existir, o componente `PrintReal` mostra um quadro neutro no lugar:

| Arquivo | Conteúdo |
|---|---|
| `print-visao-geral.png` | Painel de visão geral: KPIs + mapa com camadas oficiais |
| `print-ambiental.png` | Alertas ambientais com proveniência (ANM, CAR, Mata Atlântica) |
| `print-declividade.png` | Declividade por faixas + vedação ≥30% + mobilidade |
| `print-area-verde.png` | Área verde: bioma, verde descontado, severidade |
| `print-urbanismo.png` | Parcelamento esquemático com legenda (quintis, verde, lazer, lago) |
| `print-juridico.png` | Pré-análise jurídica: matrículas, ônus com ato, divergência de área. ATENÇÃO LGPD: cobrir/cortar nomes de proprietários antes de publicar |
| `print-financeira.png` | Financeira guiada: VGV, margem, exposição, VPL/TIR, divisão da parceria |
| `conformidade.png` | Card de conformidade legal com artigos (home, seção Confiança) |
