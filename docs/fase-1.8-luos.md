# Fase 1.8 — Extração assistida da LUOS (perfil municipal)

> Reintroduz **lote mínimo legal** e **doação** no número, a partir da diretriz municipal.
> Referencia o `ARCHITECTURE.md` (seções 0, 2, 4, 5, 6-A) e **não o contradiz**.
> **É a fase de maior risco — a única com LLM no caminho de leitura.** O checklist de aceite
> é deliberadamente apertado.

## 0. O eixo que organiza esta fase (ler antes de tudo)

```
  EXTRAÇÃO (borda)                          CÁLCULO (núcleo)
  ───────────────                           ────────────────
  LLM lê o PDF da LUOS                       consome o PERFIL CONFIRMADO
  → PROPÕE índices por zona/modalidade       → desconta doação, usa lote legal
  → NÃO-determinístico                        → 100% determinístico
  → cada valor com citação (artigo/página)    → mesma entrada = mesma saída
  → NADA entra no cálculo sem "OK" humano     → proveniência em todo número
        │                                              ▲
        └──────── CONFIRMAÇÃO HUMANA (gate) ───────────┘
```

Determinismo (ARCHITECTURE §2) **se aplica ao cálculo**, dado um perfil confirmado. A
extração é explicitamente não-determinística e por isso **travada por confirmação humana**
antes de tocar qualquer número. Quem garante a correção não é o LLM — é o humano que confirma
contra a citação. O LLM **lê e propõe**; nunca decide.

## 1. Objetivo

Hoje (1.7) o regime URBANO usa **lote mínimo declarado** pelo usuário e **doação não entra**
no número (modalidade é só rótulo). Esta fase:

1. Recebe o **PDF da LUOS / lei de parcelamento / diretriz municipal** (upload).
2. Usa LLM para **extrair, por zona (e por modalidade quando a LUOS diferencia)**: lote mínimo
   legal, frente mínima, **% de doação + base + split** (viário/verde/institucional), e índices
   extras (CA, taxa de ocupação, recuos, usos) como dados de perfil.
3. Apresenta cada valor proposto **com a citação ao lado** para **revisão humana item-a-item**
   (propor → editar → confirmar).
4. Persiste o **perfil municipal confirmado** por `cod_ibge`, elevando a cobertura da jurisdição
   e **reintroduzindo doação + lote legal** no aproveitamento.

## 2. O que NÃO muda (não-regressão)

- O **aproveitável físico-ambiental** (`total − união(mata ∪ APP ∪ faixas)`, da 2.2) **não
  muda** — doação é uma **redução adicional sobre ele**, não um recálculo.
- Os cenários da 2.3 (severidade do verde, otimista) permanecem.
- Sem perfil confirmado, o comportamento é **exatamente o da 1.7** (lote declarado, sem doação),
  rotulado "perfil municipal não carregado".
- Suítes de 1, 1.5, 1.7, 2, 2.1, 2.2, 2.3 continuam verdes.

## 3. Como funciona

### 3.1 O problema da zona (decisão de arquitetura)
A LUOS define índices **por zona** (ZR1, ZM2, ZEIS…), não por município inteiro. **Não temos
zoneamento geométrico municipal** (os polígonos das zonas). Logo:

- A extração produz uma **tabela de zonas** com seus índices.
- Na análise da gleba, o usuário **declara a zona** (dropdown das zonas extraídas — ele a obtém
  na consulta de zoneamento da prefeitura). O motor usa os índices daquela zona.
- O **cruzamento geométrico automático** (gleba × polígono de zona) é **fase futura** — fora
  do escopo aqui.

### 3.2 Extração (borda — injetável, gated por credencial)
- Interface `ExtratorLUOS` (injetável); impl real `ExtratorLUOSClaude` (Claude API — **primeira
  credencial de LLM do projeto**, atrás de env; opcional e desligável). Testes usam **stub**
  (sem rede, sem chave).
- Aceita **PDF texto e escaneado** (o modelo lê o PDF nativamente / via visão; OCR como fallback).
  PDF ilegível → **falha honesta** ("não foi possível extrair — revise manualmente"), nunca chuta.
- **Regra anti-alucinação no prompt:** índice ausente → retorna `null`/"não encontrado", **jamais
  um número inventado**. Cada valor proposto **deve** vir com `artigo/inciso`, `página` e um
  **trecho verbatim** da LUOS. Valor sem citação não é confirmável.
- LUOS longa (100+ pgs): extração pode ser por capítulo/zona (latitude de implementação).

### 3.3 Confirmação humana (gate determinístico)
- O perfil nasce com `status: "proposto"`. **Nada com status proposto entra no cálculo.**
- Tela de revisão: cada parâmetro mostra **valor + artigo + página + trecho verbatim**,
  **editável**; o humano confirma, edita (vira `origem: "editado_humano"`) ou rejeita.
- Ao confirmar o conjunto, `status: "confirmado"` + `validado_por` + `data_referencia`; persiste.

### 3.4 Cálculo com diretriz (núcleo — determinístico)
Dado perfil **confirmado** + zona + modalidade:
```
aproveitavel_fisico   = total − união(mata ∪ APP ∪ faixas)        # da 2.2, inalterado
doacao_pct, base      = índice da zona (ou override da modalidade; pode ser 0)
doacao_m2             = aplica (base total/líquida/combinada) conforme a LUOS
aproveitavel_diretriz = aproveitavel_fisico − doacao_m2
lote_min              = lote_min_LEGAL da zona  (substitui o declarado)
n_lotes               = floor(aproveitavel_diretriz / lote_min)
```
**Modalidade volta a ter regra:** se a LUOS isenta de doação (ex.: desmembramento que usa viário
existente; condomínio com regime próprio), `doacao_pct = 0` aplicado corretamente — e **0 é
válido** (não confundir com "não considerado").

## 4. Contratos de API

### 4.1 `POST /api/municipios/{cod_ibge}/perfil/extrair` (multipart: `pdf`)
Dispara a extração (LLM). Retorna **rascunho** (não persiste no cálculo):
```jsonc
{
  "cod_ibge": "3550605", "municipio": "São Roque", "uf": "SP",
  "status": "proposto",
  "fonte_documento": "luos_sao_roque.pdf",
  "zonas": [{
    "codigo": "ZR1", "descricao": "Zona Residencial 1",
    "params": {
      "lote_min_m2":  { "valor": 250, "artigo": "Art. 12, I",  "pagina": 8,  "trecho": "lote mínimo de 250 m²", "origem": "proposto_llm" },
      "frente_min_m": { "valor": 10,  "artigo": "Art. 12, II", "pagina": 8,  "trecho": "...", "origem": "proposto_llm" },
      "doacao_pct":   { "valor": 0.35, "base": "total", "artigo": "Art. 20", "pagina": 14, "trecho": "...", "origem": "proposto_llm" },
      "doacao_split": { "viario": 0.20, "verde": 0.10, "institucional": 0.05, "artigo": "Art. 20, §1º", "pagina": 14 }
      // CA, taxa_ocupacao, recuos, usos: opcionais, mesmo formato com citação
    },
    "modalidades": {           // overrides opcionais quando a LUOS diferencia
      "desmembramento": { "doacao_pct": { "valor": 0.0, "artigo": "Art. 22", "pagina": 15 } }
    }
  }],
  "avisos": ["Art. 18 cita ZEIS sem índices numéricos — revisar manualmente"]
}
```
Sem chave de LLM configurada → 503 honesto ("extração assistida indisponível — configure a
credencial ou cadastre o perfil manualmente"). PDF ilegível → 422 diagnóstico.

### 4.2 `PUT /api/municipios/{cod_ibge}/perfil`
Recebe o perfil **revisado/editado** e persiste com `status: "confirmado"`, `validado_por`,
`data_referencia`. É o **único caminho** que torna um perfil utilizável no cálculo.

### 4.3 `GET /api/municipios/{cod_ibge}/perfil`
Retorna o perfil confirmado (ou `null`/404 se não houver). Recarregável em análises futuras
**sem re-extrair**.

### 4.4 `POST /api/analises/{id}/aproveitamento` — estendido
Aceita `zona` (quando há perfil). Acrescenta `cenario_diretriz` (headline **inalterado**):
```jsonc
{
  // ... headline físico-ambiental + cenários 2.3, todos inalterados ...
  "cenario_diretriz": {                 // null se sem perfil confirmado p/ a zona
    "zona": "ZR1",
    "lote_min_m2_legal": 250,           // substitui o declarado
    "doacao_pct": 0.35, "doacao_base": "total", "doacao_m2": 8400.0,
    "area_aproveitavel_m2": /* fisico − doacao */, "pct_sobre_total": 0.xx,
    "n_lotes": /* floor(aprov_diretriz / lote_legal) */,
    "proveniencia": "Perfil São Roque · LUOS Lei X/AAAA · validado por <nome> em DD/MM · lote Art.12 I p.8 · doação Art.20 p.14",
    "ressalva": "Aplica lote legal e doação mínima legal da ZONA DECLARADA. Vias/lazer reais e a aprovação do projeto seguem fora da triagem (projeto urbanístico + prefeitura)."
  }
}
```

## 5. Critérios de aceite (testáveis — checklist apertado)

1. **Gate humano:** perfil tem `status` proposto → confirmado; **só "confirmado" alimenta o
   cálculo**. Perfil só-proposto (ou ausente) → aproveitamento mantém o comportamento 1.7
   (lote declarado, sem doação), rotulado "perfil municipal não carregado".
2. **Proveniência por parâmetro:** todo valor confirmado carrega `artigo/inciso` + `página` +
   `trecho` verbatim + `origem` (`proposto_llm`|`editado_humano`) + `validado_por` + `data`.
   Valor sem citação **não é confirmável**.
3. **LLM nunca inventa:** índice ausente na LUOS → `null`/"não encontrado", nunca número
   chutado. Testado com **stub** de extrator que devolve campos ausentes → o perfil os marca
   como pendentes, não preenche.
4. **Extração injetável + offline:** interface `ExtratorLUOS`; testes com stub (sem rede, sem
   chave). O caminho real (Claude API) fica atrás da interface, gated por env. Sem chave → 503
   honesto (não quebra o resto do app).
5. **Determinismo do cálculo:** dado perfil **confirmado** + zona + modalidade, o
   `cenario_diretriz` é sempre o mesmo número, com proveniência. (A extração é não-determinística
   e **não** é coberta por este critério — é coberta pelo gate humano.)
6. **Perfil por zona:** perfil = tabela de zonas; a análise **seleciona a zona declarada**
   (cruzamento geométrico é fora de escopo). Zona inexistente no perfil → `cenario_diretriz=null`
   + aviso, sem inventar.
7. **Modalidade com regra + doação 0 válida:** doação/lote efetivos resolvidos por (zona,
   modalidade); modalidade isenta de doação → `doacao_pct=0` aplicado (e distinto de "não
   considerado"). Valor-ouro: zona com doação 35% base "total" sobre `aproveitavel_fisico`
   conhecido → `doacao_m2` e `n_lotes` confiram com cálculo manual (teste determinístico com
   perfil-stub confirmado).
8. **Headline inalterado (não-regressão 2.2/2.3):** `area_aproveitavel_m2` físico e os cenários
   da 2.3 não mudam. `cenario_diretriz` é **aditivo**: aproveitável_diretriz = físico − doação
   (nunca recalcula o físico). [Ver decisão vetável §7.]
9. **Persistência por município:** perfil confirmado persiste por `cod_ibge` em volume (JSON
   injetável via `FontePerfilMunicipal`), com `data_referencia`/`validado_por`; recarregável sem
   re-extrair; eleva cobertura da jurisdição para a zona (`PARCIAL_UF`→`COMPLETA`).
10. **Degradação honesta:** sem PDF / sem confirmação / PDF ilegível → comportamento 1.7
    rotulado; **nunca inventa índice de LUOS**.
11. **Não-regressão geral:** suítes de 1, 1.5, 1.7, 2, 2.1, 2.2, 2.3 verdes.

## 6. Decisões de produto vetáveis

- **(A) "Com diretriz" = segundo cenário, não troca o headline.** *Recomendado.* O headline
  segue sendo o teto físico-ambiental (estável, sempre computável); o `cenario_diretriz` aparece
  como refinamento quando há perfil — **mesmo padrão da 2.3** (que adicionou o otimista sem
  trocar o headline). Alternativa vetável: fazer o "com diretriz" virar o headline quando existir
  perfil confirmado. Recomendo manter o padrão por consistência e auditabilidade.
- **(B) Extração rica, aceite focado no número.** O LLM extrai o conjunto completo (lote, frente,
  doação, CA, recuos, usos — está lendo de qualquer forma), mas os **critérios de aceite gateiam
  só os parâmetros que entram no número** (lote legal + doação). O resto persiste como dado de
  perfil para a dimensão Jurídica (Fase 3). Evita over-engineering no que ainda não é consumido.
- **(C) Provider do LLM = Claude API.** Atrás da interface, trocável. Confiança de número vem do
  gate humano, não do provider.

## 7. Fora de escopo (registrado)

- **Cruzamento geométrico gleba × zona** (zoneamento vetorial municipal) — zona é **declarada**;
  geométrico é fase futura.
- **O LLM julgar se a gleba "atende" à norma** — não. Ele **só extrai índices**; a comparação
  (gleba × índice) é determinística, no backend, depois.
- **Vias/lazer reais** (geometria do projeto urbanístico) e **aprovação municipal** (art. 6º Lei
  6.766) — seguem fora da triagem.
- **Classificação de mata / declividade** — outras fases (2.3 já fechada / 2.5).

## 8. Arquivos esperados (latitude de implementação)

- `core/perfil_municipal.py` — schema (Zona, ParamComProveniencia, PerfilMunicipal) +
  `FontePerfilMunicipal` (interface injetável: carregar/salvar por `cod_ibge`).
- `core/extrator_luos.py` — `ExtratorLUOS` (interface), `ExtratorLUOSClaude` (real, gated),
  stub de teste; regra anti-alucinação no prompt.
- `core/aproveitamento.py` — função determinística `cenario_diretriz(perfil, zona, modalidade,
  aproveitavel_fisico)`.
- `routers/perfil.py` — extrair / confirmar (PUT) / get.
- `routers/analises.py` — estende aproveitamento com `zona` + `cenario_diretriz`.
- Frontend: **tela de revisão do perfil** (propor→editar→confirmar, citação + trecho ao lado de
  cada valor); **seletor de zona** no card de aproveitamento; **card do cenário diretriz** com
  proveniência e ressalva.

> **Credencial:** esta fase introduz a **primeira chave de LLM** (Claude API), necessária só
> para o extrator real; testes e stub não precisam dela. A IA fica na borda (leitura), nunca no
> caminho do número (ARCHITECTURE §2).
