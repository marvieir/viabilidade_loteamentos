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


def construir_malha(reg: BaseGeometry, eixos_ia: Sequence[BaseGeometry], block_w: float,
                    block_h: float, via_local: float, via_tronco: float):
    """MALHA VIÁRIA CONEXA (no frame já rotacionado ``reg``): uma grade LOCAL de blocos iguais
    (sem sliver de borda — os eixos dividem a tela em N blocos exatos) somada aos EIXOS DA IA
    como TRONCO (atravessam a grade → conectam tudo numa peça só). Devolve ``(faces, ruas,
    eixos, troncos)``: ``faces`` = polígonos cercados pelas ruas (``polygonize``); ``ruas`` =
    união dos buffers das centerlines ∩ ``reg`` (conexa por construção); ``eixos`` = todas as
    centerlines (p/ medir comprimento de via); ``troncos`` = só as de tronco (hierarquia)."""
    minx, miny, maxx, maxy = reg.bounds
    W, H = (maxx - minx), (maxy - miny)
    eixos: list[tuple[LineString, float]] = []  # (centerline, largura)
    # Grade LOCAL: nº de blocos que cabe → linhas igualmente espaçadas (blocos iguais, sem ponta).
    nbx = max(int(round(W / (block_w + via_local))), 1)
    nby = max(int(round(H / (block_h + via_local))), 1)
    for i in range(1, nbx):
        x = minx + i * W / nbx
        eixos.append((LineString([(x, miny), (x, maxy)]), via_local))
    for j in range(1, nby):
        y = miny + j * H / nby
        eixos.append((LineString([(minx, y), (maxx, y)]), via_local))

    # TRONCO: os eixos da IA (semente) entram como via principal; atravessam a grade → conexão.
    troncos: list[LineString] = []
    for e in (eixos_ia or []):
        rec = _valido(e.intersection(reg)) if e is not None else None
        for part in _linhas(rec):
            eixos.append((part, via_tronco))
            troncos.append(part)
    # Sem eixo da IA: promove a linha central da grade a tronco (sempre há uma via principal).
    if not troncos and eixos:
        centrais = sorted(eixos, key=lambda gw: abs(gw[0].centroid.x - reg.centroid.x)
                          + abs(gw[0].centroid.y - reg.centroid.y))
        g, _ = centrais[0]
        eixos = [(gg, via_tronco if gg is g else w) for gg, w in eixos]
        troncos.append(g)

    if not eixos:  # gleba menor que um bloco → uma quadra só, sem via interna (degrada honesto)
        return [g for g in _componentes(reg)], None, [], []

    linhas = [reg.boundary] + [g for g, _ in eixos]
    noded = _uniao_segura(linhas)
    faces = []
    if noded is not None and not noded.is_empty:
        for f in polygonize(noded):
            if f.is_empty:
                continue
            try:
                dentro = reg.contains(f.representative_point())
            except Exception:  # noqa: BLE001 — ponto representativo degenerado
                dentro = reg.intersects(f.centroid)
            if dentro:
                faces.append(f)
    ruas = _uniao_segura([
        _valido(g.intersection(reg)).buffer(w / 2.0, cap_style=2, join_style=2)
        for g, w in eixos if g is not None and not g.intersection(reg).is_empty
    ])
    if ruas is not None and not ruas.is_empty:
        ruas = _valido(ruas.intersection(reg))
    else:
        ruas = None
    return faces, ruas, [g for g, _ in eixos], troncos


def _miolo(face: BaseGeometry, ruas: Optional[BaseGeometry]) -> Optional[Polygon]:
    """Quadra = face − ruas (o miolo, descontada a largura da via). Maior componente válido."""
    q = _diferenca_segura(face, ruas) if ruas is not None else face
    return _maior_parte(q)


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


# ============================ esqueleto da IA (intenção → eixos) ============================
def _eixos(esqueleto: Sequence, canvas: Polygon) -> tuple[list[BaseGeometry], list[str]]:
    """Denormaliza o esqueleto da IA (coords 0..1 do bbox da gleba) → eixos métricos, snapados
    à tela. Trecho inválido (auto-interseção, fora) é DESCARTADO e registrado (nunca cru)."""
    minx, miny, maxx, maxy = canvas.bounds
    w, h = (maxx - minx), (maxy - miny)
    validos: list[BaseGeometry] = []
    descartes: list[str] = []
    for i, coords in enumerate(esqueleto or []):
        try:
            pts = [(minx + float(x) * w, miny + float(y) * h) for x, y in coords]
            ls = LineString(pts)
        except Exception:  # noqa: BLE001 — coords malformadas do LLM
            descartes.append(f"esqueleto[{i}] descartado: coordenadas inválidas")
            continue
        if len(ls.coords) < 2 or not ls.is_valid or not ls.is_simple:
            descartes.append(f"esqueleto[{i}] descartado: polilinha auto-intersectada/degenerada")
            continue
        rec = ls.intersection(canvas)
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

    # (b) esqueleto da IA → eixos; usado como TRONCO quando o arquétipo NÃO é grelha pura e há
    # eixo válido. Na grelha, a malha promove a linha central a tronco (esqueleto_usado=False).
    centerlines, descartes = _eixos(programa.esqueleto, aprov)
    usar_esqueleto = programa.arquetipo_viario != ARQUETIPO_GRELHA and bool(centerlines)
    eixos_ia = centerlines if usar_esqueleto else []

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
    via_tronco = max(via, VIA_TRONCO_M)       # coletora/tronco (hierarquia ≥21 m)
    block_w = N_LOTES_QUADRA * testada_alvo    # testada da quadra ~ N lotes
    block_h = 2.0 * prof                        # quadra de duas fileiras (costas-com-costas)
    faces, ruas_reg, eixos_reg, troncos_reg = construir_malha(
        reg, eixos_ia_reg, block_w, block_h, via_local, via_tronco
    )

    # Quadras = miolo de cada face (face − ruas). Faces minúsculas → quadra verde formada (sobra).
    declividade_pct = (
        float(diretrizes.get("declividade_media_pct"))
        if diretrizes.get("declividade_media_pct") is not None else None
    )
    miolos: list[Polygon] = []
    verdes_min: list[Polygon] = []  # faces pequenas → verde formado (não sliver)
    for f in faces:
        q = _miolo(f, ruas_reg)
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

    # Conectividade do viário (critério 1): a malha é UMA peça? (ilhas da gleba → honesto False).
    n_trechos = len(_componentes(arruamento)) if arruamento is not None else 0
    conexo = n_trechos == 1
    viario_diag = {
        "conexo": conexo,
        "trechos": n_trechos,
        "trechos_descartados": len(descartes),
        "hierarquia": {"tronco_m": round(via_tronco, 1), "local_m": round(via_local, 1)},
        "obs": ("malha a partir dos eixos da IA; trechos soltos conectados ao tronco da grade"
                if conexo else
                "gleba partida em ilhas pela restrição — viário conexo dentro de cada ilha"),
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
        centerlines=centerlines if usar_esqueleto else [],
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
