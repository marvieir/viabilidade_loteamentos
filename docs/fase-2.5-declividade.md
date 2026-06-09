# Fase 2.5 — Declividade via DEM (faixas + flag legal ≥30%)

> Dimensão de viabilidade física. Referencia o `ARCHITECTURE.md` (seções 2, 4, 6-A) e **não
> o contradiz**. **Nota:** este documento foi **reconstruído a partir da implementação já
> entregue e validada ao vivo** (a lacuna do spec original — o `ARCHITECTURE.md` apontava
> `docs/fase-2.5-declividade.md` mas o arquivo não havia sido commitado). Descreve o
> comportamento **realmente implementado** em `core/declividade.py` / `routers/declividade.py`.

## 1. Objetivo

A partir do polígono da gleba e de um recorte de **DEM** (modelo digital de elevação),
calcular, **em CRS métrico**, a declividade do terreno e devolver:

- **Declividade média** (%) dentro da gleba.
- **% por faixa** — `suave` / `media` / `alta` (limiares configuráveis, default **8%** e
  **20%**).
- **Flag legal ≥30%** — a **área com declividade ≥ 30%**, que é **vedação de parcelamento**
  pela **Lei 6.766/79, art. 3º, §ún, III**, poligonizada (mancha pixelada fiel ao dado 30 m)
  para virar overlay no mapa **e entrar na união de descontos do aproveitável**.

Responde à pergunta de triagem *"o terreno comporta loteamento?"* — serra íngreme reduz (ou
veda) o aproveitável muito antes de qualquer projeto.

**Fronteira mantida:** é **DEM de superfície (DSM) 30 m, orientativo** — pode superestimar a
declividade sob vegetação/edificação e **NÃO substitui levantamento topográfico**. Triagem,
não laudo. A ressalva DSM acompanha **toda** saída consultada.

## 2. O que NÃO muda (não-regressão)

- O contrato do aproveitável (seção 6-A: `aproveitável = total − UNIÃO(restrições)`, sem dupla
  contagem) **não muda de forma** — a 2.5 só **acrescenta um item** à união (`declividade_vedada`).
- As fases 2.1 (ambiental), 2.2 (verde) e 2.3 (severidade) permanecem intactas.
- **DEM off por default no sandbox de testes:** os valores-ouro de Cachoeira/São Roque das
  suítes anteriores **não mudam** (sem fonte de DEM, a 2.5 degrada e não desconta nada).
- Fonte **injetável**; testes **100% offline** com DEM-stub sintético (sem rede).

## 3. Como funciona (determinístico, cálculo só no backend)

Separação de responsabilidades **igual à 2.2** (I/O isolado da matemática pura):

- **`FonteDEM` (injetável)** faz I/O + reprojeção e entrega um **grid já métrico** (`DEMRecorte`:
  `elevacao` 2D em metros, `px_m`, canto `x0_m/y0_m`, `crs_proj4` AEQD local). Em produção,
  `FonteDEMCopernicusAuto` lê o COG Copernicus por HTTP (`/vsicurl`) e reprojeta — `rasterio`
  só roda no container. Testes injetam um stub com grid sintético.
- **`analisar_declividade(gleba, dem)`** é matemática pura (numpy/shapely/pyproj), roda offline:

```
gy, gx     = np.gradient(elevacao, px, px)      # gradiente em METROS
slope_pct  = hypot(gx, gy) * 100                # rise/run → %
mask       = pixels cujo CENTRO cai na gleba (reprojetada ao CRS do grid) ∧ finitos
media      = slope_pct[mask].mean()
suave  = slope ≤ 8% ; media = 8–20% ; alta > 20%   # áreas/percentuais por faixa
vedado = slope ≥ 30%                                # poligonizado (boxes → união) → WGS84
```

A mancha ≥30% é poligonizada como **união dos pixels** (boxes no CRS métrico) reprojetada para
WGS84 — fiel à resolução de 30 m (mancha "pixelada", honesta). Sem LLM, sem agente.

### Fontes de DEM (cascata, keyless por default)
- **Padrão keyless:** `FonteDEMCopernicusAuto` — **Copernicus GLO-30 Public** (AWS Open Data,
  anônimo, **sem chave**), tile 1°×1° escolhido pela posição da gleba via `/vsicurl`,
  espelhando a 2.2.
- **Fallback gated:** `FonteDEMOpenTopography` só se `OPENTOPOGRAPHY_API_KEY` existir; **ausência
  não quebra** → cai no keyless.
- **Fallback offline:** `FonteDEMRasterLocal` / `DEM_RASTER_PATH` (raster local).

### Integração com o aproveitável (seção 6-A)
No `routers/analises.py`, `_coletar_geoms` amostra o DEM e, se houver mancha ≥30%, adiciona
`declividade_vedada` ao dict de geometrias; `_consolidar_descontos` a inclui na **união**
(`mata ∪ APP ∪ faixas ∪ declividade_vedada`) via `consolidar`, **sem dupla contagem** —
propaga a teto/otimista/diretriz **sem novo contrato**. Decisão de produto (§4.2 do espírito
da 2.3): ≥30% **desconta** do aproveitável, não é flag-only.

## 4. Contratos de API

### 4.1 `GET /api/analises/{id}/declividade` → `DeclividadeOut`

```jsonc
{
  "consultada": true,                       // false se DEM indisponível (degradação honesta)
  "fonte": "Copernicus GLO-30 Public (AWS Open Data) — DSM 30 m",
  "declividade_media_pct": 20.23,
  "faixas": [
    { "classe": "suave", "limite": "≤8%",   "area_m2": 9900,  "pct": 0.125 },
    { "classe": "media", "limite": "8–20%", "area_m2": 37800, "pct": 0.477 },
    { "classe": "alta",  "limite": ">20%",  "area_m2": 31500, "pct": 0.398 }
  ],
  "flag_vedacao": {                          // null se área ≥30% = 0
    "limite_pct": 30.0,
    "area_m2": 14700,
    "pct_da_gleba": 0.188,
    "geojson": { /* mancha vermelha pixelada; entra na união do aproveitável */ },
    "base_legal": "Lei 6.766/79 art. 3º §ún III",
    "ressalva": "Parcelamento vedado em declividade ≥30%, salvo atendidas exigências específicas das autoridades competentes."
  },
  "proveniencia": "Copernicus GLO-30 ... ; CRS AEQD local",
  "avisos": [ /* ... */, "DEM de SUPERFÍCIE (DSM) 30 m — orientativo; ... NÃO substitui levantamento topográfico." ]
}
```

`pct` da faixa é fração da **área medida dentro da gleba**; `pct_da_gleba` da flag idem.
Limiares `8`/`20` configuráveis por env (`DECLIVIDADE_LIMIAR_SUAVE`/`_MEDIA`); o **30%** da
vedação é fixo (regra de lei, não faixa).

### 4.2 Aproveitamento — sem novo contrato
A mancha ≥30% entra como item `declividade_vedada` na união já existente; `area_aproveitavel_m2`,
`n_lotes_teto`, `cenario_otimista` e `cenario_diretriz` continuam com o **mesmo formato** — só
passam a refletir o desconto da declividade quando o DEM está disponível.

## 5. Critérios de aceite (testáveis)

Stubs sintéticos com declividade **conhecida** (grid métrico AEQD), sem rede:

1. **Plano = 0%:** terreno plano → `media = 0.0`, faixa `suave.pct = 1.0`, `flag_vedacao = None`.
2. **Rampa 35% uniforme:** `media ≈ 35%` (±0,5), praticamente tudo em `alta` (>20%).
3. **Flag ≥30% com proveniência + geometria:** rampa 35% cobrindo a gleba → `flag_vedacao`
   presente, `limite_pct == 30`, `pct_da_gleba > 0.99`, `base_legal == "Lei 6.766/79 art. 3º
   §ún III"`, ressalva com "exigências específicas", `geojson` poligonizado (`type` presente).
4. **Rampa 15% sem vedação:** faixa `media > 0.99`, `flag_vedacao = None`, `geojson_vedacao = {}`.
5. **Degrada sem DEM:** sem fonte → `consultada = False`, `flag_vedacao = None`, aviso honesto.
6. **Degrada DEM sem elevação (egress bloqueado):** `consultada = False` + aviso "egress
   bloqueado".
7. **Ressalva DSM sempre presente** em saída consultada.
8. **Determinismo:** mesma entrada → mesma `media` e mesma `area_m2` da flag.
9. **Fonte por env:** default = `FonteDEMCopernicusAuto`; `OPENTOPOGRAPHY_API_KEY` ausente cai
   no keyless; com chave = `FonteDEMOpenTopography`; `DEM_RASTER_PATH` = `FonteDEMRasterLocal`.
10. **Tile Copernicus correto** pelo canto SW (ex.: São Roque → `S24_00_W048`).
11. **Não-regressão:** suítes de 1, 1.5, 1.7, 1.8, 2, 2.1, 2.2, 2.3 verdes; gold de
    Cachoeira/São Roque inalterados (DEM off por default).

**Validação ao vivo (São Roque, gleba 7,81 ha):** egress keyless confirmado no container
(`rasterio.open('/vsicurl/.../S23_00_W046...DEM.tif')` → 3600×3600, **sem fallback**);
declividade média **20,23%** (suave 12,5% · média 47,7% · alta 39,8%); **vedação ≥30% = 1,47 ha**
(18,8% da gleba) descontada no aproveitável — sobreposição com o verde contada **uma vez só**
(0,10 ha → base 5,89 ha → headline com diretriz 4,33 ha / 120 lotes).

## 6. Fora de escopo (registrado)

- **Levantamento topográfico / curvas de nível reais** — a 2.5 é DSM 30 m orientativo.
- **Movimentação de terra / corte-aterro / taludes** — projeto de engenharia, não triagem.
- **Faixas legais municipais de declividade** diferentes de 30% — os limiares de faixa são
  configuráveis, mas a **vedação ≥30%** é a regra federal; refinamento municipal é da Jurídica.

## 7. Arquivos (implementados)

- `core/declividade.py` — `DEMRecorte`, `FonteDEM` (Protocol) + fontes (Copernicus auto /
  OpenTopography / raster local) + `analisar_declividade` (puro) + `get_fonte_dem`.
- `routers/declividade.py` — `GET /analises/{id}/declividade`.
- `routers/analises.py` — `declividade_vedada` na união de descontos do aproveitável.
- `models/schemas.py` — `FaixaDeclividadeOut`, `FlagVedacaoOut`, `DeclividadeOut`.
- Frontend: `CardDeclividade` (média + faixas + flag ≥30% + ressalva) + overlay vermelho
  `declividade_vedada` (cor em `components/mapa/overlays.ts`).
- Testes: `tests/test_declividade.py` (stubs sintéticos, offline).
