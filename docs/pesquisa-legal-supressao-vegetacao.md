# Pesquisa legal — supressão de vegetação nativa para parcelamento (base do módulo AMB-EXC)

> Sessão de pesquisa de 08/08/2026 (padrão da casa: matéria legal se verifica na fonte antes de
> virar produto). Origem: caso Caverá (Alegrete/RS) — manchas de "Verde a verificar" travam o
> aproveitável; o operador confirmou que a prática de mercado é vistoria de campo por engenheiro
> ambiental + laudo. Esta pesquisa responde: (1) qual a régua legal da supressão; (2) se muda por
> estado/bioma (MUDA); (3) o que isso impõe ao desenho do módulo.
> **Status: 1ª rodada (fontes primárias verificadas por busca; leitura integral dos textos-chave
> pendente antes da spec). Perguntas abertas ao final.**

## 1. Régua federal comum (vale em todo o país)

- **Lei 12.651/2012 (Código Florestal), art. 26:** supressão de vegetação nativa para uso
  alternativo do solo exige **cadastro do imóvel no CAR** + **autorização prévia do órgão
  estadual do SISNAMA**. Art. 27: vedações adicionais quando há espécies ameaçadas/imunes ao
  corte (o pedido descreve volumetria e ocorrência de espécies protegidas).
- **LC 140/2011 (competências):** a autorização é em regra **estadual**; o **município** autoriza
  quando o empreendimento é licenciado por ele (e em florestas/UCs municipais); atuação supletiva
  do estado quando o município não tem órgão capacitado. Tradução prática: **quem autoriza varia
  por município** conforme o arranjo local de licenciamento.

## 2. Regime ESPECIAL da Mata Atlântica (Lei 11.428/2006) — o mais relevante p/ loteamento

- A lei tem **capítulo próprio para áreas urbanas e regiões metropolitanas**, com artigos
  desenhados exatamente para **loteamento e edificação**:
  - **Art. 30 (vegetação PRIMÁRIA e secundária em estágio AVANÇADO):** primária = supressão
    **vedada** para loteamento/edificação; secundária em estágio avançado = só em perímetro
    urbano aprovado **antes** da vigência da lei (22/12/2006), com autorização estadual e
    **preservação de ≥ 50%** da área coberta pela vegetação.
  - **Art. 31 (secundária em estágio MÉDIO):** admitida em perímetro urbano da data da lei,
    conforme **plano diretor**, com autorização estadual e **preservação de ≥ 30%**.
- **O "estágio de regeneração" é o coração do regime** — e é definido por resolução CONAMA
  **POR ESTADO** (ex.: RS = CONAMA 33/1994; SP = CONAMA 1/1994; cada UF da Mata Atlântica tem a
  sua). O enquadramento do estágio é feito por **laudo técnico de campo** (parâmetros de porte,
  estratos, espécies indicadoras) — CONFIRMA a prática que o operador descreveu: a vistoria do
  engenheiro não é burocracia, é o instrumento legal que decide a régua.
- **Dado geoespacial utilizável:** o IBGE publica o **mapa oficial da área de aplicação da Lei
  11.428** — dá para saber por polígono se a gleba está no regime da Mata Atlântica.

## 3. Pampa (o caso do RS fora da Mata Atlântica — Alegrete está aqui)

- **IN Conjunta SEMA-FEPAM 01/2021:** critérios/procedimentos das autorizações de supressão de
  vegetação nativa no bioma Pampa (base: Lei 12.651 + Lei estadual 15.434/2020 + Decreto
  52.431/2015). O rito pede caracterização da vegetação, volumetria, espécies protegidas.
- **Campo nativo TAMBÉM é vegetação nativa protegida:** a conversão de área campestre tem
  diretriz própria (**FEPAM DT 15/2024**). "Não é árvore" ≠ "liberado".
- **Lei estadual 15.434/2020 (Código Estadual do Meio Ambiente):** **banhado é APP estadual**
  (solos hidromórficos natural ou periodicamente saturados, excluídas situações efêmeras).
  Consequência direta para o produto: a "área alagada descoberta em campo" que o operador citou
  não é só restrição física — **vira APP por lei estadual**, com régua própria.

## 4. Demais biomas/estados

- Cerrado, Caatinga etc.: regime geral do Código Florestal (art. 26) + normas do órgão estadual.
  Sem lei federal especial como a da Mata Atlântica (a Amazônia Legal tem regras próprias de
  reserva legal, fora do nosso foco atual).
- Conclusão estrutural: **a régua tem 3 camadas — federal (12.651/LC 140) + bioma (11.428 com
  mapa IBGE; Pampa por norma estadual) + estadual/municipal (código estadual, resoluções de
  estágio, arranjo de licenciamento)**.

## 5. Implicações para o desenho do AMB-EXC (o que a pesquisa muda na spec)

1. **O formulário do laudo não é binário** ("libera/mantém"): na Mata Atlântica o que o laudo
   diz é o **estágio de regeneração** (primária / avançado / médio / inicial) — e o motor aplica
   a consequência legal (vedado / 50% / 30% / regra geral) citando artigo. No Pampa, o laudo
   caracteriza formação (florestal × campestre) e o rito é a IN 01/2021.
2. **O módulo precisa saber o regime por polígono:** bioma IBGE (já temos) + mapa IBGE da área de
   aplicação da 11.428 + UF → resolução de estágio aplicável. Camada nova de jurisdição
   ambiental, análoga à jurisdição urbanística que já existe.
3. **Vistoria pode ADICIONAR restrição:** banhado/área úmida achada em campo entra como APP
   (RS: lei estadual) — o fluxo de reconciliação é bidirecional, como o operador descreveu.
4. **Proveniência obrigatória:** laudo anexado (responsável técnico + data + ART), manchas
   ajustadas uma a uma, artigo aplicado por mancha — mesmo padrão LUOS/jurídico.
5. **Quem autoriza** (estado × município) muda por arranjo local — o módulo informa o rito
   provável e rotula como "verificar no órgão local" (não decide).

## 6. Perguntas abertas (próxima rodada, antes da spec)

- Ler na íntegra: arts. 30/31 da 11.428 (condicionantes exatas + jurisprudência de perímetro
  urbano pós-2006); IN SEMA-FEPAM 01/2021 (aplica-se a supressão em área URBANA no Pampa ou só
  rural/CODRAM 10740?); CONAMA 33/1994 (parâmetros de estágio no RS).
- RS tem os DOIS regimes (Pampa ao sul, Mata Atlântica ao norte) — o mapa IBGE resolve por gleba?
- Estágio INICIAL na Mata Atlântica: regra de supressão em urbano (menos restritiva — confirmar).
- Como os municípios que licenciam (LC 140) tratam o rito na prática (amostra: Alegrete).

## 7. Fontes (verificadas em 08/08/2026)

- Lei 12.651/2012, art. 26 (Planalto) — via IN SEMA-FEPAM 01/2021 que o reproduz.
- Lei 11.428/2006, arts. 30/31 — texto e doutrina (Buzaglo Dantas, artigos 2022/2023).
- Mapa da área de aplicação da Lei 11.428 — IBGE (geoftp.ibge.gov.br).
- LC 140/2011 — competências de autorização de supressão.
- IN Conjunta SEMA-FEPAM 01/2021 (sema.rs.gov.br) e FEPAM DT 15/2024 (conversão no Pampa).
- Lei estadual RS 15.434/2020 (Código Estadual do Meio Ambiente — banhado como APP).
- Resoluções CONAMA de estágios por UF: 33/1994 (RS), 1/1994 (SP) — família por estado.
- Bases de dados p/ triagem (pesquisa de 08/08, sessão anterior): MapBiomas Coleção 10 (30 m,
  série anual, classes florestal/campestre/silvicultura), dossel 1 m Meta/WRI (AWS/GEE, uso
  comercial permitido), Dynamic World (Google, 10 m, contínuo), CAR/SICAR, Inventário Florestal
  Contínuo RS (SEMA/UFSM).
