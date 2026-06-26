# Guia de download dos dados ambientais (você baixa, eu não alcanço as fontes)

> A plataforma lê cada camada de um **GeoJSON local** (ou de uma URL). Como o ambiente de dev
> bloqueia os geoservices gov e alguns endpoints estão fora do ar, **o download é do seu lado**.
> Aqui está o passo a passo por camada: baixar → converter p/ GeoJSON (WGS84) → apontar no `.env`.

## Escala "Brasil inteiro" (GeoPackage + leitura por janela)
O backend agora lê **só a janela da gleba** de cada arquivo (via `pyogrio`/GDAL). Para arquivos
grandes (estado/Brasil), use **GeoPackage** (`.gpkg`) — ele tem **índice espacial**, então a leitura
é rápida mesmo num arquivo de SP inteiro. Assim você **não precisa recortar por município/gleba**:
aponte o `.gpkg` do estado e qualquer gleba funciona.
```bash
# converter um shapefile grande p/ GeoPackage (cria índice espacial automaticamente)
ogr2ogr -f GPKG -t_srs EPSG:4326 reserva_legal_sp.gpkg RESERVA_LEGAL_1.shp
ogr2ogr -f GPKG -t_srs EPSG:4326 -update -append reserva_legal_sp.gpkg RESERVA_LEGAL_2.shp
# no .env: AMBIENTAL_CAR_RL_PATH=/data/ambiental/reserva_legal_sp.gpkg
```
> GeoJSON ainda funciona (recortes pequenos), mas faz varredura — para estado/Brasil prefira `.gpkg`.

## Pré-requisitos
- **GDAL/ogr2ogr** (converte shapefile→GeoJSON e reprojeta). Mac: `brew install gdal` (ou já vem
  com o QGIS, em `/Applications/QGIS.app/Contents/MacOS/bin/ogr2ogr`).
- Um diretório p/ os dados, ex.: `mkdir -p ~/dados-ambientais`.

## Recorte (bbox de São Roque) — usado em todos os `ogr2ogr`
Recorta o arquivo nacional p/ a região (deixa os GeoJSON leves). Box generoso ao redor da gleba:
```
minx=-47.45  miny=-23.75  maxx=-46.80  maxy=-23.30
```
Padrão do comando (ajuste o arquivo de entrada). `-t_srs` garante WGS84; `-spat_srs` diz que o
recorte está em lon/lat:
```bash
ogr2ogr -f GeoJSON -t_srs EPSG:4326 \
  -spat -47.45 -23.75 -46.80 -23.30 -spat_srs EPSG:4326 \
  SAIDA.geojson  ENTRADA.shp
```

---

## PRIORITÁRIAS p/ São Roque (vão gerar alerta)

### 1. Mata Atlântica (domínio — Lei 11.428)  → `AMBIENTAL_MATA_ATL_PATH`
- Fonte: **IBGE – Biomas** (https://www.ibge.gov.br/geociencias/informacoes-ambientais/vegetacao/15842-biomas.html)
  → baixe o shapefile "Biomas" (Brasil, 1:250.000).
- Converter só o bioma Mata Atlântica, recortado:
```bash
ogr2ogr -f GeoJSON -t_srs EPSG:4326 -spat -47.45 -23.75 -46.80 -23.30 -spat_srs EPSG:4326 \
  -where "Bioma='Mata Atlântica' OR bioma='Mata Atlântica'" \
  ~/dados-ambientais/mata_atlantica.geojson  lm_bioma_250.shp
```

### 2. Reserva Legal (CAR)  → `AMBIENTAL_CAR_RL_PATH`
- Fonte: **Consulta Pública do CAR** (https://consultapublica.car.gov.br) → busque o município
  **São Roque/SP** (ou o imóvel) → **Baixar** → shapefile. No ZIP vem `RESERVA_LEGAL.shp`.
- Converter:
```bash
ogr2ogr -f GeoJSON -t_srs EPSG:4326 \
  ~/dados-ambientais/car_rl_saoroque.geojson  RESERVA_LEGAL.shp
```

---

## NACIONAIS (cobertura geral — em São Roque tendem a "sem alerta")

### 3. Terras Indígenas (FUNAI)  → `AMBIENTAL_FUNAI_TI_PATH`
- Fonte: **FUNAI – Geoprocessamento** (https://www.gov.br/funai/pt-br/atuacao/terras-indigenas/geoprocessamento-e-mapas/geprocessamento)
  → baixe "Terras Indígenas" (polígonos), shapefile.
```bash
ogr2ogr -f GeoJSON -t_srs EPSG:4326 -spat -47.45 -23.75 -46.80 -23.30 -spat_srs EPSG:4326 \
  ~/dados-ambientais/terras_indigenas.geojson  tis_poligonais.shp
```

### 4. Assentamentos + 5. Quilombolas (INCRA)  → `AMBIENTAL_INCRA_PA_PATH` / `AMBIENTAL_QUILOMBO_PATH`
- Fonte: **INCRA – download por estado, sem login**: https://acervofundiario.incra.gov.br/i3geo/datadownload.htm
  → selecione **SP** → baixe "Assentamento Brasil" e "Áreas de Quilombolas".
```bash
ogr2ogr -f GeoJSON -t_srs EPSG:4326 -spat -47.45 -23.75 -46.80 -23.30 -spat_srs EPSG:4326 \
  ~/dados-ambientais/assentamentos.geojson  assentamento_brasil_sp.shp
ogr2ogr -f GeoJSON -t_srs EPSG:4326 -spat -47.45 -23.75 -46.80 -23.30 -spat_srs EPSG:4326 \
  ~/dados-ambientais/quilombolas.geojson  areas_quilombolas_sp.shp
```

### 6. Cavernas (CECAV/ICMBio)  → `AMBIENTAL_CECAV_CAV_PATH`
- Fonte: **ICMBio/CECAV – base de cavidades** (https://www.gov.br/icmbio/pt-br → CECAV/CANIE),
  shapefile nacional de cavidades.
```bash
ogr2ogr -f GeoJSON -t_srs EPSG:4326 -spat -47.45 -23.75 -46.80 -23.30 -spat_srs EPSG:4326 \
  ~/dados-ambientais/cavernas.geojson  cavidades_cecav.shp
```

### 7. APCB – Áreas Prioritárias Biodiversidade (MMA)  → `AMBIENTAL_MMA_APCB_PATH`
- Fonte: **MMA – Dados Abertos** (https://dados.mma.gov.br/dataset/areas_prioritarias),
  shapefile (use o bioma Mata Atlântica).
```bash
ogr2ogr -f GeoJSON -t_srs EPSG:4326 -spat -47.45 -23.75 -46.80 -23.30 -spat_srs EPSG:4326 \
  ~/dados-ambientais/apcb.geojson  areas_prioritarias_ma.shp
```

### 8. Dutovias de gás (EPE)  → `AMBIENTAL_ANP_DUTO_PATH`
- Fonte: **Webmap EPE** (https://gisepeprd2.epe.gov.br/WebMapEPE/) → tema "Infraestrutura de Gás
  Natural" → baixar shapefile "Gasodutos de Transporte".
```bash
ogr2ogr -f GeoJSON -t_srs EPSG:4326 -spat -47.45 -23.75 -46.80 -23.30 -spat_srs EPSG:4326 \
  ~/dados-ambientais/dutovias.geojson  gasodutos_transporte.shp
```

---

## ESTADUAIS SP (mais trabalhosas — opcional)

### 9. Área de Proteção de Mananciais (SP)  → `AMBIENTAL_APM_PATH`
- Fonte: **DataGEO SP** (https://datageo.ambiente.sp.gov.br) → buscar "Área de Proteção e
  Recuperação de Mananciais (APRM)" / mananciais → exportar shapefile → converter como acima.

### 10. Patrimônio/arqueológico (IPHAN)  → `AMBIENTAL_IPHAN_PATH`
- Fonte: **IPHAN** (geoserver/SICG, http://portal.iphan.gov.br) → bens tombados + sítios
  arqueológicos → exportar shapefile → converter.

### 11. Áreas contaminadas (CETESB)  → `AMBIENTAL_CETESB_AC_PATH`
- Fonte: **DataGEO SP / CETESB** → camada "Áreas Contaminadas e Reabilitadas" → exportar
  shapefile → converter. (A relação CETESB em planilha não tem geometria; use o DataGEO.)

---

## O que pôr no `backend/.env`
```dotenv
# 1) liga a aquisição real (sem isto, nenhuma camada é consultada)
AMBIENTAL_FONTE_REAL=1

# 2) caminhos dos GeoJSON (DENTRO do container — ver nota de volume abaixo)
AMBIENTAL_MATA_ATL_PATH=/dados-ambientais/mata_atlantica.geojson
AMBIENTAL_CAR_RL_PATH=/dados-ambientais/car_rl_saoroque.geojson
AMBIENTAL_FUNAI_TI_PATH=/dados-ambientais/terras_indigenas.geojson
AMBIENTAL_INCRA_PA_PATH=/dados-ambientais/assentamentos.geojson
AMBIENTAL_QUILOMBO_PATH=/dados-ambientais/quilombolas.geojson
AMBIENTAL_CECAV_CAV_PATH=/dados-ambientais/cavernas.geojson
AMBIENTAL_MMA_APCB_PATH=/dados-ambientais/apcb.geojson
AMBIENTAL_ANP_DUTO_PATH=/dados-ambientais/dutovias.geojson
# estaduais SP (opcionais)
AMBIENTAL_APM_PATH=/dados-ambientais/apm_sp.geojson
AMBIENTAL_IPHAN_PATH=/dados-ambientais/iphan.geojson
AMBIENTAL_CETESB_AC_PATH=/dados-ambientais/areas_contaminadas_sp.geojson
```
> Só configure a linha da camada que você baixou. Sem o arquivo → camada "não consultada"
> (degrada honesto, não quebra nada).

### Nota IMPORTANTE — volume no container
O backend roda em container; o caminho do `.env` é **dentro** do container. Monte a pasta de dados
no serviço `api` do `docker-compose.yml`:
```yaml
  api:
    volumes:
      - ~/dados-ambientais:/dados-ambientais:ro
```
Depois: `podman-compose up -d api` (recria com o volume). Logs: `podman-compose logs -f api`.

## Validar
Suba e abra a aba **Ambiental** → "Analisar ambiental": as camadas com arquivo aparecem em
"Camadas consultadas"; onde houver sobreposição, vira alerta + overlay no mapa.
