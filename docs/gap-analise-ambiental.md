# Gap de Análise Ambiental — laudo profissional × plataforma

> Referência: **Estudo de Viabilidade Ambiental — Geônoma (03/2025)**, Projeto Urbanisi,
> São Roque/SP (3 matrículas, ~18,19 ha). Laudo de engenheiro ambiental, 73 pp.
> Este doc cruza o que um laudo completo cobre com o que a plataforma já faz, e lista o
> que falta — para decidir o que implementar.

## 1. A "área alagada" — identificada pelo laudo

É uma **várzea / solo encharcado no fundo do vale** (cotas mais baixas do relevo), ligada a
**3 nascentes** mapeadas em campo. APP total de campo = **6,02 ha**. O cliente pretende
implantar um **lago/açude que recobre justamente essa várzea** (item 8.1.1 do laudo — "açude
que iria recobrir a várzea presente nas cotas mais baixas").

Vegetação típica da várzea citada: *Pleroma granulosum, Schinus terebinthifolia, Erythrina
speciosa, Psidium guajava, Hovenia dulcis*. Campo (06/02/25): "áreas de solo encharcado,
impossibilitando a passagem".

**Por que nossos rasters (MapBiomas 30 m / WorldCover 10 m) não pegaram:** o próprio laudo diz
que o mapeamento de campo **"difere dos mapas oficiais… por conta da escala"**. É uma várzea de
cabeceira pequena, só delimitável em campo/topografia. Conclusão para a plataforma: a triagem
por satélite serve de **pista** (talvegue de baixa declividade + nascente/curso d'água + classe
úmida), mas **não substitui** a delimitação de campo. Melhor proxy automático = **nascentes/APP
de hidrografia + declividade baixa no fundo de vale + JRC GSW (água sazonal)**.

## 2. O que a plataforma JÁ faz

| Dimensão | Fonte | Status |
|---|---|---|
| Hidrografia / APP de curso d'água | ANA (ArcGIS) | ✅ (grosseiro vs. campo — ver §4) |
| Massas d'água (lagos/represas) | ANA | ✅ |
| Unidades de Conservação | ICMBio/ANA | ✅ (só federal/estadual — ver §4) |
| Processos minerários | SIGMINE/ANM | ✅ (validado pelo laudo — §4) |
| Linhas de transmissão (faixa servidão) | ANEEL/SIGEL | ✅ |
| Cobertura vegetal | WorldCover/MapBiomas | ✅ (binário; sem bioma/fitofisionomia) |
| Declividade ≥30% (vedação) | DEM Copernicus | ✅ |
| Áreas úmidas/alagáveis | MapBiomas classe 11 + água | ✅ (novo) |
| Perfil municipal / LUOS | perfil municipal | ~ parcial |

## 3. Gaps — fatores do laudo que NÃO temos

Coluna "Auto?": 🟢 = geoserviço público federal (dá pra buscar sozinho, como MapBiomas/ANA);
🟡 = estadual/setorial (existe, mas confirmar endpoint por UF); 🔴 = por município (sem base
nacional — caso a caso).

### Prioridade ALTA
| Fator (item do laudo) | O que é / por que importa | Fonte | Auto? |
|---|---|---|---|
| **Reserva Legal + CAR** (7.1.3.2) | Déficit de RL bloqueia supressão; aqui já "começa devendo". Núcleo da viabilidade. | SICAR (federal) | 🟢 |
| **Bioma / Mata Atlântica** (7.1.2) | Lei 11.428 exige compensação florestal; muda o jogo no SE/litoral. | IBGE biomas + domínio MA (INPE/SOS) | 🟢 |
| **Área de Proteção de Mananciais (APM/APRM)** (7.2.8) | Restrição pesadíssima em SP/RMSP/litoral; limita densidade e impermeabilização. | Estadual (SP: SEMIL/DAEE) | 🟡 |
| **Terras Indígenas** (7.2.13) | Bloqueador forte onde incide. | FUNAI (geoserviço público) | 🟢 |
| **Dutovias gás/petróleo + faixa de servidão** (pedido do operador) | Comum no litoral; faixa non-aedificandi. **Não está neste laudo (interior), mas você pediu.** | ANP/EPE dados abertos; Transpetro | 🟡 |

### Prioridade MÉDIA
| Fator | O que é | Fonte | Auto? |
|---|---|---|---|
| **Territórios Quilombolas** (7.2.14) | Bloqueador onde incide. | INCRA + Fund. Palmares | 🟢 |
| **Assentamentos agrícolas** (7.2.15) | INCRA — incompatível com loteamento. | INCRA Acervo Fundiário | 🟢 |
| **Patrimônio Espeleológico (cavernas)** (7.2.7) | Raio de proteção de cavidade. | CANIE/CECAV (ICMBio) | 🟢 |
| **Áreas Prioritárias p/ Biodiversidade (APCB)** (7.2.9) | Diretriz de conservação. | MMA | 🟢 |
| **Patrimônio Arqueológico/Histórico** (7.2.16) | IPHAN (federal) + tombamento estadual (ex.: CONDEPHAAT-SP). | IPHAN geoserviço; estadual varia | 🟢/🟡 |
| **Áreas Contaminadas** (7.2.17) | CETESB (SP) e congêneres; crítico em área industrial/litoral. | Estadual (SP: relação CETESB) | 🟡 |
| **ZEE Estadual** (7.2.5) | Zoneamento Ecológico-Econômico — diretriz de uso. | Estadual | 🟡 |
| **Vegetação: bioma + fitofisionomia + estágio sucessional** | Refino do que já temos (hoje é binário verde/não-verde). | IBGE/MapBiomas | 🟢 |

### Prioridade BAIXA
| Fator | Fonte | Auto? |
|---|---|---|
| Corredores Ecológicos (7.2.11) | MMA/ICMBio | 🟢 |
| Reserva da Biosfera Mata Atlântica (7.2.10) | RBMA | 🟢 |
| Sítios RAMSAR — áreas úmidas internacionais (7.2.12) | MMA/RAMSAR | 🟢 |
| PDUI / Região Metropolitana (7.2.4) | Estadual/regional | 🟡 |
| Plano Diretor Ambiental Municipal / zoneamento (7.2.2/7.2.3) | Municipal (ZPPRE etc.) | 🔴 (casa com LUOS) |
| (bônus) Faixa de domínio rodovia/ferrovia (DNIT) | DNIT | 🟡 |
| (bônus) Zona de proteção de aeródromos | DECEA | 🟡 |

## 4. Cruzamentos do laudo com a plataforma (achados)

- ✅ **Mineração — validado:** o laudo cita "Processo **820.832/1997**, concessão de lavra
  (abril/2024)". Nossa plataforma detectou **exatamente** `ANM 820832/1997 — CONCESSÃO DE LAVRA`
  (95.628 m² na gleba). Camada correta.
- ⚠️ **UC municipal — gap:** o laudo aponta que a área faz **divisa com o Parque Municipal Mata
  da Câmara** (ZA = 3 km, sem plano de manejo). Nossa camada de UC (ICMBio/CNUC) provavelmente
  **não traz UCs municipais** → podemos estar perdendo UCs municipais. Verificar/complementar.
- 💡 **Modelo de saída:** o laudo resume tudo numa **matriz "Síntese dos Fatores Avaliados"**
  (Distância/Interferência · Anuência · Compatibilidade · Detalhes). É exatamente o formato que a
  nossa aba Ambiental poderia consolidar.
- 🏛️ **Licenciamento:** loteamento em SP → **CETESB via GRAPROHAB** (estadual). Útil como nota de
  proveniência/encaminhamento (não é cálculo).

## 5. Como decidir

Sugestão de ordem (maior valor × menor esforço, priorizando 🟢 federal auto-fetch):
1. **CAR/Reserva Legal** (🟢, ALTA) — núcleo de viabilidade.
2. **Bioma / Mata Atlântica** (🟢, ALTA) — gatilho de compensação.
3. **Terras Indígenas + Quilombolas + Assentamentos** (🟢) — bloqueadores fundiários, mesma
   família (INCRA/FUNAI/Palmares), dá pra fazer em lote.
4. **APM (mananciais)** (🟡, ALTA p/ SP) — exige fonte estadual; alto valor onde incide.
5. **Dutovias ANP** (🟡) — pedido do operador, relevante no litoral.
6. Cavernas/APCB/IPHAN/contaminadas (MÉDIA) — conforme demanda.

Cada nova camada segue o padrão já existente (fonte injetável, proveniência, degrada honesto,
teste-ouro + smoke ao vivo gated). Endpoints estaduais/🟡 a confirmar na implementação, como já
fazemos com ANA/ICMBio.
