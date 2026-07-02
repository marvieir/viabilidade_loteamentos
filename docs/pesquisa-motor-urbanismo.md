# Pesquisa — Urbanismo sofisticado para o motor de estudos de massa

> Pesquisa multi-fonte (2026-07) + análise do motor atual + roadmap. Complementa
> `boas-praticas-loteamento.md` (bibliografia canônica) e `catalogo-praticas-urbanismo.md`
> (base normativa). Este documento traz o que faltava: **números de prêmio de preço por
> atributo de lote**, **padrões de amenidades por renda** e **como motores generativos
> funcionam e "aprendem"**.

---

## 0. Metodologia e confiabilidade (como esta pesquisa foi feita)

**Critérios de busca — 5 ângulos, cada um no vocabulário nativo do domínio:**
1. *Amenidades e distribuição espacial por padrão* — literatura de prática (ULI/master-planned):
   `master-planned community amenity programming ULI clubhouse trails pocket parks 5-minute walk`
2. *Prêmio por atributo de lote* — literatura acadêmica de **hedonic pricing** (EUA e Brasil):
   `hedonic pricing residential lot premium waterfront greenbelt cul-de-sac golf frontage`
3. *Custo × prêmio de amenidades criadas* (lago artificial, parque linear, stormwater):
   `artificial lake amenity subdivision cost versus lot price premium stormwater`
4. *Site planning de lotes e traçado* + cases brasileiros (Alphaville, Riviera, Fazenda Boa Vista)
5. *Motores generativos* — `generative urban design Autodesk Forma TestFit Delve CityEngine
   multi-objective optimization`

**Verificação:** cada alegação extraída passou por verificação adversarial (3 verificadores
céticos independentes; ≥2 refutações eliminam). Por limite de sessão, **parte da verificação
não completou** — por isso cada achado abaixo carrega um rótulo de confiança:
- ✅ **VERIFICADO (3-0)** — sobreviveu à verificação adversarial completa;
- 📄 **FONTE PRIMÁRIA** — extraído com citação literal de fonte confiável, verificação não concluída;
- 💡 **SÍNTESE** — leitura minha sobre o conjunto (julgamento, não fato).

**Qualidade das fontes (31):** o filtro privilegiou **periódicos revisados por pares**
(Springer *Journal of Real Estate Finance and Economics*, Wiley *JAWRA*, ScienceDirect
*Environmental Modelling & Software*, SciELO *Nova Economia*), **working papers acadêmicos**
(Wharton Real Estate), **arXiv** (generative design), **entidades setoriais** (ULI Urban Land,
NRPA, Headwaters Economics), **dados de mercado** (Zillow Research, John Burns) e **fontes
primárias dos empreendimentos** (master plans oficiais de Riviera de São Lourenço e Fazenda
Boa Vista). Blog/consultoria só como pista, nunca como número.

**Livros (o insumo que a internet não substitui):** a bibliografia canônica do projeto
(`boas-praticas-loteamento.md`) já ancora o motor em **Lynch & Hack — *Site Planning*** (a
referência do ofício), **Alexander — *A Pattern Language*** (#49 looped roads, #51 green
streets, #60 accessible green), **Unwin — *Town Planning in Practice*** (cul-de-sac com verde,
vista-stoppers), **DPZ — SmartCode/Transect** e **Lamas — Morfologia Urbana**. Adições
recomendadas por esta pesquisa: **ULI — *Residential Development Handbook*** (o manual da
indústria de master-planned communities: programação de amenidades, faseamento, value
engineering) e **ADIT — Comunidades Planejadas** (prática brasileira). São as fontes para a
Fase U2 (biblioteca de amenidades) — extrair os parâmetros como fizemos com Lynch/Alexander.

---

## 1. Prêmio de preço por atributo de lote (o dinheiro do desenho)

| Atributo | Prêmio | Confiança | Fonte |
|---|---|---|---|
| Lote colado em campo de golfe | **+7,6%** | ✅ 3-0 | Springer, hedônica com 717 vendas (San Diego) |
| Casa em **cul-de-sac** vs grelha | **+29%** (teto; mercado único, 1990) | ✅ 3-0 | Springer (Halifax) |
| Adjacência a **lago/pond criado** (wet pond) | prêmio positivo; **maior quando o lago nasce junto com o empreendimento** | ✅ 3-0 | Wiley/JAWRA (Horry County SC, 2010-18) |
| Bacia de detenção **só funcional** (sem paisagismo) | **VISTA reduz o valor** (desamenidade) | ✅ 3-0 | ResearchGate/hedônica GIS (College Station TX) |
| Bacia **multiuso** (pond + parque de bairro) | positivo num raio de ~**274 m** | 📄 | mesma fonte |
| Testada de água (lakefront) | elasticidade **0,55–0,63** — dobrar a testada NÃO dobra o valor → **mais lotes com testadas menores** maximiza receita da orla | ✅ 3-0 | *The Pricing of Lake Lots* |
| Lote no nível do lago vs barranco (bluff) | nível do lago vale mais; frontagem real ~**+200%** vs só vista | ✅/📄 | Colwell & Dehring 2005 |
| Testada/profundidade em lote urbano comum | elasticidades ~**0,18** (muito menores que na água) | 📄 | mesmos autores, Chicago |
| Trilhas/greenways | prêmio positivo consistente | 📄 | NRPA, Headwaters Economics |

**Implicações diretas para o motor (💡):**
1. **Vale criar água — se for amenidade, não infraestrutura.** Lago paisagístico/multiuso
   valoriza o anel ao redor (e o loteador captura mais quando o cria junto do empreendimento);
   bacia de detenção pelada DESVALORIZA quem a vê. Se o motor criar lago, tem que ser
   desenhado como parque (borda pública + paisagismo), nunca um buraco técnico.
2. **A orla rende mais fatiada**: elasticidade <1 ⇒ maximizar nº de lotes com frente d'água
   moderada, não meia dúzia de lotes gigantes.
3. **Cul-de-sac é prêmio** (sossego/segurança de crianças) — o padrão híbrido recomendado é
   **cul-de-sacs veiculares + rede independente de pedestres/verde** (case Village Homes,
   Davis-CA). O template curvilíneo+cul-de-sac foi institucionalizado pelo FHA em 1936.
4. **Anel de valorização ~274 m** ao redor de amenidade verde/água — é o raio para o motor
   "puxar" lotes premium ao redor do que criar.

## 2. Amenidades por padrão de renda e distribuição espacial

- **Alta renda (BR)** — os master plans reais (Riviera de São Lourenço, Fazenda Boa Vista,
  linha Alphaville): **clube central âncora** (esporte/social/gastronomia) + **amenidades
  espalhadas** (trilhas, praças temáticas, lagos, equestre/golfe nos top) + **parkway
  arborizada de entrada** + portal monumental. 📄
- **Regra de caminhada**: prática ULI/planejamento = espaço aberto acessível a **~5 min a pé
  (~400 m)** de qualquer lote — é o argumento para **pocket parks distribuídos** além do hub
  central. 📄
- **Média renda**: clube menor (piscina + quadra + salão) + praças de bolso; **baixa renda**:
  praça/playground + campo — o essencial bem posicionado. 💡 (calibrar com ULI Handbook)
- **Tendência** (ULI/John Burns 2024): saúde/bem-estar, trilhas como amenidade nº 1 em uso,
  agrihoods, e amenidades em rede (várias menores) superando o mega-clube único. 📄

## 3. Disposição de lotes e traçado

- **Privacidade**: evitar fundos-contra-fundos rasos; fundo para verde/mata é o prêmio;
  offsets entre casas; profundidade maior nos lotes premium. 📄/💡
- **Orientação solar**: quadras orientadas para maximizar testadas N-S (insolação de quintal)
  — códigos de solar orientation exigem % de lotes bem orientados. 📄
- **Grelha × curvilíneo**: curvilíneo/cul-de-sac vende mais caro em suburbano (FHA 1936 →
  preferência consolidada); grelha rende mais lotes/eficiência — a escolha é **de perfil**:
  econômico = grelha eficiente; alto = sinuoso + cul-de-sacs + vistas terminadas. ✅/💡

## 4. Como os motores generativos funcionam e "aprendem"

- **Arquitetura padrão** (revisão sistemática de generative urban design + toolkit
  tensor-field/arXiv): *representação paramétrica* (campos/regras) → *geração de N variantes*
  → *avaliação por métricas objetivas* (yield, walkability, solar, vista, custo) →
  **otimização multi-objetivo** (metaheurística/Pareto) → humano escolhe. 📄
- **O "aprendizado" NÃO é ML mágico**: é **simulation-in-the-loop** — as variantes são
  pontuadas e o otimizador itera; Delve (Sidewalk Labs) e Forma/Spacemaker funcionam assim
  (Delve: geração + scoring por objetivos priorizados pelo dev). 📄
- **Métricas usadas**: yield (m² vendável), custo de infra, acesso a amenidade por raio,
  exposição solar, vista, conectividade viária. 📄

**💡 Tradução para o nosso motor:** já temos 80% da arquitetura (gerador determinístico +
medição + score). O que falta é (a) o score virar **função de VALOR** (R$, via prêmios da
§1 + preço por faixa que a Financeira já tem), (b) gerar **K variantes** e escolher a de
maior valor — isso É o "aprender" dos líderes de mercado — e (c) **memória de preferências**
do operador (ver §6/roadmap U5).

---

## 5. Raio-X do motor atual × práticas (gap analysis)

| Prática | Motor hoje | Gap |
|---|---|---|
| Amenidades detalhadas por perfil | LLM propõe `amenidades` (strings) **que não viram geometria** | materializar biblioteca de amenidades |
| Hub + pocket parks distribuídos | 1 quadra vira "clube" (área-alvo + frente de via) — sempre parecido | placement por cobertura de caminhada (400 m) + N praças |
| Lotes premium perto de verde/água | score mede verde (+3) e distância da entrada (+2), **depois** do desenho | score v2 multi-fator que **guia** o desenho |
| Lago/água como valorizador | inexistente (DEM disponível!) | sintetizar lago multiuso no ponto baixo + anel premium 274 m |
| Privacidade/orientação | não considerado | fatores no score v2 + regra de orientação de quadra |
| Cul-de-sac premium | traçados grelha/sinuoso, sem bolsões | arquétipo cul-de-sac p/ alta renda |
| Escolher a melhor variante | 1 geração por clique | K variantes → função de valor → melhor |
| Aprender com projetos | nada persiste | banco de programas avaliados + few-shot no LLM |

## 6. Roadmap do motor (fases U — incrementais e testáveis)

- **U1 — Score de valor v2 (fundação, barato):** fatores água/verde/cul-de-sac/privacidade
  (fundo p/ lote × fundo p/ verde)/orientação/ruído da entrada, pesos por perfil; vira R$ ao
  cruzar com o preço por faixa da Financeira. *Entrega: heatmap fiel + função de valor.*
- **U2 — Lazer distribuído + amenidades materializadas:** hub central dimensionado por perfil
  (com **programa interno rotulado**: piscina/quadras/academia/salão como sub-parcelas) +
  pocket parks até cobrir raio de 400 m; amenidades do LLM passam a mapear para a biblioteca.
- **U3 — Lago/parque linear opcional:** ponto baixo do DEM + linha de drenagem → lago
  multiuso com orla-parque pública; lotes do anel de 274 m puxados para premium; custo do
  lago entra no Custo de Infra; prêmio entra no score v2. Toggle do operador.
- **U4 — K variantes + otimizador:** gerar 3–5 variantes determinísticas (sementes de
  parâmetros: arquétipo, posição do hub, mix) → pontuar pela função de valor → apresentar a
  melhor com as alternativas. É o padrão Delve/Forma, na nossa escala.
- **U5 — Memória/aprendizado:** rating + edits do operador por proposta persistidos →
  (a) recuperação dos melhores programas da região/perfil como few-shot para o LLM;
  (b) ajuste dos pesos do score por feedback. Determinístico, auditável, sem "ML caixa-preta".

*Ordem recomendada: U1 → U2 → U4 → U3 → U5 (U3 é a maior obra geométrica; U4 multiplica o
valor de tudo que vier antes).*

## 7. Fontes

Springer JREFE (golf 7,6%; cul-de-sac 29%) · Wiley JAWRA 2025 (pond premium) · *The Pricing
of Lake Lots* (elasticidades) · ResearchGate/College Station (detention basins, raio 274 m) ·
Wharton RE working paper · SciELO Nova Economia (hedônica BR) · Zillow Research (waterfront) ·
ULI Urban Land (×3) · NRPA · Headwaters Economics · Access Magazine (cul-de-sac/FHA/Village
Homes) · arXiv 2212.06783 (tensor-field masterplans) · MDPI IJGI · ScienceDirect EMS ·
Sidewalk Labs/Delve · ESRI CityEngine · TestFit · John Burns MPC Rankings 2024 · ProBuilder ·
KGA · Riviera de São Lourenço (master plan oficial) · Fazenda Boa Vista/JHSF (master plan) ·
SunCam (site planning) · SustainableCityCode (solar orientation).
