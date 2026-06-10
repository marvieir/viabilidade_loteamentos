# Fase 3.5 — Conformidade urbanística (consumo puro do perfil da 1.8)

> Era a antiga "Fase 3" (candidato A do handoff); desceu na fila quando a sessão de spec
> decidiu que a Fase 3 seria a **pré-análise jurídica documental**. Referencia o
> `ARCHITECTURE.md` (seções 2, 4) e **não o contradiz**. **Sem dado novo, sem I/O
> geográfico, sem LLM** — consome o que a 1.8 já extrai e confirma.

## 1. Objetivo

A 1.8 extrai da LUOS, com proveniência por artigo, **mais índices do que usa**: além de
lote mínimo e doação (que entram no número), ficam parados no perfil `frente_min_m`, `ca`,
`taxa_ocupacao` e `doacao_split` — os comentários do schema os marcam "persiste p/ a
dimensão Jurídica (Fase 3)". Esta fase os **consome**: um **checklist de conformidade**
da (zona, modalidade) contra a gleba, dizendo o que já está no cálculo, o que é exigência
do projeto urbanístico e o que não foi extraído.

**Fronteira:** conformidade de **triagem** — o projeto urbanístico e as diretrizes
específicas da gleba (art. 6º/7º da Lei 6.766/79) decidem o atendimento real.

## 2. O que NÃO muda (não-regressão)

- **NÃO altera o número do aproveitável** (nem headline, nem cenários).
- Não cria dado novo nem credencial: lê o `PerfilMunicipal` confirmado (1.8) + a área da
  gleba (Fase 1). Reusa `_param_zona` (resolução zona→modalidade da 1.8).
- Suítes de 1…3 continuam verdes.

## 3. Como funciona (determinístico, cálculo só no backend)

`core/conformidade.py` — função pura `avaliar(perfil, zona, modalidade, area_total_m2)`.
Cada índice vira um item com **status**:

| status | significado |
|---|---|
| `considerado` | já entra no número (lote mínimo, doação) — evidenciado com o m² calculado |
| `exigencia_projeto` | exigência legal que o desenho urbano deve atender (frente, CA, TO, split) |
| `atencao` | inconsistência detectada (split da doação não fecha com o total, tol 0,5 p.p.) |
| `nao_extraido` | ausente do perfil confirmado → **não avaliado** (nunca inventa) |

Leituras calculadas **no backend** (o front não reformata, §2):
- doação base `total` → m² a destinar = `pct × área da gleba`; base `liquida` → "depende do projeto";
- split → m² por componente (viário/verde/institucional) + checagem `soma ≈ doacao_pct`;
- frente mínima → profundidade implícita do lote mínimo (`lote/frente`);
- CA / taxa de ocupação → potencial construtivo / projeção máxima **por lote mínimo**
  (baliza o produto; não altera o nº de lotes).

Modalidade aplica os overrides da 1.8 (doação 0 = isenção válida, com citação).

## 4. Contrato de API

`GET /api/analises/{id}/conformidade?zona=MUE&modalidade=loteamento` → `ConformidadeOut`:

```jsonc
{
  "avaliada": true,
  "zona": "MUE", "modalidade": null,
  "itens": [
    { "parametro": "lote_min_m2", "rotulo": "Lote mínimo", "valor": "360 m²",
      "status": "considerado",
      "leitura": "Lote mínimo legal da zona (360 m²) — já aplicado no cenário com diretriz…",
      "proveniencia": "Art. 7º, II, d · p.8 · diretriz.pdf · validado por marco em 2026-06-06" },
    { "parametro": "frente_min_m", "rotulo": "Frente mínima", "valor": "12,0 m",
      "status": "exigencia_projeto",
      "leitura": "Testada mínima de 12,0 m… profundidade média … 30,0 m…", "proveniencia": "…" },
    { "parametro": "doacao_split", "status": "atencao",
      "leitura": "… ATENÇÃO: a soma da repartição (25%) difere do total (20%) — confira…" },
    { "parametro": "ca", "status": "nao_extraido",
      "leitura": "Não extraído da LUOS confirmada — não avaliado…" }
  ],
  "zonas_disponiveis": ["MUE"],
  "proveniencia": "Perfil municipal confirmado de São Roque/SP · validado por marco…",
  "avisos": ["Conformidade de TRIAGEM… o projeto urbanístico e as diretrizes específicas decidem."]
}
```

Degradação honesta (sempre 200): sem perfil confirmado → `avaliada=false` + motivo
acionável ("extraia e confirme a LUOS na aba Diretriz"); sem zona → `avaliada=false` +
`zonas_disponiveis` (o front monta o seletor sem inventar); zona inexistente → idem.

## 5. Critérios de aceite (testáveis — `tests/test_conformidade.py`)

1. Checklist completo com **proveniência por artigo** herdada (+ `validado_por`).
2. Leituras **calculadas no backend**: doação m² = pct×área da gleba; profundidade 360/12=30 m;
   CA 360×1,5=540 m²; TO 360×0,6=216 m² (formato pt-BR no backend).
3. **Split consistente** (0,10+0,06+0,04=0,20) → `exigencia_projeto`; **inconsistente**
   (soma 0,25 ≠ 0,20) → `atencao` com leitura explicando.
4. **Modalidade override**: desmembramento doação 0 → "isenta", com a citação do override.
5. **Índice ausente** → `nao_extraido` ("não avaliado"), nunca inventado.
6. **Degradação**: sem perfil → motivo; sem zona → `zonas_disponiveis`; zona errada → motivo.
7. **Determinismo**: duas chamadas idênticas → mesma resposta.
8. **Não-regressão**: aproveitamento (headline/teto) **inalterado** antes/depois; suítes 1…3 verdes.

## 6. Fora de escopo (registrado)

- **Recuos/gabarito** — não estão no schema da 1.8; entram se/quando a extração os cobrir.
- **Camada estadual** (órgão licenciador, APA/manancial) — dado novo; fase própria futura.
- **Veredito de conformidade do projeto** — exige o projeto urbanístico; isto é triagem.

## 7. Arquivos (implementados)

- `core/conformidade.py` — checklist puro (reusa `_param_zona` da 1.8).
- `routers/conformidade.py` — `GET /analises/{id}/conformidade`.
- `models/schemas.py` — `ItemConformidadeOut`, `ConformidadeOut`.
- Frontend: item "Conformidade" na sidebar + `CardConformidade` (seletor de zona/modalidade
  vindo do perfil confirmado; chips por status; proveniência por item).
- Testes: `tests/test_conformidade.py` (11 testes, offline).
