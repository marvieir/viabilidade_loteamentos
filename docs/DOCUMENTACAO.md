# Documentação — Pré-Viabilidade de Loteamento

> Visão completa da plataforma (MVP). Para decisões transversais profundas, ver `ARCHITECTURE.md`;
> para convenções de desenvolvimento, `CLAUDE.md`; para o mapa mental, `docs/mapa-mental.html`.

---

## 1. O que é

Ferramenta de **pré-viabilidade / triagem de loteamento** (parcelamento do solo, Lei 6.766/79).
Recebe o **KMZ de uma gleba** e produz uma análise multidimensional que orienta **onde gastar com
due diligence** — **não decide aprovação municipal**. Tudo que não é calculável é declarado pelo
incorporador ou marcado como julgamento externo.

**Faz triagem** sobre regras gerais (federais/estaduais/municipais) + geometria.
**Não decide:** aprovação na prefeitura, diretrizes específicas da gleba (art. 6º), nem o que
exige campo/engenheiro (solo, lençol, sondagem).

## 2. Princípios inegociáveis (do `CLAUDE.md`)

1. **Cálculo numérico só no backend Python** — nunca no frontend, nunca via LLM.
2. **Frontend só renderiza JSON** — proibido geo-matemática em JavaScript.
3. **Todo número carrega proveniência** (fonte legal, perfil, data de referência).
4. **Determinismo** — mesma entrada → mesma saída, sempre.
5. **Degradação honesta** — sem dado de jurisdição, degrada para nível federal e rotula a
   cobertura (`BASE_FEDERAL` / `PARCIAL_UF` / `COMPLETA`). Nunca inventa dado ausente.

## 3. Stack

| Camada | Tecnologias |
|---|---|
| Backend | Python 3.11+, FastAPI, Pydantic v2 |
| Geo | shapely 2.x, pyproj (`Geod` — área/perímetro geodésicos), rasterio, pyogrio/GDAL |
| Frontend | Next.js (App Router), TypeScript, Tailwind, shadcn/ui, react-leaflet |
| LLM | Anthropic Claude (primário) + Google Gemini (fallback de sobrecarga) |
| Deploy | Docker Compose (`api` + `web`) → AWS Lightsail |

## 4. Arquitetura (visão de alto nível)

```
KMZ/KML  ──►  Parse + geometria (shapely/pyproj)  ──►  Jurisdição (município/UF/cód. IBGE)
                                                              │
                                                              ▼
                              STORE (em memória, por análise/usuário)
                                                              │
        ┌──────────────────────────────┬──────────────────────┴───────────────────────┐
        ▼                              ▼                                                ▼
  Dimensões (1 router + 1 card cada)   Fontes injetáveis (get_fonte_X → None se ausente)   Auth multi-tenant
   determinísticas em Python            arquivos/rasters/OSM/CAR/SIGEF/IBGE/...            (usuário dono da análise)
```

- **Cada dimensão = um router (endpoint) + um card** que chama o endpoint sob demanda.
- **Fonte injetável** (`get_fonte_X()`): se a env/arquivo não está configurado → retorna `None`
  → a dimensão degrada honesto (não inventa). Padrão usado em ambiental, declividade, bioma,
  bacia, malha fundiária, perfil municipal, etc.
- **STORE**: dicionário em memória por análise (geometria, área, perímetro, jurisdição, dono).
- **Acesso**: `analise_do_dono` garante login + posse (achado de segurança nº 1).

## 5. Dimensões de análise

| Dimensão (card) | Endpoint | O que faz | Fonte / âncora |
|---|---|---|---|
| **Visão geral** | `/analises` | Resumo: área, perímetro, restrições críticas, mapa-herói | geometria |
| **Ambiental** | `/analises/{id}/ambiental` | Overlays por interseção: APP/hidrografia, UC, mineração (ANM), reserva legal (CAR), Mata Atlântica, terras indígenas, etc. + **bacia hidrográfica** (ANA) + **malha fundiária SIGEF/SNCI** (INCRA) | INDE/IBGE/ANA/INCRA/CAR |
| ↳ **Área verde** | `/analises/{id}/vegetacao` | % de cobertura vegetal + classes (raster) + bioma nomeado | MapBiomas/WorldCover, IBGE biomas |
| ↳ **Declividade** | `/analises/{id}/declividade` | 8 faixas finas + mobilidade + relevo predominante + flag ≥30% (vedada) | DEM Copernicus GLO-30 |
| **Aproveitamento** | `/analises/{id}/aproveitamento` | Teto físico/diretriz: CA, T.O., lote mínimo, doações (viário/verde/institucional) | perfil LUOS / federal |
| **Urbanismo (IA)** | `/analises/{id}/urbanismo` | Estudo de massa: lotes + viário + quadras + áreas verdes + **pórtico**, com heatmap de score | **LLM** propõe programa, Python mede |
| **Custo (infra)** | `/analises/{id}/custo-infra` | Custo paramétrico por disciplina (terraplanagem, pavimentação, drenagem, água, esgoto, energia, reservatório, cercamento, canteiro) + BDI, por padrão (econômico/médio/alto) | **perfil de custos do operador**; âncora SICRO/SINAPI |
| **Conformidade** | `/analises/{id}/conformidade` | Confronta o projeto com a LUOS: recuos, gabarito, permeabilidade, doações | perfil LUOS |
| **Jurídico** | `/analises/{id}/juridico` | Multi-matrícula: cadeia dominial, proprietários (PF/PJ, vigente/anterior), checklist de documentos, anexos | **LLM** extrai matrícula (PDF) |
| **Financeira** | `/analises/{id}/financeira` | Fluxo de caixa mês×mês: VGV, custos (urbanização/projetos/marketing/tributos/aquisição/permuta), venda financiada (PRICE) | aritmética pura |
| **Econômica** | `/analises/{id}/economica` | Avalia o fluxo: VPL, TIR, payback simples/descontado, exposição, curva VPL×TMA | aritmética pura |
| **Localização** | `/analises/{id}/localizacao` | Enriquecimento socioeconômico IBGE (informativo, não entra em cálculo) | IBGE Censo/PIB |
| **Diretriz (LUOS)** | `/analises/{id}/perfil` | Extrai/confirma o perfil municipal da LUOS (gate humano: proposto → confirmado) | **LLM** extrai LUOS (PDF) |

## 6. Uso de LLM (importante para custo)

Apenas **3 pontos** chamam a API da Anthropic; **todas as outras dimensões são Python puro**
(custo de LLM zero):

| Ponto | Quando | Modelo | Tamanho |
|---|---|---|---|
| **Extração LUOS** | 1× por município (reutilizada nas análises seguintes) | Opus 4.8 (cadeia Fable 5 → Opus) | PDF nativo, `max_tokens=16000` |
| **Urbanismo IA** | por proposta de layout (pode regenerar) | Fable 5 → Opus 4.8 | `max_tokens=4000` |
| **Extração Jurídica** | por matrícula carregada | Opus 4.8 | PDF nativo |

- **Fallback**: se a Anthropic sobrecarrega (529), o Urbanismo cai para **Gemini** (`URBANISMO_GEMINI_MODELO`).
- Envs: `ANTHROPIC_API_KEY`, `LUOS_EXTRATOR_MODELO`, `JURIDICO_EXTRATOR_MODELO`, `URBANISMO_MODELO`.

## 7. Fontes de dados externas

| Fonte | Uso | Como entra |
|---|---|---|
| OSM / Overpass | vias (pórtico no acesso) | API (4 mirrors com failover) |
| CAR / SICAR | reserva legal | arquivo GeoJSON local |
| IBGE Biomas (`lm_bioma_250`) | bioma nomeado | arquivo local |
| ANA (Regiões Hidrográficas, campo `NMRHI`) | bacia hidrográfica | arquivo local |
| INCRA SIGEF/SNCI | malha fundiária (parcelas certificadas) | shapefiles por UF (pasta) |
| Copernicus GLO-30 DEM | declividade | raster |
| MapBiomas / WorldCover | cobertura vegetal | raster |
| IBGE Censo/PIB | localização | arquivo embarcado |
| SINAPI / SICRO | **metodologia** de custo (âncora por disciplina, Decreto 7.983/2013) | valores informados pelo operador |

Todas via **fonte injetável**: env ausente → dimensão degrada honesto.

## 8. Cobertura e proveniência

Cada número devolvido traz fonte + data + perfil. A cobertura é rotulada:
`BASE_FEDERAL` (só regra federal) · `PARCIAL_UF` (regra estadual parcial) · `COMPLETA`
(perfil municipal confirmado). O frontend exibe os rótulos; nunca recalcula.

## 9. Multi-tenant / segurança

- Autenticação por usuário; cada análise pertence a um dono (`usuario_id`).
- `analise_do_dono` bloqueia acesso a análise de terceiros (404, não revela existência).
- Perfis do operador (custos, etc.) persistidos por `usuario_id`.
- Em produção, o boot **aborta** se a config de segurança estiver insegura (segredos default,
  CORS `*`, cookie sem `Secure`).

## 10. Deploy

- **Docker Compose**: serviços `api` (FastAPI) e `web` (Next.js). Alvo: **AWS Lightsail**.
- **Portas**: frontend `>3700` (default 3700), backend `>8700` (default 8700).
- **Volumes de dados** (não vão no git): `DADOS_AMBIENTAIS` (→ `/data/ambiental`: biomas, bacias,
  CAR, SIGEF, rasters), `JURIDICO_DIR`, perfis (`perfis/`).
- **Fluxo dev→prod**: desenvolve no branch `dev` (testa no Mac via podman-compose) → promove
  `dev → main` → deploy AWS (`docker compose -f docker-compose.prod.yml up -d --build`).
  Detalhes em `docs/fluxo-dev-prod.md` e `docs/migracao-lightsail.md`.

## 11. Testes

- `pytest`. Toda fase tem **valores-ouro** (golden tests) na sua spec; a fase não é considerada
  pronta sem esses testes passando. Ex.: `tests/test_custo_infra.py` valida os totais exatos do
  motor de custo e a degradação honesta.

## 12. Estrutura de pastas (resumo)

```
backend/app/
  main.py            # app + registro de routers
  routers/           # 1 arquivo por dimensão
  core/              # parse KMZ, geometria, jurisdição, motores determinísticos, fontes injetáveis
  models/            # schemas Pydantic (contratos de API) + db_models
  perfis/            # municipais, urbanismo, financeira, custos (persistência por chave)
tests/               # valores-ouro por fase
frontend/
  app/page.tsx       # orquestra as seções/cards
  components/cards/   # 1 card por dimensão
  components/mapa/    # MapaLeaflet, overlays, camadas WMS
  components/shell/   # Sidebar, seções (navegação)
  lib/api.ts         # cliente do backend
docs/                # specs por fase + esta documentação + mapa mental
```

## 13. Diferenciais (vs. concorrência — ver `docs/gaps-urbia.md`)

1. **Urbanismo IA** com traçado real (lotes + viário + pórtico) — concorrente vende como serviço humano.
2. **Econômica** profunda: VPL/TIR/payback/sensibilidade + modos terrenista/permuta.
3. **Jurídico dominial**: matrícula/cadeia/proprietários/checklist/anexos.
4. **Ambiental** com profundidade de camadas e proveniência.
5. **Custo de infraestrutura** alimentado pelo layout real (quantidades medidas, não chute).
