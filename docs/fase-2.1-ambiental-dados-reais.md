# Fase 2.1 — Ambiental com dados reais + ANEEL

> Pré-requisito de leitura: `ARCHITECTURE.md`, `CLAUDE.md` e `docs/fase-2-ambiental.md`.
> Fase **corretiva**. A Fase 2 passou nos testes (offline, stubs) mas **não foi ligada a
> dado real** → no app aparece "camadas ambientais não consultadas (fonte não configurada)".
> Esta fase conecta as camadas oficiais reais e adiciona linhas de transmissão (ANEEL).

## Problema que corrige
Os 10 critérios da Fase 2 eram todos offline com camadas-stub (correto para determinismo),
mas a **integração com dados reais ficou fora dos critérios**. Resultado: a feature está
encanada (endpoint + interface injetável + testes verdes) e **desconectada** dos dados
nacionais. Em upload real, não consulta nada. Falha de especificação, não de código.

## Objetivo
Ligar as camadas vetoriais oficiais reais, com **smoke test ao vivo**, e adicionar
**linhas de transmissão (ANEEL)** para o alerta de faixa de servidão. Manter tudo
determinístico, com proveniência, e **degradação por camada** (uma fonte fora do ar não
derruba as outras).

## Escopo

**Dentro:**
- Downloaders reais (pipeline: download + cache + consulta por bbox; refresh agendado):
  - **Mineração** — SIGMINE/ANM (endpoint confirmado).
  - **Hidrografia** — ANA/IBGE.
  - **Unidades de conservação** — ICMBio/CNUC.
  - **Linhas de transmissão** — ANEEL/SIGEL (novo) → alerta de **faixa de servidão**
    (20/40/70 m conforme 69/230/500 kV, parametrizável por tensão da LT).
- **Smoke test ao vivo**: gleba conhecida sobre processo SIGMINE conhecido → detecta
  sobreposição **real** (marcado como teste de integração, separado dos unitários).
- **Degradação por camada**: fonte indisponível → `camada X não consultada` com aviso,
  sem bloquear as demais; `sem_alertas` só quando as camadas consultadas não acusam nada.

**Fora:**
- Declividade ≥30% via DEM → **Fase 2.5** (precisa de chave OpenTopography).
- Detecção de área alagada por imagem → **descartada** (sem proveniência, propensa a erro);
  o indicador honesto virá de declividade + proximidade de hidrografia na Fase 2.5.

## Fontes (endpoints)
| Camada | Fonte | Endpoint | Credencial |
|---|---|---|---|
| Mineração | ANM / SIGMINE | `sigmine.dnpm.gov.br/sirgas2000/{UF}.zip` (confirmado) | não |
| Hidrografia | ANA / IBGE | WFS/WMS oficial — **confirmar URL na implementação** | não |
| Unid. conservação | ICMBio / CNUC | WFS/WMS oficial — **confirmar URL** | não |
| Linhas de transmissão | ANEEL / SIGEL | serviço geoespacial ANEEL — **confirmar URL** | não |

## Contrato (estende o da Fase 2)
```
GET /api/analises/{id}/ambiental
→ {
  "alertas": [ { "tipo": "MINERACAO | UNIDADE_CONSERVACAO | APP_HIDROGRAFIA |
                          FAIXA_NAO_EDIFICAVEL | FAIXA_SERVIDAO_LT",
                 "severidade": "...", "intersecta": true, "area_afetada_m2": ...,
                 "detalhe": "...", "proveniencia": {camada, data_referencia, ressalva} } ],
  "geojson_overlays": { "app":..., "uc":..., "mineracao":..., "linhas_transmissao":... },
  "camadas_consultadas": ["SIGMINE", "ANA", "ICMBio", "ANEEL"],
  "camadas_indisponiveis": [],            // degradação por camada
  "sem_alertas": false
}
```

## Critérios de aceite
1. **Smoke test ao vivo (SIGMINE)**: gleba conhecida sobre processo minerário → alerta
   `MINERACAO` real, com nº do processo + proveniência + data. (Integração, com rede.)
2. **ANEEL**: gleba que cruza LT (fixture) → alerta `FAIXA_SERVIDAO_LT` com largura por tensão.
3. **APP/hidrografia** e **UC**: interseções reais geram alertas com proveniência.
4. **Degradação por camada**: simular fonte indisponível → `camadas_indisponiveis` populado,
   demais camadas seguem; **não** retornar "não configurada" quando há fontes configuradas.
5. **Gleba limpa** → `sem_alertas: true` honesto (camadas consultadas, nada cruza).
6. **Proveniência** (camada, data, ressalva informativa) em todo alerta.
7. **Determinismo** nos unitários (stubs) + o smoke test real isolado como integração.
8. **Não-regressão** das Fases 1, 1.5, 2 e 1.7.

## Restrições inegociáveis
- Aquisição por pipeline (download + cache + bbox); **nunca agente/LLM**.
- Interseção determinística; cada alerta citável à fonte e data; ressalva "informativo —
  verificar oficial".
- Degradação por camada, nunca bloqueio total.
- Imagem de satélite só como **fundo visual** no mapa, nunca como fonte de dado.

## Definição de pronto
Unitários offline verdes + smoke test SIGMINE ao vivo detectando uma sobreposição real;
subir a Bocaina e abrir a Ambiental consulta as camadas reais e mostra alertas (ou
"sem sobreposição" honesto), com a faixa de servidão da ANEEL incluída quando houver LT.
