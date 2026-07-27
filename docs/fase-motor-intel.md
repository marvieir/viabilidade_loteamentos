# Fase MOTOR-INTEL — o motor fica comprovadamente mais inteligente

**Data:** 26/07/2026 · **Decisão do operador:** ordem **INTEL-1 → INTEL-2 → INTEL-4**
(corpus/placar → função de valor por público → calibração pelos projetos importados).
**Referência de mercado:** Delve/Forma/TestFit não usam "IA que desenha" — geram MUITAS
variantes determinísticas, medem contra metas explícitas e a função de valor + o humano
escolhem. Nossa arquitetura (K variantes + função de valor + rating U5) já é essa; esta
fase melhora cada elo do ciclo, sem quebrar os inegociáveis (determinismo, proveniência,
número só do motor).

## INTEL-1 — Corpus de glebas-ouro + placar (ESTA FASE)

Sem medir não há aprender: todo ajuste do motor passa a ser julgado por um PLACAR fixo
sobre glebas reais — melhorou onde queríamos e não regrediu no resto.

- **Corpus**: diretório de casos (`CORPUS_MOTOR_DIR`; default `/data/perfis/corpus` no
  container, `scripts/corpus` fora). Cada caso = um JSON: `{"gleba_wkt" | "gleba_geojson",
  "restricao_wkt"?, "publicos"?}`. Glebas de clientes ficam SÓ no volume do operador
  (privacidade); o repositório embarca casos sintéticos/de teste.
- **Placar**: `python -m scripts.placar_motor` roda, POR CASO × PÚBLICO (baixa/média/alta),
  a geração determinística SEM IA (programa do preset + K variantes de `VARIANTES_U4`; a
  função de valor escolhe) e mede os KPIs:
  `n_lotes, area_media, vendavel%, sobra%, viario%, verde%, lazer%, viario_conexo,
  variante vencedora`.
- **Comparação**: grava `placar.json` no corpus e compara com `placar_base.json`
  (tolerância 1 p.p.): melhora ▲, piora ▼ marcada como **REGRESSÃO**. `--fixar-base`
  promove o placar atual a base (após o operador aceitar a evolução).
- **Determinismo**: mesma entrada → mesmo placar, sempre (testado).

## INTEL-2 — Função de valor por público (próxima)

Hoje: Σ(área × multiplicador posicional). Passa a: valor posicional − penalidades de
sobra e viário + aderência à faixa do público + bônus de amenidade — com PESOS POR PÚBLICO
no perfil de estilo versionado (baixa pesa yield; alta pesa amenidade/privacidade).
A escolha entre as K variantes fica mais esperta de imediato; o placar da INTEL-1 é o juiz
da mudança. Nenhum número novo inventado: só os já medidos entram na conta, com pesos
auditáveis.

## INTEL-4 — Calibração pelos projetos importados (depois)

Cada DWG importado (URB-IMPORT) é um gabarito de urbanista real. Extrair as métricas dos
importados (largura de via, módulo de quadra, testada×profundidade, % institucional/verde
por público e região) e propor ATUALIZAÇÕES dos alvos do perfil de estilo — sempre como
proposta auditável que o operador aceita (o estilo é versionado; nada muda sozinho). O
placar da INTEL-1 mede o antes/depois de cada calibração.

## Fora do escopo (registrado)

- RL/rede neural gerando geometria (quebra determinismo e explicabilidade legal).
- Ajuste automático de pesos sem aceite do operador.
- INTEL-3 (K maior/mais estratégias) e INTEL-5 (preferência revelada por clique) ficam
  para depois da 4 — o placar dirá se ainda precisam.
