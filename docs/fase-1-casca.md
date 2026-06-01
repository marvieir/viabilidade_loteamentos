# Fase 1 — Casca + Motor de Aproveitamento

> Pré-requisito de leitura: `ARCHITECTURE.md` e `CLAUDE.md`.
> Esta spec fixa **contrato e critério de aceite**. A implementação tem latitude
> dentro das regras inegociáveis. Não adicione o que a fase não pede.

## Objetivo
Entregar a **casca funcional** do produto: subir um KMZ, ver a gleba no mapa,
obter área/perímetro, resolver a jurisdição (com degradação graciosa) e calcular o
**aproveitamento por modalidade** (desmembramento e loteamento nas três bases de doação).

É a primeira demo de ponta a ponta e a fundação onde as próximas dimensões plugam.

## Escopo

**Dentro:**
- Upload de KMZ e parse → polígono (GeoJSON).
- Área e perímetro por cálculo geodésico.
- Resolvedor de jurisdição: centróide → município IBGE → UF → cobertura.
- Motor de aproveitamento (geométrico, paramétrico): desmembramento + loteamento (bases A/B/C).
- Frontend: upload, mapa Leaflet renderizando o polígono, card de aproveitamento, badge de cobertura.

**Fora (fases seguintes):**
- Declividade via DEM → entra junto da dimensão Ambiental (Fase 2). Nesta fase o
  motor é puramente geométrico, validável isolado, sem tocar em raster.
- Overlays geoespaciais (APP, UC, hidrografia).
- Perfis estaduais/municipais reais populados (aqui basta o resolvedor + nível `BASE_FEDERAL`;
  o perfil municipal pode ser injetado como objeto de teste).
- Qualquer cálculo financeiro.

## Backend — contratos

### 1) Criar análise (parse + geometria + jurisdição)
```
POST /api/analises          (multipart/form-data: kmz=<arquivo>)
→ 200
{
  "analise_id": "uuid",
  "geometria": {
    "area_m2": 175304.0,
    "area_ha": 17.53,
    "perimetro_m": 1820.4,
    "geojson": { "type": "Polygon", "coordinates": [...] }   // WGS84, p/ o mapa
  },
  "jurisdicao": {
    "municipio": "São Roque",
    "uf": "SP",
    "cod_ibge": "3550605",
    "cobertura": "BASE_FEDERAL"            // BASE_FEDERAL | PARCIAL_UF | COMPLETA
  },
  "avisos": [
    "KMZ continha 2 polígonos; usado o de maior área."   // se aplicável
  ]
}
```
Regras:
- KML é `lon,lat[,alt]` em WGS84 (EPSG:4326). Parse via `zipfile` + `lxml`.
- Múltiplos polígonos: usar o de **maior área** e registrar em `avisos`. Nunca silenciar.
- Validar geometria (`is_valid`, anel fechado). Geometria inválida → 422 com mensagem clara.
- Área/perímetro por `pyproj.Geod(ellps="WGS84").geometry_area_perimeter()`.

### 2) Aproveitamento por modalidade
```
POST /api/analises/{id}/aproveitamento
{
  "lote_min_m2": 200.0,
  "loteamento": {
    "vias_m2": 11500.0,            // estimativa paramétrica nesta fase
    "doacao_pct": 0.20,
    "base_doacao": "combinada",    // "total" | "liquida" | "combinada"
    "combinado_pct": 0.35          // usado só se base == "combinada"
  },
  "desmembramento": {
    "fator_aprov": 0.74            // default editável (regra de mercado, com aviso)
  }
}
→ 200
{
  "desmembramento": {
    "area_aproveitavel_m2": ..., "pct_aproveitamento": 0.74, "n_lotes": ...,
    "proveniencia": "fator de mercado (aulas de modalidade) — não é exigência legal"
  },
  "loteamento": {
    "area_aproveitavel_m2": ..., "pct_aproveitamento": ..., "n_lotes": ...,
    "base_doacao": "combinada",
    "proveniencia": "Lei 9.785/99 (doação municipal); base declarada no perfil"
  }
}
```

### Núcleo de cálculo (referência — não é exigência de assinatura)
```python
def aproveitamento_loteamento(area, vias, doacao_pct, base, combinado_pct, lote_min):
    if base == "total":
        aprov = area - vias - doacao_pct * area
    elif base == "liquida":
        bruto = area - vias
        aprov = bruto - doacao_pct * bruto
    elif base == "combinada":
        aprov = area * (1 - combinado_pct)
    else:
        raise ValueError("base_doacao inválida")
    return {"area_aproveitavel_m2": round(aprov, 2),
            "pct_aproveitamento": round(aprov / area, 4),
            "n_lotes": int(aprov // lote_min)}
```

## Frontend — componentes
- **Upload de KMZ** (shadcn: dropzone/input) → `POST /api/analises`.
- **MapaLeaflet**: renderiza `geojson` da resposta; centraliza/zoom no bounds do polígono.
  Base layer OSM ou Esri World Imagery. (WMS oficiais entram na Fase 2.)
- **CardAproveitamento** (shadcn Card + Table): tabela comparando desmembramento e as
  bases de loteamento; mostra área, %, nº de lotes e a proveniência de cada linha.
- **BadgeCobertura**: `BASE_FEDERAL` / `PARCIAL_UF` / `COMPLETA` + texto do que não foi considerado.
- Nada de cálculo no front. Só fetch + render.

## Critérios de aceite (valores-ouro)
A fase só está "testada" quando **todos** passam:

1. **Área geodésica.** Para um KMZ de polígono conhecido, `area_m2` bate com o valor
   esperado dentro de ±0,5%. (Use um retângulo de coordenadas conhecidas como fixture
   determinística, além de um KMZ real.)
2. **Bases de doação — Aula 09** (área 50.000 m², vias 11.500 m², doação 20%, lote 200 m²):
   - base `total` → 28.500 m² → **57,0%** → **142** lotes.
   - base `liquida` → 30.800 m² → **61,6%** → **154** lotes.
   - base `combinada` (35%) → 32.500 m² → **65,0%** → **162** lotes.
3. **Desmembramento default** (fator 0,74) sobre área conhecida → % = 0,74 e n_lotes coerente,
   com `proveniencia` deixando claro que não é exigência legal.
4. **Multi-polígono.** KMZ com 2 polígonos → usa o de maior área e popula `avisos`.
5. **Geometria inválida** → 422 com mensagem (não 500, não silêncio).
6. **Degradação graciosa.** Sem perfil municipal carregado → `cobertura: "BASE_FEDERAL"`
   e o relatório/badge declara que lote mínimo e doação locais não foram considerados.
7. **Determinismo.** Mesma entrada chamada duas vezes → saída idêntica.

## Restrições inegociáveis nesta fase
- Cálculo só no backend; front só renderiza.
- Saídas com proveniência.
- Sem inventar jurisdição ausente.
- Sem DEM, sem overlays, sem financeiro (são fases seguintes).

## Definição de pronto
Os 7 critérios passam em `pytest`; a demo sobe via Docker Compose; subir um KMZ
mostra a gleba no mapa, área/perímetro e o card de aproveitamento com as três bases
e o badge de cobertura.
