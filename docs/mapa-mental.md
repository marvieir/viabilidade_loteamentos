# Mapa Mental — Pré-Viabilidade de Loteamento

> Diagrama Mermaid (`mindmap`). Renderiza no GitHub, no VS Code (extensão Mermaid), no Obsidian,
> ou cole em **https://mermaid.live**. Para abrir no navegador com 2 cliques, use
> `docs/mapa-mental.html` (mesmo conteúdo, renderizado).

```mermaid
mindmap
  root((Pré-Viabilidade de Loteamento))
    Entrada
      KMZ ou KML da gleba
      Multi-matrícula
      Detecção de município
    Núcleo determinístico
      Parse e geometria
      Cálculo geodésico área e perímetro
      Jurisdição município UF IBGE
      STORE em memória por análise
      Fontes injetáveis get_fonte
    Regras inegociáveis
      Cálculo só no backend
      Front só renderiza JSON
      Proveniência em todo número
      Determinismo
      Degradação honesta
    Dimensões de análise
      Ambiental
        Área verde
        Declividade
        Bacia hidrográfica ANA
        Malha fundiária SIGEF SNCI
        Bioma
        APP e UC e mineração
        Reserva legal CAR
      Aproveitamento
      Urbanismo IA
        Lotes e viário e quadras
        Pórtico de entrada
        Heatmap de score
      Custo de infraestrutura
        Paramétrico por disciplina
        Padrão econômico médio alto
        BDI
      Conformidade LUOS
      Jurídico
        Cadeia dominial
        Proprietários PF PJ
        Checklist e anexos
      Financeira
      Econômica VPL TIR payback
      Localização IBGE
      Diretriz LUOS
    Uso de LLM
      Extração LUOS Opus
      Urbanismo IA Fable e Opus
      Extração jurídica Opus
      Fallback Gemini
    Fontes de dados
      OSM Overpass
      CAR SICAR
      IBGE biomas
      ANA bacias
      INCRA SIGEF
      Copernicus DEM
      MapBiomas WorldCover
      SINAPI SICRO metodologia
    Cobertura
      BASE_FEDERAL
      PARCIAL_UF
      COMPLETA
    Plataforma
      Backend FastAPI Python
      Frontend Next.js React Leaflet
      Auth multi-tenant
      Docker Compose
      AWS Lightsail
      Fluxo dev main AWS
```
