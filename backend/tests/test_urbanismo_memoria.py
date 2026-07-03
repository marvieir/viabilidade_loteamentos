"""Fase U5 — Memória do motor: rating do operador → few-shot no gerador.

Valores-ouro:
- só rating ≥4 do MESMO público vira referência; mesmo município tem prioridade;
- a ÚLTIMA avaliação de uma proposta prevalece (re-avaliar corrige a nota);
- o prompt do gerador ganha a seção de REFERÊNCIA quando há memória (e só então);
- /avaliar persiste com resumo do PROGRAMA (estratégia, nunca medida — §2);
- rating fora de 1..5 → 422; versão inexistente → 404. Determinístico e auditável.
"""

import pytest

from app.core import urbanismo_programa as programa_mod
from app.core.urbanismo_memoria import (
    FonteMemoriaArquivo,
    get_fonte_memoria_urbanismo,
)
from app.core.urbanismo_programa import get_gerador_programa, programa_do_preset
from app.core.urbanismo_store import FonteUrbanismoArquivo, get_fonte_urbanismo
from app.main import app
from tests.conftest import RET_RETANGULO, make_kmz


def _reg(pid, rating, publico="media", municipio="São Roque", data="2026-07-01", **extra):
    return {
        "analise_id": "a1", "versao": 1, "proposta_id": pid, "rating": rating,
        "municipio": municipio, "publico_alvo": publico, "data": data,
        "programa_resumo": {"lote_alvo_m2": 450.0, "arquetipo_viario": "sinuoso",
                            "amenidades": ["piscina"], "pct_lazer": 0.12},
        **extra,
    }


# ----------------------------- store (puro) -----------------------------
def test_melhores_filtra_rating_publico_e_prioriza_municipio(tmp_path):
    fonte = FonteMemoriaArquivo(tmp_path)
    fonte.avaliar(_reg("p1", 5))                                  # entra (local, 5★)
    fonte.avaliar(_reg("p2", 3))                                  # fora (rating < 4)
    fonte.avaliar(_reg("p3", 4, publico="alta"))                  # fora (outro público)
    fonte.avaliar(_reg("p4", 4, municipio="Sorocaba"))            # entra só sem local
    top = fonte.melhores("São Roque", "media")
    assert len(top) == 1 and top[0]["rating"] == 5                # só o local
    top_sem_local = fonte.melhores("Cidade Sem Memória", "media")
    assert {t["rating"] for t in top_sem_local} == {5, 4}         # cai p/ regional


def test_reavaliacao_corrige_a_nota(tmp_path):
    fonte = FonteMemoriaArquivo(tmp_path)
    fonte.avaliar(_reg("p1", 5, data="2026-07-01"))
    fonte.avaliar(_reg("p1", 2, data="2026-07-02"))  # operador rebaixou → sai da referência
    assert fonte.melhores("São Roque", "media") == []


def test_prompt_ganha_referencia_so_com_memoria():
    ctx = {"area_aproveitavel_m2": 100000.0, "municipio": "São Roque"}
    sem = programa_mod._prompt_usuario(ctx, "aberto", "media")
    assert "REFERÊNCIA" not in sem
    com = programa_mod._prompt_usuario(
        {**ctx, "programas_bem_avaliados": [{"lote_alvo_m2": 450.0, "rating": 5}]},
        "aberto", "media",
    )
    assert "REFERÊNCIA" in com and "450.0" in com
    assert "programas_bem_avaliados" not in com.split("REFERÊNCIA")[0]  # sem duplicar no ctx


# ----------------------------- endpoint (integração) -----------------------------
class _GeradorEspiao:
    def __init__(self):
        self.contextos: list[dict] = []

    def propor(self, contexto, tipo, publico, overrides=None):
        self.contextos.append(dict(contexto))
        return programa_do_preset(publico or "media", {"pct_lazer": 0.12})


@pytest.fixture()
def ambiente_u5(client, tmp_path):
    gerador = _GeradorEspiao()
    fonte_urb = FonteUrbanismoArquivo(tmp_path / "urb")
    fonte_mem = FonteMemoriaArquivo(tmp_path / "mem")
    app.dependency_overrides[get_gerador_programa] = lambda: gerador
    app.dependency_overrides[get_fonte_urbanismo] = lambda: fonte_urb
    app.dependency_overrides[get_fonte_memoria_urbanismo] = lambda: fonte_mem
    r = client.post(
        "/api/analises",
        files={"kmz": ("g.kmz", make_kmz([RET_RETANGULO]), "application/vnd.google-earth.kmz")},
    )
    assert r.status_code == 200, r.text
    yield client, r.json()["analise_id"], gerador
    for dep in (get_gerador_programa, get_fonte_urbanismo, get_fonte_memoria_urbanismo):
        app.dependency_overrides.pop(dep, None)


def test_avaliar_persiste_e_vira_fewshot_na_proxima_geracao(ambiente_u5):
    client, aid, gerador = ambiente_u5
    r1 = client.post(f"/api/analises/{aid}/urbanismo/propor", json={"publico_alvo": "media"})
    assert r1.status_code == 200, r1.text
    assert "programas_bem_avaliados" not in gerador.contextos[0]  # sem memória ainda

    ra = client.post(
        f"/api/analises/{aid}/urbanismo/avaliar", json={"versao": 1, "rating": 5}
    )
    assert ra.status_code == 200, ra.text
    assert ra.json()["rating"] == 5
    lista = client.get(f"/api/analises/{aid}/urbanismo-avaliacoes").json()
    assert len(lista) == 1 and lista[0]["programa_resumo"]["lote_alvo_m2"] is not None

    r2 = client.post(f"/api/analises/{aid}/urbanismo/propor", json={"publico_alvo": "media"})
    assert r2.status_code == 200, r2.text
    assert "programas_bem_avaliados" in gerador.contextos[1]  # memória entrou no contexto
    assert any("Memória (U5)" in a for a in r2.json()["avisos"])


def test_avaliar_validacoes(ambiente_u5):
    client, aid, _g = ambiente_u5
    r = client.post(f"/api/analises/{aid}/urbanismo/avaliar", json={"versao": 9, "rating": 5})
    assert r.status_code == 404  # versão inexistente
    client.post(f"/api/analises/{aid}/urbanismo/propor", json={"publico_alvo": "media"})
    r2 = client.post(f"/api/analises/{aid}/urbanismo/avaliar", json={"versao": 1, "rating": 6})
    assert r2.status_code == 422  # rating fora de 1..5 (contrato Pydantic)
