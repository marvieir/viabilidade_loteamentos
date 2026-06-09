# Fase 3 — Pré-análise jurídica documental (dominial)

> **Substitui** a spec anterior `fase-3-juridica.md` (conformidade urbanística), que passa a
> ser a **Fase 3.5** (menor — ver §6). Esta é a "viabilidade jurídica" no sentido clássico
> (Aula 09): ler matrícula/certidões e sinalizar riscos dominiais. Referencia o
> `ARCHITECTURE.md` (seções 2, 4, 5) e **não o contradiz**. Reusa o motor de extração da 1.8.

## 0. O eixo (herdado da 1.8 — ler antes de tudo)

```
  EXTRAÇÃO (borda)                          LEITURA/CHECK (núcleo)
  ───────────────                           ──────────────────────
  LLM lê matrícula/certidão                 área-matrícula × área-KMZ (determinístico)
  → PROPÕE achados com citação              roll-up de risco (regra fixa)
    (ônus R-X, averbação Av-Y, página)      → o que está confirmado é determinístico
  → NÃO-determinístico                              ▲
  → NADA vira ficha sem "OK" humano                 │
        └──────── GATE HUMANO ─────────────────────┘
```

Mesma disciplina da 1.8: o LLM **lê e propõe**; o humano confirma; o número nunca passa por
LLM. É a **segunda aplicação** do `ExtratorLUOS` — generalizado para `ExtratorDocumento`.

## 1. Objetivo

Receber os documentos do imóvel (PDF), extrair e sinalizar — para **triagem** — o que pode
travar o negócio antes da due diligence cara:

- **Matrícula (RGI)** — núcleo: proprietário atual, área registrada, **ônus reais e gravames**
  (hipoteca, alienação fiduciária, penhora, arresto, usufruto, servidão, cláusulas de
  inalienabilidade/impenhorabilidade), **averbações** (APP, reserva legal, georreferenciamento,
  construções), **indisponibilidade**.
- **Certidões** (extensão) — negativas/positivas (RFB/PGFN, estadual, municipal, CNDT
  trabalhista, distribuidores cível/fiscal/criminal): classifica e extrai débitos/ações.
- **Cross-check determinístico** — **área da matrícula × área medida do KMZ**: divergência
  acima da tolerância é um alerta (vendedor pode estar vendendo área que não tem).

**Fronteira inegociável (mais rígida que a 1.8):**
- É **pré-análise**, não parecer. Extrai o que **consta** no documento; não opina sobre validade.
- **NUNCA afirmar "imóvel livre e desembaraçado".** Ausência de achado ≠ imóvel limpo — o
  documento pode estar incompleto ou desatualizado. O tool diz "constam os seguintes ônus:
  [...]" e "certidões apresentadas: [...]", sempre com "verificar com advogado / certidão
  atualizada". **Não certifica a ausência do que não foi carregado.**

## 2. O que NÃO muda (não-regressão)

- **NÃO altera o número do aproveitável** — dimensão de conformidade/risco, não de cálculo.
- Reusa a infra da 1.8 (extrator injetável, gate `proposto→confirmado`, proveniência, TLS/CA,
  credencial `ANTHROPIC_API_KEY` já existente — **sem credencial nova**).
- Suítes de 1, 1.5, 1.7, 1.8, 2, 2.1, 2.2, 2.3, 2.5 continuam verdes.

## 3. Como funciona

### 3.1 Extração (borda — reusa/generaliza a 1.8)
- `ExtratorDocumento` (interface injetável) com prompts **por tipo de documento**
  (`matricula`, `certidao`). Real = Claude API (PDF nativo + structured outputs / tool use
  forçado), **gated por `ANTHROPIC_API_KEY`**, desligável; **stub offline nos testes**.
- **Anti-alucinação:** achado não encontrado → ausente/`null`, **nunca inventado**. Todo achado
  proposto carrega **referência ao ato** (R-5, Av-3), **página** e, quando útil, **trecho
  verbatim**. Achado sem referência **não é confirmável**.
- PDF ilegível/escaneado → tenta visão/OCR; se falhar → erro honesto ("revise manualmente"),
  nunca chuta.

### 3.2 Gate humano (idêntico à 1.8)
- A ficha nasce `status: proposto` — **não entra em lugar nenhum**.
- Tela de revisão: cada achado com **referência ao ato + página + trecho**, editável; humano
  confirma/edita (`origem: editado_humano`)/rejeita.
- Ao confirmar: `status: confirmado` + `validado_por` + `data_referencia`; persiste por análise.

### 3.3 Cross-check de área (núcleo — determinístico)
```
divergencia_pct = |area_matricula_m2 − area_kmz_m2| / area_kmz_m2
status = "conforme" se divergencia_pct ≤ tol (default 5%); senão "atencao"
```
A `area_kmz_m2` é a que o motor já mede (Fase 1); a `area_matricula_m2` vem do achado
confirmado da matrícula. Determinístico, com proveniência das duas fontes.

### 3.4 Síntese de risco (roll-up determinístico — absorve a antiga decisão C)
Junta os achados dominiais **+** os alertas geo/ambientais já calculados (ANM/2.1, verde-em-APP/
2.3, ≥30%/2.5) numa leitura única:
- `alto` se houver ônus/indisponibilidade que trava transação **ou** divergência de área **ou**
  qualquer `vedado` geo (ANM, ≥30%);
- `medio` se só houver `atencao`;
- `baixo` se nada relevante consta **nos documentos apresentados** (com a ressalva de §1).

## 4. Contrato de API

### 4.1 `POST /api/analises/{id}/juridico/extrair` (multipart: `documento`, `tipo`)
Dispara a extração (LLM). Retorna **rascunho** (não persiste no check):
```jsonc
{
  "tipo": "matricula", "status": "proposto",
  "fonte_documento": "matricula_12345.pdf",
  "identificacao": {
    "matricula": { "valor": "12.345", "pagina": 1, "origem": "proposto_llm" },
    "cartorio":  { "valor": "1º RI de São Roque/SP", "pagina": 1 },
    "proprietario_atual": { "valor": "Fulano de Tal", "ato": "R-4", "pagina": 2 },
    "area_registrada_m2": { "valor": 78110, "pagina": 1, "origem": "proposto_llm" }
  },
  "onus": [
    { "tipo": "hipoteca", "descricao": "Hipoteca em favor do Banco X",
      "ato": "R-5", "pagina": 2, "situacao": "consta",
      "trecho": "...", "origem": "proposto_llm" }
  ],
  "averbacoes": [
    { "tipo": "reserva_legal", "descricao": "Averbação de reserva legal 20%",
      "ato": "Av-3", "pagina": 3, "origem": "proposto_llm" }
  ],
  "indisponibilidade": { "consta": false, "obs": "nenhuma indisponibilidade encontrada no documento apresentado" },
  "avisos": ["Cadeia dominial anterior a R-4 não analisada neste documento."]
}
```
Sem credencial → 503 honesto. PDF ilegível → 422 diagnóstico. (Para `tipo=certidao`, o schema
de saída troca para `{ orgao, especie, resultado: negativa|positiva, debitos[], acoes[] }`.)

### 4.2 `PUT /api/analises/{id}/juridico` — confirma a ficha
Recebe a ficha revisada/editada e persiste com `status: confirmado` + `validado_por` +
`data_referencia`. **Único** caminho que torna os achados utilizáveis no check/síntese.

### 4.3 `GET /api/analises/{id}/juridico` → `JuridicoDocumentalOut`
```jsonc
{
  "documentos": [ { "tipo": "matricula", "status": "confirmado", "fonte": "matricula_12345.pdf",
                    "validado_por": "<nome>", "data_referencia": "DD/MM/AAAA" } ],
  "onus": [ { "tipo": "hipoteca", "descricao": "...", "ato": "R-5", "situacao": "consta",
              "status": "atencao", "proveniencia": "Matrícula 12.345, R-5, p.2" } ],
  "averbacoes": [ { "tipo": "reserva_legal", "descricao": "...", "ato": "Av-3",
                    "proveniencia": "Matrícula 12.345, Av-3, p.3" } ],
  "area_check": { "area_matricula_m2": 78110, "area_kmz_m2": 78110, "divergencia_pct": 0.0,
                  "status": "conforme", "proveniencia": "Matrícula R-1 × medição KMZ (Fase 1)" },
  "certidoes": [ { "orgao": "PGFN/RFB", "especie": "negativa de débitos federais",
                   "resultado": "negativa", "status": "conforme" } ],
  "sintese_risco": {
    "nivel": "alto",
    "criticos": ["Hipoteca ativa (R-5)", "Sobreposição ANM", "1,47 ha em declividade ≥30%"],
    "atencao": ["Reserva legal averbada reduz área útil (Av-3)"],
    "resumo": "Constam ônus e restrições que exigem due diligence jurídica antes de avançar."
  },
  "proveniencia": "Achados confirmados (matrícula/certidões) + alertas geo (2.1/2.3/2.5)",
  "avisos": [
    "PRÉ-ANÁLISE — extrai o que CONSTA nos documentos apresentados; NÃO substitui parecer de advogado.",
    "Ausência de ônus na lista NÃO significa imóvel livre: depende dos documentos carregados e de certidões atualizadas.",
    "Cadeia dominial e certidões pessoais do vendedor devem ser verificadas por profissional."
  ]
}
```
Degradação: sem documento/confirmação → ficha vazia rotulada ("nenhum documento jurídico
analisado"); a síntese roda só com os alertas geo. **Nunca infere "limpo".**

## 5. Critérios de aceite (testáveis)

Stubs offline: extrator-stub (matrícula com 1 hipoteca R-5 + reserva legal Av-3 + área 78.110 m²)
+ alertas-stub (ANM, ≥30% 1,47 ha).

1. **Gate humano:** ficha `proposto` **não** alimenta check/síntese; só `confirmado` (com
   `validado_por`+`data_referencia`). Achado sem referência ao ato → **não confirmável** (422).
2. **Anti-alucinação:** achado ausente → não preenchido, **nunca inventado** (testado com
   extrator-stub que devolve campos vazios). `indisponibilidade.consta=false` é reportado como
   "não encontrado no documento", **não** como "imóvel disponível".
3. **NUNCA "livre e desembaraçado":** nenhuma saída afirma ausência de ônus como fato; os
   avisos de §4.3 estão **sempre** presentes.
4. **Extração injetável + offline:** `ExtratorDocumento` stub nos testes (sem rede, sem chave);
   real gated por `ANTHROPIC_API_KEY`; sem chave → 503, não quebra o app.
5. **Cross-check de área determinístico:** `divergencia_pct` calculado vs área do KMZ (Fase 1);
   ≤5% → `conforme`, >5% → `atencao`. Valor-ouro: matrícula 78.110 × KMZ 78.110 → 0%, `conforme`.
   (E um caso com matrícula 70.000 × KMZ 78.110 → ~10% → `atencao`.)
6. **Ônus/averbação com proveniência por ato:** cada item carrega `ato` (R-x/Av-y) + página +
   (matrícula nº). Hipoteca R-5 → `onus[hipoteca].status=atencao`, proveniência "Matrícula …, R-5".
7. **Síntese determinística (roll-up §3.4):** com hipoteca + ANM + ≥30% → `nivel="alto"`,
   `criticos` os lista. Sem nada relevante → `"baixo"` **com a ressalva** de §1.
8. **Certidão (extensão):** `tipo=certidao` extrai `resultado` negativa/positiva + débitos/ações;
   positiva → `status=atencao`.
9. **Determinismo + não-regressão:** check e síntese são puros sobre entradas injetadas; mesma
   entrada → mesma saída; **número do aproveitável inalterado**; suítes 1…2.5 verdes.
10. **Degradação honesta:** sem documento → ficha vazia rotulada; síntese só com alertas geo;
    nunca infere "limpo".

## 6. Fora de escopo (registrado)

- **Conformidade urbanística (antiga Fase 3 / candidato A)** — confrontar a gleba com os índices
  da LUOS que a 1.8 extraiu (`frente_min`, `ca`, `taxa_ocupacao`, `doacao_split`). Vira **Fase
  3.5 — Conformidade** (consumo puro, barata; spec já esboçada). Não some — só desce na fila.
- **Camada estadual** (órgão licenciador, lei estadual de lote mínimo, APA/manancial) — **Fase
  3.5+/Estadual** (dado novo); APA/manancial é geométrico → família ambiental (2.x).
- **Integração automática com registros** (ONR/SREI, CNIB de indisponibilidade, certidões
  online) — o MVP trabalha com **upload** do documento; integração com cartório/centrais é
  evolução (fora agora).
- **Parecer jurídico / decidir transação** — nunca; é pré-análise de triagem.
- **Validade/autenticidade do documento** (assinatura, atualização da certidão) — verificação
  externa; o tool só lê o conteúdo apresentado.

## 7. Arquivos esperados (latitude de implementação)

- `core/extrator_documento.py` — generaliza `ExtratorLUOS`: `ExtratorDocumento` (interface) +
  real Claude API (prompts por `tipo`) + stub; anti-alucinação no prompt.
- `core/juridico_documental.py` — cross-check de área + roll-up de risco (**puros**, sem I/O).
- `routers/juridico.py` — extrair (503/422) · PUT confirmar · GET ficha.
- `models/schemas.py` — `AchadoOnusOut`, `AverbacaoOut`, `AreaCheckOut`, `CertidaoOut`,
  `JuridicoDocumentalOut` (+ schemas de proposta).
- `core/perfil_*`/persistência — ficha jurídica por análise (volume, gitignored), padrão 1.8.
- Frontend: item **"Jurídico"** na sidebar + `CardJuridico` com **tela de revisão**
  (propor→editar→confirmar, referência ao ato ao lado) + ficha confirmada (ônus/averbações/
  área-check/certidões) + síntese de risco; reporta "Restrições críticas" ao KPI via `onData`.
  Sem overlay novo. Front só renderiza JSON (§2).
- Testes: `tests/test_juridico_documental.py` (extrator-stub + alertas-stub, offline).

A spec fixa **contrato + critérios**; o resto é latitude. **Sem credencial nova** (reusa a da
1.8), **sem I/O geográfico novo** — extração assistida (borda) + checks determinísticos (núcleo).
