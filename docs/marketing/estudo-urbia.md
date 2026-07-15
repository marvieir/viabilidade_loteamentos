# Estudo de marketing — Urbia (concorrente de referência)

> Estudo para aprendizado de posicionamento e estrutura. **Nada aqui é para copiar**: copy, marca
> e identidade visual deles são deles. Usamos este estudo para (a) entender contra o que o cliente
> nos compara e (b) escolher onde nos diferenciamos.
>
> Fontes: relatório EVU real da Urbia (São Roque R01/V00, compartilhado pelo operador) analisado
> página a página; conteúdo indexado do site urbia.com.br via buscador (o acesso direto ao site é
> bloqueado pela rede da sandbox — ver "Pendências" no fim).

## 1. Quem são e o que vendem

- **Posicionamento público**: "Urbia | Análise de terrenos e viabilidade urbanística" (title do
  site). Se apresentam como "a primeira inteligência artificial de desenvolvimento de traçados
  urbanos do Brasil". Tecnologia "paramétrica + IA". Pertencem ao ecossistema do Grupo Sólido
  (escritório de urbanismo), ou seja: nasceram de uma prática de projeto, não de software.
- **O que vendem**: o **EVU (Estudo de Viabilidade Urbanística) como serviço produtizado**, por
  encomenda. O cliente manda a área, eles devolvem um relatório fechado (PDF de ~15 páginas,
  versionado R01/V00). Também vendem masterplan para glebas grandes. Canal de venda: contato
  direto (estudos@urbia.com.br, telefone). **Não é self-service**: o cliente não roda nada.
- **Escopo do estudo** (conteúdo divulgado): pesquisa da área, restrições, APPs, topografia,
  dados de ocupação, áreas vendáveis, heatmap e estimativa de custos iniciais; análise de entorno;
  no pacote completo, manchas de setorização, implantação humanizada e "pitch comercial" com
  imagens geradas por IA.

## 2. O relatório deles É a página de vendas (estrutura, página a página)

O EVU de São Roque mostra como eles convencem: design limpo, azul institucional, uma ideia por
página, e **tabela de números ao lado de cada mapa**. Sequência:

1. **Capa-resumo**: cliente, localização, tipo, área (26 ha), nº de lotes (225), lote padrão
   (400 m²), testada padrão (16 m) + miniatura do traçado. O decisor lê a capa e já tem o negócio.
2. Situação/Localização (satélite + implantação sobreposta).
3. Restrições e áreas não edificantes (manchas coloridas + tabela % da área bruta; área líquida
   72,21%). **As restrições não têm nome nem fonte legal: só "Restrição" e cor.**
4. Análise de topografia (faixas de inclinação com %).
5. Implantação (quadro de ocupação: vendável 53,3%, verdes 26,01%, lazer 4,38%, institucional 0%,
   arruamento 16,3% + indicadores: 4.017 m de vias, testada média 18,31 m, área média 444,76 m²).
6. Usos da área vendável.
7. Análise de lotes (distribuição de tamanhos, choropleth).
8. **Heatmap de score** (score médio 9,41, legenda "+quente / +frio").
9–12. **Faseamento** (3 fases, cada uma com quadro próprio) — fala direto com o caixa do loteador.
13. **Estimativa de infraestrutura** (terraplanagem, água, saneamento, energia, pavimentação...):
    total R$ 15,6 mi, **R$ 69.549 por lote, R$ 156/m²**, VGV do m² R$ 1.250.
14. **Estimativa de incorporação**: VGV bruto R$ 125,1 mi, VGV líquido R$ 76,3 mi, custo total
    R$ 28,4 mi (permuta, impostos, corretagem, licenciamento, marketing).
15. **Contracapa de prova social**: mapa do Brasil + "27.066,09 ha projetados", "+420.000 lotes
    projetados", "+66 bi de VGV projetado", "27 estados", "+200 cidades" + contato.

## 3. O que aprender com eles (e adotar, adaptado)

- **Números grandes e específicos como prova social** (ha, lotes, VGV, cidades). Específico
  convence; redondo demais desconfia. Quando tivermos números de uso reais, exibir no mesmo
  espírito (nunca inventar; ver guardrails da skill).
- **Capa-resumo**: a primeira tela responde "quantos lotes, de que tamanho, onde". Nossa página e
  nosso relatório devem entregar o resultado na primeira dobra, não no fim.
- **Mapa + tabela lado a lado** em toda seção: visual bonito para sonhar, número frio para decidir.
- **Faseamento e financeiro no mesmo documento**: eles terminam no bolso (custo por lote, VGV
  líquido). A conversa final de qualquer público é financeira.
- **Versionamento visível (R01/V00)** passa maturidade de engenharia.

## 4. Onde nos diferenciamos (matéria-prima honesta para a copy)

| Dimensão | Urbia (EVU encomendado) | Nossa plataforma |
|---|---|---|
| Modelo | Serviço: pede por e-mail, espera o relatório | Self-service: sobe o KMZ e vê a análise na hora, quantas vezes quiser |
| Proveniência | Números sem fonte no relatório ("Restrição" sem nome, sem lei, sem data) | Cada número sai com fonte legal, perfil aplicado e data de referência |
| Regras ambientais | Manchas genéricas | Camadas nomeadas e regras de lei aplicadas como invariante (via jamais em mata, Lei 11.428; declividade ≥30% lote vedado/via com laudo, Lei 6.766 art. 3º) |
| Jurisdição | Não declara cobertura | Rótulo explícito de cobertura (federal / parcial UF / completa) quando falta perfil municipal |
| Iteração | Nova rodada = novo pedido ao fornecedor | Regenerar com outro objetivo (Rendimento × Paisagem), outra diretriz, outro acesso, em minutos |
| Topografia real | Usa a topografia que eles levantam no processo | Cliente anexa o planialtimétrico das matrículas (DWG) e o traçado segue a cota de verdade |
| Reprodutibilidade | Caixa-preta do fornecedor | Determinística: mesma entrada, mesma saída, auditável |

**Cuidado ao usar a tabela acima em público**: afirmações sobre a Urbia só com fato verificável
(o que está no relatório deles ou no site deles). Na dúvida, falar de nós sem citar concorrente.

## 5. Implicações para as nossas páginas

- O comprador desse mercado já foi educado pela Urbia a esperar: traçado bonito + quadro de áreas
  + heatmap + custo/VGV. Nossa página principal deve mostrar isso em 10 segundos (print real).
- A lacuna emocional que eles deixam aberta: **confiança verificável**. O relatório deles pede fé
  no fornecedor; o nosso mostra a fonte de cada número. "Você não precisa acreditar na gente"
  é um ângulo que eles não conseguem ocupar com o modelo atual.
- A lacuna prática: **velocidade e autonomia** (rodar sozinho, na hora, iterar de graça) e
  **custo por decisão** (triagem barata antes de gastar caro com projeto/EVU completo).
- Nada de vender "IA". Eles já ocupam "primeira IA". Vendemos a transformação: decidir sobre a
  gleba com segurança em horas, não em semanas. IA/motor é mecanismo, não promessa.

## 6. Pendências deste estudo

- [ ] Copy literal do site urbia.com.br (hero, CTAs, planos/preços se públicos): a sandbox não
      acessa o domínio. Operador: abrir https://urbia.com.br/ no Mac e mandar prints (topo ao
      rodapé) que eu completo esta seção.
- [ ] Preço praticado por EVU (se descobrível de fonte pública ou por proposta recebida): âncora
      de valor para nossa oferta.
