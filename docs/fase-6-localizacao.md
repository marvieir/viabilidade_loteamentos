# Fase 6 — Localização (enriquecimento socioeconômico IBGE)

> Dimensão **puramente informativa**: contexto socioeconômico do município da gleba.
> **Não entra em nenhum cálculo** (aproveitamento/financeira/econômica intactos).
> Referencia `ARCHITECTURE.md` (§1-A, §2, §4) e respeita as decisões do operador
> (handoff §0: **4 indicadores no MVP**). **Sem LLM, sem rede em runtime** — dado
> estático embarcado, padrão da lista leve IBGE.

## 1. Objetivo

Dado o `cod_ibge` da análise (resolvido pela 1.7), exibir os **4 indicadores** decididos:

1. **População** — Censo 2022 + densidade (hab/km²) + **crescimento 2010→2022**
   (variação total % e média anual geométrica).
2. **Renda** — **PIB per capita** (IBGE, PIB dos Municípios, ano mais recente do recorte).
3. **Habitação** — **déficit habitacional (FJP)** quando disponível; **fallback rotulado**
   para domicílios ocupados + moradores/domicílio (Censo 2022).
4. **Faixa etária** — distribuição em 4 grupos (0–14 · 15–29 · 30–59 · 60+), % do Censo 2022.

Cada indicador com **comparação município × UF × Brasil** (decisão §3.6 — incluída no MVP)
e **leituras informativas** §1-A (sinal, nunca veredito de mercado).

## 2. O que NÃO muda (não-regressão)

- **Nenhum número desta fase alimenta cálculo algum** — aproveitamento, financeira e
  econômica idênticos antes/depois (testado). É card de contexto.
- Sem rede em runtime, sem credencial, sem LLM. Suítes 1…5 verdes.
- Sem perfil/jurisdição resolvida → degrada honesto (padrão do projeto).

## 3. Decisões dos pontos vetáveis (§3 do handoff)

1. **Fontes por indicador (a proveniência de cada um):**
   | Indicador | Fonte | Ano |
   |---|---|---|
   | População / densidade / domicílios / moradores·dom / faixa etária | **IBGE Censo Demográfico** (SIDRA) | 2022 |
   | População base do crescimento | IBGE Censo | 2010 |
   | PIB per capita | **IBGE — PIB dos Municípios** | mais recente do recorte (2023 hoje) |
   | Déficit habitacional | **Fundação João Pinheiro (FJP)** — Déficit Habitacional Municipal | ano da edição FJP no recorte |
2. **Déficit habitacional — o espinhoso:** o Censo **não** o entrega; a FJP publica com
   cobertura e ano que variam. **FJP, não MUNIC** (o handoff cita as duas): a MUNIC/IBGE
   traz gestão municipal (existência de cadastro habitacional, órgão, plano), não o número
   do déficit — a fonte canônica do déficit é a FJP. Regra: se o município está no recorte
   FJP → exibe valor + `fonte: "FJP", ano`; **se não está → `deficit: null`** + exibe o
   **fallback de estoque** (domicílios ocupados + moradores/domicílio, Censo 2022) com o
   rótulo *"déficit FJP indisponível para este município — exibindo estoque de domicílios
   (Censo 2022) como referência; não é o déficit"*. **Nunca estimar/inventar o déficit.**
3. **Formato/local do arquivo:** **embarcado no repo** (padrão lista leve, não volume) —
   o dado é decenal/estável e o produto deve funcionar offline desde o deploy. Um
   `localizacao_municipios.json(.gz)` com ~5.570 municípios + **27 UFs + Brasil** (para a
   comparação), ~10 campos por linha (≈1–3 MB ok; gzip se passar). Gerado por
   `scripts/gerar_localizacao_ibge.py` (pipeline SIDRA/FJP → JSON, **roda offline do
   runtime**, commitado com `data_geracao` e fontes no cabeçalho do arquivo).
4. **Crescimento populacional:** CAGR geométrico `(P2022/P2010)^(1/12) − 1` (12 anos entre
   censos) exibido como **% a.a.**, junto da **variação total %** — os dois, porque o CAGR
   sozinho esconde a magnitude em prazos longos.
5. **Cobertura/degradação por indicador:** cada bloco tem `disponivel: bool` + aviso
   próprio ("dado indisponível na fonte X para este município"); município não resolvido →
   `avaliada=false` + motivo acionável ("resolva o município na análise"). Sempre 200.
6. **Comparação UF/Brasil: SIM no MVP.** Custa 28 linhas a mais no arquivo e transforma
   número solto em leitura ("PIB per capita 39% abaixo da média estadual"). Razões
   **calculadas no backend** (`vs_uf`, `vs_brasil` como fração), rotuladas informativas.
7. **Persistência: NÃO persiste** (resposta ao §3 do handoff). O GET recalcula do arquivo
   embarcado a cada chamada — é determinístico sobre dado estático; persistir por análise
   seria cópia redundante de um dado que não varia por usuário. (Difere de premissas
   financeiras, que são do usuário.)
8. **`_fmt` em TODO número formatável** (§2/§4 do handoff): população (`79.484`), densidade
   (`258,98 hab/km²`), percentuais (`0,84%`), moeda (`R$ 57.024,90`) — todos com par
   `valor` + `valor_fmt` pt-BR gerados no backend; o front só renderiza.

## 4. Contrato de API

### `GET /api/analises/{id}/localizacao` → `LocalizacaoOut`
```jsonc
{
  "avaliada": true,
  "cobertura": "COMPLETA",                 // COMPLETA = 4 blocos | PARCIAL = faltou algum (lista em avisos) | INDISPONIVEL = município fora do arquivo
  "municipio": { "cod_ibge": "3550605", "nome": "São Roque", "uf": "SP" },
  "populacao": {
    "disponivel": true,
    "censo_2022": 79484, "censo_2010": 78821,
    "crescimento_total_pct": 0.0084, "crescimento_aa_pct": 0.0007,   // CAGR 12 anos
    "densidade_hab_km2": 258.98, "area_km2": 306.9,
    "vs_uf": 0.0018,                       // fração da população da UF (informativo)
    "fonte": "IBGE Censo 2022/2010",
    "leitura": "Crescimento de 0,84% em 12 anos (≈0,07% a.a.) — bem abaixo da média estadual; sinal de demanda demográfica fraca SOB OS DADOS CENSITÁRIOS."
  },
  "renda": {
    "disponivel": true,
    "pib_per_capita": 57024.90, "pib_per_capita_fmt": "R$ 57.024,90", "ano": 2023,
    "vs_uf": 0.xx, "vs_brasil": 1.xx,
    "fonte": "IBGE — PIB dos Municípios 2023",
    "leitura": "PIB per capita de R$ 57.024,90 — XX% da média estadual."
  },
  "habitacao": {
    "disponivel": true,
    "deficit": null,                        // ou { "valor": N, "fonte": "FJP", "ano": AAAA }
    "fallback_estoque": { "domicilios_ocupados": 28490, "moradores_por_domicilio": 2.79,
                          "fonte": "IBGE Censo 2022" },
    "aviso": "Déficit FJP indisponível para este município — exibindo estoque de domicílios (Censo 2022); NÃO é o déficit."
  },
  "faixa_etaria": {
    "disponivel": true, "fonte": "IBGE Censo 2022",
    "grupos": [ { "faixa": "0-14", "pct": 0.xx }, { "faixa": "15-29", "pct": 0.xx },
                { "faixa": "30-59", "pct": 0.xx }, { "faixa": "60+", "pct": 0.xx } ]
  },
  "proveniencia": "Arquivo embarcado localizacao_municipios.json — gerado em DD/MM/AAAA de IBGE SIDRA (Censo 2022/2010, PIB Municípios) e FJP",
  "avisos": ["Enriquecimento INFORMATIVO (§1-A): contexto socioeconômico do município — não entra em nenhum cálculo de viabilidade e não é análise de mercado."]
}
```

## 5. Critérios de aceite (valores-ouro **São Roque/SP — 3550605**, fonte IBGE)

1. **População-ouro:** `censo_2022 = 79.484`, `censo_2010 = 78.821`,
   `crescimento_total ≈ 0,84%`, `CAGR ≈ 0,07% a.a.` (±0,01 p.p.),
   `densidade = 258,98 hab/km²`.
2. **Renda-ouro:** `pib_per_capita = R$ 57.024,90` (ano 2023), `_fmt` pt-BR no backend;
   `vs_uf`/`vs_brasil` presentes e = razão exata contra as linhas UF/Brasil do arquivo.
3. **Habitação:** município **no** recorte FJP → `deficit{valor,fonte,ano}` preenchido;
   **fora** do recorte → `deficit=null` + `fallback_estoque` (Censo 2022) + o aviso "NÃO é
   o déficit". Moradores/domicílio de São Roque ≈ **2,79** (±0,01). **Nunca** déficit
   estimado/inventado (teste: município sem FJP no fixture → null, não número).
4. **Faixa etária:** 4 grupos com `Σ pct = 1` (±0,001), fonte Censo 2022. **Ouro de segunda
   geração:** os % exatos de São Roque não são cravados nesta spec (sem fonte agregada
   confiável à mão — não se inventa ouro); o **pipeline os crava na primeira geração
   validada** (extrai do SIDRA, confere Σ=1 e grava os quatro % no teste como ouro
   definitivo, com a tabela SIDRA citada na proveniência).
5. **Comparação:** razões `vs_uf`/`vs_brasil` calculadas **no backend** a partir das linhas
   UF/Brasil do mesmo arquivo (sem chamada externa); ausência da linha → comparação omitida
   com aviso (não inventa média).
6. **Offline + embarcado:** endpoint funciona **sem rede** (arquivo no repo); o pipeline
   `gerar_localizacao_ibge.py` regrava o arquivo com `data_geracao` + fontes e **valida os
   ouros de São Roque** antes de aceitar o arquivo gerado.
7. **Degradação:** município não resolvido → `avaliada=false` + motivo; indicador ausente
   no arquivo → `disponivel=false` + aviso por bloco; sempre 200.
8. **Informativo de verdade:** aproveitamento/financeira/econômica **byte a byte** com e
   sem a Fase 6 ativa; **nenhum campo desta fase é lido por outro router**.
9. **Linguagem §1-A:** `leituras` usam "sob os dados censitários"/"sinal"; **regex: sem
   "viável"/"inviável"** e sem recomendação de investimento; aviso informativo fixo presente.
10. **Determinismo + não-regressão:** mesma análise → mesma resposta; suítes 1…5 verdes.

## 6. Fora de escopo (registrado)

- **Rendimento domiciliar per capita / IDHM / emprego formal** — indicadores extras =
  evolução (o arquivo/pipeline já nasce extensível por coluna).
- **Análise mercadológica** (concorrentes, preço de lote na região, velocidade de vendas)
  — é a dimensão **Mercadológica** (Fase 7+), com busca; aqui é só dado censitário.
- **Setor censitário / raio de influência / microlocalização** (entorno da gleba, POIs,
  acesso) — evolução geoespacial; o MVP é **nível-município** (decisão fixada no handoff §1).
- **Projeções populacionais futuras** — só dado observado (Censos + PIB); projetar é
  julgamento externo.

## 7. Arquivos esperados (latitude de implementação)

- `backend/app/dados/localizacao_municipios.json(.gz)` — embarcado (municípios + UFs +
  Brasil; cabeçalho com fontes e `data_geracao`).
- `scripts/gerar_localizacao_ibge.py` — pipeline SIDRA/PIB-Municípios/FJP → JSON (roda
  fora do runtime; valida os ouros de São Roque).
- `core/localizacao.py` — leitura do arquivo + razões UF/Brasil + leituras (puro).
- `routers/localizacao.py` — `GET /analises/{id}/localizacao`.
- `models/schemas.py` — `PopulacaoOut`, `RendaOut`, `HabitacaoOut`, `FaixaEtariaOut`,
  `LocalizacaoOut`.
- Frontend: item "Localização" na sidebar + `CardLocalizacao` (4 blocos com badge de fonte
  +ano; comparações UF/Brasil; gráfico simples da faixa etária; avisos §1-A). Sem cálculo
  no front.
- Testes: `tests/test_localizacao.py` (fixture-arquivo com São Roque + UF + Brasil +
  município-sem-FJP; ouros 1–10, offline).

A spec fixa **contrato + critérios**; o resto é latitude. **Sem LLM, sem rede em runtime**
— leitura de arquivo embarcado + razões determinísticas, com fonte e ano em cada número.
