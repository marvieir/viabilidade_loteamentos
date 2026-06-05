# Handoff — Fase 2.2 (Área verde) + redesenho do Aproveitável

> Resumo das evoluções desta sessão para atualizar a especificação. Tudo validado AO VIVO
> pelo operador (gleba **Terreno_Cachoeira**, São José dos Campos/SP, 24,08 ha) e coberto por
> testes. Branch: `claude/eager-dirac-IoO3K`.

## 1. Resumo executivo
- **1.7 e 2.1 fechadas** (detecção de município real + ambiental real SIGMINE/ANA/ICMBio/
  ANEEL; achado e corrigido o caso de **massa d'água/represa** = `APP_MASSA_DAGUA`).
- **Nova dimensão 2.2 — Área verde:** identifica a cobertura vegetal da gleba e a desconta
  do aproveitável. Triagem conservadora, **não** classifica mata nativa/removível (isso é
  laudo de engenheiro ambiental, fora do escopo).
- **Modelo de "área aproveitável" redesenhado** por decisão do operador (muda o contrato da
  Fase 1): some vias e doação; entra a união mata+APP.
- **Mapa** passou a desenhar a mancha verde.

## 2. Fase 2.2 — Área verde (cobertura vegetal)
**Objetivo:** detectar o verde e removê-lo do aproveitável. Conservador: verde = fora do
aproveitável até um especialista provar o contrário. NÃO emite parecer de supressão.

**Fonte de dados — ESA WorldCover 10 m (2021), PÚBLICA e SEM LOGIN.**
- Decisão importante: o **MapBiomas via Google Earth Engine foi descartado** porque o
  `earthengine authenticate` esbarra em bloqueio de login do Google na máquina do operador.
- WorldCover é Cloud-Optimized GeoTIFF na AWS Open Data; o `rasterio` lê **só a janela da
  gleba** por HTTP (`/vsicurl/`), sem autenticar e sem baixar o tile inteiro.
- **Classes contadas como verde:** `{10 árvores, 20 arbustiva, 90 área úmida, 95 mangue}`.
  **Pastagem/campo (30) NÃO conta** (decisão do operador: pasto é área aberta/aproveitável;
  a mata é a parte com restrição). Ajustável por env `VEGETACAO_CLASSES_VERDE`.

**Como funciona (determinístico, cálculo só no backend):**
- `backend/scripts/baixar_worldcover.py` — pipeline (não-agente): recebe `--kmz` ou `--bbox`,
  calcula o tile WorldCover (grade 3°×3°), recorta a janela, salva GeoTIFF local.
- `backend/app/core/vegetacao.py` — `FonteVegetacao` (interface injetável),
  `FonteVegetacaoRaster` (lê o raster com rasterio, recorta pela gleba, poligoniza as classes
  de vegetação), `analisar_vegetacao(gleba, cobertura)` (mede o verde dentro da gleba em CRS
  métrico local AEQD). Degrada honesto sem fonte (`consultada=false`, não inventa).
- Endpoint: `GET /api/analises/{id}/vegetacao`.

**Validação ao vivo (valor-ouro):** Terreno_Cachoeira 24,08 ha → composição WorldCover
árvores 57,9% / pasto 41,3% / água 0,7%. Com as classes acima → **verde 13,77 ha (57,2%)**.
Confere visualmente com o satélite (mata na porção leste/sul; pasto no centro).

## 3. Redesenho do "Aproveitável" (decisão do operador — muda contrato da Fase 1)
Ao ver o resultado na tela, o operador definiu o modelo de TRIAGEM:

> **Área aproveitável = Área total − UNIÃO(mata ∪ APP curso d'água ∪ APP massa d'água ∪
> faixa não-edificável ∪ servidão de LT)**
> **Nº de lotes (urbano) = TETO = Área aproveitável ÷ lote mínimo**

Decisões e porquês:
1. **Vias saem do cálculo** — o % de vias só se conhece no **projeto urbanístico**.
2. **Doação sai do cálculo** — depende da **diretriz de cada prefeitura**, que a plataforma
   ainda não carrega.
3. **APP entra junto com a mata** — e por **união geométrica** (sem dupla contagem), porque
   mata ribeirinha é APP e verde ao mesmo tempo. (`core/aproveitavel.consolidar`.)
4. **Mostrar o % sobre a gleba inteira** (não sobre a base já reduzida — evita número inflado).
5. Lotes vira **teto** (limite superior): vias/doação reduzem isso depois.

**Validação ao vivo:** união = 17,18 ha (mata 13,77 + APP 5,35 − sobreposição 1,94) =
**71,33%** descontado → **aproveitável 6,9 ha (28,7% da gleba)** → teto 345 lotes (lote 200 m²).

**Removidos** (contrato Fase 1 obsoleto): motor `aproveitamento_loteamento`/`_desmembramento`,
as 3 "bases de doação" (total/líquida/combinada), os campos vias/doação/combinado/fator de
desmembramento, e os **valores-ouro da Aula 09** (que assumiam vias=11500/doação=20%).

## 4. Contratos de API novos/alterados (para a spec)
`POST /api/analises/{id}/aproveitamento` — entrada simplificada:
```jsonc
{ "regime": "URBANO"|"RURAL",
  "lote_min_m2": 200,            // URBANO (obrigatório)
  "modalidade": "loteamento_aberto",  // URBANO (rótulo, não muda o número)
  "fmp_m2": 20000 }             // RURAL (opcional; senão tabela/piso 2 ha)
```
Saída:
```jsonc
{ "regime": "URBANO",
  "descontos": {                // null se nenhuma fonte consultada
    "area_total_m2", "area_restritiva_m2" /*união*/, "area_base_m2",
    "percentual_restritivo", "sobreposicao_m2",
    "itens": [{ "tipo":"verde|app|app_massa_dagua|faixa_nao_edificavel|linhas_transmissao",
                "rotulo", "area_m2" }],
    "proveniencia" },
  "area_aproveitavel_m2", "pct_sobre_total",
  "origem_lote", "lote_min_m2", "n_lotes_teto", "ressalva_urbano",  // URBANO
  "rural": { "fmp_m2","n_parcelas","area_m2","fmp_origem","flag_conversao","proveniencia" } }
```
`GET /api/analises/{id}/vegetacao` → `VegetacaoOut` (area_total/verde/liquida, percentual,
geojson_verde, proveniencia, avisos, consultada).

## 5. Arquitetura / arquivos
- `core/vegetacao.py` — fonte injetável + motor de área verde (rasterio tardio).
- `core/aproveitavel.py` — `consolidar(gleba, geometrias)` une as restrições sem dupla
  contagem (CRS métrico local), devolve união + itens por tipo + sobreposição.
- `core/aproveitamento.py` — só `lotes_teto()` e `aproveitamento_rural()` (resto removido).
- `routers/analises.py` — endpoint injeta `get_fonte_vegetacao` **e** `get_fonte_camadas`
  (ambiental) e consolida tudo via `_consolidar_descontos`.
- `routers/vegetacao.py` — endpoint da dimensão.
- Padrão mantido: **fontes injetáveis** (igual malha/ambiental), degradação honesta, cálculo
  só no backend, proveniência em todo número, determinismo.
- Frontend: `CardVegetacao` (mancha verde no mapa via overlay `verde`), `CardAproveitamento`
  reescrito (sem vias/doação; métrica de aproveitável + teto + breakdown dos descontos).

## 6. Infra / deploy
- `rasterio==1.4.3` adicionado. **Dockerfile do backend instala GDAL** (`gdal-bin
  libgdal-dev build-essential`) — rasterio não tem wheel linux-arm64, compila do fonte.
- `python-dotenv` + `backend/.env.example` + `uvicorn --env-file .env` (fim dos `export`).
- `docker-compose.yml`: `VEGETACAO_RASTER_PATH` + volume do `verde.tif` habilitados;
  `AMBIENTAL_FONTE_REAL=1` liga as 4 fontes ambientais.
- Rasters/`.env` no `.gitignore` (ficam em volume, não no git).

## 7. Estado atual
- **70 testes + 4 skip** (skips = caminho raster gated por rasterio + smokes ao vivo).
- `tsc` limpo. Validado ao vivo via containers no Mac do operador.

## 8. Pendências / ganchos para próximas fases
- **Fonte de vegetação sob demanda:** hoje o `verde.tif` é pré-baixado por região (1 tile).
  Para produção, o backend deveria baixar o recorte WorldCover por gleba automaticamente.
- **Perfil municipal (Fase 1.8+):** quando carregar a diretriz da prefeitura, **doação** e
  **lote mínimo/LUOS** voltam a entrar (hoje rotulados como "não considerado").
- **Vias:** entram só num eventual módulo de projeto urbanístico (fora da triagem).
- Mancha verde no mapa é "quadriculada" (pixels de 10 m) — fiel ao dado, não suavizada.
