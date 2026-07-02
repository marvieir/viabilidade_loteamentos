"""Fase U1 — Score de valor v2 + função de valor posicional.

Valores-ouro da spec (docs/pesquisa-motor-urbanismo.md §1–§3, roadmap U1):
- fatores 0–1 rotulados por lote (verde/água/lazer/bolsão/privacidade/orientação/sossego);
- fator sem camada no layout fica AUSENTE (fora da média), nunca zero em silêncio;
- pesos por perfil (baixa/media/alta) e amplitude do multiplicador crescem com a renda;
- multiplicador posicional com média 1,0 → o VGV é REDISTRIBUÍDO, não inflado;
- /urbanismo/valor: preço do operador × multiplicador (sem LLM, sem cap, sem inventar R$).
"""

import math

from shapely.geometry import LineString, Point, box

from app.core import urbanismo_medida as medida
from app.core.urbanismo_store import FonteUrbanismoArquivo, get_fonte_urbanismo
from app.main import app
from tests.conftest import RET_RETANGULO, make_kmz


def _criar_analise(client):
    r = client.post(
        "/api/analises",
        files={"kmz": ("g.kmz", make_kmz([RET_RETANGULO]), "application/vnd.google-earth.kmz")},
    )
    assert r.status_code == 200, r.text
    return r.json()["analise_id"]


# ----------------------------- fatores individuais -----------------------------
def test_fator_verde_anel_274m():
    """Contato com o verde = 1,0; decai no anel de valorização (274 m); fora do anel = 0."""
    verde = box(0.0, 100.0, 300.0, 130.0)
    perto = box(0.0, 60.0, 15.0, 92.0)     # fundo a 8 m do verde → contato
    meio = box(0.0, -40.0, 15.0, -10.0)    # ~110 m do verde → dentro do anel
    longe = box(0.0, -300.0, 15.0, -270.0)  # ~370 m → fora do anel
    h = medida.pontuar([perto, meio, longe], verde)
    f = [p["fatores"]["verde"] for p in h["por_lote"]]
    assert f[0] == 1.0
    assert 0.0 < f[1] < 1.0
    assert f[2] == 0.0
    assert h["por_lote"][0]["score"] > h["por_lote"][2]["score"]


def test_fator_sossego_ancora_no_portico():
    """Com pórtico, o sossego cresce com a DISTÂNCIA da entrada (lote colado à entrada = 0)."""
    lotes = [box(i * 40.0, 0.0, i * 40.0 + 15.0, 30.0) for i in range(5)]
    portico = Point(7.5, 15.0).buffer(6.0)  # entrada sobre o 1º lote
    h = medida.pontuar(lotes, None, portico=portico)
    sossego = [p["fatores"]["sossego"] for p in h["por_lote"]]
    assert sossego == sorted(sossego)  # cresce ao afastar da entrada
    assert sossego[0] < 0.1
    assert sossego[-1] == 1.0


def test_fator_orientacao_ns():
    """Eixo de profundidade N-S = 1,0; a 45° ≈ 0,707; L-O = 0 (insolação de quintal)."""
    ns = box(0.0, 0.0, 12.0, 30.0)   # profundidade ao longo de y (N-S)
    lo = box(0.0, 0.0, 30.0, 12.0)   # profundidade ao longo de x (L-O)
    from shapely import affinity

    diag = affinity.rotate(ns, 45.0, origin="centroid")
    h = medida.pontuar([ns, lo, diag])
    f = [p["fatores"]["orientacao"] for p in h["por_lote"]]
    assert f[0] == 1.0
    assert f[1] == 0.0
    assert abs(f[2] - math.cos(math.radians(45.0))) < 0.01


def test_fator_privacidade_esquina_menor_que_frente_unica():
    """Fundo p/ verde = 1,0; esquina (2 frentes de via) < frente única (exposição)."""
    arruamento = box(0.0, -12.0, 100.0, 0.0).union(box(-12.0, -12.0, 0.0, 50.0))
    esquina = box(0.0, 0.0, 15.0, 30.0)        # via ao sul E a oeste
    frente_unica = box(30.0, 0.0, 45.0, 30.0)  # via só ao sul
    verde = box(200.0, 0.0, 230.0, 30.0)
    fundo_verde = box(190.0, 0.0, 199.0, 30.0)  # borda a 1 m do verde → contato
    h = medida.pontuar([esquina, frente_unica, fundo_verde], verde, arruamento)
    f = [p["fatores"]["privacidade"] for p in h["por_lote"]]
    assert f[2] == 1.0                 # fundo protegido pela mata/verde
    assert f[0] < f[1] < f[2]          # esquina < frente única < fundo p/ verde


def test_fator_culdesac_no_bolsao():
    """Lote a ≤30 m do fim de via sem saída pontua 1,0; junção em T e fim de malha na divisa
    NÃO contam como bolsão."""
    anel = [
        LineString([(0, 0), (200, 0)]), LineString([(200, 0), (200, 120)]),
        LineString([(200, 120), (0, 120)]), LineString([(0, 120), (0, 0)]),
    ]
    stub = LineString([(100, 0), (100, 60)])  # via sem saída p/ dentro do anel
    borda = box(-10.0, -10.0, 210.0, 130.0).boundary
    no_bolsao = box(92.0, 62.0, 108.0, 80.0)   # ~2 m do fim do stub
    longe = box(10.0, 40.0, 26.0, 58.0)        # a >30 m do fim
    h = medida.pontuar([no_bolsao, longe], None, eixos=[*anel, stub], borda_externa=borda)
    f = [p["fatores"]["culdesac"] for p in h["por_lote"]]
    assert f[0] == 1.0
    assert f[1] == 0.0


def test_fatores_ausentes_rotulados_nao_zerados():
    """Sem água/lazer/eixos no layout → fatores AUSENTES rotulados; score usa só os presentes."""
    lotes = [box(0.0, 0.0, 12.0, 30.0), box(20.0, 0.0, 32.0, 30.0)]
    h = medida.pontuar(lotes)  # nem verde, nem via, nem lazer, nem água, nem eixos
    assert set(h["fatores_ausentes"]) == {"verde", "agua", "lazer", "culdesac", "privacidade"}
    for p in h["por_lote"]:
        assert set(p["fatores"].keys()) == {"orientacao", "sossego"}
    # pesos expostos só dos fatores presentes (transparência do denominador)
    assert set(h["pesos"].keys()) == {"orientacao", "sossego"}


# ----------------------------- multiplicador e perfil -----------------------------
def _layout_variado():
    lotes = [box(i * 20.0, 0.0, i * 20.0 + 14.0, 30.0) for i in range(10)]
    verde = box(0.0, 45.0, 60.0, 90.0)  # só os primeiros lotes no anel de contato
    portico = Point(0.0, -5.0).buffer(6.0)
    return lotes, verde, portico


def test_multiplicador_media_1():
    """Média dos multiplicadores = 1,0 (±0,001): posição REDISTRIBUI o VGV, não infla."""
    lotes, verde, portico = _layout_variado()
    for perfil in ("baixa", "media", "alta"):
        h = medida.pontuar(lotes, verde, portico=portico, publico_alvo=perfil)
        mults = [p["multiplicador"] for p in h["por_lote"]]
        assert abs(sum(mults) / len(mults) - 1.0) < 1e-3, perfil
        assert h["amplitude"] == medida.AMPLITUDE_PERFIL[perfil]


def test_dispersao_cresce_com_a_renda():
    """Amplitude posicional (max−min do multiplicador) cresce baixa < alta (pesquisa §1)."""
    lotes, verde, portico = _layout_variado()
    spread = {}
    for perfil in ("baixa", "alta"):
        h = medida.pontuar(lotes, verde, portico=portico, publico_alvo=perfil)
        mults = [p["multiplicador"] for p in h["por_lote"]]
        spread[perfil] = max(mults) - min(mults)
    assert spread["baixa"] < spread["alta"]


def test_quintil_relativo_cobre_o_espectro():
    """O MAPA pinta por quintil RELATIVO (1..5): num layout variado os extremos existem
    sempre (o melhor lote é quintil 5 / o pior é 1), mesmo com scores absolutos ~5–8.
    Sem variação de score → todos no quintil 3 (não finge ranking)."""
    lotes, verde, portico = _layout_variado()
    h = medida.pontuar(lotes, verde, portico=portico)
    quintis = [p["quintil_valor"] for p in h["por_lote"]]
    assert min(quintis) == 1 and max(quintis) == 5
    melhor = max(h["por_lote"], key=lambda p: p["score"])
    pior = min(h["por_lote"], key=lambda p: p["score"])
    assert melhor["quintil_valor"] == 5 and pior["quintil_valor"] == 1
    # sem variação de score (1 lote) → quintil neutro 3, não finge ranking
    h1 = medida.pontuar([box(0.0, 0.0, 14.0, 30.0)])
    assert h1["por_lote"][0]["quintil_valor"] == 3


def test_score_v2_deterministico_e_desacoplado_do_tamanho():
    """Mesma entrada → mesmo heatmap; lote GRANDE mal-posicionado não ganha do pequeno
    bem-posicionado (o tamanho não entra no score — Fase 9.3 §3)."""
    verde = box(0.0, 45.0, 30.0, 90.0)
    pequeno_perto = box(0.0, 30.0, 12.0, 44.0)     # colado no verde
    grande_longe = box(150.0, -200.0, 200.0, -150.0)  # 4× maior, longe de tudo
    a = medida.pontuar([pequeno_perto, grande_longe], verde)
    b = medida.pontuar([pequeno_perto, grande_longe], verde)
    assert a == b
    assert a["por_lote"][0]["score"] > a["por_lote"][1]["score"]


# ----------------------------- /urbanismo/valor (endpoint) -----------------------------
def _proposta_fake(versao=1, com_multiplicador=True):
    por_lote = [
        {"lote_id": "L001", "score": 8.0, "area_m2": 300.0,
         **({"multiplicador": 1.06} if com_multiplicador else {})},
        {"lote_id": "L002", "score": 5.0, "area_m2": 300.0,
         **({"multiplicador": 1.00} if com_multiplicador else {})},
        {"lote_id": "L003", "score": 2.0, "area_m2": 400.0,
         **({"multiplicador": 0.94} if com_multiplicador else {})},
    ]
    return {
        "proposta_id": f"u_teste_{versao:03d}", "versao": versao,
        "heatmap": {"score_medio": 5.0, "faixas": [], "por_lote": por_lote,
                    "perfil": "media", "versao_score": 2},
    }


def test_valor_posicional_conserva_vgv(client, tmp_path):
    """Base por lote: VGV = n × preço médio (média do multiplicador = 1,0) — ouro da U1."""
    aid = _criar_analise(client)
    fonte = FonteUrbanismoArquivo(tmp_path)
    fonte.salvar(aid, _proposta_fake())
    app.dependency_overrides[get_fonte_urbanismo] = lambda: fonte
    try:
        r = client.post(
            f"/api/analises/{aid}/urbanismo/valor", json={"preco_lote_medio": 100000.0}
        )
        assert r.status_code == 200, r.text
        v = r.json()
        assert v["n_lotes"] == 3
        assert abs(v["vgv"] - 300000.0) < 1.0          # 3 × 100k (média 1,0 conserva)
        assert v["lote_max"]["lote_id"] == "L001"
        assert abs(v["lote_max"]["preco"] - 106000.0) < 0.01
        assert v["lote_min"]["lote_id"] == "L003"
        assert v["preco_medio_fmt"].startswith("R$")
        assert "não infla" in " ".join(v["avisos"])
    finally:
        app.dependency_overrides.pop(get_fonte_urbanismo, None)


def test_valor_posicional_por_m2_usa_area(client, tmp_path):
    """Base por m²: preço do lote = R$/m² × área × multiplicador (posição E tamanho)."""
    aid = _criar_analise(client)
    fonte = FonteUrbanismoArquivo(tmp_path)
    fonte.salvar(aid, _proposta_fake())
    app.dependency_overrides[get_fonte_urbanismo] = lambda: fonte
    try:
        r = client.post(f"/api/analises/{aid}/urbanismo/valor", json={"preco_m2_medio": 350.0})
        assert r.status_code == 200, r.text
        v = r.json()
        # L001: 350 × 300 × 1,06 = 111.300
        l1 = next(p for p in v["por_lote"] if p["lote_id"] == "L001")
        assert abs(l1["preco"] - 111300.0) < 0.01
        assert v["base"] == "por_m2"
    finally:
        app.dependency_overrides.pop(get_fonte_urbanismo, None)


def test_valor_exige_exatamente_um_preco(client, tmp_path):
    aid = _criar_analise(client)
    fonte = FonteUrbanismoArquivo(tmp_path)
    fonte.salvar(aid, _proposta_fake())
    app.dependency_overrides[get_fonte_urbanismo] = lambda: fonte
    try:
        r = client.post(f"/api/analises/{aid}/urbanismo/valor", json={})
        assert r.status_code == 422
        r = client.post(
            f"/api/analises/{aid}/urbanismo/valor",
            json={"preco_lote_medio": 100000.0, "preco_m2_medio": 350.0},
        )
        assert r.status_code == 422
    finally:
        app.dependency_overrides.pop(get_fonte_urbanismo, None)


def test_valor_proposta_pre_u1_recusa_honesta(client, tmp_path):
    """Proposta salva ANTES da U1 (sem multiplicador) → 409 com instrução, nunca inventa."""
    aid = _criar_analise(client)
    fonte = FonteUrbanismoArquivo(tmp_path)
    fonte.salvar(aid, _proposta_fake(com_multiplicador=False))
    app.dependency_overrides[get_fonte_urbanismo] = lambda: fonte
    try:
        r = client.post(
            f"/api/analises/{aid}/urbanismo/valor", json={"preco_lote_medio": 100000.0}
        )
        assert r.status_code == 409
        assert "regenere" in r.json()["detail"].lower()
    finally:
        app.dependency_overrides.pop(get_fonte_urbanismo, None)


def test_valor_sem_proposta_404(client, tmp_path):
    aid = _criar_analise(client)
    app.dependency_overrides[get_fonte_urbanismo] = lambda: FonteUrbanismoArquivo(tmp_path)
    try:
        r = client.post(
            f"/api/analises/{aid}/urbanismo/valor", json={"preco_lote_medio": 100000.0}
        )
        assert r.status_code == 404
    finally:
        app.dependency_overrides.pop(get_fonte_urbanismo, None)
