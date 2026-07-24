# Fase URB-IMPORT — Carregar projeto de loteamento pronto (DWG/DXF)

**Data:** 24/07/2026 · **Pedido:** 2 usuários reais que já têm projeto desenhado e querem
vê-lo dentro da plataforma. · **Decisões do operador (24/07):** (1) auditoria
medido×declarado ENTRA na fase 1; (2) ajuste manual fino de encaixe só se for barato — o
piso é best-fit + aceitar/rejeitar; (3) a etapa de confirmação de camadas fica (teste de
usuário dirá se incomoda); (4) formatos: **DWG e DXF** apenas (PDF de prancha fora).

**Regra de ouro:** NADA muda no fluxo atual de gerar proposta. Importar é um caminho
ADICIONAL que desemboca no MESMO contrato de proposta de urbanismo — financeira, laudo,
trilha e mapa funcionam sem saber que a proposta não foi gerada por nós.

## Fundamento (testado em 23-24/07 com os arquivos reais do cliente)

- O motor de ingestão JÁ existe (fase U9): `dwg2dxf` (libredwg) compilado no container +
  `ezdxf` lendo camadas. Reaproveitamos conversão, persistência por análise e EPSG default.
- `DESENHO1.DWG` (AutoCAD 2004/AC1018) e `Planta_de_urbanização_Final.dwg` (AutoCAD
  2018/AC1032) converteram sem erro.
- Lote em CAD ≠ polígono: linhas soltas compartilhadas entre vizinhos + rótulo MTEXT com a
  área (`A.: 429,94m²`). Fechamento por `unary_union` + `polygonize`: **89 dos 129 lotes
  fecharam de primeira**; auditoria medido×declarado bateu <2% em 70 (mediana **0,16%**).
  Snap ingênuo de grade PIORA (desloca interseções) — a costura correta é prolongar pontas
  soltas até o segmento vizinho (dangle-extend); o que não fechar vira PENDÊNCIA na UI.
- Georreferência: DESENHO1 está em SIRGAS/UTM 23S e o KMZ da gleba (Porto Real/RJ) cai
  dentro da extensão → overlay zero-toque. A Planta Final está em coordenada LOCAL
  (~570×499 m) → precisa de best-fit ao contorno da gleba.
- Privacidade: os arquivos do cliente NÃO entram no repositório. Testes usam fixture
  sintética com as mesmas patologias (linhas compartilhadas, pontas soltas, rótulos).

## Plano de entrega (3 incrementos; o operador testa entre eles)

| Incremento | Entrega | Como o operador testa |
|---|---|---|
| IMP-1 | Backend: upload → conversão → INVENTÁRIO de camadas + diagnóstico de georreferência | Swagger/curl com os DWGs reais |
| IMP-2 | Backend: confirmar de-para → fechamento + encaixe + proposta importada com auditoria e pendências | Swagger/curl; proposta aparece no card |
| IMP-3 | Frontend: wizard 3 passos no card Urbanismo + badge "importada" no seletor | Fluxo completo no navegador |

---

## IMP-1 — Inventário

`POST /api/analises/{analise_id}/urbanismo/importar` (multipart `arquivo`, dono da
análise; limite 50 MB; extensões `.dwg`/`.dxf`).

Pipeline: salva o original → DWG? converte via `converter_dwg_para_dxf` (U9) → `ezdxf`
varre o modelspace → devolve o inventário. NENHUMA decisão irreversível — só leitura.

```json
{
  "importacao_id": "sha256-do-conteudo",
  "arquivo": "Planta_final.dwg",
  "formato": "DWG 2018 (AC1032)",
  "camadas": [
    {"nome": "P1", "entidades": {"LINE": 121, "ARC": 105, "MTEXT": 129, "CIRCLE": 12},
     "rotulos_area": 129, "sugestao": "lote"},
    {"nome": "01 GUIA", "entidades": {"LWPOLYLINE": 68, "LINE": 15, "ARC": 4},
     "rotulos_area": 0, "sugestao": "via"},
    {"nome": "cotas", "entidades": {"DIMENSION": 367}, "rotulos_area": 0, "sugestao": "ignorar"}
  ],
  "georref": {"utm_detectado": false, "epsg_sugerido": null, "cobre_gleba": false,
              "largura_m": 570.0, "altura_m": 498.9},
  "avisos": []
}
```

- `importacao_id` = SHA-256 do conteúdo (determinístico; re-upload do mesmo arquivo
  reencontra tudo). Original + DXF convertido persistidos em
  `/data/perfis/importacoes/{analise_id}/{importacao_id}.*` (padrão U9; env
  `IMPORTACOES_DIR` para teste).
- **Rótulo de área:** regex sobre TEXT/MTEXT — `A.: 1.234,56m²` (nº pt-BR). Conta por
  camada; o parse fino acontece no IMP-2.
- **Detecção UTM:** E∈[160k, 834k] e N∈[1M, 10M] → UTM; zona derivada da longitude do
  CENTROIDE DA GLEBA (não do arquivo); hemisfério sul; EPSG SIRGAS 2000 (319xx).
  `cobre_gleba` = a extensão do arquivo, reprojetada, intersecta a gleba com folga de 1 km.
- **Heurística de sugestão** (pré-marcação; o usuário SEMPRE confere no IMP-3):
  `lote` = camada com mais rótulos de área; `via` = nome com GUIA/VIA/RUA/EIXO ou maior
  malha de linhas abertas; `verde`/`institucional` = nome ou MTEXT contendo VERDE/
  INSTITUCIONAL; `ignorar` = DIMENSION/cotas, molduras, texto puro, camadas de perfil
  (ESTACAS, GREIDE, CORTE, PERFIL), pontos.
- **Degradação:** conversor ausente (dev local sem container) → 422 com mensagem "envie
  DXF (Arquivo → Exportar → DXF no AutoCAD)"; DXF ilegível → 422 claro. Nunca 500.

### Valores-ouro IMP-1 (fixture sintética `tests/fixtures/projeto_importado.dxf`)

Fixture gerada por script de teste (ezdxf), espelhando as patologias reais: 6 lotes em 2
quadras como linhas compartilhadas (SEM polígono fechado), 2 pontas soltas de ≤0,3 m,
rótulos `A.: NNN,NNm²` dentro de cada lote, camada de guia, camada de cotas, moldura.
- Inventário lista as camadas com contagens exatas; `rotulos_area` = 6 na camada de lotes.
- Sugestões: lotes→`lote`, guia→`via`, cotas→`ignorar`.
- Variante em UTM 23S sobre a gleba de teste → `utm_detectado: true`, `cobre_gleba: true`;
  variante local → `false/false`.
- `.dwg` sem conversor no PATH → 422 com "DXF" na mensagem.

---

## IMP-2 — Confirmar: fechamento, encaixe, proposta importada

`POST /api/analises/{analise_id}/urbanismo/importar/{importacao_id}/confirmar`

```json
{
  "mapeamento": {"P1": "lote", "01 GUIA": "via", "P2": "verde", "cotas": "ignorar"},
  "salvar": false
}
```

`salvar: false` → calcula e devolve (preview do passo 3 do wizard); `true` → além de
devolver, grava como PROPOSTA no store de urbanismo (`origem: "importado"`), que passa a
aparecer no seletor do card. Mesma entrada → mesma saída (determinismo §4).

Motor (`core/importacao_dwg.py`, puro, sem rede/LLM):
1. Entidades das camadas `lote`+`via` → segmentos (LINE, LWPOLYLINE, ARC/CIRCLE achatados
   com flecha 5 cm; SPLINE achatada).
2. `unary_union` (nodeia cruzamentos) → **dangle-extend**: ponta solta a ≤ `tol` (default
   0,5 m) do segmento mais próximo é prolongada até ele → `polygonize`.
3. Faces classificadas: contém rótulo de área → LOTE (id sequencial por posição);
   sem rótulo, entre 40 m² e 5× o maior lote rotulado → lote_sem_rotulo (pendência);
   resto → descartada (miolo de via/sobra).
4. `verde`/`institucional`: polígonos fechados ou HATCH das camadas mapeadas; rótulo
   `Á.: ...m²` quando existir.
5. Vias = área da gleba − lotes − verde − institucional (fecho do quadro, como no motor
   atual), com o desenho da camada `via` no GeoJSON.
6. **Encaixe:** UTM detectado → reprojeta EPSG→WGS e pronto. Local → best-fit de
   similaridade (translação+rotação+escala uniforme) do casco do desenho ao polígono da
   gleba; `score` = IoU casco×gleba após o ajuste. Score < 0,80 → aviso "encaixe não
   confiável — confirme visualmente ou use arquivo georreferenciado". Ajuste manual fino é
   STRETCH (não é critério de aceite da fase).
7. Medição geodésica de tudo (`pyproj.Geod`, §regra 1) → quadro de áreas + indicadores.

Resposta (`salvar` true ou false):

```json
{
  "proposta": { "…mesmo contrato do snapshot de urbanismo…", "origem": "importado",
                "arquivo": "Planta_final.dwg" },
  "auditoria": {
    "resumo": {"lotes_medidos": 89, "com_rotulo": 87, "dif_mediana_pct": 0.0016,
               "acima_2pct": 3},
    "lotes": [{"id": "L-001", "area_medida_m2": 429.1, "area_declarada_m2": 429.94,
               "dif_pct": 0.002}]
  },
  "pendencias": {"rotulos_sem_lote": 40, "lotes_sem_rotulo": 2,
                 "itens": [{"tipo": "rotulo_sem_lote", "area_declarada_m2": 310.5,
                            "posicao": [x, y]}]},
  "encaixe": {"metodo": "best_fit", "score": 0.97}
}
```

- A proposta importada carrega quadro de áreas REAL (lotes, vias, verde, institucional, %
  da gleba), `indicadores.n_lotes`, GeoJSON por camada, e proveniência: "geometria do
  arquivo do usuário; medição geodésica da plataforma (pyproj.Geod)".
- Área declarada vem SÓ do rótulo do CAD; sem rótulo → só a medida. A plataforma NUNCA
  completa/inventa lote (§5) — pendência é informação, não correção automática.
- Financeira/laudo/trilha consomem a proposta sem mudança (teste de contrato).

### Valores-ouro IMP-2 (mesma fixture)

- 6/6 lotes fecham (dangle-extend costura as 2 pontas soltas); auditoria <2% em todos;
  quadro soma a área da gleba de teste (±0,5%).
- Rótulo órfão plantado na fixture → aparece em `pendencias.rotulos_sem_lote`.
- Fixture local (transladada+rotacionada de gabarito conhecido) → best-fit com erro médio
  <1 m e score ≥0,95; gabarito já em UTM → `metodo: "utm"`.
- `salvar: true` → snapshot no store com `origem: "importado"`; listagem do card o traz;
  trilha marca urbanismo concluído.
- Determinismo: duas chamadas idênticas → respostas idênticas.

---

## IMP-3 — Wizard no card Urbanismo

Entrada nova ao lado de "Gerar proposta": **"Carregar projeto pronto (DWG/DXF)"** — não
altera nada do fluxo existente. Wizard de 3 passos (padrão visual do `GuiaPassos`/UX-3):

1. **Arquivo** — upload; mostra formato detectado e avisos (ex.: "DWG convertido").
2. **Camadas** — tabela do inventário com as sugestões pré-marcadas; o usuário ajusta
   selects (`lote/via/verde/institucional/ignorar`). Botão "continuar" chama `confirmar`
   com `salvar: false`.
3. **Conferência** — mapa com o encaixe (score visível quando best-fit) + resumo da
   auditoria (n lotes, mediana, acima de 2%) + pendências. Botões: "Salvar como proposta"
   (`salvar: true`) e "Voltar" (ajustar camadas). Rejeitar encaixe = voltar/cancelar.

- No seletor de propostas, a importada ganha badge **"importada"** + nome do arquivo.
- Auditoria e pendências ficam visíveis na proposta aberta (tabela compacta, dif >2% em
  âmbar). O front só RENDERIZA — nenhum número é calculado em JS (§regra 2).
- Estados vazios/erros coerentes com UX-2 (o que é, o que precisa, quanto tempo leva).

---

## Degradação honesta (resumo)

- Sem conversor → só DXF, mensagem com o caminho de exportação no AutoCAD.
- Best-fit ruim → mostra com rótulo de baixa confiança; o usuário decide.
- Sem rótulos de área no arquivo → proposta sai só com áreas medidas (auditoria vazia,
  avisada).
- Nada de LLM em geometria; mesma entrada → mesma saída, sempre.

## Fora do escopo (registrado para depois)

- **Fase 1.5:** comparação lado a lado importado × proposta gerada (quadros e VGV).
- **Fase 2:** editar em cima do importado (mover vias, redesenhar quadras) — decidir após
  medir o uso da fase 1.
- PDF vetorial de prancha, XREF/blocos complexos, projetos de infra (greide, redes),
  ajuste manual de encaixe além do stretch citado.
