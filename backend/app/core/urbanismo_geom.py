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
from shapely.geometry import LineString, Polygon, box
from shapely.geometry.base import BaseGeometry
from shapely.ops import polygonize, unary_union

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
    testada_eff = max(min(alvo / depth, teto / depth), FRENTE_MIN_M)
    n = max(int(round(L / testada_eff)), 1)
    # Peça rasa: não dividir além do que o PISO comporta — senão (L/n)·depth < piso e o clamp
    # descarta tudo (gleba rasa ficaria sem lote). Cap em ⌊área/piso⌋ (≥1 quando comporta um lote).
    n = min(n, max(int(piece.area / max(piso, 1.0)), 1))
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

    verts = [minx + i * W / nbx for i in range(1, nbx)]
    horiz = [miny + j * H / nby for j in range(1, nby)]
    # a curva substitui a linha paralela mais próxima (evita via dupla, sem dropar a família toda).
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
        nrows = max(int(round(depth / prof)), 1)
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


def _eixos(esqueleto: Sequence, canvas: Polygon) -> tuple[list[BaseGeometry], list[str]]:
    """Denormaliza o esqueleto da IA (coords 0..1 do bbox) → eixos métricos CURVOS (9.9: suaviza
    a polilinha em curva). Aceita polilinha crua ou ``{"pontos":[...]}``. Trecho inválido
    (auto-interseção, fora, <2 vértices) é DESCARTADO e registrado (nunca cru)."""
    minx, miny, maxx, maxy = canvas.bounds
    w, h = (maxx - minx), (maxy - miny)
    validos: list[BaseGeometry] = []
    descartes: list[str] = []
    for i, item in enumerate(esqueleto or []):
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


def gerar_layout(
    aproveitavel: BaseGeometry,
    programa: Programa,
    restricoes: Optional[BaseGeometry] = None,
    orientacao_rad: float = 0.0,
    diretrizes: Optional[dict] = None,
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
    if restricoes is not None and not restricoes.is_empty:
        canvas = _diferenca_segura(canvas, restricoes)
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

    via_local = min(via, VIA_LOCAL_M)         # rua de quadra (local)
    # Tronco: na GRELHA, a coletora central é larga (≥21 m, hierarquia 9.8). No traçado SINUOSO,
    # a via-tronco curva usa a largura da VIA PRINCIPAL do programa (~14 m) — uma curva de 21 m de
    # largura infla o viário acima do teto; 14 m mantém a curva visível dentro de ≤18% (9.9).
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
    ruas_reg = _uniao_segura(ruas_parts)

    # Quadras = miolo de cada face (face − ruas). Faces minúsculas → quadra verde formada (sobra).
    declividade_pct = (
        float(diretrizes.get("declividade_media_pct"))
        if diretrizes.get("declividade_media_pct") is not None else None
    )
    miolos: list[Polygon] = []
    verdes_min: list[Polygon] = []  # faces pequenas → verde formado (não sliver)
    for f in faces:
        # 9.9: a via-tronco CURVA pode partir uma face em VÁRIOS pedaços — capturar TODOS (não só
        # o maior, senão a área dos demais some e quebra a invariância). Cada pedaço é uma quadra.
        for q in _componentes(_diferenca_segura(f, ruas_reg)):
            if q is None or q.is_empty:
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
    for qi, q in enumerate(pool, start=1):
        sub, res = _lotear_face(q, testada_alvo, prof, alvo_area, piso_lote, teto_lote)
        for lote in sub:
            lotes_reg.append(lote)
            lote_quadra.append(f"Q{qi}")
        residuais_reg.extend(res)

    # SOBRA → quadras verdes formadas (faces pequenas) + pontas de loteamento (mínimas).
    verde_reservado_reg = _uniao_segura([*verdes_reg, *verdes_min])
    sobra_reg = _uniao_segura(residuais_reg)
    verde_total_reg = _uniao_segura([verde_reservado_reg, sobra_reg])

    # Volta ao frame original (gira por +ang). Operação geométrica determinística (§2).
    def _back(g):
        if g is None or g.is_empty:
            return None
        return rotate(g, ang_deg, origin=cen) if ang_deg else g

    lotes = [r for r in (_back(l) for l in lotes_reg) if r is not None]
    quadras_geom = [r for r in (_back(q) for q in (miolos + verdes_min)) if r is not None]
    arruamento = _back(ruas_reg)
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
    n_trechos = len(_componentes(arruamento)) if arruamento is not None else 0
    conexo = n_trechos == 1
    conexo_por_ilha = bool(trechos_por_ilha) and all(t == 1 for t in trechos_por_ilha)
    viario_m2 = arruamento.area if arruamento is not None and not arruamento.is_empty else 0.0
    vendavel_m2 = sum(l.area for l in lotes)
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
