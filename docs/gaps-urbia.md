# Análise de gaps vs. Urbia

> Comparação funcional entre a nossa plataforma e a Urbia (25 telas analisadas).
> Status do nosso lado **verificado no código** (não inferido). Atualizado em 2026-06-29.

## Estrutura da Urbia
Cada área tem 6 abas: **Área** (CRM/metadados) · **Ambiental** (5 sub-abas) · **Legislação** ·
**Viabilidade** (motor de custo) · **Docs** (repositório) · **Urbanístico** (serviços pagos).

## Mapa funcional (Urbia × nós)

| Funcionalidade Urbia | Nosso status (verificado) | Gap |
|---|---|---|
| **Viabilidade — custo de obra por disciplina** (terraplanagem, pavimentação, saneamento, água, energia, reservatórios, cercamentos, canteiro) | Financeira tem **blocos de custo de alto nível** (urbanização por lote/m², projetos, marketing, tributos, aquisição) — **sem** quebra por disciplina | **FORTE** |
| **Viabilidade — VGV / lucro / VGV-m²** | Econômica: **VGV, custo, lucro, margem, VGV/m², nº lotes** ✓ **+ VPL, TIR, payback, sensibilidade** (mais que eles) | nenhum (somos ≥) |
| **Incorporação** (compra/permuta do terreno, impostos, corretagem) | Financeira: permuta (lotes/VGV %), ITBI, comissão ✓ | leve |
| **Malha Fundiária** (parcelas SIGEF/SNCI/CAR sobre a gleba) | Só CAR Reserva Legal (como alerta) — **sem** parcelas SIGEF/SNCI | **FORTE** |
| **Topografia** (8 faixas de declividade + mobilidade + curvas de nível) | Declividade: **3 faixas** (suave/média/alta) + flag ≥30% — sem faixas finas, sem mobilidade, sem curvas | médio |
| **Hidrografia** (bacia/região/sub-bacia + rios km) | Não temos (Localização é só socioeconômico) | médio |
| **Solo e Vegetação** (tipo de solo, bioma nomeado, % por classe) | Vegetação: % verde + classes raster (WorldCover/MapBiomas); **sem** tipo de solo, sem bioma nomeado | médio |
| **Legislação** (recuos, gabarito, permeabilidade, gabaritos viários) | LUOS/Conformidade: CA, T.O., lote, frente, doações (split viário/verde/instit.); **sem** recuos/gabarito/permeabilidade/seção viária | médio |
| **Doações por categoria** | doações split viário/verde/institucional ✓ (falta "lazer") | leve |
| **Área — portfólio/CRM** (thumbnail, proprietário, contato, estrela, status/pipeline) | Salvas: título, cidade, área, data — **sem** thumbnail/dono/contato/rating/pipeline | médio |
| **Desenhar polígono no mapa** | Só importa KMZ/KML — **sem** desenho/edição no mapa | médio |
| **Docs** (repositório de documentos) | ✅ Anexos por item do checklist (Fase 3.C) — paridade | nenhum |
| **Export Excel** | Só PDF (laudo) | leve |
| **Urbanístico** (estudo/concept/anteprojeto) | **Serviço humano PAGO** da Urbia (Pro Engenharia) — **nós fazemos automático** | nós ≥ |

## Nossos trunfos (não perder — é onde eles são fracos)
1. **Urbanismo (IA): traçado real** de lotes + viário + pórtico. A Urbia **vende isso como serviço humano** (R$7k–29k). É nosso maior diferencial e é defensável.
2. **Econômica**: VPL/TIR/payback/sensibilidade + modos terrenista/permuta — mais profundo que o VGV/lucro deles.
3. **Jurídico dominial**: matrícula/cadeia/proprietários/checklist/anexos. O "Docs" deles é só um dropbox.
4. **Ambiental**: profundidade de camadas com proveniência.

## Ordem recomendada (esforço × valor)

### Tier 1 — Ganhos rápidos (baixo esforço, fecham "completude")
- **Declividade em faixas finas + interpretação** (já temos o DEM; só re-binar + texto).
- **Malha Fundiária SIGEF/SNCI** como nova camada ambiental (reusa a leitura por janela já pronta).
- **Bioma nomeado + bacia hidrográfica** (overlays; bioma é fácil).
- **Mais índices LUOS** (recuos/gabarito/permeabilidade/seção viária) — estende extração + conformidade.
- **Export Excel** do modelo financeiro.

### Tier 2 — Médio
- **Portfólio/CRM** (thumbnail, proprietário/contato, status/pipeline, rating).
- **Desenhar polígono no mapa** (onboarding sem KMZ).

### Tier 3 — Flagship (alto esforço, alto valor)
- **Motor de custo de infraestrutura por disciplina** — o diferencial da Urbia. **Vantagem nossa:**
  alimentamos com o **layout REAL** (comprimento de viário, nº de lotes, declividade por lote, áreas),
  então nosso custo pode ser **mais preciso** que a estimativa paramétrica deles.

> Estratégia: fechar os ganhos rápidos (Tier 1) elimina os gaps "vergonhosos" barato; o motor de
> custo (Tier 3) é o passo natural depois do layout (tem layout → estima custo → viabilidade) e nos
> coloca em paridade no ponto mais forte deles, com dado que eles não têm.
