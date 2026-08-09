# Fase AMB-EXC — Reconciliação ambiental pós-vistoria (IMPLEMENTADA em 09/08/2026)

> **08/08 — DECISÕES DO OPERADOR (fecham a spec):** (1) a reconciliação é do PRÓPRIO CLIENTE
> dono da análise — a plataforma não revisa (a responsabilidade técnica é do RT que assina o
> laudo do cliente; a plataforma registra proveniência e aplica a régua); (2) feature de PLANOS
> PAGOS; (3) laudo sem nº de ART/registro é ACEITO sem alarde (campo opcional; a proveniência
> registra o que foi informado); (4) MOCKUPS antes do código.
>
> Status: rascunho para aprovação do operador (08/08/2026). Base: pesquisa legal em
> `docs/pesquisa-legal-supressao-vegetacao.md` (2 rodadas, fontes primárias), laudo-modelo
> Geônoma/São Roque destilado em `docs/gap-analise-ambiental.md`, e prática descrita pelo
> operador (engenheiro vai a campo → análise visual → laudo diz o que pode ser suprimido e o
> que apareceu de novo). **DECISÃO DO OPERADOR: o módulo vale para o BRASIL TODO** — Caverá
> (Pampa) e São Roque (Mata Atlântica) são só casos de calibração dos dois regimes.

## 1. Problema e objetivo

Hoje a camada "Verde a verificar" (satélite) entra como restrição por prudência e não tem porta
de saída: nem quando o engenheiro constata em campo que pode suprimir (caso Caverá — o norte
vira remanescente por causa de manchas não confirmadas), nem no sentido inverso (área
alagada/banhado que só o campo revela — caso documentado no laudo Geônoma: várzea + 3 nascentes
que os rasters não pegaram "por conta da escala", APP de campo de 6,02 ha).

O módulo fecha o ciclo: **pré-análise → pacote de vistoria → laudo → reconciliação → recálculo**,
com proveniência em cada ajuste. A plataforma continua TRIAGEM: ela nunca autoriza nada — aplica
a consequência legal do que o laudo declarou, citando o dispositivo.

## 2. Régua legal em 3 camadas (degradação honesta, padrão da casa)

1. **Federal (sempre, qualquer gleba):** supressão de vegetação nativa exige CAR + autorização
   prévia do órgão competente (Lei 12.651/2012, art. 26; competência por LC 140/2011 — em regra
   estadual; municipal quando o município licencia). O módulo INFORMA o rito, não decide.
2. **Bioma (automática, por dado geoespacial nacional):** bioma IBGE (já integrado) + mapa
   oficial da área de aplicação da Lei 11.428 (IBGE). Se Mata Atlântica → regime especial dos
   arts. 25/30/31 (tabela na pesquisa legal: vedado / ≥50% / ≥30% / inicial, conforme estágio ×
   data do perímetro urbano). Se Pampa → rito estadual RS (IN SEMA-FEPAM 01/2021; campo nativo
   também é protegido). Demais biomas → regra federal geral.
3. **Estadual (perfil carregável, como os perfis municipais da LUOS):** código estadual (ex.:
   RS 15.434/2020 — banhado é APP), resolução de estágio da UF (CONAMA 33/94-RS, 1/94-SP…),
   órgão/rito. **Sem perfil da UF carregado → aplica federal+bioma e rotula** "regra estadual
   não carregada — verificar no órgão da UF" (nunca inventa). Cobertura declarada no resultado.

## 3. Fluxo (4 passos)

**(a) Segunda opinião automática (pré-campo).** Para cada mancha de "verde a verificar", o motor
cruza as fontes NACIONAIS disponíveis e emite um veredito de confiança POR MANCHA:
- Fase A (dados que já temos): WorldCover × MapBiomas (classe: florestal / campestre /
  silvicultura / pastagem) × CAR (remanescente declarado);
- Fase B (plugáveis depois, mesmo mecanismo dual-intake das camadas ambientais): altura de
  dossel 1 m (Meta/WRI) e Dynamic World (Google, série contínua).
Saída por mancha: `concordancia` (fontes convergem em mata / divergem / convergem em não-mata),
rotulada — mancha divergente = prioridade de vistoria. NENHUMA mancha é liberada por satélite.

**(b) Pacote de vistoria.** Um PDF/tela para o engenheiro levar a campo: mapa com as manchas
numeradas, a segunda opinião de cada uma, área, e os campos que o laudo precisa devolver
(formato inspirado na matriz "Síntese dos Fatores Avaliados" do laudo Geônoma).

**(c) Registro do laudo e ajustes (a reconciliação).** O operador anexa o laudo (PDF) +
responsável técnico + nº ART/registro + data da vistoria, e ajusta MANCHA A MANCHA:
- Mata Atlântica: declara o **estágio** (primária / avançado / médio / inicial) → o MOTOR aplica
  a consequência da tabela legal (vedado / preservar 50% / 30% / autorização), usando também a
  data de aprovação do perímetro urbano (campo declarável com fonte municipal);
- Pampa/demais: declara a formação (florestal / campestre / não-vegetação nativa) + parecer do
  laudo (suprimível com autorização / manter) → motor aplica o rito rotulado;
- **Sentido inverso:** desenhar/importar restrições NOVAS achadas em campo (banhado, nascente,
  APP de campo) — entram como restrição com a base (ex.: banhado-APP, Lei RS 15.434/2020).
Cada ajuste grava proveniência: laudo, responsável, data, base legal aplicada. Auditável e
versionado (o ajuste não apaga a leitura de satélite — sobrepõe com trilha).

**(d) Recálculo.** Aproveitável recalculado com as manchas reconciliadas → urbanismo regenerado.
O quadro, o card Ambiental e o PDF final rotulam: "análise ajustada por laudo de vistoria de
campo (doc. X, resp. Y, data Z)" e listam o que mudou (liberado/adicionado, m², dispositivo).

## 4. Contrato (esboço)

- `GET /api/analises/{id}/ambiental/manchas` → manchas de verde a verificar com id estável,
  área, segunda opinião por fonte, concordância, regime aplicável (federal/bioma/UF + cobertura).
- `POST /api/analises/{id}/ambiental/laudo` → `{arquivo, responsavel, registro, data_vistoria,
  ajustes: [{mancha_id | geometria_nova, acao, estagio?, formacao?, observacao}]}` → devolve o
  resumo da reconciliação (o que mudou, base legal por item) e dispara o recálculo.
- Novo core `ambiental_reconciliacao.py` (determinístico; a tabela legal é dado versionado, não
  hardcode espalhado) + persistência no store da análise (padrão dos demais artefatos).

## 5. Regras da casa aplicadas

- O laudo declara FATOS (estágio/formação/achados); a CONSEQUÊNCIA é do motor, determinística e
  com artigo citado — nunca "aprovado/viável".
- Dado ausente degrada rotulado (perfil de UF, data do perímetro urbano, laudo sem nº registro →
  aviso, não bloqueio silencioso).
- Nenhum número de município/UF hardcoded: perfis carregáveis + documentos confirmados.
- Testes-ouro: Caverá (Pampa) e São Roque/Geônoma (Mata Atlântica) como fixtures dos 2 regimes.

## 6. Fora de escopo (registrado)

Cálculo de compensação florestal (art. 17 da 11.428), volumetria de supressão, PRAD, emissão de
requerimentos aos órgãos (podem virar fases futuras). O módulo prepara e organiza; não protocola.

## 7. Decisões do operador (08/08/2026)

1. **Reconciliação é do cliente** dono da análise (a plataforma não revisa análises alheias; o
   responsável técnico é o do laudo do cliente). A tela deixa claro: triagem + registro; a
   autorização é sempre do órgão competente.
2. **Planos pagos apenas** (gate no padrão da casa).
3. **Laudo sem nº de ART/registro: aceito, sem alarde** — campo opcional; a proveniência grava
   o que foi informado (sem aviso ruidoso).
4. **Mockups antes do código** — 3 telas: manchas + segunda opinião; registro do laudo +
   reconciliação; resumo/recálculo. Fontes em `docs/mockups/mockup-ambexc-*.html`.
