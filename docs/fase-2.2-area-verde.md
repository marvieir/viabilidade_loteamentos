# Fase 2.2 — Área verde (cobertura vegetal) → desconto da área aproveitável

> Spec da fase. Fonte de verdade junto com `CLAUDE.md` e `ARCHITECTURE.md`.

## Objetivo (escopo de TRIAGEM, não de laudo)
Identificar a **área verde / cobertura vegetal** dentro da gleba e **descontá-la da área
aproveitável**. A plataforma **não classifica** se é Mata Atlântica, mata nativa, capoeira
ou vegetação removível — isso é trabalho do **engenheiro ambiental** numa análise detalhada,
fora do escopo. Aqui: detectar o verde, medir, e tirar do total aproveitável.

**Princípio conservador:** verde = **fora** do aproveitável até que um especialista prove o
contrário. Melhor subestimar o aproveitável do que vender área que não se pode lotear.

## Regras inegociáveis herdadas
1. Cálculo numérico **só no backend** (rasterio/shapely), nunca no front, nunca via LLM.
2. **Determinismo:** mesma gleba + mesmo raster de referência → mesma área verde.
3. **Proveniência obrigatória:** fonte (ex.: "MapBiomas Coleção N, ano AAAA"), data, classe.
4. **Degradação honesta:** sem fonte de vegetação configurada → não inventa; reporta
   "cobertura vegetal não consultada" e não desconta nada (não zera nem chuta).

## Contrato de saída (endpoint próprio — um card por dimensão)
`GET /api/analises/{id}/vegetacao`
```jsonc
{
  "area_total_m2": 240842.15,        // área da gleba (geodésica, já medida na geometria)
  "area_verde_m2": 131000.00,        // cobertura vegetal detectada dentro da gleba
  "area_liquida_m2": 109842.15,      // area_total - area_verde (base após desconto do verde)
  "percentual_verde": 54.4,
  "geojson_verde": { /* polígono(s) da área verde, p/ overlay no mapa */ },
  "proveniencia": { "fonte": "MapBiomas Coleção 9 (2023)", "data_referencia": "2026-06-04",
                    "classes": ["Formação Florestal", "Formação Savânica"] },
  "avisos": [],
  "consultada": true                 // false = sem fonte → area_verde_m2 = null, sem desconto
}
```

## Fonte de dados (injetável, padrão da malha)
- Interface `FonteVegetacao.cobertura_verde(gleba) -> (geometria_verde, proveniencia)`.
- Produção: `FonteVegetacaoRaster` lê um **raster de uso/cobertura**, recorta pela gleba com
  `rasterio.mask`, seleciona as **classes de vegetação** e poligoniza a máscara.
- **Fonte recomendada: ESA WorldCover (10 m, 2021) — PÚBLICA, SEM LOGIN.** COG na AWS Open
  Data; `scripts/baixar_worldcover.py` lê só a janela da gleba por HTTP (sem autenticar) e
  salva um recorte local → `VEGETACAO_RASTER_PATH`. Classes verde padrão:
  `{10 árvores, 20 arbustiva, 90 área úmida, 95 mangue}` (30 pastagem fica de fora;
  ajustável por env `VEGETACAO_CLASSES_VERDE`).
- Alternativa: **MapBiomas** (`scripts/baixar_mapbiomas.py`, via Earth Engine — exige conta
  Google/projeto Cloud; pode esbarrar em bloqueio de login). Mesma `FonteVegetacaoRaster`,
  só muda a legenda de classes.
- `get_fonte_vegetacao()` → `None` por padrão (degradação); raster apontado → liga.
- Testes: **offline**, com fonte-stub determinística; o caminho raster tem teste com GeoTIFF
  sintético (gated por `rasterio`).

## Integração com Aproveitamento
A `area_liquida_m2` (após desconto do verde) entra como **base** do cálculo de aproveitamento
quando a vegetação foi consultada — com proveniência explícita do desconto. Sem fonte, o
aproveitamento segue como hoje (sem desconto), rotulando que o verde não foi considerado.

## Valores-ouro (validados ao vivo — ESA WorldCover 2021)
**Terreno_Cachoeira (tile S24W048), validado pelo operador em 2026-06-04:**
- Área total: **24,08 ha**. Composição WorldCover: árvores 57,9% (~13,95 ha),
  pastagem/campo 41,3% (~9,95 ha), água 0,7%, construído 0,1%.
- Classes verde = `{10,20,90,95}` → **área verde 13,77 ha (57,2%)**, área líquida 10,31 ha.
- **Decisão de produto (operador):** pastagem/campo (classe 30) **NÃO** conta como verde —
  é área aberta/aproveitável; a mata (classe 10) é a parte com restrição ambiental
  potencial. Confirma a regra conservadora "verde = mata, não pasto".

## Não-escopo (explícito)
- Classificar bioma/espécie/passível de supressão. - Emitir parecer de supressão/compensação.
- Substituir o laudo do engenheiro ambiental. A saída é **triagem** e diz isso na proveniência.
