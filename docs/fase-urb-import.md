# Fase URB-IMPORT — Carregar projeto de loteamento pronto (DWG/DXF)

**Data:** 24/07/2026 · **Pedido:** 2 usuários reais que já têm projeto aprovado/desenhado e
querem vê-lo dentro da plataforma. · **Decisões do operador (24/07):** (1) auditoria
medido×declarado ENTRA na fase 1; (2) ajuste manual fino de encaixe só se for barato —
o piso é best-fit + aceitar/rejeitar; (3) a etapa de confirmação de camadas fica (validar
com teste de usuário se incomoda); (4) formatos: **DWG e DXF** apenas (PDF de prancha fora).

**Regra de ouro:** NADA muda no fluxo atual de gerar proposta. Importar é um caminho
ADICIONAL que desemboca no MESMO contrato de proposta de urbanismo — financeira, laudo,
trilha e mapa funcionam sem saber que a proposta não foi gerada por nós.

## Fundamento (testado em 23-24/07 com os arquivos reais do cliente)

- O motor de ingestão JÁ existe (fase U9): `dwg2dxf` (libredwg) compilado no container +
  `ezdxf` lendo camadas. Reaproveitamos conversão, persistência por análise e EPSG default.
- `DESENHO1.DWG` (AutoCAD 2004) e `Planta_de_urbanização_Final.dwg` (AutoCAD 2018)
  converteram sem erro.
- Lote em CAD ≠ polígono: são linhas soltas compartilhadas entre vizinhos + rótulo MTEXT
  com a área (`A.: 429,94m²`). Fechamento por `unary_union` + `polygonize`:
  **89 dos 129 lotes fecharam de primeira**; auditoria medido×declarado bateu <2% em 70
  (mediana **0,16%**). Snap ingênuo de grade PIORA (perde interseções) — usar costura de
  pontas soltas (dangle-extend) para os restantes; o que sobrar vira PENDÊNCIA na UI.
- Georreferência: DESENHO1 está em SIRGAS/UTM 23S e o KMZ da gleba (Porto Real/RJ) cai
  dentro da extensão → overlay zero-toque. A Planta Final está em coordenada LOCAL →
  precisa de best-fit ao contorno da gleba.
- Privacidade: os arquivos do cliente NÃO entram no repositório. Testes usam fixture
  sintética com as mesmas patologias (linhas compartilhadas, pontas soltas, rótulos).

## Escopo da fase 1 (única fase desta spec; 1.5/2 ficam registradas no fim)

Wizard de 3 passos no card Urbanismo, entrada "Carregar projeto pronto (DWG/DXF)":

1. **Upload + inventário** — `POST /api/analises/{id}/urbanismo/importar`
   (multipart). Converte (DWG→DXF se preciso), varre o modelspace e devolve o INVENTÁRIO:
   por camada, contagem de entidades por tipo, nº de rótulos de área reconhecidos,
   extensão; e o diagnóstico de georreferência (UTM? EPSG sugerido? cobre a gleba?).
   Nenhuma decisão automática irreversível — só leitura.
2. **Mapeamento de camadas** — o usuário marca cada camada como
   `lote | via | verde | institucional | ignorar` (pré-marcadas por heurística de nome +
   geometria; ele só confere). O de-para confirmado fica salvo por análise (re-upload do
   mesmo autor reaproveita).
3. **Encaixe + conferência** — `POST /api/analises/{id}/urbanismo/importar/confirmar`
   com o de-para: fecha os polígonos (union → snap-rounding GEOS → polygonize → costura de
   pontas soltas), encaixa na gleba e devolve a PROPOSTA importada + auditoria + pendências.
   Encaixe: (a) UTM detectado e cobre a gleba → direto; (b) coordenada local → best-fit de
   similaridade (translação+rotação+escala) do desenho ao contorno da gleba, com score;
   o usuário vê o preview e ACEITA ou REJEITA. Ajuste manual fino (arrastar/girar) é
   stretch — só entra se sobrar espaço; não é critério de aceite da fase.

### O que a proposta importada carrega (mesmo contrato dos snapshots + extensões)

- `origem: "importado"` (+ nome do arquivo e data) — aparece no seletor de propostas.
- Quadro de áreas REAL medido geodesicamente (lotes, vias, verde, institucional, % da
  gleba), `indicadores.n_lotes`, GeoJSON por camada para o mapa.
- **Auditoria por lote:** `{lote, area_medida_m2, area_declarada_m2, dif_pct}` — declarada
  vem do rótulo do CAD; sem rótulo → só a medida (sem inventar). Diferenças >2% viram aviso.
- **Pendências:** rótulos de área sem polígono fechado e polígonos sem rótulo, listados —
  a plataforma NUNCA completa lote por conta própria (§5: não inventar dado).
- Proveniência: "geometria do arquivo do usuário; medição geodésica nossa (pyproj.Geod)".

### Degradação honesta

- Conversor indisponível/DWG ilegível → aceita DXF com mensagem clara de como exportar.
- Best-fit com score ruim → mostra mesmo assim com rótulo "encaixe não confiável — use
  arquivo georreferenciado (UTM/SIRGAS)"; o usuário decide.
- Nada de LLM em geometria; determinismo: mesmo arquivo + mesmo de-para → mesma proposta.

### Valores-ouro (fixture sintética espelhando a Planta Final)

- Inventário reconhece camadas e conta rótulos de área (regex `A.: N.NNN,NNm²`).
- Fechamento: fixture com N lotes de linhas compartilhadas + K pontas soltas de ≤20 cm →
  fecha N lotes; auditoria bate <2% em todos os fechados.
- Best-fit: fixture local transladada/rotacionada de um contorno conhecido → encaixa com
  erro médio <1 m; score reportado.
- Proposta importada alimenta financeira/trilha sem mudança nos cards (teste de contrato).

## Fora do escopo (registrado para depois)

- **Fase 1.5:** comparação lado a lado importado × proposta gerada (quadros e VGV).
- **Fase 2:** editar em cima do importado (mover vias, redesenhar quadras) — decidir só
  depois de medir o uso da fase 1.
- PDF vetorial de prancha, XREF/blocos complexos, projetos de infra (greide, redes).
