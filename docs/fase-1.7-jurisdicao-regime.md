# Fase 1.7 — Jurisdição real + Regime (urbano/rural) + Rural (FMP)

> Pré-requisito de leitura: `ARCHITECTURE.md` (seções 4, 5, 9 e regra "pipeline não agente")
> e `CLAUDE.md`. Fase **corretiva**, determinística, **sem LLM** (extração da LUOS = Fase 1.8).
> Esta versão incorpora as 5 decisões de contrato de 2026-06-02 e as correções de tela
> observadas em teste real. **Substitui** qualquer versão anterior desta spec.

## Problema que corrige
O aproveitamento assumia parcelamento **urbano** (lote 200 m² + doação, Lei 6.766) sem
declarar, e a jurisdição não era resolvida (stub → `null`). Em teste real, gleba rural de
109 ha recebeu "4048 lotes de 200 m²". Terra **rural** rege-se pela **FMP do INCRA** (piso
legal 2 ha), não pela Lei 6.766; lote urbano só dentro do perímetro urbano.

## Objetivo
1. Resolver **município/UF reais** a partir do KMZ, com **detecção** (geometria) e **correção
   por nome** (lista leve) desacopladas, e tratamento de divisa.
2. Introduzir **regime** (`URBANO` | `RURAL`) obrigatório no aproveitamento.
3. **RURAL** → calcular contra a **FMP do município**; sinalizar conversão rural→urbano.
4. **URBANO** → manter regras atuais, com **modalidade** capturada (rótulo) e lote mínimo
   **declarado** (provisório, até a Fase 1.8), sempre com premissa explícita.

## Decisões de contrato incorporadas (ref. histórico 2026-06-02)
- **#1 FMP, não módulo fiscal.** Piso rural = **FMP por município** (Lei 5.868/72 art. 8º;
  Estatuto da Terra art. 65; tabela INCRA IE 5/2022, Anexo IV / CCIR). **Não** é o módulo
  fiscal. Piso legal 2 ha. Ausente na tabela → default 2 ha + aviso "confirmar no CCIR".
- **#2 Lista leve embarcada.** Detectar usa a **malha geométrica** (pesada, volume); corrigir/
  buscar por **nome** usa a **lista leve** `cod_ibge+nome+UF` (~150 KB, no repo). Override
  funciona mesmo sem a malha.
- **#3 Modalidade = rótulo.** Na 1.7 a modalidade urbana é proveniência/rótulo; o motor
  calcula igual (desmembramento + 3 bases). Regra por modalidade é da Fase 1.8 (depende da LUOS).
- **#4 Divisa = escolha humana.** Polígono em >1 município → candidatos com **% de área**,
  default no maior, **confirmação humana**. Nunca "mais restritivo" automático.
- **#5 Malha intermediária + nearest.** Nível intermediário; ponto em gap de borda → fallback
  município mais próximo, marcado `aproximado — confirmar` (não "não resolvido").

## Escopo

**Dentro:**
- Resolvedor real (promove o stub da Fase 1), em duas peças desacopladas:
  - **Detectar**: centróide → point-in-polygon na malha geométrica IBGE → `cod_ibge`;
    fallback nearest na borda (`aproximado`).
  - **Corrigir**: busca/autocomplete por **nome** sobre a lista leve (tolerante a acento/caixa:
    "sao roque" = "São Roque"); resolve nome → `cod_ibge` internamente (usuário nunca vê código).
- Proveniência da origem: `detectado` | `aproximado` | `informado`.
- Divisa: candidatos + % de área por município + default maior + confirmação humana.
- Regime obrigatório no aproveitamento; premissa declarada.
- RURAL: FMP do município (tabela INCRA, offline); `n_parcelas = floor(area_m2 / fmp_m2)`;
  flag "loteamento urbano exige conversão rural→urbano (perímetro urbano)".
- URBANO: `modalidade` (desmembramento, loteamento aberto, loteamento fechado, condomínio de
  lotes, condomínio edilício) capturada como rótulo; `lote_min_m2` declarado; bases de doação
  e fator de desmembramento como hoje; UI sinaliza lote **provisório**.

**Fora:**
- Upload/leitura da LUOS por LLM → **Fase 1.8** (não implementar agora).
- Regra de cálculo específica por modalidade → **Fase 1.8** (depende da LUOS).
- Classificação automática urbano/rural (perímetro urbano não é base nacional) → usuário declara.

## Fontes de dados (pipeline, offline — não agente)
| Dado | Fonte | Forma | Hospedagem |
|---|---|---|---|
| Malha geométrica | IBGE (nível intermediário) | shapefile (point-in-polygon) | volume Lightsail, pipeline |
| Lista leve | IBGE | `cod_ibge+nome+UF` (~150 KB) | **embarcada no repo** |
| FMP por município | INCRA (IE 5/2022, Anexo IV; CCIR) | tabela (ha) | volume/repo, a confirmar |

Todos **injetáveis nos testes** para a suíte rodar offline e determinística.

## Contrato

`POST /api/analises` — jurisdição real:
```
"jurisdicao": {
  "municipio": "São Roque" | null,
  "uf": "SP" | null,
  "cod_ibge": "3550605" | null,
  "origem": "detectado" | "aproximado" | "informado",
  "cruza_divisa": false,
  "candidatos": [ {cod_ibge, municipio, uf, pct_area} ]   // se cruza_divisa; ordenado desc
}
```

`GET /api/municipios?q=sao roque` — autocomplete por nome (lista leve; sem malha):
```
→ [ {cod_ibge:"3550605", municipio:"São Roque", uf:"SP"}, ... ]
```

`POST /api/analises/{id}/municipio` — aplicar correção/seleção:
```
{ "cod_ibge": "3550605" } → jurisdição com origem "informado"
```

`POST /api/analises/{id}/aproveitamento` — exige `regime`:
```
// RURAL
{ "regime":"RURAL", "fmp_m2":20000 }   // fmp puxado da tabela pelo cod_ibge; editável se ausente
→ { "rural": { "fmp_m2":20000, "n_parcelas":54, "area_m2":1094111.1,
               "fmp_origem":"tabela INCRA" | "default 2 ha (confirmar no CCIR)",
               "flag_conversao":"loteamento urbano exige conversão rural→urbano",
               "proveniencia":"FMP por município — Lei 5.868/72 art. 8º" } }

// URBANO
{ "regime":"URBANO", "modalidade":"loteamento_aberto",
  "lote_min_m2":200, "vias_m2":..., "doacao_pct":0.2,
  "base_doacao":"combinada", "combinado_pct":0.35, "fator_desmemb":0.74 }
→ { "desmembramento":{...}, "loteamento":{...},
    "premissa":"parcelamento URBANO (Lei 6.766)",
    "modalidade":"loteamento_aberto",   // rótulo
    "origem_lote":"declarado pelo usuário (provisório — extração da LUOS na Fase 1.8)" }
```
Sem `regime` → **422** (`regime_obrigatorio`); nunca assumir urbano calado.

## Frontend (inclui correções de tela observadas em teste)
- Jurisdição: mostra "Identificado: **São Roque/SP**" quando detectado; **campo de busca por
  NOME** (não código IBGE) com autocomplete; aviso visível se `cruza_divisa` com os % por
  município. Badge de origem (`detectado`/`aproximado`/`informado`).
- Aproveitamento: **primeiro** o toggle URBANO/RURAL.
  - RURAL → FMP do município, nº de parcelas, flag de conversão.
  - URBANO → **seletor de modalidade** (obrigatório) + campos; **rótulo visível** "lote mínimo
    declarado/provisório — leitura automática da LUOS por modalidade entra na Fase 1.8".
- Só render do JSON; nenhum cálculo no front.

## Critérios de aceite (valores-ouro, offline com malha/lista/FMP injetáveis)
1. **Detecção real**: KMZ sobre São Roque → detecta `São Roque/SP` automaticamente, `origem:
   "detectado"`, **com a malha real carregada** (não só fixture). Sem digitar nada.
2. **Busca por nome sem malha**: com a malha geométrica ausente, `GET /api/municipios?q=sao roque`
   ainda retorna São Roque (lista leve) — o plano B sobrevive.
3. **Correção**: aplicar `cod_ibge` via `/municipio` → `origem:"informado"`.
4. **Divisa**: polígono em 2 municípios → `cruza_divisa:true`, `candidatos` com `pct_area`
   ordenados desc, default no maior, exige confirmação.
5. **Borda**: ponto em gap de generalização → fallback nearest, `origem:"aproximado"` (não "não resolvido").
6. **RURAL — valor-ouro**: `n_parcelas = floor(area_m2 / fmp_m2_do_município)`. Para Bocaina
   (1.094.111,1 m²) com FMP de 2 ha → **54**; o teste lê a FMP da tabela injetada, não chumba 2 ha.
7. **FMP ausente**: município sem FMP na tabela → default 2 ha + `fmp_origem` = "default…confirmar no CCIR".
8. **URBANO**: regime urbano + modalidade + lote 200 m² → mantém os números das bases de doação
   da Fase 1 (não-regressão), com `premissa`, `modalidade` (rótulo) e `origem_lote` provisório.
9. **Sem regime** → 422 `regime_obrigatorio`.
10. **Proveniência** em toda saída (origem do município, regime, premissa, origem/ origem da FMP).
11. **Determinismo + offline**; **não-regressão** das Fases 1, 1.5 e 2.

## Restrições inegociáveis
- Pipeline (download+cache) para malha/lista/FMP; **nunca agente/LLM** nesta fase.
- Nunca assumir regime; nunca cravar município em silêncio; busca por **nome**, nunca exigir código.
- Rural usa **FMP** (não módulo fiscal, não 125 m²); sinaliza conversão para uso urbano.
- Divisa decidida por humano; proveniência e determinismo sempre.

## Definição de pronto
Os 11 critérios passam em `pytest` (offline); subir um KMZ de São Roque **detecta o município
sozinho**; a busca por nome funciona mesmo sem a malha; RURAL mostra ~54 parcelas pela FMP da
tabela; URBANO pede modalidade e marca o lote como provisório.
