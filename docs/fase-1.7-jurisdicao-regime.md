# Fase 1.7 — Jurisdição real + Regime (urbano/rural) + Rural (FMP)

> Pré-requisito de leitura: `ARCHITECTURE.md` e `CLAUDE.md`.
> Fase **corretiva**. Resolve a falha detectada em teste real (gleba rural de 109 ha
> recebeu cálculo de loteamento urbano em silêncio). Determinística, **sem LLM**
> (a extração da LUOS é a Fase 1.8).

## Problema que corrige
O aproveitamento assumia parcelamento **urbano** (lote 200 m² + doação, Lei 6.766) sem
declarar, e a jurisdição não era resolvida (stub → `null`). Em terra **rural** isso é
inválido: o piso é a **FMP/módulo fiscal do município** (INCRA, ~2 ha), não 125 m². Lote
urbano só é possível se a gleba está no **perímetro urbano**.

## Objetivo
1. Resolver **município/UF reais** a partir do KMZ (point-in-polygon na malha IBGE),
   com **detecção + override** e alerta de divisa.
2. Introduzir **regime** (`URBANO` | `RURAL`) no início do aproveitamento.
3. **RURAL** → calcular contra a **FMP do município**; sinalizar conversão rural→urbano.
4. **URBANO** → manter as regras atuais, com lote mínimo **declarado** no interino e a
   premissa sempre explícita na proveniência.

## Escopo

**Dentro:**
- Resolvedor IBGE real (promove o stub da Fase 1): malha municipal IBGE carregada offline;
  point-in-polygon do centróide → `{municipio, uf, cod_ibge}`.
- Detecção com override: campo de busca/autocomplete sobre a lista IBGE local; proveniência
  `detectado` vs `informado`.
- Alerta de divisa: se o **polígono inteiro** intersecta >1 município → `cruza_divisa: true`
  + lista de candidatos + pede confirmação.
- Centróide fora de qualquer município → `municipio: null`, exige seleção manual (sem inventar).
- Regime obrigatório no aproveitamento; premissa declarada na proveniência.
- RURAL: tabela módulo fiscal/FMP por município (INCRA/EMBRAPA, offline). Parcelas rurais =
  `floor(area / FMP_m2)`; flag "loteamento urbano exige conversão (perímetro urbano)".
- URBANO: pergunta `modalidade` (desmembramento, loteamento aberto, loteamento fechado,
  condomínio de lotes, condomínio edilício); `lote_min_m2` **declarado** (proveniência
  "declarado pelo usuário — pendente extração da LUOS, Fase 1.8"); aplica bases de doação
  (loteamento) ou fator (desmembramento), como hoje.

**Fora:**
- Extração assistida da LUOS por LLM → **Fase 1.8**.
- Classificação automática urbano/rural (perímetro urbano municipal não é base nacional
  estruturada) → o usuário **declara** o regime; auto-classificação fica futura.

## Fontes de dados (pipeline, offline — não agente)
| Dado | Fonte | Forma | Credencial |
|---|---|---|---|
| Malha municipal | IBGE | shapefile nacional (point-in-polygon) | não |
| Módulo fiscal / FMP | INCRA (via EMBRAPA) | tabela por município (ha) | não |

Ambos carregados uma vez e cacheados. **Injetáveis nos testes** (padrão do stub de
jurisdição da Fase 1) para a suíte rodar offline e determinística.

## Contrato

`POST /api/analises` — jurisdição agora real:
```
"jurisdicao": {
  "municipio": "Bocaina" | null,
  "uf": "SP" | null,
  "cod_ibge": "...",
  "origem": "detectado" | "informado",
  "cruza_divisa": false,
  "municipios_candidatos": [ {cod_ibge, municipio, uf}, ... ]   // se cruza_divisa
}
```

`POST /api/analises/{id}/municipio` — correção/seleção manual:
```
{ "cod_ibge": "..." } → atualiza jurisdição com origem "informado"
```

`POST /api/analises/{id}/aproveitamento` — agora exige `regime`:
```
{ "regime": "RURAL",
  "fmp_m2": 20000 }            // puxado da tabela; editável se município não resolvido
→ { "rural": { "fmp_m2": 20000, "n_parcelas": 54, "area_m2": 1094111.1,
               "flag_conversao": "loteamento urbano exige conversão rural→urbano",
               "proveniencia": "FMP/módulo fiscal do município (INCRA)" } }

{ "regime": "URBANO",
  "modalidade": "loteamento_aberto",
  "lote_min_m2": 200, "vias_m2": ..., "doacao_pct": 0.2,
  "base_doacao": "combinada", "combinado_pct": 0.35, "fator_desmemb": 0.74 }
→ { "desmembramento": {...}, "loteamento": {...},
    "premissa": "parcelamento URBANO (Lei 6.766)",
    "origem_lote": "declarado pelo usuário (pendente LUOS — Fase 1.8)" }
```
Sem `regime` → **422** (`regime_obrigatorio`); nunca assumir urbano calado.

## Frontend
- Após upload: card de jurisdição mostra "Identificado: **Bocaina/SP**" + botão/área
  "corrigir município" (autocomplete local). Aviso visível se `cruza_divisa`.
- Aproveitamento: primeiro pergunta **URBANO ou RURAL**.
  - RURAL → mostra FMP do município, nº de parcelas e o flag de conversão.
  - URBANO → escolhe modalidade + informa lote mínimo (campo), com nota "pendente LUOS".
- Toda saída exibe a **premissa** e a **origem** (município detectado/informado;
  lote declarado/extraído). Sem cálculo no front.

## Critérios de aceite (valores-ouro, offline com malha/FMP injetáveis)
1. **Bocaina** (centróide −45,72 / −22,64) → resolve o município correto, UF `SP`,
   `origem: "detectado"`.
2. **Correção** via `/municipio` → `origem: "informado"`, jurisdição atualizada.
3. **Divisa**: polígono que cruza 2 municípios (fixture) → `cruza_divisa: true` +
   `municipios_candidatos` + aviso.
4. **Fora da malha**: centróide sem município → `municipio: null`, exige seleção, sem inventar.
5. **RURAL** com FMP de 2 ha sobre 109,41 ha → `n_parcelas = 54` (`floor(1.094.111 / 20.000)`)
   + flag de conversão + sem doação. **Valor-ouro.**
6. **URBANO** loteamento, lote 200 m² → mantém os números das bases de doação da Fase 1
   (não-regressão), agora com `premissa` e `origem_lote` declarados.
7. **Sem regime** → 422 `regime_obrigatorio`; nunca assume urbano.
8. **Proveniência**: toda saída traz regime, origem do município e origem do lote.
9. **Determinismo + offline** (malha e FMP injetadas; sem rede).
10. **Não-regressão** das Fases 1, 1.5 e 2.

## Restrições inegociáveis
- Pipeline (download+cache) para malha e FMP; **nunca agente/LLM** nesta fase.
- Nunca assumir regime; nunca cravar município em silêncio (detecção com override).
- Rural usa FMP, não 125 m²; sinaliza conversão para uso urbano.
- Proveniência e determinismo sempre.

## Definição de pronto
Os 10 critérios passam em `pytest` (offline); subir a Bocaina mostra município
detectado com opção de corrigir; escolher RURAL mostra ~54 parcelas pela FMP; escolher
URBANO pede modalidade + lote e calcula com a premissa declarada.
