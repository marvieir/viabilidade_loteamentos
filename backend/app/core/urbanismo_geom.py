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
from app.core import urbanismo_tracado as trac
from app.core.urbanismo_medida import Layout, _lados_mrr
from app.core.urbanismo_programa import PERFIL_LOTE, Programa

# Convergência: |medido − alvo| ≤ tol → "atendido" (spec §4.1).
TOL_CONVERGENCIA_PP = 0.03
# Degradação: reserva lazer só até sobrar área para ~este nº de lotes (preserva o parcelamento).
MIN_LOTES_RESERVA = 8
# Fração da reserva de lazer destinada ao clube central (resto = áreas verdes ao redor).
LAZER_CLUBE_FRAC = 0.40
ARQUETIPO_GRELHA = "grelha_eficiente"
# Via LOCAL (rua de quadra) — separa as quadras na grelha. A via PRINCIPAL (esqueleto) usa a
# largura do programa; ruas locais são estreitas (~8 m), o que mantém o viário realista.
VIA_LOCAL_M = 8.0
# Frente mínima legal (Lei 6.766/79 art. 4º II) — testada nunca abaixo disso.
FRENTE_MIN_M = 5.0

# ---- Fase 9.7: MALHA VIÁRIA + QUADRAS COMO FACES (a inversão da geração, §0 da spec) ----
# Largura do TRONCO/coletora (hierarquia legal ≥21 m) — os eixos da IA viram via principal.
VIA_TRONCO_M = 21.0
# Nº de lotes que dá a TESTADA de uma quadra (espaça os eixos da grade local; o tamanho do lote
# continua emergindo da subdivisão — isto é só o passo da malha).
N_LOTES_QUADRA = 6
# Face menor que isso (m²) não vira quadra loteável → quadra VERDE formada (sobra, não sliver).
MIN_QUADRA_M2 = 250.0
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


def construir_malha(reg: BaseGeometry, eixos_ia: Sequence[BaseGeometry], block_w: float,
                    block_h: float, via_local: float, via_tronco: float, podar: bool = True):
    """MALHA de UMA ILHA (frame rotacionado ``reg``): grade local recortada à ilha + tronco,
    depois PODA dos stubs (Fase 9.8). Devolve ``(faces, ruas, eixos, troncos, n_stubs)`` — a
    malha é conexa DENTRO da ilha (a gleba partida por restrição é tratada como ilhas separadas)."""
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
        minx, miny, maxx, maxy = c.bounds
        depth = maxy - miny
        # Só faces CLARAMENTE desperdiçadas (≥ 4·prof de fundo): aí as 2 fileiras deixam um miolo
        # grande. Faces medianas ficam intactas (injetar via nelas só comeria 1 lote — regressão).
        if depth < 2.0 * banda:
            faces_out.append(c)
            continue
        n = max(int(round(depth / banda)), 2)  # nº de bandas (cada uma ~2·prof de fundo)
        linhas = []
        for k in range(1, n):
            yk = miny + k * depth / n
            seg = LineString([(minx - 1.0, yk), (maxx + 1.0, yk)]).intersection(c)
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
        for sf in _componentes(_diferenca_segura(c, via)):
            if sf is not None and not sf.is_empty:
                faces_out.append(sf)
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


def clube_como_quadra(quadras: Sequence[BaseGeometry], ruas: Optional[BaseGeometry], alvo: float):
    """Clube/lazer como FIGURA FORMADA com frente para via (não o disco central da v1).
    Escolhe a face com frente ≥10 m mais próxima do ``alvo`` de área. Devolve ``(geom, diag)``."""
    cands = []
    for q in quadras:
        fr, pr = _lados_mrr(q)
        toca = bool(ruas is not None and not ruas.is_empty and q.distance(ruas) < 0.6)
        if fr >= INST_FRENTE_MIN_M and (toca or ruas is None):
            cands.append((q, fr, pr))
    if not cands or alvo <= 0:
        return None, {}
    alvo = max(alvo, 1.0)
    q, fr, pr = min(cands, key=lambda c: abs(c[0].area - alvo))
    return q, {"forma": "quadra", "frente_via_m": round(fr, 2)}


def _selecionar_verde(pool: Sequence[BaseGeometry], alvo: float):
    """Reserva quadras VERDES formadas até somar ~``alvo`` (sem estourar muito além — preserva
    lotes). Faces inteiras (não slivers). Devolve ``(verdes, resto)``."""
    if alvo <= 0 or not pool:
        return [], list(pool)
    ordem = sorted(pool, key=lambda g: -g.area)  # blocos maiores primeiro (menos peças → limpo)
    verdes, acc = [], 0.0
    for f in ordem:
        if acc >= alvo - 1e-6:
            break
        if acc + f.area <= alvo + f.area * 0.5:  # não estoura mais que meia face além do alvo
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
) -> Layout:
    """Materializa o estudo de massa dentro de ``aproveitavel`` (CRS métrico). ``diretrizes``
    (Fase 9.4) traz piso/teto LEGAL de lote e o split de doação (município→federal); sem ele,
    cai nas faixas de mercado do perfil. ``orientacao_rad`` gira a grelha (topografia 9.1)."""
    # Diretrizes: piso/teto LEGAL do lote + reservas mínimas (lei vence o mercado). Sem 1.8 →
    # piso federal + mercado (rotulado pelo chamador).
    if diretrizes is None:
        from app.core.urbanismo_diretrizes import resolver_diretrizes
        diretrizes = resolver_diretrizes(None, None, None, programa.publico_alvo)

    canvas = aproveitavel
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
    pct_inst = max(0.0, min(max(programa.pct_institucional, pct_inst_min), 0.3))

    # (b) Fase 9.9 — EIXOS CURVOS: a IA propõe a geometria dos eixos (polilinha → curva suave);
    # usados como TRONCO quando o arquétipo NÃO é grelha. Se o esqueleto vier VAZIO (a falha que o
    # diagnóstico 9.8 achou), NÃO cair na grade silenciosa: gerar uma ESPINHA SINUOSA por ilha
    # (fallback explícito, rotulado). Na grelha (baixa), mantém a linha central reta (intencional).
    centerlines, descartes = _eixos(programa.esqueleto, aprov)
    usar_esqueleto = programa.arquetipo_viario != ARQUETIPO_GRELHA and bool(centerlines)
    eixos_ia = centerlines if usar_esqueleto else []
    quer_curva = programa.arquetipo_viario != ARQUETIPO_GRELHA  # arquétipo sinuoso/misto → curva
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
    inst_area = pct_inst * aprov_area
    disp_lazer = max(aprov_area - inst_area - MIN_LOTES_RESERVA * lote_area, 0.0)
    alvo_lazer_area = pct_lazer0 * aprov_area
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

    via_local = min(via, VIA_LOCAL_M)         # rua de quadra (local)
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
        fcs, ruas_i, eix_i, _tron_i, n_stub = construir_malha(
            ilha, eixos_ia_ilha, bw_i, bh_i, via_local, via_tronco, podar=True
        )
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
    # REGRA B — porção ISOLADA (sem borda livre): suas faces não viram lote, viram verde (honesto).
    isoladas_reg = _uniao_segura([p["geom"] for p in porcoes_info if not p["conectada"]])

    # Quadras = miolo de cada face (face − ruas). Faces minúsculas → quadra verde formada (sobra).
    declividade_pct = (
        float(diretrizes.get("declividade_media_pct"))
        if diretrizes.get("declividade_media_pct") is not None else None
    )
    miolos: list[Polygon] = []
    verdes_min: list[Polygon] = []  # faces pequenas → verde formado (não sliver)
    for f in faces:
        # Fase 10.8 — a parte ≥30% da face vira VERDE preservado (lote a evita); só o <30% é loteável.
        # A via já passou por cima (canvas não foi recortado), então a malha continua conexa.
        if restr_lote_reg is not None:
            f_sem30 = _diferenca_segura(f, restr_lote_reg)
            f_30 = _diferenca_segura(f, f_sem30)  # = f ∩ ≥30%
            if f_30 is not None and not f_30.is_empty:
                for g in _componentes(_diferenca_segura(f_30, ruas_reg) or f_30):
                    if g is not None and not g.is_empty and g.area > 1.0:
                        verdes_min.append(g)
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

    # 4.a INSTITUCIONAL: uma quadra com frente para via que satisfaça os 4 checks legais (borda).
    inst_reg, inst_diag = (
        institucional_como_quadra(miolos, ruas_reg, reg, inst_area, declividade_pct)
        if (pct_inst > 0 and _pode_reservar(miolos)) else (None, {})
    )
    pool = [q for q in miolos if inst_reg is None or q is not inst_reg]

    # 4.b CLUBE: figura formada com frente para via (não círculo). Verde de lazer = quadras verdes.
    clube_target = LAZER_CLUBE_FRAC * lazer_area
    clube_reg, clube_diag = (
        clube_como_quadra(pool, ruas_reg, clube_target) if _pode_reservar(pool) else (None, {})
    )
    # só materializa o clube se couber no orçamento de lazer (degradação: gleba não comporta).
    if clube_reg is not None and clube_reg.area > lazer_area * 1.5 + 1e-6:
        clube_reg, clube_diag = None, {}
    pool = [q for q in pool if clube_reg is None or q is not clube_reg]

    # 4.c VERDE: quadras verdes formadas até o orçamento de lazer — sempre deixando ≥1 p/ lotes.
    verde_budget = max(lazer_area - (clube_reg.area if clube_reg is not None else 0.0), 0.0)
    verdes_reg, pool = _selecionar_verde(pool, verde_budget) if _pode_reservar(pool) else ([], pool)
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
            sub, res = _lotear_face(sf, testada_alvo, prof, alvo_area, piso_lote, teto_lote)
            for lote in sub:
                lotes_reg.append(lote)
                lote_quadra.append(f"Q{qi}")
            residuais_reg.extend(res)
    # as vias internas injetadas entram na malha ANTES do frente-via (p/ os lotes do miolo contarem
    # como lindeiros) e no arruamento medido.
    if vias_internas_reg:
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
    lotes_reg, lote_quadra, encravados_verde, frente_stats = garantir_frente_via(
        lotes_reg, lote_quadra, ruas_reg, piso_lote, teto_lote, FRENTE_MIN_M
    )
    residuais_reg.extend(encravados_verde)  # encravado sem via vira verde (não lote fantasma)


    # SOBRA → quadras verdes formadas (faces pequenas) + pontas de loteamento (mínimas).
    # RESERVADA = só o que foi PEDIDO (lazer/verde de programa); faces pequenas (verdes_min) e as
    # pontas de loteamento são LEFTOVER geométrico → sobra_ponta (não "reserva inventada"). Mantém
    # ``areas_verdes_reservada is None`` quando nada foi pedido (Fase 9.6/9.12). Fase 9.14: a RESERVA
    # (mata/lazer do programa) permanece verde; só a SOBRA cai quando o contorno dá acesso (regra D).
    verde_reservado_reg = _uniao_segura(verdes_reg)
    sobra_reg = _uniao_segura([*residuais_reg, *verdes_min])
    # Fase 9.14 — regra D: o que virou LOTE/ via de contorno (recuperado) sai da sobra-verde (cai).
    if lotes_rec_reg or contorno_mat_reg:
        sobra_reg = _diferenca_segura(sobra_reg, _uniao_segura([*lotes_rec_reg, *contorno_mat_reg]))
    verde_total_reg = _uniao_segura([verde_reservado_reg, sobra_reg])
    verde_reserva_m2 = verde_reservado_reg.area if verde_reservado_reg is not None else 0.0
    verde_sobra_m2 = sobra_reg.area if sobra_reg is not None else 0.0

    # Volta ao frame original (gira por +ang). Operação geométrica determinística (§2).
    def _back(g):
        if g is None or g.is_empty:
            return None
        return rotate(g, ang_deg, origin=cen) if ang_deg else g

    lotes = [r for r in (_back(l) for l in lotes_reg) if r is not None]
    quadras_geom = [r for r in (_back(q) for q in (miolos + verdes_min)) if r is not None]
    arruamento = _back(ruas_reg)
    # Fase 10.4 — SOLDA FINAL da malha (no frame ORIGINAL já validado, onde a união é ESTÁVEL — no
    # frame rotacionado a solda é frágil e o buffer(0) do _back a quebra): com travessia VIÁVEL,
    # garante UMA malha viária contínua (fecha o "buraco" entre as porções). Sem travessia/greide
    # inviável → não roda (degradação honesta: segue partido com alerta de engenharia).
    if travessia_viavel and arruamento is not None and not arruamento.is_empty:
        arruamento = _conectar_malha(arruamento, conexao_mod.CAIXA_TRONCO_M) or arruamento
    clube = _back(clube_reg)
    inst = _back(inst_reg)
    verde_reservado = _back(verde_reservado_reg)
    verde = _back(verde_total_reg)
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
    if arruamento is not None and not arruamento.is_empty:
        gminx, gminy, gmaxx, gmaxy = aprov.bounds
        # entrada = ponto do arruamento mais próximo do acesso pela via pública (borda sul da gleba)
        portico_pt = nearest_points(Point((gminx + gmaxx) / 2.0, gminy), arruamento)[1]
        if inst is not None and not inst.is_empty:
            diag_gleba = math.hypot(gmaxx - gminx, gmaxy - gminy)
            inst_na_entrada = inst.distance(portico_pt) <= 0.35 * max(diag_gleba, 1.0)
    porticos = 1 if portico_pt is not None else 0
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

    lazer_reservado_m2 = sum(
        g.area for g in (clube, verde_reservado) if g is not None and not g.is_empty
    )
    retalho_m2 = 0.0  # a sobra foi destinada à área pública (sem retalho perdido)

    avisos: list[str] = []
    if not lotes:
        avisos.append(
            "A subdivisão não acomodou lotes na área aproveitável "
            "(gleba pequena/irregular para o perfil)."
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
    }

    return Layout(
        lotes=lotes,
        arruamento=arruamento,  # 9.7 — a MALHA medida (não mais subtração)
        areas_verdes=verde,  # TOTAL (reservado ∪ sobra) — quadro/conformidade usam este
        areas_verdes_reservada=verde_reservado,  # 9.6/9.7 — quadras verdes formadas (mapa)
        sobra_ponta=sobra_ponta,
        sistema_lazer=clube,
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
