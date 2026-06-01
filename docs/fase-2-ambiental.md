# Fase 2 — Ambiental (overlays vetoriais)

> Pré-requisito de leitura: `ARCHITECTURE.md` e `CLAUDE.md`.
> Esta fase cruza o polígono da gleba (saída da ingestão) contra camadas vetoriais
> oficiais e devolve **alertas geoespaciais de triagem** com proveniência. É
> determinística e **não usa credencial** — a declividade via DEM fica na Fase 2.5.

## Objetivo
Responder, para uma gleba já ingerida: a área tem indício de **APP** (hidrografia),
sobrepõe **unidade de conservação**, ou tem **processo minerário** por baixo? Tudo por
**interseção espacial** contra camadas oficiais, com cada alerta citável até a fonte e
a data. É a primeira camada de alto impacto visual do produto.

## Princípio: aquisição é PIPELINE, não agente
Cada fonte tem endpoint oficial e formato definido (shapefile/WFS/KMZ, SIRGAS2000). A
aquisição é **download de recurso conhecido + cache local**, consultado por bounding
box da gleba — `requests.get` agendado, não agente, não LLM. O cruzamento
`shapely.intersects(gleba, camada)` é determinístico e auditável. Escrever agente aqui
degradaria proveniência e determinismo (regra inegociável nº 1 e nº 2).

## Escopo

**Dentro (overlays vetoriais, sem credencial):**
- Hidrografia → buffers legais:
  - **APP** (Cód. Florestal, Lei 12.651 art. 4º): 30/50/100/200/500 m por largura do curso.
  - **Faixa não-edificável** (Lei 6.766 art. 4º III): 15 m de cada lado de águas.
- Unidades de conservação (ICMBio/CNUC) → interseção.
- Mineração (SIGMINE/ANM) → interseção com processos minerários.
- Camadas de buffer/sobreposição devolvidas como GeoJSON para render no mapa.
- Lista de alertas, cada um com fonte, data de referência e ressalva "caráter informativo".

**Fora:**
- **Declividade ≥30% via DEM → Fase 2.5** (exige chave OpenTopography + raster).
- Faixa não-edificável de **rodovia/ferrovia/dutos** (precisa de camada DNIT/ANTT) → futura.
- Delimitação fina de APP urbana sob a Lei 14.285/2021 (modulação municipal) → triagem conservadora aqui, refino na Jurídica.

## Regra conservadora de APP (limitação honesta)
O buffer de APP depende da **largura do curso d'água**, atributo que a camada de
hidrografia nem sempre traz. Regra de triagem:
- Se a largura é conhecida → aplica a faixa correspondente (30→500 m).
- Se desconhecida → aplica **o mínimo de 30 m** e marca `largura_confirmada: false`
  com aviso "largura do curso não confirmada — verificar".
- O alerta usa **o maior buffer aplicável** (APP ≥ faixa não-edificável), coerente com
  a decisão do `ARCHITECTURE.md` (seção 9, APP urbana).

## Fontes de dados (pipeline)
| Camada | Fonte | Endpoint | Credencial |
|---|---|---|---|
| Mineração | ANM / SIGMINE | `sigmine.dnpm.gov.br/sirgas2000/{UF}.zip` (shapefile) ou ArcGIS REST `geo.anm.gov.br/arcgis/rest/services/SIGMINE/dados_anm/MapServer` | não |
| Hidrografia | ANA / IBGE (base nacional) | WFS/WMS oficial via INDE — **confirmar URL exata na implementação** | não |
| Unidades de conservação | ICMBio / CNUC | WFS/WMS via INDE — **confirmar URL exata** | não |

Implementação: baixar/recortar por bbox da gleba, cachear localmente, refresh agendado
(SIGMINE atualiza diariamente). Camada como **interface injetável** (igual ao resolvedor
de jurisdição da Fase 1), para os testes rodarem **offline e determinísticos** com
camadas-stub. As URLs reais ficam em config, não hardcoded no caminho de teste.

## Contrato
```
GET /api/analises/{id}/ambiental
→ 200
{
  "alertas": [
    {
      "tipo": "MINERACAO | UNIDADE_CONSERVACAO | APP_HIDROGRAFIA | FAIXA_NAO_EDIFICAVEL",
      "severidade": "ALERTA | INFORMATIVO",
      "intersecta": true,
      "area_afetada_m2": 1234.0,           // quando aplicável (buffer ∩ gleba)
      "detalhe": "processo ANM nº ... (concessão de lavra)",
      "proveniencia": {
        "camada": "SIGMINE/ANM",
        "data_referencia": "2026-05-31",
        "ressalva": "caráter informativo — verificar instrumento oficial na ANM"
      }
    }
  ],
  "geojson_overlays": {                     // para o mapa
    "app": {...}, "faixa_nao_edificavel": {...},
    "uc": {...}, "mineracao": {...}
  },
  "avisos": ["largura do curso d'água não confirmada — APP aplicada com mínimo de 30 m"],
  "sem_alertas": false                       // true se nada intersecta
}
```
Não altera os contratos da casca nem do aproveitamento — é endpoint novo, aditivo.

## Frontend
- **CardAmbiental** (shadcn): lista de alertas com badge de severidade, detalhe e
  proveniência (camada + data + ressalva). Estado vazio claro quando `sem_alertas`.
- **Camadas no mapa**: render dos `geojson_overlays` sobre o polígono (APP, faixa, UC,
  mineração), com legenda e toggle por camada. WMS oficial opcional como base.
- Sem cálculo no front; só render do que o backend devolveu, incluindo proveniência.

## Critérios de aceite (valores-ouro, offline com camadas-stub)
A fase só está "testada" quando **todos** passam:

1. **Gleba sobre processo minerário (stub)** → alerta `MINERACAO`, `intersecta: true`,
   com `detalhe` do processo e proveniência SIGMINE.
2. **Gleba dentro de UC (stub)** → alerta `UNIDADE_CONSERVACAO`.
3. **Curso d'água de largura conhecida (stub, ex. 8 m)** → APP de **30 m**; buffer ∩ gleba
   com `area_afetada_m2` correta (validável geometricamente).
4. **Curso d'água de largura desconhecida** → APP **mínima de 30 m** + `largura_confirmada:
   false` + aviso.
5. **Faixa não-edificável** de 15 m aplicada à água; alerta usa o **maior** buffer (APP).
6. **Gleba sem nenhuma sobreposição** → `sem_alertas: true`, lista vazia, sem erro.
7. **Proveniência obrigatória** em todo alerta (camada, data, ressalva informativa).
8. **Determinismo**: mesma gleba + mesmas camadas-stub → mesmos alertas, sempre.
9. **Offline**: a suíte roda sem rede (camadas injetadas), sem chamar endpoint real.
10. **Sem regressão**: Fases 1 e 1.5 seguem verdes.

## Restrições inegociáveis
- Aquisição por pipeline (download de endpoint fixo + cache); **nunca agente/LLM**.
- Interseção determinística; cada alerta citável à fonte e data.
- Ressalva "caráter informativo — verificar oficial" em todo alerta (é triagem, não veredito).
- Camadas injetáveis para teste offline (padrão do resolvedor de jurisdição).
- Nada de DEM/declividade nesta fase (é a 2.5).

## Definição de pronto
Os 10 critérios passam em `pytest` (offline); subir uma gleba e abrir a Ambiental mostra
os alertas com proveniência e as camadas desenhadas no mapa; gleba "limpa" mostra estado
vazio honesto.
