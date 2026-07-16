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

## Prints reais de interface (opcionais, melhoram ainda mais)

Se capturados em produção (PNG ≥ 1400 px, sem dado de cliente), substituem/complementam:

| Arquivo | Conteúdo |
|---|---|
| `conformidade.png` | Card de conformidade legal com os artigos ao lado (home, seção Confiança) |
| `hero-tracado.png` | Print do mapa real com traçado + quadro (alternativa de hero) |

Enquanto um print não existir, o componente `PrintReal` mostra um quadro neutro no lugar.
