# Fase U6 — Arquétipo de COMPOSIÇÃO PAISAGÍSTICA (loops/pods, padrão das referências)

> **U6a IMPLEMENTADA (2026-07-03)** — ver a entrada U6a no log do `ARCHITECTURE.md`.
> Knob extra: `paisagem_area_min_m2` (default 80.000 — gleba menor degrada rotulado).
> U6b (dedos d'água) segue como extensão futura.

> Spec derivada de 4 master plans de referência enviados pelo operador (Solido: Isla,
> Verano; + 2 planos com lagoas) e das 2 imagens Urbia anteriores. Objetivo: o estudo de
> massa do perfil ALTO deixar de "amontoar lotes em grelha" e compor como os escritórios
> de referência. Complementa a pesquisa (`pesquisa-motor-urbanismo.md`) e o perfil de
> estilo (Mov.2).

## 1. Gramática extraída das referências (o que TODAS têm em comum)

Ordem de camadas — **paisagem primeiro, lotes por último** (inversão do motor atual):

1. **Cinturão verde perimetral**: faixa preservada/arborizada em TODA a divisa (10–40 m);
   nenhum lote encosta na borda da gleba — a mata/buffer emoldura o empreendimento.
2. **Armadura central de amenidade**: lago (Isla, planos 3/4) ou verde central com
   trilhas (Verano) ocupando o miolo/vale; o clube ancora NA armadura (na orla, numa
   ilha, ou na borda do verde central) — nunca perdido no meio de quadras.
3. **Viário que ACOMPANHA a armadura**: anéis/loops concêntricos (Verano: espiral de
   3 anéis em torno do verde central; Isla: loops contornando o lago) ligados por uma
   espinha à entrada (boulevard + rotatória/portal). Sem grelha ortogonal.
4. **Fitas duplas de lotes** entre vias consecutivas: 2 fileiras costas-com-costas,
   perpendiculares à via, formando pods/"bairrinhos" curvos de **10–30 lotes**; o FUNDO
   do lote é o prêmio — fundo para água/verde sempre que possível (planos 3/4 levam ao
   extremo: dedos d'água serpenteiam para dar fundo-água a quase todo lote — coerente
   com a elasticidade <1 da orla na pesquisa §1).
5. **Cul-de-sacs com bulbo** encerrando loops que não fecham (bulbo circular; mini-praça/
   playground no olho do bulbo em vários casos).
6. **Amenidades SEMEADAS ao longo da rede** (Mov.1 já dá a biblioteca): estações pequenas
   nos bulbos, nos encontros de anéis e na orla — além do clube âncora.

### 1.1 Dois MODOS de traçado, escolhidos pela FORMA da gleba (2ª leva de referências)

- **"Anéis" (cebola)** — gleba COMPACTA (elongação < ~2,2): anéis aninhados de fitas
  curvas em volta da armadura (Lagoon-PR, Lake Side-RS, Verano); gleba grande pode
  partir em 2 células com via de costura.
- **"Folha" (espinha + nervuras)** — gleba ALONGADA/triangular (elongação ≥ ~2,2):
  espinha central no eixo longo + nervuras curvas diagonais (fitas duplas) morrendo em
  cul-de-sac (Ribeira-PB; SMA-PR é o caso linear). Seleção determinística pela razão
  dos lados do MRR da aproveitável; o operador pode forçar pelo estilo.
- A armadura pode ser MÚLTIPLAS células (verdes preservados + lago — SR-SP): os loops
  abraçam cada célula e os corredores as conectam.

## 2. Contrato da fase

- Novo arquétipo viário `"loops_paisagem"` no motor (ao lado de `grelha_eficiente`/
  sinuoso). Default do perfil ALTO via perfil de estilo (`arquetipo: "loops_paisagem"`
  no estilo — Mov.2); demais perfis mantêm os atuais.
- Pipeline determinístico (mesma gleba+programa+estilo → mesmo desenho):
  - **P1 cinturão**: buffer interno da divisa (largura no estilo, default 15 m) vira
    verde perimetral (entra na doação como verde);
  - **P2 armadura**: lago U3 (se pedido) OU o verde central (maior mancha de
    restrição/declividade OU o centróide) definem o "coração";
  - **P3 espinha+anéis**: boulevard da entrada ao coração + 2–3 anéis offsetados do
    coração (offsets = profundidade do lote ×2 + caixa da via), recortados à gleba;
  - **P4 fitas**: entre anéis consecutivos, fitas duplas de lotes (subdivisão atual
    reaproveitada por faixa curva); pods separados a cada ~24 lotes por corredor verde
    transversal (largura no estilo, default 12 m) ligando anel a anel;
  - **P5 bulbos**: ponta de anel que não fecha ganha bulbo de cul-de-sac (raio 9 m) com
    mini-praça no olho quando couber;
  - **P6 amenidades**: hub na armadura + estações da biblioteca semeadas nos corredores
    e bulbos (1 a cada N pods — knob de estilo).
- **U6b (extensão, fase própria)**: dedos d'água serpenteantes a partir do lago
  (planos 3/4) maximizando fundo-água — depende de DEM/outorga; fica fora da U6a.
- Critérios-ouro: cinturão contínuo ≥ largura mínima; nenhum lote encostando na divisa;
  ≥70% dos lotes em fitas de ≤2 fileiras; pods de 10–30 lotes; todo anel termina fechado
  ou em bulbo; corredores verdes ligando armadura↔cinturão em ≥2 pontos; clube a ≤50 m
  da armadura; determinismo; clamp legal e frente mínima intactos; conformidade de
  doação preservada.

## 3. Knobs novos no perfil de estilo (Mov.2)

| Chave | Default alto | Efeito |
|---|---|---|
| `arquetipo` | `loops_paisagem` | liga o arquétipo novo no perfil |
| `cinturao_verde_m` | 15 | largura do buffer perimetral |
| `pod_lotes_max` | 24 | corta corredor verde a cada N lotes |
| `corredor_verde_m` | 12 | largura dos corredores entre pods |
| `bulbo_raio_m` | 9 | raio do cul-de-sac |

## 4. Fora de escopo da U6a

Dedos d'água (U6b), pontes cerimoniais/ilha do clube, 2ª portaria, terraplenagem fina
dos anéis por cota (os anéis seguem a orientação topográfica global já existente).
