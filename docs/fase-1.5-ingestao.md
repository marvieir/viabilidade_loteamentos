# Fase 1.5 — Ingestão determinística de geometria

> Pré-requisito de leitura: `ARCHITECTURE.md` e `CLAUDE.md`.
> Esta fase **substitui o parser cru da Fase 1** por uma camada de ingestão que
> classifica o arquivo por conteúdo e resolve, de forma determinística e sem inventar,
> os casos sem ambiguidade. O caso difícil (CAD sujo) é roteado para a Fase 1.6.

## Por que esta fase fura a fila
~99% dos arquivos reais de análise chegam como export de topografia/CAD (linhas, não
polígonos). Sem ler a entrada, nenhuma dimensão (Ambiental, Jurídica, Financeira…)
agrega valor. Logo a ingestão é o gargalo de viabilidade do produto e vem antes das dimensões.

## Princípio: classificar por CONTEÚDO, não por origem
A fonte (Google Earth, AutoCAD, software de topografia) é só uma dica. O que decide o
tratamento é **o que o arquivo contém**. Três rotas:

| Rota | Condição | Ação |
|---|---|---|
| `POLYGON_DIRETO` | ≥1 `<Polygon>` | usa direto (se vários, o de maior área + `aviso`) |
| `LINHA_FECHAVEL` | exatamente 1 `<LineString>` simples, e fechada OU com gap ≤ tolerância | fecha e converte em polígono |
| `TOPOGRAFIA_CAD` | qualquer outro caso sem polígono (multi-linha, linha aberta além da tolerância, ou auto-intersectada) | **recusa com diagnóstico** e roteia para Fase 1.6 |

Pontos (`<Point>`) são ignorados na decisão de rota (não podem ser perímetro), mas
contam no diagnóstico. Esta fase **não** tenta adivinhar qual linha é o perímetro
quando há várias — ambiguidade vai para a 1.6 (com confirmação humana). Manter 1.5
estritamente sem ambiguidade é o que a torna segura e determinística.

## Escopo

**Dentro:**
- Parser robusto a namespace: KML 2.2, KML 2.1 e `xmlns=""` (casar por **nome local** da tag).
- Classificador de conteúdo (3 rotas acima).
- Conversão determinística `LINHA_FECHAVEL` → `Polygon`.
- Diagnóstico estruturado para `TOPOGRAFIA_CAD` (contagens + orientação).
- Campo de proveniência `origem_geometria` em toda resposta bem-sucedida.

**Fora (Fase 1.6):**
- Isolar o perímetro entre várias linhas, fechar gaps grandes, resolver auto-interseções.
- Qualquer reconstrução que exija confirmação visual do usuário.

## Tolerância de fechamento
- Default **1,0 m**, configurável. `gap` = distância geodésica entre o primeiro e o
  último ponto da linha.
- Fechamento automático **só** se a linha for `is_simple` **e** `gap ≤ tolerância`.
- Ao fechar, **sempre** emitir `aviso` declarando o gap fechado. Nunca fechar em silêncio.
- `gap > tolerância` ou linha auto-intersectada → `TOPOGRAFIA_CAD` (não chutar).

## Contrato (alteração aditiva ao `POST /api/analises` da Fase 1)

Sucesso (rotas `POLYGON_DIRETO` ou `LINHA_FECHAVEL`):
```
POST /api/analises   (multipart: kmz | kml)
→ 200
{
  "analise_id": "uuid",
  "geometria": { "area_m2": ..., "area_ha": ..., "perimetro_m": ..., "geojson": {...} },
  "jurisdicao": { "municipio": ..., "uf": ..., "cod_ibge": ..., "cobertura": "..." },
  "origem_geometria": {
    "rota": "POLYGON_DIRETO | LINHA_FECHAVEL",
    "descricao": "polígono direto do arquivo"
                 // ou "linha fechada automaticamente (gap = 0.34 m ≤ 1,0 m)"
  },
  "avisos": ["..."]   // multi-polígono usou maior; gap fechado; etc.
}
```

Recusa (rota `TOPOGRAFIA_CAD`) — **422 com corpo diagnóstico** (não erro genérico):
```
→ 422
{
  "erro": "geometria_nao_ingerivel",
  "rota": "TOPOGRAFIA_CAD",
  "diagnostico": {
    "n_poligonos": 0,
    "n_linhas": 50,
    "motivo": "multiplas_linhas",   // | "linha_aberta" | "auto_intersecao"
    "detalhe": "arquivo de topografia/CAD: 50 linhas, 0 polígonos"
  },
  "orientacao": "Exporte a gleba como polígono fechado (uma feição <Polygon>), "
                "ou aguarde a importação assistida de topografia (fase futura)."
}
```
O downstream (`/aproveitamento`) **não muda** — continua recebendo um polígono válido.

## Frontend
- O upload passa a exibir a `origem_geometria` (badge: "polígono do arquivo" / "linha
  fechada automaticamente") e os `avisos`.
- Em `422 TOPOGRAFIA_CAD`, mostrar a mensagem diagnóstica de forma clara e amigável,
  sem stack trace. (A confirmação visual do CAD é tela da Fase 1.6.)

## Critérios de aceite (valores-ouro)
A fase só está "testada" quando **todos** passam:

1. **1 Polygon** → `POLYGON_DIRETO`; área igual à da Fase 1.
2. **Multi-Polygon** → usa o de maior área + `aviso` (regressão da Fase 1 preservada).
3. **1 LineString simples fechada** (`is_ring`) → `LINHA_FECHAVEL`; área bate com o esperado.
4. **1 LineString simples aberta, gap ≤ 1,0 m** → fecha + converte; `aviso` declara o gap.
5. **1 LineString simples aberta, gap > 1,0 m** → `422 TOPOGRAFIA_CAD`, motivo `linha_aberta`.
6. **1 LineString auto-intersectada** → `422 TOPOGRAFIA_CAD`, motivo `auto_intersecao`.
7. **Arquivo CAD multi-linha real** (`PERIMETRO_SAO_ROQUE.kml`, fixture) → `422
   TOPOGRAFIA_CAD`, motivo `multiplas_linhas`, diagnóstico reporta 50 linhas / 0 polígonos.
8. **Robustez de namespace**: KML com `xmlns=""` / namespace 2.1 tem suas geometrias
   detectadas (não retornar "0 geometrias" em arquivo válido).
9. **Proveniência**: toda resposta de sucesso traz `origem_geometria`.
10. **Determinismo**: mesma entrada → mesma rota e mesma saída, sempre.

## Restrições inegociáveis
- Classificar por conteúdo; nunca por suposição de origem.
- Nunca fechar linha em silêncio; sempre declarar o gap.
- Nunca adivinhar qual linha é o perímetro quando há várias → isso é Fase 1.6.
- Recusa sempre diagnóstica (conta o que viu e orienta), nunca erro genérico.

## Definição de pronto
Os 10 critérios passam em `pytest`; subir um KMZ de polígono ou de linha fechável
gera a análise no mapa com a proveniência da rota; subir o arquivo de São Roque
retorna o diagnóstico de topografia/CAD de forma clara.
