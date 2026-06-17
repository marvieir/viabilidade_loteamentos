"""Fase 9.1 — Urbanismo: FIDELIDADE do traçado ao programa.

Casos sintéticos (geometria controlada) cravam convergência/degradação/arquétipo/topografia de
forma determinística — a parte criativa (programa/esqueleto) é fixa. A fronteira do §2 não se
move: a IA dá intenção (programa+esqueleto); o Python materializa por operações geométricas e
mede. Os ouros de `/medir` da Fase 9 permanecem (não-regressão).
"""

import math
import re

from shapely.geometry import box
from shapely.ops import unary_union

from app.core import urbanismo_geom as geom
from app.core import urbanismo_medida as medida
from app.core.declividade import DEMRecorte
from app.core.urbanismo_programa import programa_do_preset
from tests.conftest import RET_RETANGULO, make_kmz


def _frac_lazer(med, layout=None):
    # Lazer RESERVADO (9.4): a sobra de ponta anexada ao verde não conta como lazer do programa.
    if layout is not None and layout.meta.get("lazer_reservado_pct") is not None:
        return layout.meta["lazer_reservado_pct"]
    q = med.quadro
    liq = q["area_liquida_m2"] or 1.0
    return (q["sistema_lazer"]["m2"] + q["areas_verdes"]["m2"]) / liq


# --------------------------- (a) materialização das áreas ---------------------------
def test_convergencia_lazer_ouro():
    """Critério 1: programa lazer 25% + inst 5% numa gleba ~58.682 m² → lazer materializado
    substancial (∈ [18%,30%]), institucional ≥ 5%. A v1 (2,5%) ficaria FORA — o critério morde.

    Fase 9.7: as áreas públicas viram QUADRAS FORMADAS (faces da malha), não discos de área
    exata; a convergência é mais grossa (granularidade da face), mas o lazer é uma figura real
    com frente para via — o ganho que o operador pediu. A faixa reflete essa discretização."""
    aprov = box(0.0, 0.0, 360.0, 163.0)  # 58.680 m²
    prog = programa_do_preset("alta", {"pct_lazer": 0.25, "pct_institucional": 0.05})
    layout = geom.gerar_layout(aprov, prog)
    med = medida.medir(layout)
    lazer = _frac_lazer(med, layout)
    inst = med.quadro["institucional"]["m2"] / med.quadro["area_liquida_m2"]
    assert 0.18 <= lazer <= 0.30  # materializado como quadra formada (a v1 dava ~0,025)
    assert inst >= 0.05 - 0.001
    assert not layout.meta["lazer_degradado"]
    fid = medida.construir_fidelidade(med, layout)
    # a fidelidade pode marcar "atenção" (face discreta ≠ alvo exato) — o que importa é que
    # NÃO está degradado e o lazer é substancial. Status atendido OU atencao, nunca degradado.
    item = next(a for a in fid["areas"] if a["item"] == "lazer")
    assert item["status"] in ("atendido", "atencao")


def test_reserva_antes_de_lotear():
    """Critério 2: soma das classes = área aproveitável (±0,5 m²); lazer/inst NÃO intersectam lotes."""
    aprov = box(0.0, 0.0, 360.0, 163.0)
    prog = programa_do_preset("alta", {"pct_lazer": 0.25, "pct_institucional": 0.05})
    layout = geom.gerar_layout(aprov, prog)
    med = medida.medir(layout)
    q = med.quadro
    soma = (
        q["vendavel"]["m2"] + q["areas_verdes"]["m2"] + q["sistema_lazer"]["m2"]
        + q["institucional"]["m2"] + q["arruamento"]["m2"]
    )
    assert abs(soma - q["area_liquida_m2"]) < 0.5
    reservas = unary_union(
        [g for g in (layout.sistema_lazer, layout.areas_verdes, layout.institucional)
         if g is not None]
    )
    invasao = sum(l.intersection(reservas).area for l in layout.lotes)
    assert invasao < 1e-6


def test_degradacao_honesta():
    """Critério 3: numa gleba pequena para o lote-alvo, o lazer 25% é REDUZIDO (preservando
    lotes), rotulado 'degradado', medido < alvo — nunca inflado nem zerado."""
    aprov = box(0.0, 0.0, 150.0, 33.0)  # ~4.950 m² — não comporta 25% + lotes (calibração 9.3)
    prog = programa_do_preset("alta", {"pct_lazer": 0.25, "pct_institucional": 0.05})
    layout = geom.gerar_layout(aprov, prog)
    med = medida.medir(layout)
    assert layout.meta["lazer_degradado"] is True
    assert _frac_lazer(med, layout) < 0.25  # reduzido
    assert med.indicadores["n_lotes"] > 0  # lotes preservados
    fid = medida.construir_fidelidade(med, layout)
    item = next(a for a in fid["areas"] if a["item"] == "lazer")
    assert item["status"] == "degradado" and item["leitura"]
    assert "urbanista" in item["leitura"]


# --------------------------- (b) viário por arquétipo + esqueleto ---------------------------
def test_esqueleto_consumido():
    """Critério 4: esqueleto válido (normalizado 0..1) vira eixo de via; a via segue o eixo
    (pontos do eixo caem na arruamento); esqueleto_usado=true."""
    esq = [[[0.1, 0.5], [0.9, 0.5]]]  # eixo horizontal no meio
    prog = programa_do_preset("alta", {"pct_lazer": 0.1, "esqueleto": esq})
    layout = geom.gerar_layout(box(0.0, 0.0, 400.0, 200.0), prog)
    assert layout.meta["esqueleto_usado"] is True
    assert len(layout.centerlines) >= 1
    eixo = unary_union(layout.centerlines)
    # O eixo virou CORREDOR DE VIA: os lotes não sentam sobre ele (foi reservado do loteamento).
    corredor = eixo.buffer(prog.largura_via_m / 2.0)
    invasao = sum(l.intersection(corredor).area for l in layout.lotes)
    assert invasao < corredor.area * 0.05


def test_esqueleto_invalido_descartado_e_contado():
    """Critério 4: trecho auto-intersectado é descartado, contado, e não vira via crua."""
    bowtie = [[0.1, 0.1], [0.9, 0.9], [0.1, 0.9], [0.9, 0.1]]
    prog = programa_do_preset("alta", {"esqueleto": [bowtie]})
    layout = geom.gerar_layout(box(0.0, 0.0, 400.0, 400.0), prog)
    assert layout.meta["trechos_descartados"] == 1
    assert not layout.centerlines  # nada cru entrou
    assert layout.lotes  # a grelha ainda loteia


def test_arquetipo_distingue_grelha_de_sinuoso():
    """Critério 5: o mesmo esqueleto diagonal é CONSUMIDO no arquétipo sinuoso e IGNORADO na
    grelha eficiente — comportamento de viário distinto entre arquétipos."""
    esq = [[[0.1, 0.1], [0.9, 0.9]]]  # diagonal
    lay_sin = geom.gerar_layout(
        box(0.0, 0.0, 400.0, 400.0),
        programa_do_preset("alta", {"pct_lazer": 0.1, "esqueleto": esq}),  # alta = sinuoso
    )
    lay_gre = geom.gerar_layout(
        box(0.0, 0.0, 400.0, 400.0),
        programa_do_preset("baixa", {"esqueleto": esq}),  # baixa = grelha_eficiente
    )
    assert lay_sin.meta["esqueleto_usado"] is True
    assert lay_gre.meta["esqueleto_usado"] is False
    assert lay_gre.meta["arquetipo"] == "grelha_eficiente"


# --------------------------- (c) topografia ---------------------------
def test_orientacao_contorno_do_dem():
    """Critério 6: rampa p/ leste → curva de nível VERTICAL (90°); plano/sem DEM → None."""
    import numpy as np

    z_leste = np.tile(np.arange(20, dtype="float64") * 2.0, (20, 1))  # sobe p/ leste
    ang = geom.orientacao_contorno(DEMRecorte(elevacao=z_leste, px_m=30.0))
    assert ang is not None and round(math.degrees(ang) % 180, 0) == 90
    assert geom.orientacao_contorno(DEMRecorte(elevacao=np.ones((8, 8)), px_m=30.0)) is None
    assert geom.orientacao_contorno(None) is None


def test_grelha_orientada_pela_topografia():
    """Critério 6: com orientação ≠ 0, os quarteirões GIRAM para acompanhar a curva de nível."""
    ang = math.radians(30)
    layout = geom.gerar_layout(box(0.0, 0.0, 400.0, 400.0), programa_do_preset("media"), orientacao_rad=ang)
    assert layout.lotes
    def _ang(l):
        xs, ys = l.minimum_rotated_rectangle.exterior.coords.xy
        return round(math.degrees(math.atan2(ys[1] - ys[0], xs[1] - xs[0])) % 90, 0)
    # A grelha gira para 30°; lotes de borda (recortados) podem fugir — a MAIORIA segue a curva.
    em30 = sum(1 for l in layout.lotes if _ang(l) == 30)
    assert em30 >= 0.8 * len(layout.lotes)
    med = medida.medir(layout)
    fid = medida.construir_fidelidade(med, layout)
    assert fid["topografia"]["orientacao_por_declividade"] is True
    assert "terraplenagem" in fid["topografia"]["obs"]


# --------------------------- (d) fronteira §2 / determinismo ---------------------------
def test_fronteira_programa_sem_numero():
    """Critério 7: o programa (artefato da IA) não tem nº de lotes/área; o Python materializa e
    mede. Programa SEM lazer → SEM lazer materializado (não inventa default)."""
    prog = programa_do_preset("media")
    assert not hasattr(prog, "n_lotes") and not hasattr(prog, "area_vendavel_m2")
    med = medida.medir(geom.gerar_layout(box(0.0, 0.0, 500.0, 500.0), prog))
    assert med.indicadores["n_lotes"] > 0  # número computado, não fornecido

    prog0 = programa_do_preset("media", {"pct_lazer": 0.0, "pct_institucional": 0.0})
    lay0 = geom.gerar_layout(box(0.0, 0.0, 500.0, 500.0), prog0)
    assert lay0.sistema_lazer is None and lay0.areas_verdes is None


def test_determinismo_por_snapshot():
    """Critério 8: materializar+medir o mesmo programa/gleba 2× → quadro idêntico."""
    aprov = box(0.0, 0.0, 360.0, 163.0)
    prog = programa_do_preset("alta", {"pct_lazer": 0.25})
    a = medida.medir(geom.gerar_layout(aprov, prog)).quadro
    b = medida.medir(geom.gerar_layout(aprov, prog)).quadro
    assert a == b


# --------------------------- §1-A ponta a ponta + não-regressão ---------------------------
def test_1a_e_fidelidade_no_propor(client, gerador_urbanismo, fonte_urbanismo):
    """Critério 9/10: /propor traz fidelidade + §1-A; regex sem 'aprovado/viável/regular'."""
    r = client.post(
        "/api/analises",
        files={"kmz": ("g.kmz", make_kmz([RET_RETANGULO]), "application/vnd.google-earth.kmz")},
    )
    aid = r.json()["analise_id"]
    resp = client.post(f"/api/analises/{aid}/urbanismo/propor", json={"publico_alvo": "alta"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["fidelidade"] is not None
    assert "viario" in body["fidelidade"] and "topografia" in body["fidelidade"]
    texto = " ".join(body["avisos"]).lower()
    assert "verificar com urbanista" in texto
    assert not re.search(r"\b(aprovad|viáve|viave|regular)", texto)
