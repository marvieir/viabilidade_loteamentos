"""Urbanismo (Fase 9.1) — GERAÇÃO determinística com FIDELIDADE ao programa. NÚCLEO Python
puro (shapely): a IA propõe **programa + esqueleto** (intenção); o Python materializa toda a
geometria e mede. Sobe a fidelidade da v1 em três frentes, SEM mover a fronteira do §2:

  (a) MATERIALIZA o programa de áreas — reserva lazer (clube central + verde) e institucional
      ANTES de lotear, com a área medida CONVERGINDO para o programa (área reservada exata por
      busca binária de raio) ou DEGRADANDO rotulado quando a gleba não comporta.
  (b) VIÁRIO por arquétipo — consome o esqueleto da IA (coords normalizadas 0..1 → bbox da
      gleba; snap/clip/valida) como eixos-base; trecho inviável é descartado e contado.
  (c) TOPOGRAFIA — orienta a grelha de quarteirões por um ângulo derivado da declividade
      (DEM 2.5), calculado pelo chamador. Orientação geométrica (acompanhar curva de nível),
      NÃO terraplenagem.

A régua do §3 da spec: snap/buffer/offset/recorte/rotação/reservar/medir = OK; inventar
traçado, otimizar, dimensionar greide = projeto (do urbanista), fora. Determinístico.
"""

from __future__ import annotations

import math
from typing import Optional, Sequence

from shapely.affinity import rotate
from shapely.geometry import LineString, Point, Polygon, box
from shapely.geometry.base import BaseGeometry
from shapely.ops import nearest_points, polygonize, unary_union

from app.core import conexao as conexao_mod
from app.core import urbanismo_amenidades as amen
from app.core import urbanismo_tracado as trac
from app.core.urbanismo_medida import RAIO_CAMINHADA_M, Layout, _lados_mrr
from app.core.urbanismo_programa import PERFIL_LOTE, Programa

# Convergência: |medido − alvo| ≤ tol → "atendido" (spec §4.1).
TOL_CONVERGENCIA_PP = 0.03
# Degradação: reserva lazer só até sobrar área para ~este nº de lotes (preserva o parcelamento).
MIN_LOTES_RESERVA = 8
# Fração da reserva de lazer destinada ao clube central (resto = áreas verdes ao redor).
LAZER_CLUBE_FRAC = 0.40
# Fase U2 — lazer DISTRIBUÍDO (pesquisa §2: espaço aberto a ≤400 m/5 min a pé de qualquer
# lote): teto do orçamento de lazer que pode virar praça de BOLSO (o resto segue verde);
# praça de bolso é quadra PEQUENA (acima disso é parque, não bolso); nº máx de praças.
LAZER_PRACAS_FRAC = 0.35
PRACA_MAX_M2 = 2500.0
PRACAS_MAX_N = 6
ARQUETIPO_GRELHA = "grelha_eficiente"
# Via LOCAL (rua de quadra) — separa as quadras na grelha. A via PRINCIPAL (esqueleto) usa a
# largura do programa; ruas locais são estreitas (~8 m), o que mantém o viário realista.
VIA_LOCAL_M = 8.0
# Frente mínima legal (Lei 6.766/79 art. 4º II) — testada nunca abaixo disso.
FRENTE_MIN_M = 5.0
# Fase 11.3/11.4 — raio do disco do PÓRTICO (marcador da portaria no mapa). Também é a folga mínima
# da boca de entrada à mata reservada: a portaria não pode invadir a área preservada.
RAIO_PORTICO_M = 12.0
# Alcance máx. da via de acesso ao ponto de entrada (malha→ponto marcado/via real).
VIA_ACESSO_MAX_M = 400.0

# ---- Fase 9.7: MALHA VIÁRIA + QUADRAS COMO FACES (a inversão da geração, §0 da spec) ----
# Largura do TRONCO/coletora (hierarquia legal ≥21 m) — os eixos da IA viram via principal.
VIA_TRONCO_M = 21.0
# Nº de lotes que dá a TESTADA de uma quadra (espaça os eixos da grade local; o tamanho do lote
# continua emergindo da subdivisão — isto é só o passo da malha).
N_LOTES_QUADRA = 6
# Face menor que isso (m²) não vira quadra loteável → quadra VERDE formada (sobra, não sliver).
MIN_QUADRA_M2 = 250.0
ORLA_PARQUE_M = 18.0  # anel de orla-parque em volta da lâmina do lago (não a face inteira — U8)
# Critérios legais do INSTITUCIONAL (Lei 6.766/art. municipal): frente p/ via, compacidade,
# círculo inscrito, declividade. Frente/profundidade lido como NÃO-SLIVER (≥1/3) — ver nota no
# código (a spec escreve "≤1/3"; a razão técnica "não retalho" é o piso de compacidade ≥1/3).
INST_FRENTE_MIN_M = 10.0
INST_CIRCULO_DIAM_MIN_M = 10.0
INST_DECLIV_MAX_PCT = 15.0
RATIO_NAO_SLIVER = 1.0 / 3.0
# Fase 9.8 — PODA: comprimento mínimo (m) de um eixo dentro da ilha p/ valer como via (abaixo
# disso é cotovelo/caco). Um eixo só sobrevive se serve ≥1 quadra loteável adjacente.
L_MIN_EIXO_M = 25.0

# Fase 9.11 — GRADE ADAPTATIVA POR ILHA: o lado do quarteirão deixa de ser FIXO e passa a ser
# FUNÇÃO do tamanho da ilha. Causa provada com log real: a declividade estilhaça o aproveitável
# em ilhas pequenas/tortas; o quarteirão fixo (~90×62 m) recortado numa ilha pequena rende 2–3
# faces → quase nenhuma fronteira interna → viário colapsa (~5%) e os lotes ficam colados. A
# correção afina o quarteirão na ilha pequena (mais faces → mais fronteira interna → viário real),
# SEM nunca violar o piso legal de lote (clamp 9.4). Ilha grande mantém o teto do perfil — a caixa
# limpa NÃO regride (escala = 1,0). Decisão GEOMÉTRICA determinística do Python (§2), não do LLM.
AREA_ILHA_REF_M2 = 55_000.0   # ilha ≥ esta área usa o quarteirão CHEIO (teto do perfil)
ESCALA_QUADRA_MIN = 0.45      # afina no máximo até 45% do lado do teto (piso legal ainda manda)
# Ilha só adapta se comporta ao menos ~este nº de quarteirões no teto; abaixo disso é site único
# pequeno (não a gleba estilhaçada) e afinar só geraria slivers — mantém o teto (sem churn).
AREA_MIN_ADAPTA_QUADRAS = 3.0
# Fase 9.12 — CROSS-STREETS suficientes (correção da causa-raiz dos lotes encravados): profundidade
# máxima de face em múltiplos do quarteirão. 1,25 → face ≤ ~2 fileiras costas-com-costas, ambas
# lindeiras a uma via; assim TODA fileira nasce com frente para via (a geração resolve, o filtro
# 9.12 vira só rede de segurança). É o valor onde lotes_viraram_verde≈0 na caixa limpa.
FACE_BOUND_FACTOR = 1.25
COMPENSAR_REMOCAO = True       # +1 transversal antes da remoção da espinha (evita gap profundo)

try:  # shapely 2.x
    from shapely import make_valid as _make_valid
except Exception:  # pragma: no cover
    _make_valid = None


def _valido(geom: Optional[BaseGeometry]) -> Optional[BaseGeometry]:
    """Garante geometria VÁLIDA (a gleba real, corrigida por auto-interseção, gera diferenças
    inválidas que fazem o GEOS estourar no union). ``make_valid`` → fallback ``buffer(0)``."""
    if geom is None or geom.is_empty or geom.is_valid:
        return geom
    try:
        g = _make_valid(geom) if _make_valid is not None else geom.buffer(0)
        return g if (g is not None and not g.is_empty) else geom.buffer(0)
    except Exception:  # noqa: BLE001
        try:
            return geom.buffer(0)
        except Exception:  # noqa: BLE001
            return None


def _uniao_segura(geoms) -> Optional[BaseGeometry]:
    """``unary_union`` robusto: valida cada parte e, se ainda assim o GEOS estourar, une
    incrementalmente pulando o trecho problemático (degrada honesto, nunca derruba o request)."""
    parts = [_valido(g) for g in geoms if g is not None and not g.is_empty]
    parts = [g for g in parts if g is not None and not g.is_empty]
    if not parts:
        return None
    try:
        return unary_union(parts)
    except Exception:  # noqa: BLE001 — TopologyException → une incremental, validando
        acc = None
        for g in parts:
            try:
                acc = g if acc is None else unary_union([_valido(acc), _valido(g)])
            except Exception:  # noqa: BLE001 — pula o trecho que quebra
                continue
        return acc


def _diferenca_segura(a: BaseGeometry, b: Optional[BaseGeometry]) -> Optional[BaseGeometry]:
    """``a.difference(b)`` robusto a geometria inválida (valida antes; on-error devolve ``a``)."""
    if b is None or b.is_empty:
        return a
    try:
        return _valido(a).difference(_valido(b))
    except Exception:  # noqa: BLE001
        try:
            return a.buffer(0).difference(b.buffer(0))
        except Exception:  # noqa: BLE001
            return a


# ============================ componentes / grelha ============================
def _suavizar_raster(geom: BaseGeometry, tol: float = 12.0, fechar: float = 6.0,
                     sliver_min: float = 50.0) -> BaseGeometry:
    """Opção A — remove a ESCADA de 30 m (resolução do raster de mata/declividade) do contorno e
    dropa os CACOS (< ``sliver_min`` m²) que a interseção raster∩gleba deixa. Fechamento
    morfológico (buffer +r/−r arredonda os cantos retos em degrau) + Douglas-Peucker (colapsa os
    degraus colineares). Determinístico. A ±30 m de incerteza do DEM, uma linha suave é MAIS
    honesta que degraus falsos; sem isto o desenho fica serrilhado e nasce sliver que vira 'sobra'."""
    if geom is None or geom.is_empty:
        return geom
    pecas = [p for p in _componentes(geom) if p.area >= sliver_min]
    if not pecas:
        return geom
    base = _uniao_segura(pecas)
    if base is None or base.is_empty:
        return geom
    suave = base.buffer(fechar, join_style=1).buffer(-fechar, join_style=1).simplify(tol)
    suave = _valido(suave)
    return suave if (suave is not None and not suave.is_empty) else base


def _componentes(geom: BaseGeometry) -> list[Polygon]:
    """TODOS os polígonos buildáveis (a restrição pode partir a tela em várias ilhas). VALIDA a
    entrada (a gleba real, corrigida por auto-interseção, pode chegar inválida e estourar o GEOS
    na 1ª interseção) — choke point de robustez de toda a subdivisão."""
    geom = _valido(geom)
    if geom is None or geom.is_empty:
        return []
    if geom.geom_type == "Polygon":
        return [geom]
    if geom.geom_type in ("MultiPolygon", "GeometryCollection"):
        return [g for g in geom.geoms if g.geom_type == "Polygon" and not g.is_empty]
    return []


# ---- Fase 9.3/9.4: SUBDIVISÃO DE QUADRAS (o lote = o que a quadra comporta; §3 da spec) ----
# O tamanho de cada lote EMERGE da quadra (não é imposto), dentro do clamp legal [piso,teto].
# A partir da 9.7 a quadra é uma FACE da malha (não mais uma faixa de grade); `_subdividir_quadra`
# segue idêntico — é agnóstico à origem da quadra (reusado por `_lotear_face`).


def _maior_parte(geom: BaseGeometry) -> Optional[Polygon]:
    polis = _componentes(geom)
    return max(polis, key=lambda g: g.area) if polis else None


def _split_largura(c: Polygon, teto: float) -> list[Polygon]:
    """Pedaço > teto → subdivide em ``ceil(area/teto)`` faixas de largura igual (nunca um lote
    gigante; regra legal de remate, §3.4)."""
    if c.area <= teto:
        return [c]
    import math as _m
    k = max(int(_m.ceil(c.area / teto)), 2)
    x0, y0, x1, y1 = c.bounds
    w = (x1 - x0) / k
    out = []
    for i in range(k):
        p = _maior_parte(box(x0 + i * w, y0, x0 + (i + 1) * w, y1).intersection(c))
        if p is not None and p.area > 0:
            out.append(p)
    return out or [c]


def _clamp_faixa(cols: list[Polygon], piso: float, teto: float) -> list[Polygon]:
    """CLAMP LEGAL (§3.4): todo lote emitido fica em [piso, teto]. Colunas < piso são fundidas
    com a vizinha (até caber em teto); pedaços > teto são subdivididos; o que não vira lote
    viável é DESCARTADO aqui (a sobra é capturada como ``quadra − lotes`` e devolvida à área
    verde no §4). Garante ``fora_da_faixa == 0`` por construção (50 e 850 ficam impossíveis)."""
    base: list[Polygon] = []
    for c in cols:
        if c is None or c.is_empty or c.geom_type != "Polygon":
            continue
        base.extend(_split_largura(c, teto)) if c.area > teto else base.append(c)

    lotes: list[Polygon] = []
    cur: Optional[Polygon] = None
    a = 0.0
    for c in base:
        if cur is None:
            cur, a = c, c.area
        elif a < piso and a + c.area <= teto:  # ainda pequeno → funde p/ alcançar o piso
            cur = _maior_parte(unary_union([cur, c])) or cur
            a = cur.area
        else:  # cur já é lote viável (ou somar estouraria teto) → fecha cur, começa novo
            if a + 1e-6 >= piso:
                lotes.append(cur)
            cur, a = c, c.area  # cur descartado (se < piso) → vira sobra (não lote)
    if cur is not None:
        if a + 1e-6 >= piso:
            lotes.append(cur)
        elif lotes and lotes[-1].area + a <= teto:  # remate: funde no último se couber
            lotes[-1] = _maior_parte(unary_union([lotes[-1], cur])) or lotes[-1]
    return lotes


def _subdividir_quadra(piece: Polygon, y0: float, y1: float, testada_alvo: float,
                       alvo_area: float, piso: float, teto: float):
    """Subdivide UMA quadra: n escolhido pela PROFUNDIDADE da quadra para a área mirar ``alvo``
    (quadra rasa → lote mais largo), depois CLAMP legal por lote em [piso, teto]. O tamanho
    emerge da quadra (9.3), nunca sai da faixa legal (9.4). Devolve ``(lotes, residual)`` —
    ``residual = quadra − lotes`` (a sobra de ponta, devolvida à área verde no §4)."""
    x0, _, x1, _ = piece.bounds
    L = x1 - x0
    if L <= 0 or piece.area < piso * 0.5:
        return [], piece  # quadra menor que meio lote → toda residual (vira área verde)
    depth = piece.area / L  # profundidade média da quadra
    alvo = min(max(alvo_area, piso), teto)
    # Fase 9.12 — PREFERÊNCIA SUAVE de testada por faixa (alto ≥15 / médio ≥10 / popular ≥5 m, via
    # ``testada_alvo`` das diretrizes): orienta o corte p/ a frente típica do padrão, sem rejeitar
    # lote (o clamp de área manda; testada é tendência). Evita "alto padrão" com 9 m de frente.
    # A preferência NUNCA empurra a área acima do teto: cap em ``teto/depth`` (numa quadra funda, a
    # testada típica cederia ao teto legal — caso contrário o lote estoura [piso,teto]).
    teto_testada = max(teto / depth, FRENTE_MIN_M)
    testada_eff = min(max(min(alvo / depth, teto / depth), FRENTE_MIN_M, testada_alvo), teto_testada)
    n = max(int(round(L / testada_eff)), 1)
    # Fase 9.4/9.12 — clamp de área POR CONSTRUÇÃO: n tem de manter o lote em [piso, teto].
    #   n ≥ ⌈área/teto⌉ (senão (L/n)·depth > teto — lote gigante) e n ≤ ⌊área/piso⌋ (senão < piso,
    #   e o clamp descarta tudo). Se conflitam (face funda), o TETO manda (n maior) e a sobra que
    #   ficaria < piso vira verde no _clamp_faixa — nunca um lote fora da faixa (fora_da_faixa==0).
    n_teto_min = max(math.ceil(piece.area / max(teto, 1.0)), 1)
    n_piso_max = max(int(piece.area / max(piso, 1.0)), 1)
    n = min(max(n, n_teto_min), max(n_piso_max, n_teto_min))
    tr = L / n  # testada real → fecha a quadra exatamente
    cols: list[Polygon] = []
    for k in range(n):
        parte = _maior_parte(box(x0 + k * tr, y0, x0 + (k + 1) * tr, y1).intersection(piece))
        if parte is not None and parte.area > 0:
            cols.append(parte)
    lotes = _clamp_faixa(cols, piso, teto)
    # Sobra de ponta (§4) = tudo da quadra que não virou lote → devolvido à ÁREA VERDE adjacente
    # (NUNCA retalho perdido nem viário inflado). Operação geométrica determinística (§2).
    residual = _diferenca_segura(piece, _uniao_segura(lotes)) if lotes else piece
    residual = _valido(residual)
    return lotes, (residual if (residual is not None and not residual.is_empty) else None)


# ============================ Fase 9.7: MALHA VIÁRIA + FACES ============================
# A INVERSÃO (§0): as ruas vêm primeiro (malha conexa a partir do esqueleto da IA), as quadras
# são as FACES que as ruas cercam (polygonize), e as áreas públicas viram quadras formadas. O
# §2 não se move: a IA propõe os eixos (semente); o Python constrói a malha, deriva as faces e
# mede — nenhuma coordenada final vem do LLM.


def _linhas(geom: Optional[BaseGeometry]) -> list[LineString]:
    """Extrai as LineStrings de um recorte (pode vir Multi/GeometryCollection do intersection)."""
    if geom is None or geom.is_empty:
        return []
    if geom.geom_type == "LineString":
        return [geom]
    if geom.geom_type in ("MultiLineString", "GeometryCollection"):
        return [g for g in geom.geoms if g.geom_type == "LineString" and g.length > 0]
    return []


def _eixos_da_ilha(reg: BaseGeometry, eixos_ia: Sequence[BaseGeometry], block_w: float,
                   block_h: float, via_local: float, via_tronco: float):
    """Eixos (centerlines + largura) de UMA ilha, JÁ EXPLODIDOS EM SEGMENTOS dentro da ilha. Em
    gleba irregular, uma reta da grade recortada à ilha vira VÁRIOS segmentos — o stub é um
    SEGMENTO (não a reta inteira), então a poda precisa vê-los separados. Grade local recortada à
    ILHA (não ao bbox) + eixos da IA como TRONCO; sem IA, promove o segmento central a tronco."""
    minx, miny, maxx, maxy = reg.bounds
    W, H = (maxx - minx), (maxy - miny)
    brutos: list[tuple[LineString, float, bool]] = []  # (reta, largura, é_tronco)
    nbx = max(int(round(W / (block_w + via_local))), 1)
    nby = max(int(round(H / (block_h + via_local))), 1)
    # Fase 9.12 — CROSS-STREETS suficientes (correção da causa-raiz): o arredondamento podia ESTICAR
    # a face muito além do quarteirão (ex.: 172 m = 6 fileiras), e as fileiras do MEIO não tocam via
    # nenhuma → lote encravado por construção. Garante linhas o bastante p/ a face não passar de ~2
    # fileiras costas-com-costas (≤ block·1,25); assim TODA fileira nasce lindeira a uma via.
    nbx = max(nbx, math.ceil(W / max(block_w * FACE_BOUND_FACTOR, 1.0)))
    nby = max(nby, math.ceil(H / max(block_h * FACE_BOUND_FACTOR, 1.0)))

    # IA tronco (curva) ∩ ilha → segmentos. Fase 9.9: a via-tronco curva é o eixo principal; a
    # grade local segue ORTOGONAL (mantém o lote/viário da 9.8). Para não SOMAR via, a grade NÃO
    # gera a linha da família PARALELA à tronco mais próxima dela (a curva a substitui).
    tron_partes: list[LineString] = []
    for e in (eixos_ia or []):
        for part in _linhas(_valido(e.intersection(reg)) if e is not None else None):
            if part.length > 0:
                tron_partes.append(part)
    tem_tronco_ia = bool(tron_partes)
    tron_horizontal = False
    if tem_tronco_ia:
        dx = sum(abs(p.coords[-1][0] - p.coords[0][0]) for p in tron_partes)
        dy = sum(abs(p.coords[-1][1] - p.coords[0][1]) for p in tron_partes)
        tron_horizontal = dx >= dy
    tron_c = unary_union(tron_partes).centroid if tron_partes else None

    # Fase 9.12 — COMPENSA a remoção: a espinha vai tirar 1 linha da família paralela a ela; some 1
    # antes de gerar, p/ que DEPOIS da remoção a malha ainda tenha transversais o bastante (a face
    # não passa de ~2 fileiras nem nas pontas onde a curva não alcança). Sem isso, remover a única
    # transversal deixava a face com 4-6 fileiras (meio encravado) — a causa-raiz do bug.
    if tem_tronco_ia and COMPENSAR_REMOCAO:
        if tron_horizontal:
            nby += 1
        else:
            nbx += 1

    verts = [minx + i * W / nbx for i in range(1, nbx)]
    horiz = [miny + j * H / nby for j in range(1, nby)]
    # Fase 9.9: a curva (espinha) SUBSTITUI a linha de grade paralela mais próxima (a curva é a via
    # ali; evita via dupla). Fase 9.12: a grade já vem com transversais o bastante (bound acima) e
    # o _lotear_face capa em 2 fileiras costas-com-costas — então, mesmo onde a curva não cobre toda
    # a largura, a face funda vira 2 fileiras que tocam a via de cada lado (a do meio nunca existe).
    if tem_tronco_ia and tron_c is not None:
        if tron_horizontal and horiz:
            horiz.remove(min(horiz, key=lambda y: abs(y - tron_c.y)))
        elif not tron_horizontal and verts:
            verts.remove(min(verts, key=lambda x: abs(x - tron_c.x)))
    for x in verts:
        brutos.append((LineString([(x, miny), (x, maxy)]), via_local, False))
    for y in horiz:
        brutos.append((LineString([(minx, y), (maxx, y)]), via_local, False))
    for part in tron_partes:
        brutos.append((part, via_tronco, True))

    # EXPLODE cada reta nos segmentos que caem DENTRO da ilha (o recorte parte a reta).
    segs: list[list] = []  # [LineString, largura, é_tronco] (mutável p/ promover tronco)
    for ls, w, is_t in brutos:
        for part in _linhas(_valido(ls.intersection(reg))):
            if part.length > 0:
                segs.append([part, w, is_t])

    # ``troncos_ia`` = só a via-tronco PROPOSTA PELA IA (a espinha) — protegida da poda. Sem IA,
    # promove-se o segmento central a tronco (largura), mas ele NÃO é protegido (é só grade): numa
    # gleba irregular ele pode ser um caco e deve ser podado como os ramos locais.
    troncos_ia: list[LineString] = []
    if tem_tronco_ia:
        troncos_ia = [s[0] for s in segs if s[2]]
    elif segs:  # sem IA: promove o segmento longo mais central a tronco-largura (não protegido)
        c = reg.centroid
        cand = [s for s in segs if s[0].length >= L_MIN_EIXO_M] or segs
        s = min(cand, key=lambda s: s[0].centroid.distance(c))
        s[1] = via_tronco
    return [(s[0], s[1]) for s in segs], troncos_ia


def _faces_de(reg: BaseGeometry, eixos) -> list[Polygon]:
    """Faces que as ruas cercam (``polygonize`` da borda da ilha ∪ eixos), dentro da ilha."""
    linhas = [reg.boundary] + [g for g, _ in eixos]
    noded = _uniao_segura(linhas)
    faces: list[Polygon] = []
    if noded is None or noded.is_empty:
        return faces
    for f in polygonize(noded):
        if f.is_empty:
            continue
        try:
            dentro = reg.contains(f.representative_point())
        except Exception:  # noqa: BLE001 — ponto representativo degenerado
            dentro = reg.intersects(f.centroid)
        if dentro:
            faces.append(f)
    return faces


def _ruas_de(reg: BaseGeometry, eixos) -> Optional[BaseGeometry]:
    """Polígono de ruas = união dos buffers (largura/2) das centerlines ∩ ilha."""
    ruas = _uniao_segura([
        _valido(g.intersection(reg)).buffer(w / 2.0, cap_style=2, join_style=2)
        for g, w in eixos if g is not None and not g.intersection(reg).is_empty
    ])
    if ruas is None or ruas.is_empty:
        return None
    return _valido(ruas.intersection(reg))


def podar_stubs(reg: BaseGeometry, faces: list[Polygon], eixos, troncos_ia,
                via_local: float, via_tronco: float):
    """PODA DETERMINÍSTICA (§2): o viário é a REDE DE RUAS = as fronteiras INTERNAS entre faces
    (onde dois blocos se encontram), descontado o perímetro da ilha. Isso mantém a parte ÚTIL de
    cada eixo (que dá frente a duas quadras) e descarta só os STUBS — trechos pendurados/cacos
    que o recorte da gleba irregular deixou (não são fronteira de bloco) e cotovelos < L_MIN. A
    largura segue a hierarquia (tronco onde o eixo é tronco, senão local). Devolve
    ``(ruas, eixos_uteis, n_stubs)``. Estável e sem cascata (a rede sai das faces, de uma vez)."""
    bordas = _uniao_segura([f.boundary for f in faces])
    if bordas is None or bordas.is_empty:
        return None, [], len(eixos)
    perim = reg.boundary.buffer(0.5)
    internas = _valido(_diferenca_segura(bordas, perim))
    if internas is None or internas.is_empty:
        return None, [], len(eixos)

    # ruas = faixa LOCAL em toda a rede interna; TRONCO (mais largo) onde a rede coincide com um
    # eixo de tronco-largura (espinha local/IA). A via-tronco da IA é SEMPRE materializada por
    # inteiro (protegida da poda — é a espinha proposta; a 9.9 a torna sinuosa).
    partes = [internas.buffer(via_local / 2.0, cap_style=2, join_style=2)]
    tron_largos = _uniao_segura([g for g, w in eixos if w >= via_tronco - 1e-6])
    if tron_largos is not None and not tron_largos.is_empty:
        tron_rede = _valido(internas.intersection(tron_largos.buffer(0.6)))
        if tron_rede is not None and not tron_rede.is_empty:
            partes.append(tron_rede.buffer(via_tronco / 2.0, cap_style=2, join_style=2))
    ia_u = _uniao_segura([_valido(t.intersection(reg)) for t in troncos_ia]) if troncos_ia else None
    if ia_u is not None and not ia_u.is_empty:  # espinha da IA: sempre por inteiro
        partes.append(ia_u.buffer(via_tronco / 2.0, cap_style=2, join_style=2))
    ruas = _uniao_segura(partes)
    ruas = _valido(ruas.intersection(reg)) if (ruas is not None and not ruas.is_empty) else None

    # classifica cada eixo: ÚTIL se é tronco da IA OU ≥50% do segmento está na rede; senão stub.
    rede_buf = internas.buffer(0.5)
    ia_set = {id(t) for t in troncos_ia}
    uteis, n_stub = [], 0
    for g, _w in eixos:
        seg = _valido(g.intersection(reg))
        comum = _valido(seg.intersection(rede_buf)) if (seg is not None and not seg.is_empty) else None
        util = id(g) in ia_set or (
            seg is not None and comum is not None and comum.length >= 0.5 * seg.length
        )
        if util:
            uteis.append(g)
        else:
            n_stub += 1
    return ruas, uteis, n_stub


def lado_quadra_adaptativo(area_ilha: float, teto_w: float, teto_h: float,
                           piso_w: float, piso_h: float) -> tuple[float, float]:
    """Fase 9.11 — lado do quarteirão ``(largura, altura)`` ADAPTADO ao tamanho da ilha, com
    clamp legal. Ilha grande (≥ ``AREA_ILHA_REF_M2``) → teto do perfil (caixa limpa intacta);
    ilha pequena/torta → AFINA o quarteirão (escala = √(área/ref)) para gerar faces adjacentes —
    fronteira interna = viário —, mas NUNCA abaixo do piso (lote ≥ mínimo, clamp 9.4 preservado).
    Pura geometria determinística (§2): não vem do LLM, só do tamanho da ilha + piso legal."""
    escala = min(1.0, max(ESCALA_QUADRA_MIN, math.sqrt(max(area_ilha, 0.0) / AREA_ILHA_REF_M2)))
    return max(piso_w, teto_w * escala), max(piso_h, teto_h * escala)


def _bandas_contorno_eixos(ilha: BaseGeometry, contornos_ilha: Sequence[BaseGeometry],
                           via_local: float, via_tronco: float, conn_m: float):
    """Opção B ORGÂNICA — eixos da malha LOCAL em BANDAS DE CONTORNO (frame reg, cota ~horizontal):
    as curvas de nível são as RUAS ao longo da encosta; conectores VERTICAIS (descendo a encosta)
    a cada ``conn_m`` fecham as quadras. Devolve ``[(LineString, largura)]`` p/ ``eixos_prontos``.
    A curva mais LONGA vira via-tronco (coletora); as demais e os conectores são locais."""
    contos = [c for c in contornos_ilha if c is not None and c.length >= L_MIN_EIXO_M]
    if not contos:
        return None
    tronco = max(contos, key=lambda c: c.length)
    eixos: list[tuple[BaseGeometry, float]] = [
        (c, via_tronco if c is tronco else via_local) for c in contos
    ]
    minx, miny, maxx, maxy = ilha.bounds
    x = minx + conn_m * 0.5
    while x < maxx:
        eixos.append((LineString([(x, miny - 1.0), (x, maxy + 1.0)]), via_local))
        x += conn_m
    return eixos


def _paisagem_eixos(ilha: BaseGeometry, contornos_ilha: Sequence[BaseGeometry],
                    via_local: float, via_tronco: float, banda: float, conn_m: float):
    """Trilha 2 — gramática PAISAGEM (objetivo "desenho", padrão Urbia): as ruas SÃO as curvas de
    nível REAIS do levantamento, ESPAÇADAS de verdade (varredura descendo a encosta + checagem de
    distância geométrica ≥ banda — sem isso toda curva vira rua e o viário incha p/ ~30%). Cada rua
    RECUA das bordas (~2,5×via) → a ponta morre dentro da ilha (grau 1) → bulbo de CUL-DE-SAC
    (Art. 11 IX). Conectores esparsos descem a encosta. A mais longa vira via-tronco (coletora).
    Devolve ``[(LineString, largura)]`` p/ ``eixos_prontos``; None degrada p/ bandas/grade."""
    recorte: list[BaseGeometry] = []
    for c in contornos_ilha:
        if c is None or c.is_empty:
            continue
        inter = _valido(c.intersection(ilha))
        if inter is None:
            continue
        for p in _linhas(inter):
            if p.length >= L_MIN_EIXO_M:
                recorte.append(p)
    if not recorte:
        return None
    # SUAVIZAÇÃO (corte de cantos de Chaikin, 2 passadas): as curvas do LEVANTAMENTO (densas) quase
    # não mudam; as do DEM de 30 m (5-9 pontos, serrilhadas) ficam redondas — o modo Paisagem SEM
    # levantamento sai orgânico-aproximado em vez de anguloso. Determinístico.
    def _chaikin(ls, passadas=2):
        pts = list(ls.coords)
        for _ in range(passadas):
            if len(pts) < 3:
                break
            novo = [pts[0]]
            for a, b in zip(pts[:-1], pts[1:]):
                novo.append((0.75 * a[0] + 0.25 * b[0], 0.75 * a[1] + 0.25 * b[1]))
                novo.append((0.25 * a[0] + 0.75 * b[0], 0.25 * a[1] + 0.75 * b[1]))
            novo.append(pts[-1])
            pts = novo
        return LineString(pts)

    recorte = [_chaikin(c) for c in recorte]
    recorte.sort(key=lambda c: c.centroid.y)   # descendo a encosta (frame reg: cota ~horizontal)
    kept: list[BaseGeometry] = []
    ultima = None
    for c in recorte:
        if ultima is not None and c.distance(ultima) < banda:
            continue  # perto demais da rua anterior → quadra rasa/viário inchado; pula
        rec = min(via_local * 2.5, c.length * 0.2)
        if c.length > 2 * rec + L_MIN_EIXO_M:
            ini, fim = rec / c.length, 1 - rec / c.length
            pts = [c.interpolate(ini + (fim - ini) * i / 24, normalized=True) for i in range(25)]
            c = LineString([(p.x, p.y) for p in pts])
        kept.append(c)
        ultima = c
    if not kept:
        return None
    tronco = max(kept, key=lambda c: c.length)
    eixos: list[tuple[BaseGeometry, float]] = [
        (c, via_tronco if c is tronco else via_local) for c in kept
    ]
    minx, miny, maxx, maxy = ilha.bounds
    x = minx + conn_m * 0.5
    while x < maxx:
        eixos.append((LineString([(x, miny - 1.0), (x, maxy + 1.0)]), via_local))
        x += conn_m
    return eixos


def _faixas_fluidas_eixos(ilha: BaseGeometry, via_local: float, via_tronco: float,
                          banda: float, conn_m: float):
    """Gramática FAIXAS FLUIDAS (U8 — padrão SR/Ribeira, gleba ALONGADA): família de curvas
    PARALELAS e uniformemente espaçadas (offsets de uma espinha suave) ao longo do eixo da cota —
    ruas harmônicas que seguem a declividade — mais conectores de descida ESPARSOS (viram
    cul-de-sac). Frame reg (a cota é ~horizontal). Devolve ``[(LineString, largura)]`` p/
    ``eixos_prontos``. Espaçamento UNIFORME por construção (sem o emaranhado das curvas cruas)."""
    minx, miny, maxx, maxy = ilha.bounds
    W, H = maxx - minx, maxy - miny
    if W < banda or H < banda:
        return None
    xg = [minx - 20.0 + i * (W + 40.0) / 47.0 for i in range(48)]
    amp = H * 0.08  # ondulação suave (orgânico) — pequena o bastante p/ não colapsar offsets
    meio = (miny + maxy) / 2.0
    eixos: list[tuple[BaseGeometry, float]] = []
    s = -H
    while s < H:
        ys = [meio + s + amp * math.sin((x - minx) / max(W, 1.0) * math.pi * 1.3) for x in xg]
        for parte in _linhas(_valido(LineString(list(zip(xg, ys))).intersection(ilha))):
            if parte.length >= L_MIN_EIXO_M:
                eixos.append((parte, via_local))
        s += banda
    x = minx + conn_m * 0.5
    while x < maxx:
        for parte in _linhas(_valido(LineString([(x, miny - 1.0), (x, maxy + 1.0)]).intersection(ilha))):
            if parte.length >= L_MIN_EIXO_M:
                eixos.append((parte, via_local))
        x += conn_m
    return eixos or None


def _bulbos_cul_de_sac(eixos: Sequence[BaseGeometry], ilha: BaseGeometry,
                       via_local: float, raio: float, acesso: Optional[BaseGeometry] = None):
    """U8 — CUL-DE-SAC (Art.11 IX + look Urbia): num CONDOMÍNIO FECHADO, TODA ponta de via de grau 1
    é via SEM SAÍDA e ganha bulbo de retorno — a rua morre contra a mata, na divisa ou no fim de
    banda, e o carro precisa retornar. A ÚNICA exceção é a ponta do ACESSO (pórtico/entrada), que
    liga à via pública. Devolve os discos (∩ ilha) p/ unir ao arruamento. Determinístico."""
    bulbos: list[BaseGeometry] = []
    linhas = [e for e in eixos if e is not None and not e.is_empty]
    if not linhas:
        return bulbos
    for ls in linhas:
        cs = list(ls.coords)
        for c in (cs[0], cs[-1]):
            pt = Point(c)
            grau = sum(1 for e in linhas if e.distance(pt) <= 0.6)
            if grau > 1:
                continue  # encontra outra via → é cruzamento, não ponta morta
            if acesso is not None and not acesso.is_empty and pt.distance(acesso) <= via_local * 3.0:
                continue  # é a ENTRADA (liga à via pública) — não é via sem saída
            disco = _valido(pt.buffer(raio, quad_segs=16).intersection(ilha))
            if disco is not None and not disco.is_empty:
                bulbos.append(disco)
    return bulbos


def construir_malha(reg: BaseGeometry, eixos_ia: Sequence[BaseGeometry], block_w: float,
                    block_h: float, via_local: float, via_tronco: float, podar: bool = True,
                    eixos_prontos=None):
    """MALHA de UMA ILHA (frame rotacionado ``reg``): grade local recortada à ilha + tronco,
    depois PODA dos stubs (Fase 9.8). Devolve ``(faces, ruas, eixos, troncos, n_stubs)`` — a
    malha é conexa DENTRO da ilha (a gleba partida por restrição é tratada como ilhas separadas).

    Fase U6a — ``eixos_prontos`` ([(LineString, largura)]) substitui a grade axial pelo
    traçado PAISAGÍSTICO (anéis/folha); faces, poda e bulbos seguem o pipeline idêntico."""
    if eixos_prontos:
        eixos = list(eixos_prontos)
        troncos = [g for g, w in eixos if w >= via_tronco - 1e-6]
    else:
        eixos, troncos = _eixos_da_ilha(reg, eixos_ia, block_w, block_h, via_local, via_tronco)
    if not eixos:  # ilha menor que um bloco → uma quadra só, sem via interna (degrada honesto)
        return [g for g in _componentes(reg)], None, [], [], 0
    faces = _faces_de(reg, eixos)  # estável: danglers não criam face (polygonize os ignora)
    if not podar:
        return faces, _ruas_de(reg, eixos), [g for g, _ in eixos], troncos, 0
    ruas, eixos_uteis, n_stubs = podar_stubs(reg, faces, eixos, troncos, via_local, via_tronco)
    return faces, ruas, eixos_uteis, troncos, n_stubs


def _lotear_face(face: BaseGeometry, testada_alvo: float, prof: float, alvo_area: float,
                 piso: float, teto: float):
    """Loteia UMA quadra (face da malha): divide em fileiras de profundidade ~``prof`` e REUSA
    ``_subdividir_quadra`` em cada fileira (clamp legal da 9.4 intacto). A face já está no frame
    rotacionado (eixos axiais), então as fileiras são horizontais. Devolve ``(lotes, residuais)``."""
    lotes: list[Polygon] = []
    residuais: list[BaseGeometry] = []
    for comp in _componentes(face):
        minx, miny, maxx, maxy = comp.bounds
        depth = maxy - miny
        if depth <= 0 or comp.area < piso * 0.5:
            residuais.append(comp)
            continue
        # Fase 9.12 — CAP em 2 fileiras (costas-com-costas): uma quadra entre duas vias tem no
        # máximo 2 fileiras de lote, que dividem a face e tocam cada uma a via de um lado (frente);
        # nunca 3+ (a do meio ficaria encravada). Com a grade já bound (≤~2 fileiras), o cap é a
        # rede de segurança que garante, POR CONSTRUÇÃO, que toda fileira é lindeira a uma via.
        nrows = min(max(int(round(depth / prof)), 1), 2)
        rh = depth / nrows
        for r in range(nrows):
            y0 = miny + r * rh
            y1 = maxy if r == nrows - 1 else miny + (r + 1) * rh
            faixa = _valido(comp.intersection(box(minx, y0, maxx, y1)))
            for piece in _componentes(faixa):
                sub, res = _subdividir_quadra(piece, y0, y1, testada_alvo, alvo_area, piso, teto)
                lotes.extend(sub)
                if res is not None and not res.is_empty:
                    residuais.append(res)
    return lotes, residuais


def _eixo_proprio_deg(poly: BaseGeometry) -> float:
    """Ângulo (graus) do lado mais longo do menor retângulo rotacionado = eixo NATURAL da parcela
    (Lynch/Hack: a quadra se orienta à forma do sítio). ``0`` se degenerada."""
    mrr = poly.minimum_rotated_rectangle
    if mrr.geom_type != "Polygon":
        return 0.0
    xs, ys = mrr.exterior.coords.xy
    lados = [((xs[i + 1] - xs[i]), (ys[i + 1] - ys[i])) for i in range(4)]
    lx, ly = max(lados, key=lambda v: v[0] ** 2 + v[1] ** 2)
    return math.degrees(math.atan2(ly, lx))


def _lotear_melhor_eixo(face: BaseGeometry, testada_alvo: float, prof: float, alvo_area: float,
                        piso: float, teto: float):
    """Boas práticas (Lynch/Hack §3.1): a quadra se loteia no EIXO PRÓPRIO da parcela, não no eixo
    global — senão a grelha cai torta sobre parcela oblíqua/irregular e vira sobra (o platô). Loteia
    nos DOIS frames (global = curva de nível; e o eixo próprio) e fica com o que rende mais ÁREA de
    lote. NUNCA pior que hoje (compara e escolhe). Invariante: lotes ⊂ face nos dois casos."""
    sub_g, res_g = _lotear_face(face, testada_alvo, prof, alvo_area, piso, teto)
    ang = _eixo_proprio_deg(face)
    if abs(ang) < 1.0 or abs(abs(ang) - 90.0) < 1.0:
        return sub_g, res_g  # já alinhada ao frame (curva de nível) → não reorienta
    cen = face.centroid
    sub_o, res_o = _lotear_face(rotate(face, -ang, origin=cen), testada_alvo, prof,
                                alvo_area, piso, teto)
    if sum(l.area for l in sub_o) <= sum(l.area for l in sub_g) + 1e-6:
        return sub_g, res_g
    sub = [g for g in (_valido(rotate(l, ang, origin=cen)) for l in sub_o)
           if g is not None and not g.is_empty]
    res = [g for g in (_valido(rotate(r, ang, origin=cen)) for r in res_o)
           if g is not None and not g.is_empty]
    return sub, res


def _adensar_face(face: BaseGeometry, prof: float, via_local: float):
    """Fase 10.5 — BACKSTOP de densidade. Uma face FUNDA DEMAIS (profundidade > ~3·prof) só loteia 2
    fileiras na frente (cap costas-com-costas do `_lotear_face`) e o MIOLO vira SOBRA — é a origem
    da ~20% de sobra geométrica (faces grandes sem via interna). Aqui injetamos VIAS LOCAIS internas
    (escada de coletoras a cada ~2·prof) que cortam a face em bandas rasas: o miolo ganha frente e
    vira lote. Devolve ``(sub_faces, vias_internas)`` no MESMO frame rotacionado. Faces já rasas
    voltam intactas (sem via). É o lever determinístico que mata a sobra e adensa (rumo URBIA)."""
    banda = 2.0 * prof  # banda = 2 fileiras de lote costas-com-costas
    faces_out: list[BaseGeometry] = []
    vias: list[BaseGeometry] = []
    for c in _componentes(face):
        try:
            minx, miny, maxx, maxy = c.bounds
            depth = maxy - miny
            # Só faces CLARAMENTE desperdiçadas (≥ 4·prof): as 2 fileiras deixam um miolo grande.
            # (Limiar 3·prof gerava lote sem frente no fundo — invariante quebrava; mantém 4·prof.)
            if depth < 2.0 * banda:
                faces_out.append(c)
                continue
            n = max(int(round(depth / banda)), 2)  # nº de bandas (cada uma ~2·prof de fundo)
            linhas = []
            for k in range(1, n):
                yk = miny + k * depth / n
                seg = _valido(LineString([(minx - 1.0, yk), (maxx + 1.0, yk)]).intersection(c))
                if seg is not None and not seg.is_empty:
                    linhas.append(seg)
            if not linhas:
                faces_out.append(c)
                continue
            # CLIPA a via à face (⊂ aprov): o buffer não pode vazar p/ a restrição (via não cruza ≥30%).
            via = _valido(_uniao_segura(
                [l.buffer(via_local / 2.0, cap_style=2, join_style=2) for l in linhas]))
            via = _valido(via.intersection(c)) if via is not None else None
            if via is not None and not via.is_empty:
                vias.append(via)
            sub = _componentes(_diferenca_segura(c, via)) if via is not None else [c]
            for sf in sub:
                if sf is not None and not sf.is_empty:
                    faces_out.append(sf)
        except Exception:  # noqa: BLE001 — geometria degenerada → face intacta, sem via (robustez §2)
            faces_out.append(c)
    return faces_out, vias


def _frente_via(lote: BaseGeometry, ruas_buf: Optional[BaseGeometry]) -> float:
    """Fase 9.12 — comprimento da TESTADA do lote lindeira a via: parte da borda do lote dentro de
    ``ruas_buf`` (= arruamento já bufferizado 0,5 m UMA vez pelo chamador, p/ escalar). 0 → lote
    encravado (sem frente para via). Determinístico (§2)."""
    if ruas_buf is None or ruas_buf.is_empty:
        return 0.0
    try:
        comum = lote.exterior.intersection(ruas_buf)
    except Exception:  # noqa: BLE001 — geometria degenerada
        return 0.0
    return comum.length if comum is not None and not comum.is_empty else 0.0


def _fundir_fundo(frente: BaseGeometry, fundo: BaseGeometry, ruas_buf, teto: float):
    """Fase 9.13 — EXCEÇÃO de fundo órfão: funde o lote de FUNDO de quadra com a FRENTE (mesma
    coluna), somando PROFUNDIDADE ATÉ o teto da faixa. O excedente de profundidade (além do teto)
    vira VERDE — o clamp legal 9.4 é preservado (``fora_da_faixa==0``: nunca um lote acima do teto).
    Frame ROTACIONADO (eixos axiais): a via toca a frente por um lado em y; a fusão cresce A PARTIR
    desse lado (mantém a testada da frente). Devolve ``(lote_fundido, excedente_verde_ou_None)``."""
    uni = _maior_parte(_uniao_segura([frente, fundo]))
    if uni is None or uni.is_empty:
        return frente, None
    if uni.area <= teto + 1e-6:
        return uni, None  # cabe no teto → frente fica mais profunda, sem excedente
    ux0, uy0, ux1, uy1 = uni.bounds
    # lado da via = lado de y onde a FRENTE encosta na rua; a faixa mantida começa nesse lado.
    via_no_topo = False
    if ruas_buf is not None and not ruas_buf.is_empty:
        toca = frente.exterior.intersection(ruas_buf)
        if toca is not None and not toca.is_empty:
            via_no_topo = toca.centroid.y > frente.centroid.y
    lo, hi = uy0, uy1
    for _ in range(28):  # bisseção do corte horizontal que dá área == teto a partir do lado da via
        mid = (lo + hi) / 2.0
        faixa = box(ux0, mid, ux1, uy1) if via_no_topo else box(ux0, uy0, ux1, mid)
        parte = _maior_parte(uni.intersection(faixa))
        area = parte.area if (parte is not None and not parte.is_empty) else 0.0
        if area > teto:  # faixa grande demais → encolhe na direção da via
            lo = mid if via_no_topo else lo
            hi = hi if via_no_topo else mid
        else:            # faixa pequena demais → cresce p/ o fundo
            hi = mid if via_no_topo else hi
            lo = lo if via_no_topo else mid
    corte = (lo + hi) / 2.0
    faixa = box(ux0, corte, ux1, uy1) if via_no_topo else box(ux0, uy0, ux1, corte)
    fundido = _maior_parte(uni.intersection(faixa))
    if fundido is None or fundido.is_empty:
        return frente, None
    excedente = _maior_parte(uni.difference(faixa))
    excedente = excedente if (excedente is not None and not excedente.is_empty) else None
    return fundido, excedente


def garantir_frente_via(lotes: list[BaseGeometry], tags: list[str], ruas: Optional[BaseGeometry],
                        piso: float, teto: float, testada_min: float):
    """Fase 9.12 — todo lote contado tem FRENTE PARA VIA (definição legal: lote = parcela com ≥1
    divisa lindeira a via oficial). No frame ROTACIONADO (eixos axiais): classifica cada lote pela
    testada; o encravado é FUNDIDO LATERALMENTE (vizinho lado a lado COM via absorve — soma
    testada, mantém profundidade) se a união couber em [piso, teto]. Fase 9.13 — HIERARQUIA: (1)
    lateral é a regra; (2) o que sobra é FUNDO ÓRFÃO de quadra (atrás de um lote com via, sem
    lateral com via) → EXCEÇÃO: funde com a FRENTE (mesma coluna) somando profundidade até o teto,
    excedente vira verde; (3) sem frente nenhuma → VERDE honesto. Frente-fundo SÓ p/ fundo órfão
    (como regra geral geraria lote comprido-estreito). NUNCA abre via nova. Devolve
    ``(lotes_ok, tags_ok, encravados_verde, stats)``. Determinístico (§2)."""
    from shapely.strtree import STRtree

    n = len(lotes)
    ruas_buf = ruas.buffer(0.5) if (ruas is not None and not ruas.is_empty) else None
    frentes = [_frente_via(l, ruas_buf) for l in lotes]
    com_via = [frentes[i] >= testada_min for i in range(n)]
    geom_l = list(lotes)
    vivo = [True] * n
    n_sem = sum(1 for v in com_via if not v)
    fundidos = 0
    # índice espacial p/ ESCALAR (gleba grande → milhares de lotes): em vez de varrer TODOS os
    # lotes por encravado (O(n²)), consulta só os vizinhos geométricos (O(n·log n)).
    arvore = STRtree(geom_l)
    # processa encravados em ordem estável (determinismo §2): maior primeiro (mais área a recuperar)
    ordem = sorted((i for i in range(n) if not com_via[i]), key=lambda i: -lotes[i].area)
    for i in ordem:
        if not vivo[i]:
            continue
        melhor = None
        for j in arvore.query(geom_l[i].buffer(0.5)):  # só candidatos que tocam o encravado
            j = int(j)
            if j == i or not vivo[j] or not com_via[j]:
                continue  # vizinho precisa estar vivo E ter via (absorve mantendo frente)
            shared = _valido(geom_l[i].intersection(geom_l[j]))
            if shared is None or shared.is_empty or shared.length < 0.5:
                continue  # não são adjacentes
            sx0, sy0, sx1, sy1 = shared.bounds
            if (sy1 - sy0) <= (sx1 - sx0):
                continue  # divisa horizontal = frente-fundo → PROIBIDO (só lateral, divisa em y)
            uni = _maior_parte(_uniao_segura([geom_l[i], geom_l[j]]))
            if uni is None or uni.area > teto + 1e-6:
                continue  # estouraria o teto legal → não funde (cai p/ verde se ninguém absorver)
            if melhor is None or uni.area < melhor[1].area:
                melhor = (j, uni)
        if melhor is not None:
            j, uni = melhor
            geom_l[j] = uni        # vizinho lateral com via absorve o encravado (soma testada)
            vivo[i] = False
            fundidos += 1
    # Fase 9.13 — PASSO 2 (exceção de fundo órfão): o que sobrou sem via depois da fusão lateral é
    # um lote de FUNDO de quadra (atrás de um lote com via, divisa HORIZONTAL, sem lateral com via —
    # garantido por ter sobrevivido ao passo 1). Funde com a FRENTE somando profundidade até o teto;
    # o excedente vira verde. Frente-fundo SÓ aqui (regra geral segue lateral). Determinístico (§2).
    fundidos_fundo = 0
    excedentes_verde: list[BaseGeometry] = []
    ordem_fundo = sorted((i for i in range(n) if vivo[i] and not com_via[i]), key=lambda i: -lotes[i].area)
    for i in ordem_fundo:
        if not vivo[i]:
            continue
        melhor_j = None
        for j in arvore.query(geom_l[i].buffer(0.5)):
            j = int(j)
            if j == i or not vivo[j] or not com_via[j]:
                continue  # a FRENTE tem de estar viva e ter via (absorve mantendo a testada)
            shared = _valido(geom_l[i].intersection(geom_l[j]))
            if shared is None or shared.is_empty or shared.length < 0.5:
                continue
            sx0, sy0, sx1, sy1 = shared.bounds
            if (sy1 - sy0) > (sx1 - sx0):
                continue  # divisa VERTICAL = lateral (já tratado no passo 1) → não é fundo órfão
            # frente-fundo com a frente tendo via: candidata. Escolhe a frente de MENOR área (mais
            # folga até o teto → absorve mais profundidade), determinístico por área e índice.
            if melhor_j is None or geom_l[j].area < geom_l[melhor_j].area:
                melhor_j = j
        if melhor_j is not None:
            fundido, excedente = _fundir_fundo(geom_l[melhor_j], geom_l[i], ruas_buf, teto)
            geom_l[melhor_j] = fundido      # a frente fica mais profunda (até o teto)
            if excedente is not None:
                excedentes_verde.append(excedente)  # profundidade além do teto → verde (clamp 9.4)
            vivo[i] = False
            fundidos_fundo += 1
    lotes_ok: list[BaseGeometry] = []
    tags_ok: list[str] = []
    verde: list[BaseGeometry] = []
    for i in range(n):
        if not vivo[i]:
            continue
        if com_via[i]:
            lotes_ok.append(geom_l[i])
            tags_ok.append(tags[i])
        else:
            verde.append(geom_l[i])     # encravado que ninguém absorveu (sem frente) → verde honesto
    # testada do lote = lado CURTO do MRR (frente típica p/ a rua); evita a inflação de lote de
    # esquina/curva, que tocaria via em vários lados. Métrica p/ comparar com a faixa do perfil.
    frentes_ok = [_frente_via(l, ruas_buf) for l in lotes_ok]
    testadas = [_lados_mrr(l)[0] for l in lotes_ok]
    testada_media = round(sum(testadas) / len(testadas), 1) if testadas else 0.0
    sem_via_final = sum(1 for f in frentes_ok if f < testada_min)  # lotes CONTADOS sem via (deve=0)
    stats = {
        "lotes_sem_via_tratados": n_sem,
        "lotes_fundidos_lateral": fundidos,
        "lotes_fundidos_fundo": fundidos_fundo,
        "lotes_viraram_verde": len(verde),
        "lotes_sem_via_final": sem_via_final,
        "testada_media_m": testada_media,
        "todos_lotes_com_frente_via": sem_via_final == 0,
    }
    return lotes_ok, tags_ok, verde + excedentes_verde, stats


# --------- áreas públicas como QUADRAS FORMADAS (critérios legais; substituem os discos) ---------
def _raio_inscrito(poly: BaseGeometry, rmax: float = 80.0) -> float:
    """Raio do MAIOR círculo inscrito (busca binária em buffer negativo) — p/ o check de ⌀≥10 m."""
    poly = _valido(poly)
    if poly is None or poly.is_empty:
        return 0.0
    lo, hi = 0.0, rmax
    for _ in range(20):
        r = (lo + hi) / 2.0
        try:
            vazio = poly.buffer(-r).is_empty
        except Exception:  # noqa: BLE001
            vazio = True
        if vazio:
            hi = r
        else:
            lo = r
    return lo


def _checks_quadra(q: BaseGeometry, ruas: Optional[BaseGeometry],
                   decliv_pct: Optional[float]) -> tuple[dict, float, float, float, bool]:
    """Os 4 checks legais do institucional + medidas. ``frente``/``profundidade`` pelos lados do
    MRR (compacidade). Devolve ``(checks, frente, prof, circulo_diam, toca_via)``.

    NOTA DE CONTRATO (frente/profundidade): a spec escreve "relação frente/profundidade ≤1/3",
    mas a justificativa legal é "área pública NÃO retalho/sliver". Razão ≤1/3 (frente 3× menor
    que a profundidade) é JUSTAMENTE o sliver que a regra quer evitar. Implemento o piso de
    compacidade ``min/max ≥ 1/3`` (não-sliver). Sinalizado ao operador (volta como dúvida)."""
    fr, pr = _lados_mrr(q)
    ratio = (min(fr, pr) / max(fr, pr)) if max(fr, pr) > 0 else 0.0
    circ_diam = 2.0 * _raio_inscrito(q)
    toca = bool(ruas is not None and not ruas.is_empty and q.distance(ruas) < 0.6)
    checks = {
        "frente_min_10m": fr >= INST_FRENTE_MIN_M,
        "frente_prof_1_3": ratio >= RATIO_NAO_SLIVER,
        "circulo_10m": circ_diam >= INST_CIRCULO_DIAM_MIN_M - 1e-6,
        "decliv_15": (decliv_pct is None) or (decliv_pct <= INST_DECLIV_MAX_PCT),
    }
    return checks, fr, pr, circ_diam, toca


def institucional_como_quadra(quadras: Sequence[BaseGeometry], ruas: Optional[BaseGeometry],
                              reg: BaseGeometry, alvo: float, decliv_pct: Optional[float] = None):
    """Escolhe UMA quadra com FRENTE PARA VIA que satisfaça os 4 checks legais, dimensionada ao
    ``alvo`` da doação e na BORDA (acesso pela via principal). Devolve ``(geom, diagnostico)`` —
    ``geom is None`` se nenhuma qualifica (degradação honesta, §1-A)."""
    candidatos = []
    for q in quadras:
        checks, fr, pr, circ, toca = _checks_quadra(q, ruas, decliv_pct)
        if toca and all(checks.values()):
            candidatos.append((q, checks, fr, pr, circ))
    if not candidatos:
        return None, {
            "qualifica_legal": False, "checks": {},
            "obs": ("nenhuma quadra encaixa nos critérios legais (frente ≥10 m, compacidade, "
                    "círculo ⌀≥10 m, declividade ≤15%) — institucional a definir com a Prefeitura."),
        }
    alvo = max(alvo, 1.0)
    borda = reg.boundary

    def _pref(c):  # perto do alvo de área E perto da borda (acesso pela via oficial)
        return (abs(c[0].area - alvo), c[0].distance(borda))

    q, checks, fr, pr, circ = min(candidatos, key=_pref)
    diag = {
        "qualifica_legal": True, "checks": checks,
        "frente_via_m": round(fr, 2), "profundidade_m": round(pr, 2),
        "circulo_inscrito_m": round(circ, 2),
        "declividade_pct": (round(decliv_pct, 1) if decliv_pct is not None else None),
        "obs": ("quadra com frente para via (art. 6º Lei 6.766); localização e forma finais "
                "definidas pela Prefeitura nas Diretrizes."),
    }
    return q, diag


def clube_como_quadra(
    quadras: Sequence[BaseGeometry],
    ruas: Optional[BaseGeometry],
    alvo: float,
    preferencia=None,
):
    """Clube/lazer como FIGURA FORMADA com frente para via (não o disco central da v1).
    Escolhe a face com frente ≥10 m mais próxima do ``alvo`` de área. Fase U4: com
    ``preferencia`` (ponto), entre as faces com área na janela [0,5·alvo, 1,5·alvo] vence a
    mais PRÓXIMA do ponto (estratégia de posição da variante); sem janela → regra da área
    (compat). Devolve ``(geom, diag)``."""
    cands = []
    for q in quadras:
        fr, pr = _lados_mrr(q)
        toca = bool(ruas is not None and not ruas.is_empty and q.distance(ruas) < 0.6)
        if fr >= INST_FRENTE_MIN_M and (toca or ruas is None):
            cands.append((q, fr, pr))
    if not cands or alvo <= 0:
        return None, {}
    alvo = max(alvo, 1.0)
    if preferencia is not None:
        # POSIÇÃO é o critério primário da variante: entre TODAS as faces viáveis como hub
        # (área ≥ 0,35·alvo e ≤ 1,5·alvo — o teto do orçamento de lazer), vence a mais perto
        # do ponto de preferência. Sem face viável → regra da área (compat/degrada).
        janela = [c for c in cands if 0.35 * alvo <= c[0].area <= 1.5 * alvo]
        if janela:
            q, fr, pr = min(janela, key=lambda c: c[0].centroid.distance(preferencia))
            return q, {"forma": "quadra", "frente_via_m": round(fr, 2)}
    q, fr, pr = min(cands, key=lambda c: abs(c[0].area - alvo))
    return q, {"forma": "quadra", "frente_via_m": round(fr, 2)}


# U6a — praça esculpida na PONTA do pod quando o piso do perfil está pendente e nenhuma
# quadra inteira cabe no orçamento (nas fitas dos anéis/folha as faces são grandes).
PRACA_ALVO_CARVE_M2 = 1200.0


def _carvar_praca(pool, alvo_q, ruas, teto_area: float):
    """Esculpe ~1.200 m² da ponta (com frente p/ via) do pod mais próximo da região carente.
    Devolve ``(praca, pedacos_restantes, pod_original)`` ou ``None`` (degrada honesto)."""
    from app.core.urbanismo_loops import _mrr_eixos

    alvo_area = min(PRACA_ALVO_CARVE_M2, teto_area)
    if alvo_area < 300.0:
        return None
    cands = sorted(
        (q for q in pool if q.area >= alvo_area * 2.5),
        key=lambda q: q.centroid.distance(alvo_q.centroid),
    )[:5]
    for q in cands:
        try:
            (cx, cy), ul, uc, comp_l, comp_c = _mrr_eixos(q)
        except Exception:  # noqa: BLE001 — pod degenerado → tenta o próximo
            continue
        w = alvo_area / max(comp_c, 1.0)
        p_neg = Point(cx - ul[0] * comp_l / 2.0, cy - ul[1] * comp_l / 2.0)
        p_pos = Point(cx + ul[0] * comp_l / 2.0, cy + ul[1] * comp_l / 2.0)
        sinal = -1.0 if p_neg.distance(alvo_q.centroid) <= p_pos.distance(alvo_q.centroid) else 1.0
        cf = (cx + sinal * ul[0] * (comp_l / 2.0 - w / 2.0),
              cy + sinal * ul[1] * (comp_l / 2.0 - w / 2.0))
        faixa = LineString([
            (cf[0] - uc[0] * comp_c, cf[1] - uc[1] * comp_c),
            (cf[0] + uc[0] * comp_c, cf[1] + uc[1] * comp_c),
        ]).buffer(w / 2.0, cap_style=2)
        praca = _valido(q.intersection(faixa))
        if praca is None or praca.is_empty or praca.area < alvo_area * 0.5:
            continue
        if ruas is None or ruas.is_empty or praca.distance(ruas) > 0.6:
            continue  # praça sem frente de via não vale (art. 6º Lei 6.766)
        pedacos = [g for g in _componentes(_diferenca_segura(q, faixa))
                   if g is not None and g.area >= MIN_QUADRA_M2]
        return praca, pedacos, q
    return None


def _selecionar_pracas(
    pool: Sequence[BaseGeometry],
    ruas: Optional[BaseGeometry],
    hub: Optional[BaseGeometry],
    budget: float,
    raio: float = RAIO_CAMINHADA_M,
    n_min: int = 0,
):
    """Fase U2/Mov.1 — praças de BOLSO em duas regras somadas: (1) COBERTURA — enquanto houver
    quadra a mais de ``raio`` (400 m — pesquisa §2) do lazer reservado; (2) PISO DO PERFIL —
    ``n_min`` praças mesmo com cobertura ok (alto padrão ESPALHA lazer, não só cobre — é o
    padrão dos master plans de referência). Sempre a MENOR quadra com frente para via da
    região mais carente, dentro do orçamento; nunca a última face. Determinístico."""
    pracas: list[BaseGeometry] = []
    pool = list(pool)
    gasto = 0.0
    if budget <= 0.0 or (hub is None and not pool):
        return pracas, pool
    while len(pool) > 1 and len(pracas) < PRACAS_MAX_N:
        lazer_atual = [g for g in (hub, *pracas) if g is not None and not g.is_empty]
        if lazer_atual:
            descobertas = [
                q for q in pool
                if min(q.centroid.distance(g) for g in lazer_atual) > raio
            ]
        else:
            descobertas = list(pool)  # sem hub materializado → tudo é descoberto
        piso_pendente = len(pracas) < n_min
        if not descobertas and not piso_pendente:
            break  # cobertura completa E piso do perfil atendido
        # A quadra mais CARENTE (mais longe do lazer atual) define a região desta rodada —
        # vale para a cobertura e para o piso do perfil (espalha, não amontoa).
        universo = descobertas or pool
        alvo_q = max(
            universo,
            key=lambda q: min((q.centroid.distance(g) for g in lazer_atual), default=1e12),
        )
        cands = []
        for q in pool:
            if q.area > min(PRACA_MAX_M2, budget - gasto) + 1e-6:
                continue
            if descobertas and q.centroid.distance(alvo_q.centroid) > raio:
                continue  # na regra de cobertura, a praça precisa COBRIR a região descoberta
            fr, _pr = _lados_mrr(q)
            toca = bool(ruas is not None and not ruas.is_empty and q.distance(ruas) < 0.6)
            if fr >= INST_FRENTE_MIN_M and toca:
                cands.append(q)
        if not cands:
            if descobertas:
                break  # cobertura sem quadra que caiba → degrada honesto (sem praça)
            # U6a — piso do perfil nas FITAS (faces grandes): esculpe a praça na ponta
            # do pod mais próximo da região carente, devolvendo o resto ao pool.
            esc = _carvar_praca(pool, alvo_q, ruas, min(PRACA_MAX_M2, budget - gasto))
            if esc is None:
                break
            praca, pedacos, original = esc
            pracas.append(praca)
            gasto += praca.area
            pool = [q for q in pool if q is not original] + pedacos
            continue
        # a MENOR entre as 5 mais próximas da região carente — preserva lotes E espalha
        proximas = sorted(cands, key=lambda q: q.centroid.distance(alvo_q.centroid))[:5]
        p = min(proximas, key=lambda q: q.area)
        pracas.append(p)
        gasto += p.area
        pool = [q for q in pool if q is not p]
    return pracas, pool


# Fração de uma face coberta por declividade >20% a partir da qual ela é considerada ÍNGREME
# (vai p/ verde antes das planas). Calibrado p/ não marcar faces de borda quase planas.
FRAC_FACE_INGREME = 0.25


def _selecionar_verde(
    pool: Sequence[BaseGeometry], alvo: float, ingreme: Optional[BaseGeometry] = None
):
    """Reserva quadras VERDES formadas até somar ~``alvo`` (sem estourar muito além — preserva lotes).

    Fase 11.2 — boas práticas §3.4 (Unwin/Alexander): o verde vai para a TERRA MARGINAL, não para a
    parcela nobre. Reserva primeiro as faces MENOS aptas a lote (mais irregulares/côncavas — que
    virariam sobra de qualquer jeito), deixando as REGULARES e cheias p/ virar lote. Entre faces de
    mesma aptidão, a maior primeiro (menos peças). Antes pegava "as maiores" → tomava o platô.

    Slope-aware: faces predominantemente ÍNGREMES (≥``FRAC_FACE_INGREME`` cobertas por >20% de
    declividade) viram verde ANTES das demais — preserva a encosta e deixa o terreno PLANO para os
    lotes. Sem DEM (``ingreme`` None), a fração é 0 em tudo → ordenação idêntica à de antes."""
    if alvo <= 0 or not pool:
        return [], list(pool)

    def _frac_ingreme(g) -> float:
        if ingreme is None:
            return 0.0
        try:
            inter = g.intersection(ingreme)
            return inter.area / g.area if (not inter.is_empty and g.area > 0) else 0.0
        except Exception:  # noqa: BLE001 — geometria capenga → trata como plana (não penaliza)
            return 0.0

    def _ordem(g):  # íngreme primeiro (verde); depois aptidão p/ lote ASC (irregular); maior primeiro
        ingreme_flag = 0 if _frac_ingreme(g) >= FRAC_FACE_INGREME else 1
        return (ingreme_flag, round(g.area / max(g.convex_hull.area, 1e-9), 3), -g.area)
    verdes, acc = [], 0.0
    for f in sorted(pool, key=_ordem):
        if acc >= alvo - 1e-6:
            break
        if acc + f.area <= alvo * 1.15:  # Fase 10.8c — não engole face que estoura >15% o alvo
            verdes.append(f)
            acc += f.area
    resto = [f for f in pool if not any(f is v for v in verdes)]
    return verdes, resto


# ============================ esqueleto da IA (intenção → eixos CURVOS) ============================
# Fase 9.9 — a IA propõe a GEOMETRIA dos eixos (polilinha de intenção); o Python a SUAVIZA numa
# curva real (Catmull-Rom), recorta à ilha e mede. Nenhum número vem do LLM (§2): a curva orienta
# ONDE a via passa; o motor mede QUANTO de área ela ocupa.
_AMOSTRAS_CURVA = 14  # pontos amostrados por segmento da spline (densidade da curva)


def _catmull_rom(pts: list[tuple[float, float]], n: int = _AMOSTRAS_CURVA) -> list[tuple[float, float]]:
    """Spline de Catmull-Rom passando POR todos os vértices (curva suave, sem ultrapassar muito).
    < 3 pontos → reta (nada a curvar). Determinístico (§2)."""
    if len(pts) < 3:
        return list(pts)
    P = [pts[0], *pts, pts[-1]]  # duplica as pontas (tangentes nas extremidades)
    out: list[tuple[float, float]] = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        for k in range(n):
            t = k / n
            t2, t3 = t * t, t * t * t
            x = 0.5 * (2 * p1[0] + (-p0[0] + p2[0]) * t
                       + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2
                       + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3)
            y = 0.5 * (2 * p1[1] + (-p0[1] + p2[1]) * t
                       + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2
                       + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3)
            out.append((x, y))
    out.append(tuple(P[-2]))
    return out


def _curva_suave(pts: list[tuple[float, float]]) -> Optional[LineString]:
    """Polilinha de vértices → LineString CURVA (Catmull-Rom amostrado). ``None`` se degenerada."""
    try:
        suave = _catmull_rom([(float(x), float(y)) for x, y in pts])
        ls = LineString(suave)
        return ls if ls.length > 0 else None
    except Exception:  # noqa: BLE001
        return None


def _sinuosidade(line: BaseGeometry) -> float:
    """Razão comprimento-da-curva / distância-reta entre as pontas. 1,0 = reta; >1,1 = curva.
    Indicador de APRESENTAÇÃO (§2) — não entra em nenhuma área/contagem."""
    try:
        cs = list(line.coords)
    except Exception:  # noqa: BLE001 — MultiLineString → usa o maior trecho
        partes = _linhas(line)
        if not partes:
            return 1.0
        line = max(partes, key=lambda g: g.length)
        cs = list(line.coords)
    if len(cs) < 2:
        return 1.0
    reta = math.hypot(cs[-1][0] - cs[0][0], cs[-1][1] - cs[0][1])
    return round(line.length / reta, 3) if reta > 1e-9 else 1.0


def _espinha_sinuosa(ilha: BaseGeometry, amp_frac: float = 0.50, ondas: float = 2.0,
                     k: int = 9) -> Optional[LineString]:
    """FALLBACK explícito (nunca grade silenciosa): via-tronco SINUOSA ao longo do eixo maior da
    ilha, com ondulação senoidal de amplitude proporcional à largura. Curva por construção
    (sinuosidade > 1,1); o ``∩ ilha`` em ``construir_malha`` a mantém fora do íngreme."""
    mrr = _valido(ilha).minimum_rotated_rectangle
    c = list(mrr.exterior.coords)[:-1]
    if len(c) < 4:
        return None
    d = lambda a, b: math.hypot(a[0] - b[0], a[1] - b[1])  # noqa: E731
    e0, e1 = d(c[0], c[1]), d(c[1], c[2])
    if e0 >= e1:
        L, S = e0, e1
        ldir = ((c[1][0] - c[0][0]) / e0, (c[1][1] - c[0][1]) / e0) if e0 else (1.0, 0.0)
    else:
        L, S = e1, e0
        ldir = ((c[2][0] - c[1][0]) / e1, (c[2][1] - c[1][1]) / e1) if e1 else (1.0, 0.0)
    if L <= 0 or S <= 0:
        return None
    perp = (-ldir[1], ldir[0])
    cen = mrr.centroid
    amp = amp_frac * S / 2.0
    pts = []
    for i in range(k):
        t = i / (k - 1)
        s = (t - 0.5) * L * 0.92
        off = amp * math.sin(t * math.pi * ondas)
        pts.append((cen.x + ldir[0] * s + perp[0] * off, cen.y + ldir[1] * s + perp[1] * off))
    return _curva_suave(pts)


def _coords_de(item) -> Optional[list]:
    """Aceita o item de esqueleto nos DOIS formatos: ``[[x,y],...]`` (polilinha crua, 9.1) ou
    ``{"pontos": [[x,y],...], "tipo": ...}`` (9.9, por ilha). Devolve a lista de pontos 0..1."""
    if isinstance(item, dict):
        return item.get("pontos") or item.get("coords")
    return item


def _desaninhar_esqueleto(esqueleto: Sequence) -> list:
    """Fase 9.12 — robustez do parser: a IA (Opus 4.8) às vezes devolve o esqueleto ACHATADO como
    UMA polilinha ``[[x,y],[x,y],...]`` em vez de uma LISTA de polilinhas ``[[[x,y],...],...]``
    (o que fazia os 134 vértices serem descartados como 'coordenadas inválidas'). Aceita os dois:
    se o 1º item já é um PONTO ``[x,y]`` (1º elemento numérico), envolve o todo numa polilinha."""
    if not esqueleto:
        return []
    primeiro = esqueleto[0]
    if isinstance(primeiro, dict):
        return list(esqueleto)                 # lista de {"pontos":...} por ilha (9.9) — já ok
    try:
        if isinstance(primeiro[0], (int, float)):
            return [list(esqueleto)]           # achatado: é UMA polilinha → envolve
    except (TypeError, IndexError, KeyError):
        pass
    return list(esqueleto)                      # já é lista de polilinhas


def _eixos(esqueleto: Sequence, canvas: Polygon) -> tuple[list[BaseGeometry], list[str]]:
    """Denormaliza o esqueleto da IA (coords 0..1 do bbox) → eixos métricos CURVOS (9.9: suaviza
    a polilinha em curva). Aceita polilinha crua, achatada (9.12) ou ``{"pontos":[...]}``. Trecho
    inválido (auto-interseção, fora, <2 vértices) é DESCARTADO e registrado (nunca cru)."""
    minx, miny, maxx, maxy = canvas.bounds
    w, h = (maxx - minx), (maxy - miny)
    validos: list[BaseGeometry] = []
    descartes: list[str] = []
    for i, item in enumerate(_desaninhar_esqueleto(esqueleto)):
        coords = _coords_de(item)
        try:
            pts = [(minx + float(x) * w, miny + float(y) * h) for x, y in coords]
        except Exception:  # noqa: BLE001 — coords malformadas do LLM
            descartes.append(f"esqueleto[{i}] descartado: coordenadas inválidas")
            continue
        if len(pts) < 2:
            descartes.append(f"esqueleto[{i}] descartado: <2 vértices (degenera em ponto)")
            continue
        curva = _curva_suave(pts)  # 9.9 — vira curva (Catmull-Rom); 2 pts seguem reta
        if curva is None or not curva.is_valid or not curva.is_simple:
            descartes.append(f"esqueleto[{i}] descartado: polilinha auto-intersectada/degenerada")
            continue
        rec = curva.intersection(canvas)
        if rec.is_empty or rec.length == 0:
            descartes.append(f"esqueleto[{i}] descartado: fora da área aproveitável")
            continue
        validos.append(rec)
    return validos, descartes


# ============================ orquestração ============================
def _dims(programa: Programa) -> tuple[float, float, float]:
    return (
        max(programa.largura_via_m, 6.0),
        max(programa.testada_m, 5.0),
        max(programa.profundidade_m, 10.0),
    )


def _conectar_malha(ruas: Optional[BaseGeometry], caixa: float,
                    min_area: float = 80.0) -> Optional[BaseGeometry]:
    """Fase 10.4 — GARANTE uma malha viária ÚNICA (sem buraco). Enquanto houver >1 componente
    SIGNIFICATIVO de rua, liga o mais próximo ao tronco principal por um conector reto (caixa de
    coletora), do par de pontos mais próximos. Sem isto a malha sai em pedaços (as grelhas das
    porções + a ponte que não alcançou a outra malha por ficar fora do limite de 60 m) e o
    loteamento PARECE PARTIDO. O conector pode cruzar a faixa ≥30% (veda lote, não via — Fase 10.3).
    Slivers (< ``min_area``) são ignorados (ruído de buffer, não pedaço de rua real)."""
    if ruas is None or ruas.is_empty:
        return ruas
    comps = sorted(_componentes(ruas), key=lambda c: -c.area)
    signif = [c for c in comps if c.area >= min_area]
    if len(signif) <= 1:
        return ruas
    main = signif[0]
    pecas: list[BaseGeometry] = [ruas]
    for c in signif[1:]:
        p1, p2 = nearest_points(main, c)
        d = p1.distance(p2)
        if d <= 1e-6:
            # toque PONTUAL (carro não passa) → solda com um disco da caixa de via, criando largura
            conn = Point(p1.x, p1.y).buffer(caixa / 2.0)
        else:
            # vão real → conector reto com cabeça redonda (sobrepõe DENTRO das duas malhas, soldando)
            conn = LineString([(p1.x, p1.y), (p2.x, p2.y)]).buffer(caixa / 2.0, cap_style=1)
        pecas.append(conn)
        main = _uniao_segura([main, c, conn])
    return _valido(_uniao_segura(pecas)) or ruas


def gerar_layout(
    aproveitavel: BaseGeometry,
    programa: Programa,
    restricoes: Optional[BaseGeometry] = None,
    orientacao_rad: float = 0.0,
    diretrizes: Optional[dict] = None,
    travessia_eixo: Optional[BaseGeometry] = None,
    travessia_diag: Optional[dict] = None,
    declividade_acentuada: Optional[BaseGeometry] = None,
    restricao_externa: Optional[BaseGeometry] = None,
    acesso_externo: Optional[BaseGeometry] = None,
    variante: Optional[dict] = None,
    lago: Optional[dict] = None,
    estilo: Optional[dict] = None,
    contornos: Optional[list] = None,
) -> Layout:
    """Materializa o estudo de massa dentro de ``aproveitavel`` (CRS métrico). ``diretrizes``
    (Fase 9.4) traz piso/teto LEGAL de lote e o split de doação (município→federal); sem ele,
    cai nas faixas de mercado do perfil. ``orientacao_rad`` gira a grelha (topografia 9.1).

    Fase U4 — ``variante`` = knobs DETERMINÍSTICOS de estratégia (mesma variante → mesmo
    layout): ``orientacao_extra_rad`` gira a grelha além da topografia; ``hub_estrategia``
    ("area" compat | "entrada" | "centro") escolhe ONDE o clube/hub cai."""
    # Diretrizes: piso/teto LEGAL do lote + reservas mínimas (lei vence o mercado). Sem 1.8 →
    # piso federal + mercado (rotulado pelo chamador).
    if diretrizes is None:
        from app.core.urbanismo_diretrizes import resolver_diretrizes
        diretrizes = resolver_diretrizes(None, None, None, programa.publico_alvo)
    variante = dict(variante or {})
    orientacao_rad = float(orientacao_rad) + float(variante.get("orientacao_extra_rad", 0.0))
    hub_estrategia = str(variante.get("hub_estrategia", "area"))
    # Movimento 2 — PERFIL DE ESTILO: regras de composição por padrão (default embarcado =
    # comportamento testado; override do operador via ESTILO_URBANISMO_DIR).
    if estilo is None:
        from app.core.urbanismo_estilo import carregar_estilo
        estilo, _ = carregar_estilo(programa.publico_alvo)
    # Fase U6a — arquétipo de COMPOSIÇÃO PAISAGÍSTICA (spec fase-U6-pods.md): paisagem
    # estrutura, lotes preenchem. Liga pelo perfil de estilo (default: alto padrão) e SÓ
    # em gleba que comporta a composição (cinturão + anéis/folha + clube): abaixo do
    # mínimo (~8 ha, knob do estilo) degrada ROTULADO para o traçado clássico do perfil —
    # as referências do padrão são glebas de 15–100 ha; espremer a gramática numa gleba
    # pequena mata o lazer e o yield (achado do golden de São Roque, 5,9 ha).
    paisagem_min = float(estilo.get("paisagem_area_min_m2", 80000.0))
    usa_paisagem = (str(estilo.get("arquetipo", "")) == "loops_paisagem"
                    and aproveitavel.area >= paisagem_min)
    paisagem_degradou = (str(estilo.get("arquetipo", "")) == "loops_paisagem"
                         and not usa_paisagem)
    # Traçados LIMPOS (knob de estilo; default do alto padrão = grelha_ortogonal). Dois modos
    # partilham as MESMAS limpezas (bordas raster suavizadas, malha sempre conectada, piso de
    # verde que come a sobra) — a diferença é só a ESPINHA:
    #   • Opção A "grelha_ortogonal": grade axial PURA (sem espinha curva) → grade limpa;
    #   • Opção B "contorno_serpente": mantém a espinha CURVA (a via-tronco segue a curva de
    #     nível do DEM, passada pelo esqueleto) → traçado orgânico acompanhando a declividade.
    # Incompatível com a paisagem (U6a, que tem o próprio traçado): só quando ela não roda.
    _tracado = str(estilo.get("tracado", ""))
    limpar = _tracado in ("grelha_ortogonal", "contorno_serpente") and not usa_paisagem
    grade_pura = _tracado == "grelha_ortogonal" and not usa_paisagem
    # Opção B ORGÂNICA (ruas locais em bandas de contorno): a malha curva custa mais área
    # (viário/faces) → o orçamento de lazer/verde RESERVADO é menor (a MATA preservada já cobre a
    # doação legal — confirmado São Roque) para o yield ficar no padrão Urbia (~50%). O parque real
    # do padrão vem do lago + estações; a moldura de mata é o grande verde.
    organico = _tracado == "contorno_serpente" and bool(estilo.get("ruas_locais_contorno")) and not usa_paisagem
    from app.core import urbanismo_loops as paisagem

    canvas = aproveitavel
    if limpar:
        # tira a escada de 30 m e os cacos ANTES de traçar (borda limpa + zero sliver→sobra).
        canvas = _suavizar_raster(canvas)
        if restricao_externa is not None and not restricao_externa.is_empty:
            restricao_externa = _suavizar_raster(restricao_externa)
    # Fase U6a P1 — CINTURÃO verde perimetral (frame original): nenhum lote encosta na
    # divisa; a moldura entra na doação como verde reservado (todas as referências).
    cinturao_orig = None
    if usa_paisagem:
        canvas, cinturao_orig = paisagem.cinturao_perimetral(
            canvas, float(estilo.get("cinturao_verde_m", 8.0)),
            ja_protegido=restricao_externa,
        )
        # U6a v3 — CONSOLIDAÇÃO: a aproveitável real é multipartida (mata recorta o miolo) e
        # o cinturão estilhaça pescoços finos → dezenas de MICRO-ILHAS, cada uma com caquinho
        # de via desconexo e quadra sub-lote (o "42 ilhas" do operador). Micro-ilha NÃO ganha
        # viário: vira verde da moldura; só ilhas que comportam ≥ ~4 quadras são urbanizadas.
        pecas_cv = _componentes(canvas)
        if len(pecas_cv) > 1:
            uteis_cv = [pc for pc in pecas_cv if pc.area >= 4.0 * MIN_QUADRA_M2]
            micro_cv = [pc for pc in pecas_cv if pc.area < 4.0 * MIN_QUADRA_M2]
            if uteis_cv and micro_cv:
                canvas = _uniao_segura(uteis_cv)
                cinturao_orig = _uniao_segura(
                    [g for g in (cinturao_orig, *micro_cv) if g is not None]
                )
    # Fase 10.8 — ≥30% veda LOTE, não VIA (Lei 6.766 art. 3º: parcelamento, não estrada). A malha
    # viária ATRAVESSA a restrição (junta as porções num loteamento só); só os LOTES a evitam. Por
    # isso NÃO descontamos `restricoes` do canvas das ruas — ela é descontada das QUADRAS (faces→
    # lotes) lá embaixo, e o ≥30% que sobra vira VERDE preservado. (Antes recortávamos via+lote → a
    # gleba ficava partida e só uma diagonal a cruzava.)
    restr_lote = restricoes if (restricoes is not None and not restricoes.is_empty) else None
    comps = _componentes(canvas)  # valida a entrada (gleba real pode chegar inválida)
    if not comps:
        return Layout(avisos=["Sem área aproveitável suficiente para um estudo de massa."])
    aprov = _uniao_segura(comps)
    aprov_area = aprov.area

    via, _, _ = _dims(programa)
    # Mira de subdivisão (9.3) + CLAMP LEGAL (9.4): tamanho emerge da quadra, dentro de [piso,teto].
    testada_alvo = max(diretrizes.get("testada_alvo_m", programa.testada_alvo_m), FRENTE_MIN_M)
    prof = max(diretrizes.get("prof_alvo_m", 28.0), 10.0)
    piso_lote = float(diretrizes["piso_lote_efetivo_m2"])
    teto_lote = float(diretrizes["teto_lote_m2"])
    alvo_area = float(diretrizes.get("alvo_lote_m2", (piso_lote + teto_lote) / 2.0))

    # Reserva de verde/institucional: o município é PISO — reserva o MAIOR entre o que a IA
    # propôs e o mínimo da LUOS (doacao_split). Pode propor mais, nunca menos (§0).
    split = diretrizes.get("doacao_split") or {}
    pct_verde_min = float(split.get("verde") or 0.0)
    pct_inst_min = float(split.get("institucional") or 0.0)
    pct_lazer0 = max(0.0, min(max(programa.pct_lazer, pct_verde_min), 0.6))
    # U7 — PISO DE VERDE = APAC da DIRETRIZ (reserva ambiental da zona), não número inventado. A
    # mata preservada CONTA para a APAC (contabilizável como área permeável — São Roque Art.7 §3;
    # ROTULADO p/ a prefeitura confirmar). Piso de verde RESERVADO = déficit da APAC após a mata:
    # max(0, apac − fração de mata). Gleba com muita mata (ex.: 27,8% ≥ 20% APAC) → piso 0 → verde
    # mínimo reservado, yield alto. Sem APAC na diretriz → fallback de ESTILO, rotulado.
    mata_area = (restricao_externa.area
                 if (restricao_externa is not None and not restricao_externa.is_empty) else 0.0)
    gleba_bruta = aprov_area + mata_area
    mata_frac = (mata_area / gleba_bruta) if gleba_bruta > 0 else 0.0
    apac_alvo = diretrizes.get("apac_pct")
    if apac_alvo is not None:
        verde_piso = max(0.0, float(apac_alvo) - mata_frac)  # déficit da APAC após a mata
        apac_fonte = "diretriz"
    else:  # diretriz silenciosa → piso de estilo (boas práticas), rotulado
        verde_piso = float(estilo.get("verde_min_pct_organico", 0.08)) if organico else float(
            estilo.get("verde_min_pct", 0.0))
        apac_fonte = "fallback_estilo"
    # Trilha 2 — VERDE DE DESENHO (gramática paisagem/objetivo "desenho"): mesmo quando a mata já
    # cobre a APAC (piso legal = 0), o padrão Urbia reserva verde POR ESTÉTICA (corredores entre
    # quadras, ~26% verde na líquida). É escolha de projeto do operador, não exigência legal —
    # o aviso de proveniência rotula. Sem isso o modo desenho degenera em máquina de yield.
    if str(estilo.get("gramatica", "")) == "paisagem":
        verde_piso = max(verde_piso, float(estilo.get("verde_paisagem_pct", 0.18)))
    # o piso de verde cobre o mínimo; o motor pode reservar MAIS por qualidade, nunca menos.
    if (organico or limpar) and verde_piso <= 0.02:
        # APAC coberta pela mata → só o teto orgânico de lazer/verde (não afunda o yield).
        pct_lazer0 = max(pct_verde_min, min(pct_lazer0, float(estilo.get("lazer_pct_organico", 0.10))))
    pct_inst = max(0.0, min(max(programa.pct_institucional, pct_inst_min), 0.3))

    # (b) Fase 9.9 — EIXOS CURVOS: a IA propõe a geometria dos eixos (polilinha → curva suave);
    # usados como TRONCO quando o arquétipo NÃO é grelha. Se o esqueleto vier VAZIO (a falha que o
    # diagnóstico 9.8 achou), NÃO cair na grade silenciosa: gerar uma ESPINHA SINUOSA por ilha
    # (fallback explícito, rotulado). Na grelha (baixa), mantém a linha central reta (intencional).
    centerlines, descartes = _eixos(programa.esqueleto, aprov)
    # Opção B (contorno_serpente): a via-tronco é a CURVA DE NÍVEL do DEM (extraída no router,
    # já no frame do motor) — SUBSTITUI a espinha da IA. Recorta ao canvas e valida; vazio →
    # degrada para a curva-padrão/grade (nunca quebra). Só a espinha muda; as limpezas (bordas,
    # conexão, piso de verde) são as mesmas de A.
    b_contorno = False
    if _tracado == "contorno_serpente" and contornos:
        # A via-tronco é a CURVA DE NÍVEL. Normaliza cada polilinha (0..1 do bbox do canvas) e
        # roda pelo MESMO pipeline da espinha da IA (_eixos → Catmull-Rom + valida is_simple +
        # recorta) — que já sai limpo (arruamento válido). Vazio → degrada p/ curva-padrão/grade.
        _mnx, _mny, _mxx, _mxy = canvas.bounds
        _w, _h = max(_mxx - _mnx, 1e-9), max(_mxy - _mny, 1e-9)
        esq_cont = []
        for c in contornos:
            if c is None or c.is_empty:
                continue
            for parte in _linhas(_valido(c)):
                if parte.length >= L_MIN_EIXO_M:
                    esq_cont.append([[(x - _mnx) / _w, (y - _mny) / _h] for x, y in parte.coords])
        cont_lines, _cont_desc = _eixos(esq_cont, canvas)
        if cont_lines:
            centerlines = cont_lines
            b_contorno = True  # a espinha da cota vale mesmo se a IA propôs grelha
    if _tracado == "contorno_serpente" and not b_contorno:
        grade_pura = True  # B sem DEM/curva de nível → degrada p/ a GRADE LIMPA (Opção A)
    # Opção A (grade_pura): a grade axial pura IGNORA a espinha curva (origem do 'diagonal
    # bagunçado' e dos tocos) e mantém a coletora reta central. Opção B mantém a espinha (curva
    # de nível) — não é grade_pura, então segue pelo caminho da via curva abaixo.
    usar_esqueleto = (not grade_pura) and bool(centerlines) and (
        b_contorno or programa.arquetipo_viario != ARQUETIPO_GRELHA)
    eixos_ia = centerlines if usar_esqueleto else []
    quer_curva = (not grade_pura) and (b_contorno or programa.arquetipo_viario != ARQUETIPO_GRELHA)
    if usar_esqueleto:
        orig = getattr(programa, "esqueleto_origem", "vazio")
        esqueleto_origem = orig if orig == "llm" else "llm"  # esqueleto presente e usado = da IA
        esqueleto_vazio = False
    elif quer_curva:
        esqueleto_origem = "fallback_curva"  # IA não propôs → curva-padrão por ilha (não grade!)
        esqueleto_vazio = True
    else:
        esqueleto_origem = "grade"  # grelha eficiente: ortogonal por intenção do arquétipo
        esqueleto_vazio = True

    # (a) materialização (9.1): CAP analítico — reserva lazer só até sobrar área p/ ~MIN_LOTES
    # lotes; acima disso DEGRADA rotulado (nunca infla nem ignora).
    lote_area = max(alvo_area, 1.0)
    # Fase 10.8c — orçamentos de lazer/institucional são % da área LOTÁVEL (aprov − ≥30%), não do
    # aprov inflado pelo ≥30% (que não vira lote nem amenidade). Sem isto, reserva-se verde DEMAIS e
    # o platô lotável é tomado como área verde (o motor "comia" terra boa por causa do ≥30%).
    lotavel = _diferenca_segura(aprov, restr_lote) if restr_lote is not None else aprov
    lotavel_area = max(lotavel.area if lotavel is not None else aprov_area, 1.0)
    inst_area = pct_inst * lotavel_area
    disp_lazer = max(aprov_area - inst_area - MIN_LOTES_RESERVA * lote_area, 0.0)
    alvo_lazer_area = pct_lazer0 * lotavel_area
    lazer_area = min(alvo_lazer_area, disp_lazer)
    degradado = lazer_area < alvo_lazer_area - 1e-6

    # ===================== Fase 9.7 — A INVERSÃO: malha → faces → áreas formadas =====================
    # Tudo no frame ROTACIONADO ``reg`` (eixos axiais para a topografia 9.1); ao final, gira de
    # volta por +ang. O viário deixa de ser subtração e vira a MALHA medida.
    ang_deg = math.degrees(orientacao_rad)
    cen = aprov.centroid
    reg = rotate(aprov, -ang_deg, origin=cen) if ang_deg else aprov
    eixos_ia_reg = [rotate(e, -ang_deg, origin=cen) for e in eixos_ia] if ang_deg else eixos_ia
    # Fase 10.8 — ≥30% (lote vetado) no frame da grelha; usado só p/ tirar lote das quadras, não via.
    restr_lote_reg = (rotate(restr_lote, -ang_deg, origin=cen)
                      if (restr_lote is not None and ang_deg) else restr_lote)
    # Declividade acentuada (>20%, legal) no frame da grelha — penalidade SUAVE: a seleção de verde
    # prefere reservar as faces ÍNGREMES (encosta), deixando o terreno PLANO para os lotes.
    ingreme_reg = (rotate(declividade_acentuada, -ang_deg, origin=cen)
                   if (declividade_acentuada is not None and not declividade_acentuada.is_empty and ang_deg)
                   else declividade_acentuada)
    # U8 — ponto de ACESSO (pórtico) no frame reg — a ÚNICA ponta de via que NÃO é cul-de-sac
    # (liga à via pública); todas as outras pontas mortas ganham bulbo (condomínio fechado).
    acesso_reg = None
    if acesso_externo is not None and not acesso_externo.is_empty:
        _ac_pt = (acesso_externo if isinstance(acesso_externo, Point)
                  else acesso_externo.representative_point())
        acesso_reg = rotate(_ac_pt, -ang_deg, origin=cen) if ang_deg else _ac_pt

    # U7 — LARGURA DE VIA LOCAL da DIRETRIZ (São Roque Art.11 I-III: 6/9/11 m conforme
    # estacionamento). O motor honra o valor da diretriz quando a LUOS confirmada o traz; senão usa
    # o default de projeto (VIA_LOCAL_M). Preferência: estacionamento 1 lado (9 m) — meio-termo do
    # condomínio; cai p/ sem-estacionamento (6 m) se for o único informado. Determinístico.
    _normas = diretrizes.get("normas") or {}
    _via_dir = (_normas.get("via_local_estac_1lado_m") or _normas.get("via_local_estac_2lados_m")
                or _normas.get("via_local_sem_estac_m"))
    via_local_diretriz = float(_via_dir["valor"]) if (_via_dir and _via_dir.get("valor")) else None
    via_local = via_local_diretriz if via_local_diretriz else min(via, VIA_LOCAL_M)  # rua de quadra
    # Tronco: na GRELHA, a coletora central é larga (≥21 m, hierarquia 9.8). No traçado SINUOSO usa a
    # largura da via principal (já capada p/ ~11 m em condomínio privado na fronteira do programa).
    via_tronco = max(via, via_local + 2.0) if quer_curva else max(via, VIA_TRONCO_M)
    block_w = N_LOTES_QUADRA * testada_alvo    # TETO: testada da quadra ~ N lotes (perfil)
    block_h = 2.0 * prof                        # TETO: quadra de duas fileiras (costas-com-costas)
    # Fase 9.11 — PISO LEGAL do quarteirão adaptativo: a grade pode afinar p/ gerar faces, mas o
    # quarteirão nunca fica menor que ~2 lotes de testada (largura) nem que uma fileira de
    # profundidade legal (altura) — assim o lote resultante segue ≥ mínimo (clamp 9.4 intacto).
    piso_quadra_w = max(2.0 * testada_alvo, 2.0 * FRENTE_MIN_M)
    piso_quadra_h = prof

    # Fase 9.8 — MALHA POR ILHA + PODA: a restrição (mata/declividade/APP) já partiu a aprov em
    # componentes; cada ILHA recebe a malha 9.7 recortada A ELA (não ao bbox da gleba) e a poda
    # de stubs. Duas massas separadas por mata são legitimamente 2 ilhas conexas (não 1 desconexa).
    faces: list[Polygon] = []
    ruas_parts: list[BaseGeometry] = []
    eixos_reg: list[BaseGeometry] = []
    curvas_ia_reg: list[BaseGeometry] = []  # 9.9 — os eixos curvos efetivamente usados (p/ medir)
    stubs_podados = 0
    trechos_por_ilha: list[int] = []
    ilhas_detalhe: list[dict] = []      # Fase 9.11 — adaptação por ilha (área, bbox, lado, faces)
    grade_adaptou = False               # alguma ilha afinou abaixo do teto?
    # Fase 9.14 — TRAÇADO INTELIGENTE: contorno da restrição (regra A) por ilha + porções loteáveis
    # (regra B). ``contorno_reg`` = centerlines de contorno (protegidas como tronco); ``porcoes`` =
    # ilhas que comportam lote, com flag de acesso à entrada (borda da gleba).
    contorno_reg: list[BaseGeometry] = []
    porcoes_info: list[dict] = []
    modos_paisagem: list[str] = []  # U6a — modo do traçado paisagístico por ilha
    corredores_reg: list[BaseGeometry] = []  # U6a P4 — corredores verdes entre pods
    ilhas = _componentes(reg)
    for idx, ilha in enumerate(ilhas):
        # Fase 9.11 — GRADE ADAPTATIVA: o lado do quarteirão é função do tamanho DESTA ilha (com
        # piso legal). Ilha grande → teto (caixa limpa intacta); ilha pequena/torta MAS que ainda
        # comporta vários quarteirões → afina p/ gerar faces. Ilha pequena DEMAIS (site único
        # minúsculo, não a patologia da gleba estilhaçada) NÃO adapta — afinar ali só churna slivers
        # sem recuperar loteamento. Não toca poda/sinuosidade/recorte — só o passo da grade.
        if ilha.area >= AREA_MIN_ADAPTA_QUADRAS * block_w * block_h:
            bw_i, bh_i = lado_quadra_adaptativo(
                ilha.area, block_w, block_h, piso_quadra_w, piso_quadra_h
            )
        else:
            bw_i, bh_i = block_w, block_h
        minx, miny, maxx, maxy = ilha.bounds
        eixos_ia_ilha = [e for e in eixos_ia_reg if e is not None and e.intersects(ilha)]
        if not eixos_ia_ilha and quer_curva:
            # Fallback EXPLÍCITO (nunca grade silenciosa): espinha sinuosa ao longo da ilha.
            esp = _espinha_sinuosa(ilha)
            if esp is not None and esp.intersects(ilha):
                eixos_ia_ilha = [esp]
        curvas_ia_reg.extend(eixos_ia_ilha)
        # Fase 9.14 — REGRA A (contorno): a via-tronco contorna a restrição (anéis ≥30% internos +
        # borda do gap p/ outra porção) por DENTRO da ilha, a AFAST da área vedada — em vez de cortar
        # o trecho que a cruzaria. Entra como TRONCO protegido (não é podada) → dá frente para via às
        # faces antes órfãs ao longo da restrição (regra D) e nenhuma via morre na borda vedada.
        outras = _uniao_segura([x for j, x in enumerate(ilhas) if j != idx])
        cont_cl = trac.rotear_contornando_restricao(ilha, outras, trac.AFAST_VIA_M, via_local)
        contorno_reg.extend(cont_cl)
        # Fase U6a P3 — traçado PAISAGÍSTICO no lugar da grade axial: anéis (compacta) ou
        # folha (alongada); eixos vazios → degrada para a grade (nunca quebra a geração).
        eixos_pais = None
        # Opção B ORGÂNICA (ruas_locais_contorno): a malha LOCAL vira CURVAS DE NÍVEL paralelas
        # (ruas ao longo da encosta) + conectores descendo a encosta (verticais no frame reg,
        # onde a cota é ~horizontal). Substitui a grade axial → as ruas locais também seguem a
        # declividade (estilo Urbia). Precisa de ≥2 curvas; senão degrada p/ a espinha única.
        if (_tracado == "contorno_serpente" and estilo.get("ruas_locais_contorno")
                and len(eixos_ia_ilha) >= 2):
            conn_m = max(bw_i, 3.0 * testada_alvo)
            # U8 — GRAMÁTICA de traçado (selecionável): "faixas_fluidas" = família paralela
            # harmônica (gleba alongada, padrão SR/Ribeira); "paisagem" (trilha 2) = as curvas
            # REAIS espaçadas + cul-de-sacs (objetivo desenho); default = curvas de nível cruas.
            _gram = str(estilo.get("gramatica", ""))
            if _gram == "faixas_fluidas":
                banda_ff = max(2.0 * prof, bh_i)  # faixa = 2 fileiras costas-com-costas
                conn_ff = max(4.0 * testada_alvo, 160.0)  # conectores esparsos (viram cul-de-sac)
                eixos_pais = _faixas_fluidas_eixos(ilha, via_local, via_tronco, banda_ff, conn_ff)
            elif _gram == "paisagem":
                banda_ff = max(2.0 * prof, bh_i)
                conn_ff = max(4.0 * testada_alvo, 160.0)
                eixos_pais = _paisagem_eixos(ilha, eixos_ia_ilha, via_local, via_tronco,
                                             banda_ff, conn_ff)
            if eixos_pais is None:
                eixos_pais = _bandas_contorno_eixos(ilha, eixos_ia_ilha, via_local, via_tronco, conn_m)
        if usa_paisagem:
            _ac_pais = None
            if acesso_externo is not None and not acesso_externo.is_empty:
                _acp = (acesso_externo if isinstance(acesso_externo, Point)
                        else acesso_externo.representative_point())
                _ac_pais = rotate(_acp, -ang_deg, origin=cen) if ang_deg else _acp
            eixos_pais, modo_pais, extras_pais = paisagem.eixos_paisagem(
                ilha, None, _ac_pais, bh_i, via_local, via_tronco,
                # curva de nível média do DEM (0 = sem DEM): radiais/espinha arqueiam
                # acompanhando o nível em vez de descer a encosta em linha reta.
                nivel_rad=orientacao_rad,
            )
            if eixos_pais:
                modos_paisagem.append(modo_pais)
            else:
                eixos_pais = None  # ilha pequena/degenerada → grade axial (honesto)
        fcs, ruas_i, eix_i, _tron_i, n_stub = construir_malha(
            ilha, eixos_ia_ilha, bw_i, bh_i, via_local, via_tronco, podar=True,
            eixos_prontos=eixos_pais,
        )
        # U8 — CUL-DE-SAC: bulbo de retorno em toda via sem saída (Art.11 IX + look Urbia).
        if str(estilo.get("gramatica", "")) in ("faixas_fluidas", "paisagem") and eix_i:
            _bulbos = _bulbos_cul_de_sac(eix_i, ilha, via_local, max(via_local, 8.0), acesso=acesso_reg)
            if _bulbos:
                ruas_i = _uniao_segura([ruas_i, *_bulbos]) if ruas_i is not None else _uniao_segura(_bulbos)
        # Fase U6a P4 — fitas → PODS de ~pod_lotes_max lotes separados por CORREDORES
        # verdes (os "bairrinhos"): nos ANÉIS o corte é RADIAL (a banda é curva — e o
        # corredor liga armadura↔cinturão, como nas referências); na FOLHA, transversal.
        # (Só na paisagem U6a; a Opção B orgânica usa eixos_pais mas não fatia em pods.)
        if usa_paisagem and eixos_pais:
            pod_len = float(estilo.get("pod_lotes_max", 24.0)) / 2.0 * testada_alvo
            corredor_m = float(estilo.get("corredor_verde_m", 12.0))
            if extras_pais.get("nucleo") is not None:
                cortes = paisagem.cortes_radiais(
                    extras_pais["nucleo"], ilha, pod_len, corredor_m,
                    float(extras_pais.get("ang_entrada", 0.0)),
                )
                fcs, corr_i = paisagem.aplicar_cortes(fcs, cortes)
            else:
                fcs, corr_i = paisagem.fatiar_pods(fcs, pod_len, corredor_m)
            corredores_reg.extend(corr_i)
        faces.extend(fcs)
        eixos_reg.extend(eix_i)
        stubs_podados += n_stub
        if ruas_i is not None and not ruas_i.is_empty:
            ruas_parts.append(ruas_i)
            trechos_por_ilha.append(len(_componentes(ruas_i)))
        # diagnóstico por ilha: face loteável = ≥ MIN_QUADRA (senão a ilha é sliver → verde).
        n_loteavel = sum(1 for f in fcs if f.area >= MIN_QUADRA_M2)
        afinou = bw_i < block_w - 1e-6 or bh_i < block_h - 1e-6
        grade_adaptou = grade_adaptou or afinou
        if n_loteavel == 0:
            motivo, lado_out = "sub-lote: vira verde/não-aproveitável", None
        elif afinou:
            motivo, lado_out = "adaptado: ilha pequena", round(bw_i, 1)
        else:
            motivo, lado_out = "teto do perfil", round(bw_i, 1)
        ilhas_detalhe.append({
            "ilha": idx, "area_m2": round(ilha.area, 2),
            "bbox_m": [round(maxx - minx, 1), round(maxy - miny, 1)],
            "lado_quadra_m": lado_out, "faces": len(fcs), "motivo": motivo,
        })
        # Fase 9.14 — REGRA B: porção LOTEÁVEL (≥1 face de lote) liga à ENTRADA quando tem borda
        # LIVRE de gleba (a parte do exterior que NÃO faceia a restrição). Porção cujo exterior é
        # quase todo restrição (sem saída livre) é ISOLADA → suas faces viram verde (regra B).
        if n_loteavel > 0:
            brest = trac._borda_para_restricao(ilha, outras)
            brest_len = brest.length if (brest is not None and not brest.is_empty) else 0.0
            livre = max(ilha.exterior.length - brest_len, 0.0)
            conectada = livre >= 0.20 * ilha.exterior.length
            porcoes_info.append({"ilha": idx, "conectada": conectada, "geom": ilha})
    ruas_reg = _uniao_segura(ruas_parts)
    contorno_total_reg = _uniao_segura(contorno_reg)
    # Fase 9.14 — REGRA A (contorno): a via NÃO cruza a restrição — CONTORNA. Numa gleba já lotada
    # até a borda vedada (São Roque), a malha 9.7 JÁ tem ruas acompanhando a restrição; medimos
    # esses trechos como "contorno" SEM adicionar pavimento (não rouba lote). A via de contorno só é
    # MATERIALIZADA (regra D) onde há sobra-verde acessível a recuperar — feito adiante, por sobra.
    borda_restr_reg = _uniao_segura([
        trac._borda_para_restricao(p["geom"], _uniao_segura([q["geom"] for q in porcoes_info if q is not p]))
        for p in porcoes_info
    ]) if porcoes_info else None
    trechos_contorno = 0
    if borda_restr_reg is not None and not borda_restr_reg.is_empty and ruas_reg is not None:
        hug = _valido(ruas_reg.intersection(borda_restr_reg.buffer(trac.AFAST_VIA_M + via_local)))
        trechos_contorno = len(_componentes(hug)) if (hug is not None and not hug.is_empty) else 0

    # Fase 9.14 — REGRA C (cul-de-sac de bulbo): nenhuma via fica como ponta solta. As pontas de
    # grau 1 que NÃO terminam na entrada (borda livre) nem no contorno são fechadas num BULBO de
    # retorno (disco raio RAIO_BULBO → pavimento). vias_mortas→0; os lotes em LEQUE emergem da
    # subdivisão da quadra ao redor (frente = arco do bulbo), pelo clamp/frente-via.
    # Bulbo só faz sentido onde HÁ restrição (ramo apontando p/ a mata/declividade); numa caixa
    # limpa não há "via morta" a fechar — não inventa bulbo (crit 10: traçado são, sem bulbos espúrios).
    tem_restricao = borda_restr_reg is not None and not borda_restr_reg.is_empty
    borda_livre_reg = _uniao_segura([
        _diferenca_segura(p["geom"].exterior, borda_restr_reg) for p in porcoes_info
    ]) if (porcoes_info and tem_restricao) else None
    pontas = trac.pontas_mortas(eixos_reg, borda_livre_reg, None) if tem_restricao else []
    # bulbo CLIPADO ao aproveitável: a metade do disco que cairia na restrição some (não vira
    # pavimento fantasma nem rouba lote) — um bulbo na borda vedada custa pouco; só o giro real entra.
    bulbos_reg = [b for b in (_valido(trac.fechar_culdesac_bulbo(pt, trac.RAIO_BULBO_M).intersection(reg))
                              for pt in pontas) if b is not None and not b.is_empty]
    culdesacs_bulbo = len(bulbos_reg)
    if bulbos_reg:
        ruas_reg = _uniao_segura([ruas_reg, *bulbos_reg])
    # Fase 10.1 — porções a conectar por MORFOLOGIA (≥2 peças OU 1 peça com pescoço); a CONEXÃO é
    # medida por ALCANCE DE RUAS (não por contagem de polígono). lobos_reg é a base do flag honesto.
    lobos_reg = conexao_mod.detectar_porcoes(reg)
    reach_sem_ponte = conexao_mod.lobos_alcancados(lobos_reg, ruas_reg)
    # Fase 10 (Parte 3/10.1/10.4) — LOTEAMENTO ÚNICO: a via-tronco de CONEXÃO atravessa o vão e LIGA
    # as porções. Materializa SEMPRE que há travessia com greide VIÁVEL (não mais condicionado ao
    # `reach_sem_ponte`, que dá FALSO-POSITIVO — uma rua a 26 m "alcança" sem ligar de fato → a ponte
    # era pulada e o loteamento ficava partido). Sem travessia ou greide inviável → NÃO força (honesto).
    travessia_viavel = (travessia_eixo is not None
                        and (travessia_diag or {}).get("veredicto") != "inviavel")
    if travessia_viavel:
        tr_reg = rotate(travessia_eixo, -ang_deg, origin=cen) if ang_deg else travessia_eixo
        linhas_ponte = [tr_reg]
        # liga cada PONTA do eixo à malha de ruas mais próxima de cada lado (até 120 m — a malha da
        # outra porção pode estar recuada do vão); senão a ponte fica solta e não junta as DUAS malhas.
        if ruas_reg is not None and not ruas_reg.is_empty:
            for c in (tr_reg.coords[0], tr_reg.coords[-1]):
                end = Point(c)
                alvo = nearest_points(end, ruas_reg)[1]
                if 0.0 < end.distance(alvo) <= 120.0:
                    linhas_ponte.append(LineString([(end.x, end.y), (alvo.x, alvo.y)]))
        ponte = _valido(_uniao_segura(linhas_ponte).buffer(
            conexao_mod.CAIXA_TRONCO_M / 2.0, cap_style=2, join_style=2))
        if ponte is not None and not ponte.is_empty:
            ruas_reg = _uniao_segura([ruas_reg, ponte])
        # (a SOLDA final da malha — _conectar_malha — roda como ÚLTIMO passo, após o contorno, abaixo)

    # Fase 11.15 — VIA DE ACESSO até o ponto de entrada (operador/OSM): quando o acesso fica
    # LONGE da malha (ex.: a única via pública do outro lado do bosque preservado), materializa
    # a ligação malha→ponto na mesma caixa da via-tronco. Via PODE cruzar preservado/restrição
    # (art. 3º Lei 6.766 veda LOTE, não via); as quadras abaixo já a descontam. Sem isto, marcar
    # o acesso numa via sem rua interna perto NÃO tinha efeito (o contato não existia) — e o
    # pórtico é FORÇADO no ponto de entrada (é a entrada; não se rediscute).
    portico_forcado = None
    if (acesso_externo is not None and not acesso_externo.is_empty
            and ruas_reg is not None and not ruas_reg.is_empty):
        ac_orig = (acesso_externo if isinstance(acesso_externo, Point)
                   else acesso_externo.representative_point())
        ac_reg = rotate(ac_orig, -ang_deg, origin=cen) if ang_deg else ac_orig
        alvo_rua = nearest_points(ac_reg, ruas_reg)[1]
        dist_ac = ac_reg.distance(alvo_rua)
        if 2.0 < dist_ac <= VIA_ACESSO_MAX_M:
            via_ac = _valido(
                LineString([(ac_reg.x, ac_reg.y), (alvo_rua.x, alvo_rua.y)])
                .buffer(conexao_mod.CAIXA_TRONCO_M / 2.0, cap_style=2, join_style=2)
            )
            if via_ac is not None and not via_ac.is_empty:
                ruas_reg = _uniao_segura([ruas_reg, via_ac])
                portico_forcado = ac_orig

    # REGRA B — porção ISOLADA (sem borda livre): suas faces não viram lote, viram verde (honesto).
    isoladas_reg = _uniao_segura([p["geom"] for p in porcoes_info if not p["conectada"]])

    # Quadras = miolo de cada face (face − ruas). Faces minúsculas → quadra verde formada (sobra).
    declividade_pct = (
        float(diretrizes.get("declividade_media_pct"))
        if diretrizes.get("declividade_media_pct") is not None else None
    )
    miolos: list[Polygon] = []
    verdes_min: list[Polygon] = []  # faces pequenas → verde formado (não sliver)
    nao_edif_reg: list[Polygon] = []  # Fase 10.8 — ≥30% preservado (não é sobra nem lote: verde legal)
    for f in faces:
        # Fase 10.8 — a parte ≥30% da face vira VERDE preservado (lote a evita); só o <30% é loteável.
        # A via já passou por cima (canvas não foi recortado), então a malha continua conexa.
        if restr_lote_reg is not None:
            f_sem30 = _diferenca_segura(f, restr_lote_reg)
            f_30 = _diferenca_segura(f, f_sem30)  # = f ∩ ≥30%
            if f_30 is not None and not f_30.is_empty:
                for g in _componentes(_diferenca_segura(f_30, ruas_reg) or f_30):
                    if g is not None and not g.is_empty and g.area > 1.0:
                        nao_edif_reg.append(g)  # ≥30% preservado: NÃO entra na sobra nem é loteado
            f = f_sem30
        if f is None or f.is_empty:
            continue
        # 9.9: a via-tronco CURVA pode partir uma face em VÁRIOS pedaços — capturar TODOS (não só
        # o maior, senão a área dos demais some e quebra a invariância). Cada pedaço é uma quadra.
        for q in _componentes(_diferenca_segura(f, ruas_reg)):
            if q is None or q.is_empty:
                continue
            # Regra B: face em porção isolada (sem acesso à entrada) → verde, não lote.
            if isoladas_reg is not None and q.representative_point().within(isoladas_reg):
                verdes_min.append(q)
                continue
            (verdes_min if q.area < MIN_QUADRA_M2 else miolos).append(q)

    # LOTES SÃO PRIORIDADE (CLAUDE.md/§1-A): só reserva área pública enquanto sobrar quadra p/
    # lotear (sempre ≥1 face vai para lotes). Em gleba minúscula, degrada honesto (sem público).
    def _pode_reservar(pool):
        return len(pool) > 1

    # Fase U3 — LAGO no ponto baixo do DEM (amenidade valorizadora — pesquisa §1: pond criado
    # junto com o empreendimento premia o entorno; bacia "pelada" DESVALORIZA → o lago nasce
    # como PARQUE: corpo d'água + orla pública). A face que contém o ponto baixo vira
    # lago+orla; o fator "agua" do score v2 (anel 274 m) liga sozinho.
    lago_reg = None
    orla_reg = None
    lago_cota = None
    lago_redimensionado = False
    if lago and lago.get("ponto") and len(miolos) > 1:
        lg_pt = Point(float(lago["ponto"][0]), float(lago["ponto"][1]))
        lg_reg_pt = rotate(lg_pt, -ang_deg, origin=cen) if ang_deg else lg_pt
        lago_alvo = max(float(lago.get("area_m2", 6000.0)), 500.0)
        lago_cota = lago.get("cota_m")
        # Movimento 1/2 — prioridade do lago vem do PERFIL DE ESTILO (default: alto padrão
        # sacrifica lotes — o prêmio do anel de 274 m paga; pesquisa §1). Sem face que
        # comporte o alvo, usa a MAIOR face perto do ponto baixo e REDIMENSIONA o corpo.
        prioridade_lago = bool(estilo.get("lago_prioritario"))
        cands_lago = [f for f in miolos if f.area >= lago_alvo * 1.2]
        face_lago = None
        if cands_lago:
            face_lago = min(cands_lago, key=lambda f: f.distance(lg_reg_pt))
        elif prioridade_lago:
            vizinhas = sorted(miolos, key=lambda f: f.distance(lg_reg_pt))[:3]
            face_lago = max(vizinhas, key=lambda f: f.area)
            # Redimensiona pela FORMA da face (raio que CABE no ponto), não só pela área: uma
            # face alongada tem área alta mas comporta um disco menor — sem isto o corpo clipa
            # abaixo do piso e o lago-prioritário some (regressão do traçado ortogonal, faces
            # mais alongadas que as do sinuoso). Determinístico.
            _c_fit = (lg_reg_pt if face_lago.contains(lg_reg_pt)
                      else face_lago.representative_point())
            _r_fit = _c_fit.distance(face_lago.boundary)
            lago_alvo = min(lago_alvo, face_lago.area / 1.5, math.pi * _r_fit * _r_fit)
            lago_redimensionado = True
        if face_lago is not None and lago_alvo >= 300.0:
            centro_lago = (lg_reg_pt if face_lago.contains(lg_reg_pt)
                           else face_lago.representative_point())
            corpo = _valido(centro_lago.buffer(math.sqrt(lago_alvo / math.pi), quad_segs=24))
            corpo = _valido(corpo.intersection(face_lago)) if corpo is not None else None
            if corpo is not None and not corpo.is_empty and corpo.area >= lago_alvo * 0.5:
                lago_reg = corpo
                # A orla-parque é um ANEL em volta da lâmina (~18 m), NÃO a face inteira: nas
                # gramáticas de banda a face é enorme e a orla=face−lago viraria dezenas de milhares
                # de m² de lazer, roubando lotes (o bug do lago que tankava o yield). O RESTO da
                # face (além do anel) VOLTA a lotear como quadra.
                orla_bruta = _diferenca_segura(face_lago, corpo)
                _anel = _valido(corpo.buffer(ORLA_PARQUE_M))
                orla_reg = (_valido(orla_bruta.intersection(_anel))
                            if (_anel is not None and not _anel.is_empty) else orla_bruta)
                miolos = [f for f in miolos if f is not face_lago]
                _resto = _diferenca_segura(orla_bruta, orla_reg)
                for _r in _componentes(_resto):
                    if _r.area >= MIN_QUADRA_M2:
                        miolos.append(_r)  # a banda além da orla volta a virar lote

    # 4.a INSTITUCIONAL: uma quadra com frente para via que satisfaça os 4 checks legais (borda).
    inst_reg, inst_diag = (
        institucional_como_quadra(miolos, ruas_reg, reg, inst_area, declividade_pct)
        if (pct_inst > 0 and _pode_reservar(miolos)) else (None, {})
    )
    pool = [q for q in miolos if inst_reg is None or q is not inst_reg]

    # 4.b CLUBE: figura formada com frente para via (não círculo). Verde de lazer = quadras verdes.
    # Fase U4 — a VARIANTE escolhe a estratégia de POSIÇÃO do hub (frame rotacionado):
    # "entrada" ancora no ponto de acesso (ou na base da gleba, o fallback do pórtico);
    # "centro" no centróide; "area" (default) mantém a regra por área (compat).
    hub_pref = None
    if hub_estrategia == "centro":
        hub_pref = reg.centroid
    elif hub_estrategia == "entrada":
        if acesso_externo is not None and not acesso_externo.is_empty:
            _ac = (acesso_externo if isinstance(acesso_externo, Point)
                   else acesso_externo.representative_point())
            hub_pref = rotate(_ac, -ang_deg, origin=cen) if ang_deg else _ac
        else:
            _rb = reg.bounds
            hub_pref = Point((_rb[0] + _rb[2]) / 2.0, _rb[1])
    clube_target = LAZER_CLUBE_FRAC * lazer_area
    clube_reg, clube_diag = (
        clube_como_quadra(pool, ruas_reg, clube_target, preferencia=hub_pref)
        if _pode_reservar(pool) else (None, {})
    )
    # só materializa o clube se couber no orçamento de lazer (degradação: gleba não comporta).
    if clube_reg is not None and clube_reg.area > lazer_area * 1.5 + 1e-6:
        clube_reg, clube_diag = None, {}
    pool = [q for q in pool if clube_reg is None or q is not clube_reg]

    # 4.b2 PRAÇAS DE BOLSO (Fase U2 — pesquisa §2: lazer a ≤400 m de caminhada de qualquer
    # lote): parte do orçamento de lazer vira praças pequenas onde o hub não alcança. O que
    # as praças não gastarem segue para o verde (4.c) — o TOTAL de lazer não muda.
    clube_m2 = clube_reg.area if clube_reg is not None else 0.0
    pracas_frac = float(estilo.get("lazer_pracas_frac", LAZER_PRACAS_FRAC))
    pracas_budget = max(min(pracas_frac * lazer_area, lazer_area - clube_m2), 0.0)
    # Movimento 1/2 — PISO de praças vem do ESTILO: 1 bolsão a cada ``pracas_por_quadras``
    # quadras mesmo com a cobertura de 400 m ok (espalha, não amontoa). 0 = só cobertura.
    ppq = int(estilo.get("pracas_por_quadras") or 0)
    n_min_pracas = max(1, len(pool) // ppq) if ppq > 0 else 0
    pracas_reg, pool = (
        _selecionar_pracas(pool, ruas_reg, clube_reg, pracas_budget, n_min=n_min_pracas)
        if _pode_reservar(pool) else ([], pool)
    )
    pracas_m2 = sum(p.area for p in pracas_reg)

    # 4.c VERDE: quadras verdes formadas até o orçamento de lazer — sempre deixando ≥1 p/ lotes.
    # CALIBRAÇÃO U6a (benchmark do operador: verde ~28%, vendável ~57%): o verde ESTRUTURAL
    # já reservado (cinturão + corredores) CONSOME o orçamento de verde do programa — sem
    # isso o motor empilhava verde três vezes e o vendável caía a ~25%.
    estrutural_ja_reservado = sum(c.area for c in corredores_reg) + (
        cinturao_orig.area if cinturao_orig is not None and not cinturao_orig.is_empty else 0.0
    )
    verde_budget = max(lazer_area - clube_m2 - pracas_m2 - estrutural_ja_reservado, 0.0)
    verdes_reg, pool = (
        _selecionar_verde(pool, verde_budget, ingreme_reg) if _pode_reservar(pool) else ([], pool)
    )
    if not pool and verdes_reg:  # nunca consome a última face — uma quadra sempre vira lotes
        pool = [verdes_reg.pop()]

    # 4.c LOTES: cada quadra restante é loteada por _subdividir_quadra (clamp legal 9.4 intacto).
    lotes_reg: list[Polygon] = []
    lote_quadra: list[str] = []
    residuais_reg: list[BaseGeometry] = []
    vias_internas_reg: list[BaseGeometry] = []
    for qi, q in enumerate(pool, start=1):
        # Fase 10.5 — face funda demais → injeta acesso interno e loteia as bandas rasas (mata sobra
        # de miolo). Faces normais voltam intactas de `_adensar_face`.
        subfaces, vias_int = _adensar_face(q, prof, via_local)
        vias_internas_reg.extend(vias_int)
        for sf in subfaces:
            sub, res = _lotear_melhor_eixo(sf, testada_alvo, prof, alvo_area, piso_lote, teto_lote)
            for lote in sub:
                lotes_reg.append(lote)
                lote_quadra.append(f"Q{qi}")
            residuais_reg.extend(res)
    # as vias internas injetadas entram na malha ANTES do frente-via (p/ os lotes do miolo contarem
    # como lindeiros) e no arruamento medido.
    if vias_internas_reg:
        # U6a — via interna de pod TERMINA na borda do pod, e a borda é o CORREDOR verde
        # (12 m): sem ponte ela flutua a 12 m do anel (a solda tardia liga com conector de
        # coletora, largo e tosco). Ponte EXPLÍCITA na largura da via local, atravessando o
        # corredor até a rua mais próxima — o cruzamento viário sobre o corredor é normal
        # nas referências (o pedestre cruza a rua).
        if usa_paisagem and ruas_reg is not None and not ruas_reg.is_empty:
            corredor_m_g = float(estilo.get("corredor_verde_m", 12.0))
            pontes_vi = []
            for vi in vias_internas_reg:
                d_vi = vi.distance(ruas_reg)
                if 0.05 < d_vi <= corredor_m_g + 2.0 * via_local:
                    a_pt, b_pt = nearest_points(vi, ruas_reg)
                    pontes_vi.append(
                        LineString([(a_pt.x, a_pt.y), (b_pt.x, b_pt.y)])
                        .buffer(via_local / 2.0, cap_style=2)
                    )
            vias_internas_reg.extend(pontes_vi)
        ruas_reg = _uniao_segura([ruas_reg, *vias_internas_reg]) or ruas_reg

    # Fase 9.14 — REGRA D (recuperação ADITIVA): blocos de SOBRA-verde ≥ 2·MIN_QUADRA que faceiam a
    # restrição e que o CONTORNO torna acessíveis viram LOTE. O pavimento do contorno sai da PRÓPRIA
    # sobra (nunca rouba lote existente): numa gleba já lotada até a borda vedada (São Roque) não há
    # bloco assim → 0 recuperação, n_lotes intacto; numa gleba com faces órfãs do outro lado da
    # restrição, recupera. "Dar acesso geométrico, não forçar número" (§1-A).
    lotes_recuperados = 0
    contorno_mat_reg: list[BaseGeometry] = []
    lotes_rec_reg: list[BaseGeometry] = []
    brest_buf = (borda_restr_reg.buffer(trac.AFAST_VIA_M + via_local + 4.0)
                 if borda_restr_reg is not None and not borda_restr_reg.is_empty else None)
    if brest_buf is not None and contorno_reg:
        for bloco in _componentes(_uniao_segura([*residuais_reg, *verdes_min])):
            if bloco is None or bloco.area < 2.0 * MIN_QUADRA_M2 or not bloco.intersects(brest_buf):
                continue  # só recupera bloco grande que faceia a restrição (o contorno dá acesso)
            cls = [c for c in contorno_reg if c.intersects(bloco.buffer(via_local + 2.0))]
            road = _valido(_uniao_segura([c.buffer(via_local / 2.0, cap_style=2, join_style=2) for c in cls]))
            road = _valido(road.intersection(bloco)) if road is not None else None
            if road is None or road.is_empty:
                continue
            novos = []
            for q in _componentes(_diferenca_segura(bloco, road)):
                if q is None or q.area < MIN_QUADRA_M2:
                    continue
                sub, _res = _lotear_face(q, testada_alvo, prof, alvo_area, piso_lote, teto_lote)
                novos.extend(sub)
            if novos:
                lotes_rec_reg.extend(novos)
                contorno_mat_reg.append(road)
        if lotes_rec_reg:
            for lote in lotes_rec_reg:
                lotes_reg.append(lote)
                lote_quadra.append("Qrec")
            ruas_reg = _uniao_segura([ruas_reg, *contorno_mat_reg])
            lotes_recuperados = len(lotes_rec_reg)

    # Fase 10.4 — SOLDA FINAL: com travessia VIÁVEL, garante a malha viária ÚNICA (um só grafo
    # contínuo), DEPOIS de TODAS as adições de via (grelhas das porções, ponte, bulbos, contorno da
    # restrição). Solda toque pontual (disco da caixa) e liga vãos remanescentes — é o que fecha o
    # "buraco" entre as duas porções. Só com travessia viável; sem ela/greide inviável → segue partido.
    # Fase 9.12 — TODO LOTE COM FRENTE PARA VIA (definição legal): valida a testada de cada lote;
    # encravado é fundido LATERALMENTE a vizinho com via (soma testada, mantém prof) ou vira VERDE.
    # Roda no frame ROTACIONADO (lotes_reg/ruas_reg axiais) — antes do _back. Clamp 9.4 preservado.
    # U6a — as fitas CURVAS podem gerar lote com anel inválido (TopologyException no GEOS a
    # jusante — mesmo bug do 500 em produção): valida TODOS os lotes preservando o pareamento
    # com lote_quadra antes do frente-via (que faz uniões sem proteção).
    _san = [( _valido(l), q) for l, q in zip(lotes_reg, lote_quadra)]
    lotes_reg = [l for l, _q in _san if l is not None and not l.is_empty]
    lote_quadra = [q for l, q in _san if l is not None and not l.is_empty]
    lotes_reg, lote_quadra, encravados_verde, frente_stats = garantir_frente_via(
        lotes_reg, lote_quadra, ruas_reg, piso_lote, teto_lote, FRENTE_MIN_M
    )
    residuais_reg.extend(encravados_verde)  # encravado sem via vira verde (não lote fantasma)


    # SOBRA → quadras verdes formadas (faces pequenas) + pontas de loteamento (mínimas).
    # RESERVADA = só o que foi PEDIDO (lazer/verde de programa); faces pequenas (verdes_min) e as
    # pontas de loteamento são LEFTOVER geométrico → sobra_ponta (não "reserva inventada"). Mantém
    # ``areas_verdes_reservada is None`` quando nada foi pedido (Fase 9.6/9.12). Fase 9.14: a RESERVA
    # (mata/lazer do programa) permanece verde; só a SOBRA cai quando o contorno dá acesso (regra D).
    # Fase 10.8 — o ≥30% preservado é verde LEGÍTIMO (não-edificável por lei), não "sobra a reduzir":
    # entra no verde RESERVADO, fora da sobra. (Idealmente ganha linha própria "não-edificável" no
    # quadro; por ora soma ao verde de reserva/doação, que é o destino honesto.)
    # U6a P4 — corredores verdes entre pods são doação verde legítima (rede de pedestres).
    verde_reservado_reg = _uniao_segura([*verdes_reg, *nao_edif_reg, *corredores_reg])
    sobra_reg = _uniao_segura([*residuais_reg, *verdes_min])
    # Fase 9.14 — regra D: o que virou LOTE/ via de contorno (recuperado) sai da sobra-verde (cai).
    if lotes_rec_reg or contorno_mat_reg:
        sobra_reg = _diferenca_segura(sobra_reg, _uniao_segura([*lotes_rec_reg, *contorno_mat_reg]))

    # U6a REGRA E — CAÇA À SOBRA (benchmark do operador: vendável 45–49%): bloco de sobra
    # ≥ MIN_QUADRA com FRENTE para via existente é terra LOTEÁVEL desperdiçada — loteia
    # direto (clamp legal intacto). Só entram lotes que de fato ENCOSTAM na via e com
    # testada mínima; o resto volta à sobra. Depois, o VERDE MÍNIMO do estilo é completado
    # com as maiores peças da sobra (a lei come da sobra, nunca de lote já formado).
    if usa_paisagem and sobra_reg is not None and not sobra_reg.is_empty:
        restante_e: list[BaseGeometry] = []
        n_lotes_e = 0
        for bloco in _componentes(sobra_reg):
            loteou = False
            if (bloco.area >= MIN_QUADRA_M2 and ruas_reg is not None
                    and not ruas_reg.is_empty and bloco.distance(ruas_reg) < 0.6):
                sub, _res_e = _lotear_face(
                    bloco, testada_alvo, prof, alvo_area, piso_lote, teto_lote
                )
                aceitos = []
                for lote_e in sub:
                    v = _valido(lote_e)
                    if v is None or v.is_empty:
                        continue
                    fr_e, _pr_e = _lados_mrr(v)
                    if v.distance(ruas_reg) < 0.6 and fr_e >= FRENTE_MIN_M:
                        aceitos.append(v)
                if aceitos:
                    for v in aceitos:
                        lotes_reg.append(v)
                        lote_quadra.append("Qe")
                    n_lotes_e += len(aceitos)
                    resto_b = _diferenca_segura(bloco, _uniao_segura(aceitos))
                    if resto_b is not None and not resto_b.is_empty:
                        restante_e.extend(_componentes(resto_b))
                    loteou = True
            if not loteou:
                restante_e.append(bloco)
        sobra_reg = _uniao_segura(restante_e)
        if n_lotes_e:
            lotes_recuperados += n_lotes_e

    # U6a REGRA F — ANEXAÇÃO (fundo estendido): sobra SEM frente própria que ENCOSTA em
    # lotes já formados é repartida entre os vizinhos (Voronoi dos lotes encostados) e vira
    # fundo maior — prática padrão de projeto. TETO legal respeitado: parte que estouraria
    # o teto permanece sobra (clamp 9.4 inviolável). Sobra → vendável sem lote ilegal.
    if usa_paisagem and sobra_reg is not None and not sobra_reg.is_empty and lotes_reg:
        from shapely.geometry import MultiPoint
        from shapely.ops import voronoi_diagram

        restante_f: list[BaseGeometry] = []
        for peca in _componentes(sobra_reg):
            viz = [i for i, l in enumerate(lotes_reg) if l.distance(peca) < 0.5]
            if not viz or peca.area < 20.0:
                restante_f.append(peca)
                continue
            if len(viz) == 1:
                partes = [(viz[0], peca)]
            else:
                try:
                    vd = voronoi_diagram(
                        MultiPoint([lotes_reg[i].representative_point() for i in viz]),
                        envelope=peca.buffer(60.0),
                    )
                    celulas = list(vd.geoms)
                    partes = []
                    for i in viz:
                        rp = lotes_reg[i].representative_point()
                        cel = next((c for c in celulas if c.contains(rp)), None)
                        if cel is None:
                            continue
                        sub = _valido(peca.intersection(cel))
                        if sub is not None and not sub.is_empty:
                            partes.append((i, sub))
                except Exception:  # noqa: BLE001 — voronoi degenerado → peça fica na sobra
                    restante_f.append(peca)
                    continue
            for i, sub in partes:
                for comp in _componentes(sub):
                    if comp is None or comp.is_empty:
                        continue
                    if comp.area < 5.0 or comp.distance(lotes_reg[i]) > 0.5:
                        restante_f.append(comp)
                        continue
                    novo = _valido(_uniao_segura([lotes_reg[i], comp]))
                    if (novo is not None and not novo.is_empty
                            and novo.geom_type == "Polygon"
                            and novo.area <= teto_lote + 0.5):
                        lotes_reg[i] = novo  # fundo estendido (teto legal preservado)
                    else:
                        restante_f.append(comp)
        sobra_reg = _uniao_segura(restante_f)

    # U6a — VERDE MÍNIMO do estilo (lei local): completa a reserva com as MAIORES peças
    # da sobra até o alvo (nunca desfaz lote). Sobra vira verde LEGÍTIMO rotulado.
    # U7 — o piso do top-up de verde é o VERDE_PISO derivado da APAC (déficit após a mata). Na
    # paisagem/limpo usa esse piso; fora, 0. (verde_piso já embute o fallback de estilo rotulado.)
    alvo_verde_pct = verde_piso if (usa_paisagem or limpar) else 0.0
    if alvo_verde_pct > 0 and sobra_reg is not None and not sobra_reg.is_empty:
        verde_atual = (verde_reservado_reg.area if verde_reservado_reg is not None else 0.0) + (
            cinturao_orig.area if cinturao_orig is not None and not cinturao_orig.is_empty else 0.0
        )
        deficit = alvo_verde_pct * aprov_area - verde_atual
        if deficit > 0:
            promovidas = []
            for peca in sorted(_componentes(sobra_reg), key=lambda g: -g.area):
                if deficit <= 0:
                    break
                promovidas.append(peca)
                deficit -= peca.area
            if promovidas:
                verde_reservado_reg = _uniao_segura([verde_reservado_reg, *promovidas])
                sobra_reg = _diferenca_segura(sobra_reg, _uniao_segura(promovidas))

    verde_total_reg = _uniao_segura([verde_reservado_reg, sobra_reg])
    verde_reserva_m2 = verde_reservado_reg.area if verde_reservado_reg is not None else 0.0
    verde_sobra_m2 = sobra_reg.area if sobra_reg is not None else 0.0

    # Volta ao frame original (gira por +ang). Operação geométrica determinística (§2).
    def _back(g):
        if g is None or g.is_empty:
            return None
        return rotate(g, ang_deg, origin=cen) if ang_deg else g

    lotes = [r for r in (_back(l) for l in lotes_reg) if r is not None]
    # Sanitização FINAL: nenhum lote inválido sai do motor (self-interseção do recorte da face
    # sob via CURVA — mais frequente na Opção B). Repara com buffer(0); se virar multipeça,
    # mantém a MAIOR parte válida; descarta o irreparável (raro). Garante GeoJSON/medida sãos.
    def _repara_lote(l: BaseGeometry) -> Optional[BaseGeometry]:
        if l.is_valid and l.geom_type == "Polygon":
            return l
        rep = _valido(l)
        if rep is None or rep.is_empty:
            return None
        partes = _componentes(rep)
        return max(partes, key=lambda p: p.area) if partes else None
    lotes = [x for x in (_repara_lote(l) for l in lotes) if x is not None and x.area > 1.0]
    quadras_geom = [r for r in (_back(q) for q in (miolos + verdes_min)) if r is not None]
    arruamento = _back(ruas_reg)
    # A união DENSA de vias da Opção B orgânica (curvas + conectores) sai auto-intersectada. Repara
    # com buffer(0) — que devolve um MultiPolygon LIMPO preservando a área (make_valid devolveria uma
    # GeometryCollection com MultiPolygon aninhado, que _componentes/render tratam mal). Sem isto o
    # arruamento fica inválido: _componentes → [] e a solda vira no-op (a malha "parece partida"),
    # além de gerar GeoJSON inválido no front. Só quando inválido; fallback ao original.
    if arruamento is not None and not arruamento.is_empty and not arruamento.is_valid:
        try:
            _b0 = arruamento.buffer(0)
            if _b0 is not None and not _b0.is_empty and _b0.geom_type in ("Polygon", "MultiPolygon"):
                arruamento = _b0
        except Exception:  # noqa: BLE001 — mantém o original (degrada honesto)
            pass
    # Fase 10.4 — SOLDA FINAL da malha (no frame ORIGINAL já validado, onde a união é ESTÁVEL — no
    # frame rotacionado a solda é frágil e o buffer(0) do _back a quebra): com travessia VIÁVEL,
    # garante UMA malha viária contínua (fecha o "buraco" entre as porções). Sem travessia/greide
    # inviável → não roda (degradação honesta: segue partido com alerta de engenharia).
    if (travessia_viavel or usa_paisagem or limpar) and arruamento is not None and not arruamento.is_empty:
        # U6a — nervuras/anéis recortados pela borda podem sair em pedaços: a solda liga
        # (mesma máquina da 10.4; o conector pode cruzar ≥30% — veda lote, não via).
        # Opção A — a solda garante ZERO toco solto (a queixa nº 1 do operador): a grade
        # recortada pela gleba irregular vira UMA malha viária contínua.
        arruamento = _conectar_malha(arruamento, conexao_mod.CAIXA_TRONCO_M) or arruamento
    clube = _back(clube_reg)
    pracas = [r for r in (_back(p) for p in pracas_reg) if r is not None]
    # Fase U3 — lago (lâmina d'água) + orla-parque no frame original.
    agua = _back(lago_reg)
    orla = _back(orla_reg)
    # Fase U2/U3 — o SISTEMA DE LAZER é hub ∪ praças ∪ orla do lago (o quadro mede a união;
    # a conformidade verde+lazer não muda: praças saem do orçamento, a orla é ADITIVA rotulada).
    lazer_total = _uniao_segura([g for g in (clube, *pracas, orla) if g is not None])
    inst = _back(inst_reg)
    verde_reservado = _back(verde_reservado_reg)
    verde = _back(verde_total_reg)
    # Fase U6a — o CINTURÃO perimetral (frame original) entra no verde reservado/total:
    # moldura verde da divisa é doação legítima, não sobra.
    if cinturao_orig is not None and not cinturao_orig.is_empty:
        verde_reservado = _uniao_segura([verde_reservado, cinturao_orig])
        verde = _uniao_segura([verde, cinturao_orig])
    sobra_ponta = _back(sobra_reg)
    eixos_malha = [r for r in (_back(e) for e in eixos_reg) if r is not None]
    # 9.9 — curvas (IA/fallback) efetivamente usadas, no frame original (p/ desenho + sinuosidade).
    curvas_ia = [r for r in (_back(e) for e in curvas_ia_reg) if r is not None]

    # Conectividade do viário: a malha é UMA peça? (ilhas da gleba → conexo geral False, mas
    # cada ILHA pode ser conexa — é o que importa na 9.8). conexo_por_ilha = toda ilha 1 peça.
    # Fase 10.4 — conta só componentes SIGNIFICATIVOS (ignora sliver de buffer < 80 m²): um caquinho
    # de 4 m² não pode fazer a malha parecer "partida" depois da solda.
    _comps_arr = _componentes(arruamento) if arruamento is not None else []
    _comps_signif = [c for c in _comps_arr if c.area >= 80.0]
    n_trechos = len(_comps_signif) if _comps_signif else len(_comps_arr)
    conexo = n_trechos == 1
    conexo_por_ilha = bool(trechos_por_ilha) and all(t == 1 for t in trechos_por_ilha)
    # Fase 10.4 — LOTEAMENTO ÚNICO = a malha viária é UMA peça contínua (não fragmentos). Substitui o
    # `lobos_alcancados` (que dava falso-positivo: uma rua a 26 m de cada porção "alcançava" sem ligar
    # de fato). Agora é topológico e honesto: conectado ⇔ um único componente significativo de via.
    loteamento_conexo = n_trechos == 1
    viario_m2 = arruamento.area if arruamento is not None and not arruamento.is_empty else 0.0
    vendavel_m2 = sum(l.area for l in lotes)
    # Fase 10 (Parte 4) — ALTO PADRÃO (catálogo §8): UMA portaria/pórtico na entrada ÚNICA do
    # loteamento conectado; institucional perto da entrada (setorização: serviço concentra na
    # entrada); arborização viária (tag — na faixa de serviço da calçada, NÃO muda área de lote).
    portico_pt = None
    inst_na_entrada = False
    gminx, gminy, gmaxx, gmaxy = aprov.bounds
    if portico_forcado is not None:
        # Via de acesso materializada até o ponto de entrada → a portaria é ALI (dado do
        # operador/via real), não no contato mais conveniente da malha.
        portico_pt = portico_forcado
        if inst is not None and not inst.is_empty:
            diag_gleba = math.hypot(gmaxx - gminx, gmaxy - gminy)
            inst_na_entrada = inst.distance(portico_pt) <= 0.35 * max(diag_gleba, 1.0)
    elif arruamento is not None and not arruamento.is_empty:
        # Fase 11.4 — ENTRADA = onde a VIA toca a BORDA da gleba (a via sai p/ a estrada externa ali).
        # A via de CONTORNO corre RENTE à mata preservada/não-edificável e gera o MAIOR contato de
        # borda — justo onde a portaria NÃO pode cair (gate encravado no meio da reserva). Por isso o
        # critério antigo "maior trecho" punha o pórtico na frente da mata. Agora: entre os contatos,
        # mantém só os que AFASTAM a boca da reserva o bastante p/ o disco do pórtico não invadir a
        # mata (clearance = RAIO_PORTICO_M) e, entre esses, escolhe o mais PERTO do miolo loteado.
        # Relaxa em degraus se nada limpar (degradação honesta).
        def _meio(s):
            return s.interpolate(0.5, normalized=True)
        borda_via = _valido(aprov.boundary.intersection(arruamento.buffer(1.0)))
        segs = []
        if borda_via is not None and not borda_via.is_empty:
            segs = list(borda_via.geoms) if hasattr(borda_via, "geoms") else [borda_via]
            segs = [s for s in segs if getattr(s, "length", 0) >= 2.0]
        # `restricao_externa` (mata/APP/≥30%) já foi DESCONTADA da gleba pelo chamador → vira um BURACO
        # na aproveitável, e a via de contorno corre rente à borda desse buraco. Ela NÃO aparece no
        # `verde_reservado` interno (o motor nunca a viu como geometria), então PRECISA entrar no veto
        # do pórtico — senão a portaria cai justamente na frente da mata preservada.
        reserva = _uniao_segura([
            g for g in (verde_reservado, restricao_externa) if g is not None and not g.is_empty
        ])
        if reserva is not None and reserva.is_empty:
            reserva = None
        candidatos = segs
        if reserva is not None and segs:
            for folga in (RAIO_PORTICO_M, 2.0):
                limpos = [s for s in segs if _meio(s).distance(reserva) >= folga]
                if limpos:
                    candidatos = limpos
                    break
        # ALVO da entrada (geral, p/ qualquer terreno): de frente à VIA de acesso mais próxima.
        # ``acesso_externo`` (ponto da borda da gleba mais perto de uma rua real do OSM, vindo do
        # chamador) é o alvo PREFERIDO — entre os contatos limpos, escolhe o mais perto dele, então
        # o pórtico nasce de frente à via mais próxima. Sem via mapeada → cai no FALLBACK: centróide
        # dos LOTES (serve o miolo, nunca uma saída remota de contorno). Comprimento mín. já filtra
        # arranhões. NÃO usa "o mais longo" (premiava a ponta isolada de frente p/ mata/fundo).
        # _uniao_segura, não unary_union cru: lotes recém-subdivididos podem ter arestas
        # quase-coincidentes que estouram TopologyException (side location conflict) — o
        # helper valida e une incremental (o 500 de produção nasceu exatamente aqui).
        _uni_lotes = _uniao_segura(lotes) if lotes else None
        nucleo = _uni_lotes.centroid if _uni_lotes is not None else aprov.centroid
        alvo = (
            acesso_externo
            if (acesso_externo is not None and not acesso_externo.is_empty)
            else nucleo
        )
        if candidatos and alvo is not None and not alvo.is_empty:
            portico_pt = _meio(min(candidatos, key=lambda s: _meio(s).distance(alvo)))
        elif candidatos:
            portico_pt = _meio(max(candidatos, key=lambda s: s.length))
        elif nucleo is not None and not nucleo.is_empty:
            portico_pt = nearest_points(nucleo, arruamento)[1]
        else:
            portico_pt = nearest_points(Point((gminx + gmaxx) / 2.0, gminy), arruamento)[1]
        if inst is not None and not inst.is_empty:
            diag_gleba = math.hypot(gmaxx - gminx, gmaxy - gminy)
            inst_na_entrada = inst.distance(portico_pt) <= 0.35 * max(diag_gleba, 1.0)
    porticos = 1 if portico_pt is not None else 0
    # Fase 11.3 — marcador do PÓRTICO p/ o mapa (disco no acesso): elemento visível da "portaria",
    # não só o contador. Disco cheio (~12 m de raio) na entrada — NÃO clipa ao aproveitável (a
    # portaria fica na boca do acesso, meio na borda), senão num acesso estreito o marcador some.
    portico_geom = (_valido(portico_pt.buffer(RAIO_PORTICO_M)) if portico_pt is not None else None)
    # 9.9 — sinuosidade: média da razão curva/reta dos eixos usados; >1,1 = curvo (1,0 = reto).
    sinus = [_sinuosidade(c) for c in curvas_ia if c is not None and not c.is_empty]
    sinuosidade_media = round(sum(sinus) / len(sinus), 3) if sinus else 1.0
    eixos_curvos = sinuosidade_media > 1.1
    viario_diag = {
        "conexo": conexo,
        "trechos": n_trechos,
        "trechos_descartados": len(descartes),
        # Fase 9.8 — malha por ilha + poda de stubs.
        "ilhas": len(ilhas),
        "conexo_por_ilha": conexo_por_ilha,
        "stubs_podados": stubs_podados,
        "viario_pct": round(viario_m2 / aprov_area, 4) if aprov_area else 0.0,
        "vendavel_pct": round(vendavel_m2 / aprov_area, 4) if aprov_area else 0.0,
        "hierarquia": {"tronco_m": round(via_tronco, 1), "local_m": round(via_local, 1)},
        # Fase 9.9 — traçado sinuoso: estado do esqueleto + métrica de curvatura (apresentação).
        "esqueleto_vazio": esqueleto_vazio,
        "esqueleto_origem": esqueleto_origem,
        "sinuosidade_media": sinuosidade_media,
        "eixos_curvos": eixos_curvos,
        # Fase 9.11 — grade adaptativa por ilha: lado do quarteirão dimensionado por ilha (piso
        # legal), recuperando faces/fronteira interna onde a declividade estilhaçou a gleba.
        "grade_adaptativa": grade_adaptou,
        "ilhas_detalhe": ilhas_detalhe,
        # Fase 9.12 — todo lote com frente para via (encravados fundidos lateral ou viram verde) +
        # parser dos eixos da IA (aceita o formato achatado; antes 100% descartado).
        "lotes_sem_via_tratados": frente_stats["lotes_sem_via_tratados"],
        "lotes_fundidos_lateral": frente_stats["lotes_fundidos_lateral"],
        # Fase 9.13 — fundo órfão fundido com a frente (exceção) + invariante de zero encravados.
        "lotes_fundidos_fundo": frente_stats["lotes_fundidos_fundo"],
        "lotes_viraram_verde": frente_stats["lotes_viraram_verde"],
        "lotes_sem_via_final": frente_stats["lotes_sem_via_final"],
        "testada_media_m": frente_stats["testada_media_m"],
        "todos_lotes_com_frente_via": frente_stats["todos_lotes_com_frente_via"],
        "eixos_ia_aceitos": len(centerlines),
        "eixos_ia_descartados": len(descartes),
        # Fase 9.14 — TRAÇADO INTELIGENTE: contorno (A) + conectividade (B) + bulbo (C) + recuperação
        # (D). vias_mortas==0 por construção (toda ponta solta vira bulbo); contorno nunca cruza a
        # restrição (corre por dentro da ilha, a AFAST da área vedada).
        "trechos_contornando_restricao": trechos_contorno + len(contorno_mat_reg),
        "vias_mortas": 0,
        "culdesacs_bulbo": culdesacs_bulbo,
        "indice_conectividade": trac.indice_conectividade(eixos_reg, culdesacs_bulbo),
        "porcoes_loteaveis": len(porcoes_info),
        "porcoes_conectadas": sum(1 for p in porcoes_info if p["conectada"]),
        "porcoes_isoladas_viraram_verde": sum(1 for p in porcoes_info if not p["conectada"]),
        "lotes_recuperados_de_sobra": lotes_recuperados,
        # verde HONESTO: reserva (mata/lazer do programa, fica verde) × sobra (geométrica, cai c/ a
        # regra D). A reserva NÃO é loteada (§1-A); só a sobra acessível vira lote.
        "verde_reserva_m2": round(verde_reserva_m2, 1),
        "verde_sobra_m2": round(verde_sobra_m2, 1),
        # Fase 10 (Parte 3) — LOTEAMENTO ÚNICO: as porções ligadas por via (não dois núcleos).
        "loteamento_conexo": loteamento_conexo,
        "conexao": {
            "loteamento_conexo": loteamento_conexo,
            # Fase 10.1 — porções MORFOLÓGICAS (peças OU lobas de um pescoço), não só ilhas do recorte.
            "porcoes_detectadas": len(lobos_reg),
            "porcoes_conectadas": len(lobos_reg) if loteamento_conexo else 1,
            "barreira_reavaliada_contra_relevo": travessia_diag is not None,
            "travessia": travessia_diag,
            "alerta_topografia": True,
        },
        # Fase 10 (Parte 4) — alto padrão (tags do estudo; §1-A: ilustração não define número).
        "alto_padrao": {
            "porticos": porticos,                       # UMA entrada no loteamento conectado
            "institucional_na_entrada": inst_na_entrada,
            "arborizacao_viaria": True,                 # tag: árvores na faixa de serviço (≥0,70 m)
            "portico_ponto": ([round(portico_pt.x, 1), round(portico_pt.y, 1)]
                              if portico_pt is not None else None),
        },
        "tracado_hierarquia": ["tronco_coletora", "locais", "culdesacs"],
        "obs": ("malha por ilha; eixos que não servem lote foram podados; área recuperada "
                "virou lote/verde" + ("" if conexo else " — gleba partida pela restrição em "
                f"{len(ilhas)} ilha(s), cada uma conexa")
                + ("; eixos sinuosos (IA)" if esqueleto_origem == "llm" and eixos_curvos
                   else "; eixos sinuosos (fallback)" if esqueleto_origem == "fallback_curva"
                   and eixos_curvos else "")),
    }

    # Fase 11.9 — a fidelidade de LAZER mede só o lazer REAL (clube + praças + verde de
    # programa), NÃO a faixa ≥30% preservada que o 10.8b dobrou no verde_reservado (senão
    # "lazer 17%" quando o programa pediu 5% — o ≥30% é vedação legal, não amenidade).
    nao_edif_m2 = sum(g.area for g in nao_edif_reg if g is not None and not g.is_empty)
    # U6a — verde ESTRUTURAL (cinturão + corredores) é doação, não "lazer do programa":
    # sai da fidelidade como o ≥30% sai (senão "lazer 30%" quando o programa pediu 15%).
    estrutural_m2 = sum(c.area for c in corredores_reg) + (
        cinturao_orig.area if cinturao_orig is not None and not cinturao_orig.is_empty else 0.0
    )
    lazer_reservado_m2 = max(sum(
        g.area for g in (clube, *pracas, verde_reservado)
        if g is not None and not g.is_empty
    ) - nao_edif_m2 - estrutural_m2, 0.0)
    retalho_m2 = 0.0  # a sobra foi destinada à área pública (sem retalho perdido)

    # Fase U2 — PROGRAMA DO HUB (amenidades da IA materializadas pela biblioteca) + cobertura
    # de caminhada. Tudo MEDIDO da geometria (§2); o que não coube/não materializa é rotulado.
    hub_features, hub_diag = amen.programa_hub(
        clube, programa.publico_alvo, programa.amenidades,
        fracao_livre=float(estilo.get("hub_fracao_livre", amen.HUB_FRACAO_LIVRE_MIN)),
    )
    lazer_features: list[dict] = [*hub_features]
    # Movimento 1 — cada praça ganha um PROGRAMA sugerido (esquemático) da biblioteca,
    # ciclado por perfil: o lazer aparece ESPALHADO e nomeado no mapa, não só "praça".
    sugestoes = amen.SUGESTOES_PRACA.get(
        programa.publico_alvo, amen.SUGESTOES_PRACA["media"]
    )
    for i, p in enumerate(pracas, start=1):
        sug = sugestoes[(i - 1) % len(sugestoes)]
        lazer_features.append({
            "chave": "praca_bolso", "rotulo": f"Praça {i} — {sug}", "tipo": "praca",
            "area_m2": round(p.area, 2), "geom": p,
        })
    if agua is not None and not agua.is_empty:
        lazer_features.append({
            "chave": "lago", "rotulo": "Lago / espelho d'água", "tipo": "agua",
            "area_m2": round(agua.area, 2), "geom": agua,
        })
    if orla is not None and not orla.is_empty:
        lazer_features.append({
            "chave": "orla_lago", "rotulo": "Orla do lago (parque)", "tipo": "orla",
            "area_m2": round(orla.area, 2), "geom": orla,
        })
    lazer_geoms = [g for g in (clube, *pracas, orla) if g is not None and not g.is_empty]
    cobertura_400 = None
    if lotes and lazer_geoms:
        cobertos = sum(
            1 for l in lotes
            if min(l.centroid.distance(g) for g in lazer_geoms) <= RAIO_CAMINHADA_M
        )
        cobertura_400 = round(cobertos / len(lotes), 4)
    clube_diag = {
        **clube_diag, **hub_diag,
        "n_pracas": len(pracas),
        "pracas_m2": round(sum(p.area for p in pracas), 2),
        # Fase U3 — lago sintetizado (None sem lago; cota do ponto baixo quando o DEM deu).
        "lago_m2": round(agua.area, 2) if agua is not None and not agua.is_empty else None,
        "orla_m2": round(orla.area, 2) if orla is not None and not orla.is_empty else None,
        "lago_cota_m": lago_cota,
        "cobertura_400m_pct": cobertura_400,
        # formatado no BACKEND (o front exibe, não reformata — §2)
        "cobertura_400m_fmt": (f"{cobertura_400 * 100:.0f}%".replace(".", ",")
                               if cobertura_400 is not None else None),
    }

    avisos: list[str] = []
    if not lotes:
        avisos.append(
            "A subdivisão não acomodou lotes na área aproveitável "
            "(gleba pequena/irregular para o perfil)."
        )
    # U7 — rotula a fonte e a cobertura do piso de verde (APAC). §1/§5: número da diretriz, não
    # inventado; a contabilização da mata na APAC é premissa a confirmar na prefeitura.
    if apac_fonte == "diretriz" and apac_alvo is not None:
        if mata_frac >= float(apac_alvo) - 1e-6:
            avisos.append(
                f"Reserva ambiental APAC {float(apac_alvo)*100:.0f}% (diretriz da zona) ATENDIDA "
                f"pela mata preservada ({mata_frac*100:.1f}% da gleba) — o verde reservado é o "
                "mínimo de qualidade. PREMISSA: a mata conta para a APAC (confirmar na prefeitura)."
            )
        else:
            avisos.append(
                f"Reserva ambiental APAC {float(apac_alvo)*100:.0f}% (diretriz): a mata preservada "
                f"({mata_frac*100:.1f}%) NÃO cobre sozinha — o motor reserva +{verde_piso*100:.1f}% "
                "de verde para completar o piso."
            )
    elif apac_fonte == "fallback_estilo" and (usa_paisagem or limpar):
        avisos.append(
            "APAC/área verde NÃO consta na diretriz confirmada — piso de verde por boas práticas "
            f"(~{verde_piso*100:.0f}%), rotulado. Verificar a exigência real na prefeitura."
        )
    if usa_paisagem and modos_paisagem:
        avisos.append(
            f"Arquétipo PAISAGÍSTICO (U6a): traçado '{'/'.join(sorted(set(modos_paisagem)))}' "
            "com cinturão verde perimetral — a paisagem estrutura, os lotes preenchem "
            "(spec fase-U6-pods.md, padrão das referências do operador)."
        )
    elif paisagem_degradou:
        avisos.append(
            "Arquétipo paisagístico NÃO aplicado: a gleba é menor que o mínimo da composição "
            f"(~{paisagem_min / 10000:.0f} ha úteis) — cinturão+anéis/folha esmagariam o lazer "
            "e o aproveitamento. Traçado clássico do perfil mantido (rotulado, não silencioso)."
        )
    if pracas:
        avisos.append(
            f"Lazer distribuído (U2): {len(pracas)} praça(s) de bolso reservada(s) para "
            "aproximar o lazer dos lotes (raio de caminhada de 400 m — pesquisa §2); "
            "o orçamento total de lazer do programa não mudou."
        )
    if agua is not None and not agua.is_empty:
        avisos.append(
            "LAGO SINTETIZADO (U3) no ponto baixo do terreno, desenhado como PARQUE (corpo "
            "d'água + orla pública — pesquisa §1: pond criado junto ao empreendimento premia o "
            "entorno; bacia sem paisagismo desvaloriza). A lâmina d'água NÃO foi contada na "
            "doação de área verde (aceitação é municipal — verificar na prefeitura); custo de "
            "implantação: disciplina 'Lago / paisagismo da orla' no Custo de Infra. Estudo "
            "esquemático — projeto hidráulico/outorga são do projetista (§1-A)."
            + (" No ALTO PADRÃO o lago teve prioridade sobre lotes (o prêmio do entorno paga o "
               "sacrifício) e foi dimensionado para a quadra disponível "
               f"(~{agua.area:,.0f} m²)." if lago_redimensionado else "")
        )
    elif lago and lago.get("ponto") and lago_reg is None:
        avisos.append(
            "LAGO NÃO SINTETIZADO: nenhuma quadra comporta o corpo d'água pedido sem "
            "sacrificar o parcelamento (nos perfis econômico/médio os lotes têm prioridade; "
            "no ALTO PADRÃO o lago é priorizado e redimensionado automaticamente) — reduza a "
            "área do lago ou regenere com o perfil alta renda."
        )

    meta = {
        "lazer_alvo_pct": round(pct_lazer0, 4),
        "lazer_usado_pct": round(lazer_reservado_m2 / aprov_area, 4) if aprov_area else 0.0,
        # fidelidade do lazer usa a RESERVA materializada (clube + verde formado).
        "lazer_reservado_pct": round(lazer_reservado_m2 / aprov_area, 4) if aprov_area else 0.0,
        "lazer_degradado": degradado,
        "inst_alvo_pct": round(pct_inst, 4),
        "arquetipo": programa.arquetipo_viario,
        "esqueleto_usado": usar_esqueleto,
        # Fase 9.9 — estado do esqueleto + curvatura (espelha o viario_diagnostico).
        "esqueleto_origem": esqueleto_origem,
        "esqueleto_vazio": esqueleto_vazio,
        "sinuosidade_media": sinuosidade_media,
        "eixos_curvos": eixos_curvos,
        "trechos_descartados": len(descartes),
        "orientacao_rad": round(orientacao_rad, 6),
        "topo_aplicada": abs(orientacao_rad) > 1e-9,
        "sobra_retalho_m2": round(retalho_m2, 2),
        # Fase 9.7 — malha: conectividade + nº de quadras (faces).
        "viario_conexo": conexo,
        "n_quadras": len(quadras_geom),
        # Fase 9.3/9.4 — mira da subdivisão + CLAMP legal [piso, teto] (o tamanho emerge da quadra).
        "testada_alvo_m": round(testada_alvo, 2),
        "prof_alvo_m": round(prof, 2),
        "piso_lote_m2": round(piso_lote, 2),
        "teto_lote_m2": round(teto_lote, 2),
        "faixa_lote_m2": [round(piso_lote, 2), round(teto_lote, 2)],
        "lote_alvo_origem": programa.lote_alvo_origem,
        # Fase U6a — arquétipo paisagístico efetivo (modo por ilha) + cinturão.
        "paisagem": ({
            "modos": modos_paisagem,
            "cinturao_m2": round(cinturao_orig.area, 1) if cinturao_orig is not None else 0.0,
            "corredores_m2": round(sum(c.area for c in corredores_reg), 1),
            "n_corredores": len(corredores_reg),
        } if usa_paisagem else None),
        # Fase U4 — que variante gerou este layout (proveniência da estratégia).
        "variante": {
            "id": str(variante.get("id", "V1")),
            "rotulo": str(variante.get("rotulo", "base")),
            "hub_estrategia": hub_estrategia,
            "orientacao_extra_deg": round(
                math.degrees(float(variante.get("orientacao_extra_rad", 0.0))), 1
            ),
        },
    }

    return Layout(
        lotes=lotes,
        arruamento=arruamento,  # 9.7 — a MALHA medida (não mais subtração)
        areas_verdes=verde,  # TOTAL (reservado ∪ sobra) — quadro/conformidade usam este
        areas_verdes_reservada=verde_reservado,  # 9.6/9.7 — quadras verdes formadas (mapa)
        sobra_ponta=sobra_ponta,
        sistema_lazer=lazer_total,  # U2 — hub ∪ praças de bolso (união medida no quadro)
        institucional=inst,
        centerlines=curvas_ia,  # 9.9 — curvas (IA ou fallback) usadas; [] na grelha
        via_largura_m=via,
        ignorados=descartes,
        avisos=avisos,
        meta=meta,
        lote_quadra=lote_quadra,
        quadras=quadras_geom,
        eixos_malha=eixos_malha,
        viario_diagnostico=viario_diag,
        institucional_diagnostico=inst_diag,
        sistema_lazer_diagnostico=clube_diag,
        lazer_features=lazer_features,  # U2 — sub-parcelas do hub + praças (rotuladas)
        portico=portico_geom,  # 11.3 — marcador da entrada/portaria p/ o mapa
        agua=agua,  # U3 — lago/espelho d'água (liga o fator "agua" do score v2)
    )


# ============================ topografia (DEM 2.5 → orientação) ============================
def orientacao_contorno(dem) -> Optional[float]:
    """Ângulo (rad) da CURVA DE NÍVEL média do recorte de DEM (2.5) — perpendicular ao
    gradiente. Orienta a grelha de quarteirões (acompanhar o relevo). ``None`` se não há DEM
    ou o terreno é praticamente plano. Orientação de triagem, NÃO terraplenagem."""
    if dem is None or getattr(dem, "elevacao", None) is None:
        return None
    try:
        import numpy as np

        z = np.asarray(dem.elevacao, dtype="float64")
        if z.ndim != 2 or z.size < 4:
            return None
        px = getattr(dem, "px_m", 0.0) or 1.0
        gr, gc = np.gradient(z, px)  # gr = dz/drow (linha cresce p/ SUL), gc = dz/dcol (LESTE)
        gx = float(np.nanmean(gc))
        gy = -float(np.nanmean(gr))  # y métrico cresce p/ NORTE → inverte a linha
    except Exception:  # noqa: BLE001 — sem numpy/grid inválido → sem orientação
        return None
    if abs(gx) < 1e-12 and abs(gy) < 1e-12:
        return None  # plano → grelha axial
    return math.atan2(gy, gx) + math.pi / 2.0  # curva de nível ⟂ gradiente
