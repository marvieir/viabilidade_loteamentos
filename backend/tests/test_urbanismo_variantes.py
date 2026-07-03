"""Fase U4 — K variantes + otimizador (padrão Delve/Forma na nossa escala).

Valores-ouro da spec (roadmap U4 da pesquisa):
- UMA chamada de IA gera K variantes geométricas determinísticas; a FUNÇÃO DE VALOR
  (Σ área×multiplicador do score v2) escolhe a melhor (índice 100);
- materializar uma alternativa (/urbanismo/variante) NÃO chama a IA e NÃO consome o cap
  de gerações (o cap passa a contar só origem_geracao == "llm");
- determinismo: a mesma variante materializada duas vezes → mesmas medidas.
"""

import pytest

from app.core.urbanismo_programa import get_gerador_programa, programa_do_preset
from app.core.urbanismo_store import FonteUrbanismoArquivo, get_fonte_urbanismo
from app.main import app
from tests.conftest import RET_RETANGULO, make_kmz


class _GeradorStub:
    """Gerador determinístico de teste — conta as chamadas (prova o 'zero IA' da variante)."""

    def __init__(self):
        self.chamadas = 0

    def propor(self, contexto, tipo, publico, overrides=None):
        self.chamadas += 1
        return programa_do_preset(publico or "media", {"pct_lazer": 0.12})


@pytest.fixture()
def ambiente_u4(client, tmp_path):
    gerador = _GeradorStub()
    fonte = FonteUrbanismoArquivo(tmp_path)
    app.dependency_overrides[get_gerador_programa] = lambda: gerador
    app.dependency_overrides[get_fonte_urbanismo] = lambda: fonte
    r = client.post(
        "/api/analises",
        files={"kmz": ("g.kmz", make_kmz([RET_RETANGULO]), "application/vnd.google-earth.kmz")},
    )
    assert r.status_code == 200, r.text
    yield client, r.json()["analise_id"], gerador, fonte
    app.dependency_overrides.pop(get_gerador_programa, None)
    app.dependency_overrides.pop(get_fonte_urbanismo, None)


def test_propor_gera_k_variantes_e_a_funcao_de_valor_escolhe(ambiente_u4):
    client, aid, gerador, fonte = ambiente_u4
    r = client.post(f"/api/analises/{aid}/urbanismo/propor", json={"publico_alvo": "media"})
    assert r.status_code == 200, r.text
    corpo = r.json()
    vs = corpo["variantes"]
    assert len(vs) == 4  # V1..V4 com UMA chamada de IA
    assert gerador.chamadas == 1
    escolhidas = [v for v in vs if v["escolhida"]]
    assert len(escolhidas) == 1
    assert escolhidas[0]["valor_indice"] == 100.0  # a escolhida é a base do índice
    assert all(v["valor_indice"] is not None and v["valor_indice"] <= 100.0 for v in vs)
    assert "Otimizador (U4)" in " ".join(corpo["avisos"])
    # persistência guarda o programa p/ rematerializar sem IA
    salvo = fonte.listar(aid)[-1]
    assert salvo["origem_geracao"] == "llm"
    assert salvo["_programa_motor"]["publico_alvo"] == "media"


def test_variante_materializa_sem_ia_e_fora_do_cap(ambiente_u4, monkeypatch):
    client, aid, gerador, fonte = ambiente_u4
    monkeypatch.setenv("URBANISMO_MAX_GERACOES", "1")
    r = client.post(f"/api/analises/{aid}/urbanismo/propor", json={"publico_alvo": "media"})
    assert r.status_code == 200, r.text
    # cap atingido para IA…
    r2 = client.post(f"/api/analises/{aid}/urbanismo/propor", json={"publico_alvo": "media"})
    assert r2.status_code == 429
    # …mas a VARIANTE materializa sem IA e fora do cap
    rv = client.post(f"/api/analises/{aid}/urbanismo/variante", json={"variante_id": "V3"})
    assert rv.status_code == 200, rv.text
    corpo = rv.json()
    assert gerador.chamadas == 1  # NENHUMA chamada extra de IA
    assert len(corpo["variantes"]) == 1 and corpo["variantes"][0]["variante_id"] == "V3"
    assert "sem chamada de IA" in " ".join(corpo["avisos"])
    assert fonte.listar(aid)[-1]["origem_geracao"] == "variante"
    # e o cap segue bloqueando só a IA (variante salva não conta)
    r3 = client.post(f"/api/analises/{aid}/urbanismo/propor", json={"publico_alvo": "media"})
    assert r3.status_code == 429


def test_variante_deterministica(ambiente_u4):
    client, aid, _gerador, _fonte = ambiente_u4
    r = client.post(f"/api/analises/{aid}/urbanismo/propor", json={"publico_alvo": "media"})
    assert r.status_code == 200, r.text
    a = client.post(f"/api/analises/{aid}/urbanismo/variante", json={"variante_id": "V2"}).json()
    b = client.post(f"/api/analises/{aid}/urbanismo/variante", json={"variante_id": "V2"}).json()
    assert a["quadro_areas"] == b["quadro_areas"]
    assert a["indicadores"] == b["indicadores"]
    assert a["heatmap"]["score_medio"] == b["heatmap"]["score_medio"]


def test_variante_sem_base_409_e_id_invalido_404(ambiente_u4):
    client, aid, _gerador, _fonte = ambiente_u4
    r = client.post(f"/api/analises/{aid}/urbanismo/variante", json={"variante_id": "V2"})
    assert r.status_code == 409  # nenhuma proposta com programa salvo
    client.post(f"/api/analises/{aid}/urbanismo/propor", json={"publico_alvo": "media"})
    r2 = client.post(f"/api/analises/{aid}/urbanismo/variante", json={"variante_id": "V9"})
    assert r2.status_code == 404
