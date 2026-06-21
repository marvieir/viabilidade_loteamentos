# Boas práticas de urbanismo de loteamento — fonte de verdade do método

> Consolidação de **referências externas reais** (entidades, urbanistas e normas) para o desenho
> de loteamentos. Enquanto o `CLAUDE.md`/`ARCHITECTURE.md` fixam o **piso legal e técnico** (≥30%
> veda lote, frente para via, doação mínima, área geodésica), **este documento fixa o MÉTODO de
> DESENHO**: como dimensionar quadra/lote, hierarquizar o viário, posicionar áreas públicas, adaptar
> à topografia e **valorizar** — para o motor parar de decidir por heurística solta e passar a
> seguir um critério defensável.
>
> Status: v1 (2026-06-21). Pesquisa externa consolidada; pendente de validação do operador.

---

## 1. Quem são as referências (a quem ancorar)

- **ADIT Brasil** — Associação para o Desenvolvimento Imobiliário e Turístico. Entidade que orienta
  e capacita o setor de **comunidades planejadas e loteamentos** dentro das melhores práticas
  nacionais e internacionais. Promove o **COMPLAN** (principal evento nacional do tema) e publicou o
  livro **"Comunidades Planejadas"** (Conselho Editorial ADIT) — referência institucional do setor.
- **Alphaville Urbanismo** — **maior e mais reconhecida** desenvolvedora de loteamentos/bairros
  planejados de alto padrão do Brasil. Fundada em 1973 por **Renato Albuquerque** e **Yojiro
  Takaoka**; desenho urbano original dos arquitetos **José de Almeida Pinto** e **Reinaldo Pestana**.
  Mantém **time próprio de urbanistas** (padrão entre projetos) + consultores regionais para clube e
  paisagismo. É o benchmark prático de loteamento de alta renda no país.
- **New Urbanism (Novo Urbanismo)** — corrente de desenho urbano que estrutura grande parte das
  comunidades planejadas brasileiras (caminhabilidade, conectividade, diversidade). Exemplos
  nacionais: **Pedra Branca** (Palhoça/SC) e **Sete Sóis** (MRV, Hortolândia/SP).
- **Normas e manuais** — **Lei Federal 6.766/79** (parcelamento, base legal); **Lei 16.402/16-SP**
  e **GRAPROHAB-SP** (percentuais e aprovação); **Manual de Desenho Urbano e Obras Viárias da PMSP**
  (hierarquia/seções viárias); normas municipais de parcelamento (ex.: Aracaju) com dimensões.

---

## 2. Princípios gerais (o "porquê" do desenho)

1. **Caminhabilidade** — serviços/amenidades a ~10 min a pé; ruas amigáveis ao pedestre. *(New Urb.)*
2. **Conectividade** — malha viária **interligada** que distribui o tráfego e facilita o caminhar;
   evitar a gleba "partida". *(New Urb.; é o que a Fase 10.8 resolveu.)*
3. **Diversidade de lotes** — mix de **tamanhos e faixas de preço** próximos, não monocultura.
4. **Qualidade do desenho e do espaço público** — beleza, conforto humano, paisagismo, redes
   enterradas, drenagem; o espaço público bem-cuidado é o que **valoriza** o produto.
5. **Adaptação ao sítio** — o relevo, a drenagem e a mata **comandam** o traçado; não se força grelha
   sobre encosta. A topografia é fator decisivo do sucesso **antes da primeira máquina**.

---

## 3. Regras concretas de desenho (o que o motor deve seguir)

### 3.1 Quadra (quarteirão)
- **Forma retangular** e **duas fileiras de lotes costas-com-costas** (eficiência clássica).
- **Comprimento ≤ ~400 m** (norma municipal típica; acima disso, abrir via). 
- **Profundidade da quadra ≈ 2 × profundidade do lote** (as duas fileiras).
- **Orientada ao eixo PRÓPRIO da parcela e à curva de nível** — não ao eixo global. *(É a falha
  atual: `_lotear_face` lota no eixo global e desperdiça parcelas oblíquas/irregulares.)*

### 3.2 Lote
- **Frente para via** (testada), **perpendicular à rua**.
- **Profundidade mínima ~25 m** para testada > 8 m (norma); **profundidade > testada** (lote mais
  fundo que largo).
- **Mix de tamanhos** por posição (premium/padrão), não tamanho único.

### 3.3 Sistema viário
- **Hierarquia**: via-tronco/coletora (costura a gleba) → vias locais (servem as quadras) →
  **cul-de-sacs** nos fundos de exclusividade.
- **Malha conectada** (um grafo só) — não loteamento partido.
- **Acompanha a curva de nível**; greide controlado. **≥30% veda LOTE, não VIA** (a via cruza em
  corte/aterro com laudo; Lei 6.766 art. 3º).
- Caixa de via dimensionada ao papel (coletora > local); em condomínio, vias privadas mais estreitas.

### 3.4 Áreas públicas / verdes / institucional
- **Percentuais de referência (SP, Lei 16.402/16):** **área verde ≥ 15%**, **institucional ≥ 5%**
  da gleba (o mínimo legal varia por município; é PISO, não meta).
- **Localização (regra de ouro):** verde e institucional vão para a **terra marginal** (encosta,
  fundo, faixa ≥30%, APP) **ou viram amenidade DEFINIDA** (clube/parque que ancora valor). **Nunca**
  tomar a parcela nobre/plana para verde genérico. *(É a falha que reservava o platô como verde.)*
- O **≥30%/APP/mata** já contam como verde preservado — frequentemente suprem boa parte da doação.

### 3.5 Topografia e drenagem
- Levantamento planialtimétrico; traçado segue curvas de nível; **≥30% = via/verde, não lote**.
- Drenagem orientada pela declividade (a água manda no arruamento).

### 3.6 Valorização (o "melhor aproveitamento" = VALOR, não só nº de lotes — esp. alta renda)
- **Lotes premium** onde há **vista panorâmica / cota alta**, **fundo de mata** (privacidade) e
  **frente para verde/lazer/clube**. *(Drivers reais de valorização em alto padrão.)*
- **Penalizar** lotes na via principal e junto à **entrada/portaria** (ruído/passagem).
- **Cul-de-sac** cria endereços de exclusividade (lote grande em leque, baixo tráfego).
- O **clube/lazer** é âncora de valor: lotes voltados a ele ganham preço.

---

## 4. Benchmarks de aproveitamento (parâmetro de comparação)

Distribuição típica de uma gleba **plana e bem resolvida** (referência URBIA, sobre a área líquida):

| Uso | Faixa de referência |
|---|---|
| Vendável (lotes) | **~55–58%** |
| Sistema viário | **~15%** |
| Áreas verdes (verde + lazer + institucional) | **~28%** |
| Sobra geométrica | **~0%** (meta) |

> Atenção: a **gleba real comanda**. Terreno de serra com faixa ≥30% relevante tem teto de vendável
> menor (o ≥30% não vira lote). O benchmark é **alvo de eficiência** (viário enxuto, sobra ~0), não
> promessa — a proveniência e a honestidade do quadro (§3 da spec) continuam valendo.

---

## 5. Ponte para o motor (o que já atende × o que falta)

**Já segue a boa prática:**
- Malha conectada / gleba única; ≥30% veda lote, não via (Fase 10.8).
- ≥30% como verde preservado, não "sobra" (Fase 10.8b).
- Frente para via em todo lote; clamp legal de lote; doação medida vs mínimo.
- Orçamento de áreas públicas sobre a área **lotável** (Fase 10.8c).

**Falta ancorar (próximas fases):**
1. **Subdivisão adaptada (3.1/3.2):** quadra/lote no **eixo próprio da parcela + curva de nível**,
   com **acesso interno** quando a quadra é grande/funda — para o platô e os blocos irregulares
   virarem lote, não sobra. *(Maior alavanca de aproveitamento hoje.)*
2. **Localização de verde/institucional (3.4):** escolher a **terra marginal**, nunca a parcela
   nobre; clube como amenidade definida.
3. **Valorização por perfil (3.6):** alta renda = **posicionar valor** (premium em cota alta/fundo de
   mata/frente verde; penalizar entrada/via principal; cul-de-sac); baixa/média = **densidade**.

---

## 6. Fontes
- ADIT Brasil — Comunidades Planejadas e Loteamentos: <https://adit.com.br/comunidades-planejadas-solucoes-urbanas-eficientes-para-a-qualidade-de-vida/> · publicação "Comunidades Planejadas": <https://adit.com.br/conselho-editorial-adit-brasil-realiza-sua-primeira-publicacao-intitulada-comunidades-planejadas/>
- Alphaville Urbanismo (histórico/projeto): <https://pt.wikipedia.org/wiki/AlphaVille_Urbanismo>
- 10 pilares do Novo Urbanismo (loteamentos): <https://halonotoriedade.com.br/conheca-os-10-pilares-do-novo-urbanismo-que-estao-impactando-diretamente-na-construcao-de-loteamentos/>
- Manual de Desenho Urbano e Obras Viárias — PMSP (princípios viários): <https://manualurbano.prefeitura.sp.gov.br/manual/3-parametros-de-desenho-viario/3-1-principios-de-projeto-para-o-espaco-viario>
- Percentuais de áreas públicas (Lei 16.402/16-SP): <https://www.migalhas.com.br/depeso/383550/percentual-de-areas-publicas-nos-loteamentos>
- Manual GRAPROHAB-SP — Projeto Urbanístico: <https://app.habitacao.sp.gov.br/ManualGraprohab/10ProjetoUrbanistico.html>
- Normas de parcelamento (dimensões de quadra/lote) — Aracaju: <https://www.aracaju.se.gov.br/userfiles/emurb/2011/02/DPS_Normas_ParcelamentoSolo.pdf>
- Topografia e valorização do loteamento — Ferrucci: <https://ferrucciempreendimentos.com/2025/08/27/topografia-do-terreno-potencial-loteamento/>
- Projeto urbanístico de loteamento — Ávila Urbanismo: <https://www.avilaurbanismo.com.br/projeto-urbanistico/>
- Lei Federal 6.766/79: <https://www.planalto.gov.br/ccivil_03/leis/l6766.htm>
