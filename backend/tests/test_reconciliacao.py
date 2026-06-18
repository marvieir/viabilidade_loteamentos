"""Fase 9.10 — Ponte de reconciliação (teto teórico × estudo realista). PURO TEXTO/APRESENTAÇÃO:
cada aba rotula o seu número e cita o da outra, sem mover NENHUM cálculo e sem acoplar as abas
(a referência cruzada é só exibição). Offline.
"""

import re

from shapely.geometry import box

from app.core import aproveitamento as motor
from app.core import urbanismo_geom as geom
from app.core import urbanismo_medida as medida
from app.core.urbanismo_programa import programa_do_preset

_PROMESSA = re.compile(r"cabem \d|serão \d|garantid|com certeza|aprovad|viáve|viave")


def _med_urbanismo():
    layout = geom.gerar_layout(box(0.0, 0.0, 343.0, 172.0), programa_do_preset("alta", {"pct_lazer": 0.2}))
    return medida.medir(layout)


# --------------------------- nº1: zero mudança de número ---------------------------
def test_aproveitamento_nao_recalcula_o_teto():
    """Critério 1/8: a ponte só ECOA o teto que a aba já calculou — não recomputa nem usa o nº do
    estudo em conta própria. Mudar o nº do estudo NÃO muda lotes_teto."""
    sem = motor.reconciliacao_aproveitamento(120, 360, 0.20, lotes_estudo=None)
    com = motor.reconciliacao_aproveitamento(120, 360, 0.20, lotes_estudo=51)
    assert sem["lotes_teto"] == 120 and com["lotes_teto"] == 120  # idêntico
    assert sem["lote_base_m2"] == 360 and com["doacao_base_pct"] == 0.20


def test_urbanismo_nao_recalcula_o_estudo():
    """Critério 1/8: a ponte ECOA o n_lotes medido — não o recomputa a partir do teto."""
    med = _med_urbanismo()
    n = med.indicadores["n_lotes"]
    sem = medida.reconciliacao_urbanismo(med, lotes_teto=None)
    com = medida.reconciliacao_urbanismo(med, lotes_teto=120)
    assert sem["lotes_estudo"] == n and com["lotes_estudo"] == n  # idêntico, com/sem o teto
    assert sem["lote_mediano_m2"] > 0 and 0.0 <= com["doacao_desenhada_pct"] <= 1.0


# --------------------------- nº2/3: cada card rotula e cita o outro ---------------------------
def test_aproveitamento_rotula_teto_e_cita_estudo():
    """Critério 2/7: rótulo 'teto teórico', premissa (lote 360, doação 20%), referência ao estudo
    (~51) e a RAZÃO da diferença (lote/doação maiores no desenho)."""
    r = motor.reconciliacao_aproveitamento(120, 360, 0.20, lotes_estudo=51)
    assert r["papel"] == "teto_teorico"
    assert r["ref_estudo_massa"] == {"fonte": "urbanismo", "lotes": 51}
    t = r["leitura"].lower()
    assert "teto teórico" in t and "360" in r["leitura"] and "20%" in r["leitura"]
    assert "51" in r["leitura"] and "urbanismo" in t
    assert "lote maior" in t and "doação maior" in t  # explica a razão


def test_urbanismo_rotula_estudo_e_cita_teto():
    """Critério 3/7: rótulo 'estudo geométrico', premissa (lote ~mediana, doação desenhada),
    referência ao teto regulatório (~120)."""
    med = _med_urbanismo()
    r = medida.reconciliacao_urbanismo(med, lotes_teto=120)
    assert r["papel"] == "estudo_geometrico"
    assert r["ref_teto_regulatorio"] == {"fonte": "aproveitamento", "lotes": 120}
    t = r["leitura"].lower()
    assert "estudo de massa" in t and "120" in r["leitura"]
    assert "teto regulatório" in t


# --------------------------- nº4: números interpolados (não hardcoded) ---------------------------
def test_texto_interpolado_muda_com_os_numeros():
    """Critério 4: trocar gleba/perfil muda os números do texto (premissas + ref) — não são
    hardcoded. (O nº do teto fica no campo ``lotes_teto``/headline; a leitura interpola as
    premissas e o nº do estudo.)"""
    a = motor.reconciliacao_aproveitamento(120, 360, 0.20, lotes_estudo=51)
    b = motor.reconciliacao_aproveitamento(300, 125, 0.35, lotes_estudo=90)
    assert a["lotes_teto"] == 120 and b["lotes_teto"] == 300            # campo estruturado
    assert "360" in a["leitura"] and "20%" in a["leitura"] and "51" in a["leitura"]
    assert "125" in b["leitura"] and "35%" in b["leitura"] and "90" in b["leitura"]
    assert "360" not in b["leitura"] and "51" not in b["leitura"]       # não vazou o caso A


# --------------------------- nº5: degradação honesta ---------------------------
def test_degradacao_sem_a_outra_aba():
    """Critério 5: sem a outra aba, mostra o seu número + CONVITE a rodar a outra, sem inventar."""
    ra = motor.reconciliacao_aproveitamento(120, 360, 0.20, lotes_estudo=None)
    assert ra["ref_estudo_massa"] is None
    assert "rode o estudo de massa" in ra["leitura"].lower()
    # não inventa o número do estudo (nenhum "~N lotes com lotes do perfil").
    assert "estima ~" not in ra["leitura"]

    med = _med_urbanismo()
    ru = medida.reconciliacao_urbanismo(med, lotes_teto=None)
    assert ru["ref_teto_regulatorio"] is None
    assert "rode o aproveitamento" in ru["leitura"].lower()


# --------------------------- nº6: §1-A (sem promessa) ---------------------------
def test_linguagem_1a_sem_promessa():
    """Critério 6: 'teto/estimativa/estudo/verificar' — nunca 'cabem N'/'serão N'/'garantido'."""
    med = _med_urbanismo()
    textos = [
        motor.reconciliacao_aproveitamento(120, 360, 0.20, 51)["leitura"],
        motor.reconciliacao_aproveitamento(120, 360, 0.20, None)["leitura"],
        medida.reconciliacao_urbanismo(med, lotes_teto=120)["leitura"],
        medida.reconciliacao_urbanismo(med, lotes_teto=None)["leitura"],
    ]
    for t in textos:
        assert not _PROMESSA.search(t.lower()), t
        assert "verificar" in t.lower() or "rode" in t.lower()


# --------------------------- nº8: ponta a ponta (sem acoplamento, ambas as abas) ---------------------------
def test_ponte_ponta_a_ponta(client, gerador_urbanismo, fonte_urbanismo):
    """Critério 1/3/8: o /propor expõe a ponte do estudo; o nº de lotes é MEDIDO (não vem do teto).
    A referência ao teto é só exibição (a aba não usa o teto na conta do estudo)."""
    from tests.conftest import RET_RETANGULO, make_kmz

    r = client.post(
        "/api/analises",
        files={"kmz": ("g.kmz", make_kmz([RET_RETANGULO]), "application/vnd.google-earth.kmz")},
    )
    aid = r.json()["analise_id"]
    body = client.post(f"/api/analises/{aid}/urbanismo/propor", json={"publico_alvo": "alta"}).json()
    rec = body["reconciliacao"]
    assert rec is not None and rec["papel"] == "estudo_geometrico"
    # o nº do estudo é o MEDIDO (idêntico ao indicador), não derivado do teto.
    assert rec["lotes_estudo"] == body["indicadores"]["n_lotes"]
    assert not _PROMESSA.search(rec["leitura"].lower())
