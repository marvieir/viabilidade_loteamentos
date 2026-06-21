# Boas práticas de urbanismo de loteamento — fonte de verdade do método

> Consolidação das **referências canônicas de desenho urbano e site planning** (os urbanistas que
> ensinam o ofício) para fundamentar como o motor desenha um loteamento. O `CLAUDE.md`/`ARCHITECTURE.md`
> fixam o **piso legal/técnico** (≥30% veda lote, frente para via, doação mínima, área geodésica);
> **este documento fixa o MÉTODO de DESENHO** — para o motor seguir critério de autor, não heurística
> solta.
>
> Status: v2 (2026-06-21). Ancorado em autores de referência; padrões numéricos marcados como
> "corrente" devem ser conferidos nas obras (ver §6 — algumas são livres/baixáveis).

---

## 1. As referências (os urbanistas do ofício)

### Canônicas — desenho de sítio / loteamento / bairro
- **Kevin Lynch & Gary Hack — _Site Planning_ (MIT Press).** A obra de referência sobre **arranjar o
  ambiente físico externo**: lote, quadra, via, drenagem, **adaptação ao relevo**, com apêndices de
  **padrões numéricos**. É exatamente o que o motor faz. Lynch também: _A Imagem da Cidade_ —
  legibilidade por **caminhos, bordas, bairros, nós e marcos** (base de orientação e valor).
- **Christopher Alexander — _A Pattern Language_.** 253 padrões acionáveis. Os diretamente
  aplicáveis ao loteamento:
  - **#49 Looped Local Roads** — vias locais em **laço**, sem tráfego de passagem.
  - **#51 Green Streets** — via local majoritariamente **verde** (faixa de rodagem mínima).
  - **#52 Network of Paths and Cars** — rede de **pedestres** entrelaçada com a de carros.
  - (correlatos: #30 Activity Nodes, #60 Accessible Green, #106 Positive Outdoor Space.)
- **Raymond Unwin — _Town Planning in Practice_ (1909).** Pai do *garden suburb* (Letchworth,
  Hampstead): **fileiras curtas com jardins fundos**, **cul-de-sac com verde central** e permeabilidade
  de pedestre, **_vista-stoppers_** (vistas terminadas), **junções oblíquas**, densidade
  **10–20 casas/acre líquido** (≈ 25–50 lotes/ha, excluindo vias). Domínio público.
- **Andrés Duany & Elizabeth Plater-Zyberk (DPZ) — _SmartCode_ / o Transect.** Código baseado em
  forma que une zoneamento + parcelamento + desenho urbano. **Transect** em 6 zonas (T1 natural →
  T6 urbano); o loteamento residencial vive em **T3 (sub-urbano)/T4**. Bairro caminhável, quadras
  curtas, padrões de via/lote por zona. Open-source.
- **José Lamas — _Morfologia Urbana e Desenho da Cidade_.** Referência luso-brasileira sobre os
  **elementos morfológicos** (traçado, quarteirão, lote, praça) e sua composição.

### Setoriais brasileiras (mercado e regulação)
- **ADIT Brasil** — entidade do setor; evento **COMPLAN** e livro **"Comunidades Planejadas"**.
- **Alphaville Urbanismo** — maior referência prática de loteamento de alto padrão no Brasil
  (Renato Albuquerque / Yojiro Takaoka; desenho de José de Almeida Pinto e Reinaldo Pestana).
- **Lei 6.766/79** (parcelamento federal); **Lei 16.402/16-SP** e **GRAPROHAB-SP** (percentuais e
  aprovação); **Manual de Desenho Urbano e Obras Viárias da PMSP** (seções viárias).

---

## 2. Princípios gerais (de onde sai o "porquê")

1. **Adaptação ao sítio (Lynch/Hack).** O **relevo, a drenagem e a mata comandam** o traçado; ler as
   curvas de nível **antes** de desenhar. ≥30% não loteia (vira via/verde).
2. **Conectividade + laço (Alexander #49, DPZ).** Malha **interligada**, vias locais em **loop**;
   nada de loteamento partido nem de espinha de peixe que só gera fundo de saco mal resolvido.
3. **Caminhabilidade e quadra curta (DPZ/Transect, New Urbanism).** Quarteirões curtos, percursos
   de pedestre, amenidades a ~10 min a pé.
4. **Legibilidade (Lynch, _Imagem da Cidade_).** Hierarquia clara (marcos, nós, vistas terminadas);
   o **clube/portaria/praça** como marco que organiza e valoriza.
5. **Diversidade (New Urbanism/DPZ).** Mix de tamanhos e faixas de lote, não monocultura.
6. **Espaço aberto positivo (Unwin, Alexander #106).** Verde **desenhado e útil** (jardim fundo,
   verde central de cul-de-sac, parque), não retalho/sobra.

---

## 3. Regras concretas de desenho (o que o motor deve seguir)

> Números marcados "(corrente)" são prática usual de site planning a confirmar nas obras.

### 3.1 Quadra (quarteirão) — Lynch/Hack, DPZ
- Retangular, **duas fileiras de lotes costas-com-costas**; profundidade ≈ **2 × prof. do lote**.
- **Comprimento curto** para conectividade/caminhabilidade: **~80–250 m** (corrente; DPZ prefere o
  extremo curto), **nunca > 400 m** (norma BR).
- **Orientada ao eixo PRÓPRIO da parcela e à curva de nível** — não ao eixo global. *(Falha atual:
  `_lotear_face` lota no eixo global e desperdiça parcela oblíqua/irregular → vira sobra.)*

### 3.2 Lote — Unwin, Lynch/Hack, norma BR
- **Frente para via**, **perpendicular à rua**; **profundidade > testada** (lote mais fundo que largo).
- Profundidade **~25–40 m** (corrente; mín. legal ~25 m p/ testada > 8 m); testada conforme o padrão.
- **Mix de tamanhos** por posição (premium/padrão).

### 3.3 Sistema viário — Alexander #49/#51, DPZ, Lynch/Hack
- **Hierarquia:** coletora/tronco que costura a gleba → **locais em laço** que servem as quadras →
  **cul-de-sac** curto nos fundos de exclusividade (com verde central e permeabilidade de pedestre).
- **Malha conectada** (um grafo só); **segue a curva de nível**, greide controlado.
- **≥30% veda LOTE, não VIA** (a via cruza em corte/aterro + laudo; Lei 6.766 art. 3º).
- Caixa por papel (coletora > local); condomínio = vias privadas mais estreitas.

### 3.4 Áreas públicas / verde / institucional — Unwin, Alexander, Lei 16.402/16
- **Percentuais-piso (SP):** verde **≥15%**, institucional **≥5%** da gleba (varia por município).
- **Localização (regra de ouro):** verde/institucional vão para a **terra marginal** (encosta, fundo,
  ≥30%, APP) **ou viram amenidade DEFINIDA** (clube/parque/verde central de cul-de-sac que ancora
  valor). **Nunca tomar a parcela nobre/plana para verde genérico.** *(Falha que reservava o platô.)*
- ≥30%/APP/mata já contam como verde preservado — costumam suprir parte da doação.

### 3.5 Topografia e drenagem — Lynch/Hack
- Levantamento planialtimétrico; traçado segue curvas; ≥30% = via/verde, não lote; a água (declividade)
  orienta o arruamento.

### 3.6 Valorização ("melhor aproveitamento" = VALOR, sobretudo alta renda) — Unwin, Lynch
- **Lotes premium** em **cota alta/vista panorâmica**, **fundo de mata** (privacidade) e **frente para
  verde/lazer/clube**; **_vista-stoppers_** (a rua termina num marco/verde).
- **Penalizar** lote na via principal e junto à **entrada/portaria**.
- **Cul-de-sac** = endereço de exclusividade (lote grande em leque, baixo tráfego).
- O **clube** é marco âncora: lotes voltados a ele valem mais.

---

## 4. Benchmarks de aproveitamento (alvo de eficiência)

Gleba **plana e bem resolvida** (referência URBIA, sobre a área líquida):

| Uso | Faixa de referência |
|---|---|
| Vendável (lotes) | ~55–58% |
| Sistema viário | ~15% |
| Áreas verdes (verde + lazer + institucional) | ~28% |
| Sobra geométrica | ~0% (meta) |

Densidade (Unwin, garden suburb): **~25–50 lotes/ha líquido**. **A gleba real comanda** — serra com
≥30% relevante tem teto de vendável menor. Benchmark é alvo de eficiência, não promessa (vale a
honestidade do quadro, §3 da spec).

---

## 5. Ponte para o motor (o que já atende × o que falta)

**Já segue a boa prática:**
- Malha conectada / gleba única; ≥30% veda lote, não via (10.8); ≥30% = verde preservado (10.8b).
- Frente para via em todo lote; clamp legal; doação medida vs mínimo; orçamento de áreas sobre a área
  lotável (10.8c).

**Falta ancorar (próximas fases), por prioridade:**
1. **Subdivisão adaptada (§3.1/3.2 — Lynch/Hack):** quadra/lote no **eixo próprio + curva de nível**,
   com **acesso interno** em quadra grande/funda → o platô e os blocos irregulares viram lote, não
   sobra. *(Maior alavanca de aproveitamento hoje.)*
2. **Vias locais em laço (§3.3 — Alexander #49):** trocar fundos de saco mal resolvidos por loops.
3. **Localização de verde/institucional (§3.4):** terra marginal/amenidade definida, nunca a nobre.
4. **Valorização por perfil (§3.6):** alta = posicionar valor (premium em cota alta/fundo de mata/
   frente verde; *vista-stoppers*; cul-de-sac; penalizar entrada); baixa/média = densidade.

---

## 6. Fontes (★ = livre/baixável)
- Kevin Lynch & Gary Hack, *Site Planning*, MIT Press: <https://mitpress.mit.edu/9780262121064/site-planning/>
- Christopher Alexander, *A Pattern Language* — padrões online ★: <https://patternlanguage.cc/> (ex.: <https://patternlanguage.cc/Patterns/Looped-Local-Roads-(49)>)
- Raymond Unwin, *Town Planning in Practice* (1909) — domínio público ★: <https://archive.org/details/townplanninginpr00unwiuoft>
- DPZ — *SmartCode* (open-source) ★ e Transect (CNU): <https://www.cnu.org/publicsquare/transect> · <https://transect.org/transect.html>
- José Lamas, *Morfologia Urbana e Desenho da Cidade* ★ (PDF acadêmico): <https://www.academia.edu/30879301/Morfologia_Urbana_e_Desenho_da_Cidade_Jos%C3%A9_Lamas>
- ADIT Brasil — Comunidades Planejadas: <https://adit.com.br/comunidades-planejadas-solucoes-urbanas-eficientes-para-a-qualidade-de-vida/>
- Alphaville Urbanismo (histórico): <https://pt.wikipedia.org/wiki/AlphaVille_Urbanismo>
- Lei 6.766/79 ★: <https://www.planalto.gov.br/ccivil_03/leis/l6766.htm>
- Percentuais de áreas públicas (Lei 16.402/16-SP): <https://www.migalhas.com.br/depeso/383550/percentual-de-areas-publicas-nos-loteamentos>
