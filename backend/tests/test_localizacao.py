"""Fase 6 — Localização (enriquecimento IBGE): 10 critérios de aceite (spec §5).

Offline, determinístico — lê um dataset embarcado de TESTE (conftest.LOCALIZACAO_DATASET).
Valores-ouro: São Roque/SP (3550605). Sem rede, sem LLM, sem persistência.
"""

import re

import pytest

from app.core import localizacao as motor
from tests.conftest import LOCALIZACAO_DATASET, RET_RETANGULO, make_kmz


def _criar_analise(client):
    r = client.post(
        "/api/analises",
        files={"kmz": ("g.kmz", make_kmz([RET_RETANGULO]), "application/vnd.google-earth.kmz")},
    )
    assert r.status_code == 200
    return r.json()["analise_id"]


def _get_loc(client, aid):
    r = client.get(f"/api/analises/{aid}/localizacao")
    assert r.status_code == 200
    return r.json()


@pytest.fixture
def aid(client):
    return _criar_analise(client)


# ----- 1. População-ouro -----
def test_populacao_ouro_sao_roque(client, localizacao, aid):
    pop = _get_loc(client, aid)["populacao"]
    assert pop["disponivel"] is True
    assert pop["censo_2022"] == 79484
    assert pop["censo_2010"] == 78821
    assert pop["censo_2022_fmt"] == "79.484"
    assert abs(pop["crescimento_total_pct"] - 0.0084) < 0.0001
    assert abs(pop["crescimento_aa_pct"] - 0.0007) < 0.0001
    assert abs(pop["densidade_hab_km2"] - 258.98) < 0.01
    assert pop["densidade_fmt"] == "258,98 hab/km²"
    assert pop["crescimento_total_fmt"] == "0,84%"


# ----- 2. Renda-ouro + comparações como razão exata -----
def test_renda_ouro_e_comparacoes(client, localizacao, aid):
    renda = _get_loc(client, aid)["renda"]
    assert renda["pib_per_capita"] == 57024.90
    assert renda["pib_per_capita_fmt"] == "R$ 57.024,90"
    assert renda["ano"] == 2023
    reg = LOCALIZACAO_DATASET["registros"]
    esperado_uf = round(57024.90 / reg["UF:SP"]["pib_per_capita"], 6)
    esperado_br = round(57024.90 / reg["BR"]["pib_per_capita"], 6)
    assert renda["vs_uf"] == esperado_uf
    assert renda["vs_brasil"] == esperado_br


# ----- 3. Habitação: sem FJP → null + fallback rotulado; com FJP → preenchido -----
def test_habitacao_sao_roque_fallback_sem_fjp(client, localizacao, aid):
    hab = _get_loc(client, aid)["habitacao"]
    assert hab["disponivel"] is True
    assert hab["deficit"] is None  # São Roque fora do recorte FJP no fixture
    assert hab["fallback_estoque"]["domicilios_ocupados"] == 28490
    assert abs(hab["fallback_estoque"]["moradores_por_domicilio"] - 2.79) < 0.01
    assert "NÃO é o déficit" in hab["aviso"]


def test_habitacao_com_fjp_preenchido(client, localizacao, aid, malha, lista):
    # Mairinque tem déficit FJP no fixture → exercita o caminho preenchido.
    from shapely.geometry import Polygon
    from app.core.jurisdicao import Municipio

    mairinque = Municipio(cod_ibge="3528502", municipio="Mairinque", uf="SP")
    malha([(mairinque, Polygon([(-47.20, -23.60), (-47.00, -23.60), (-47.00, -23.50), (-47.20, -23.50)]))])
    lista([{"cod_ibge": "3528502", "municipio": "Mairinque", "uf": "SP"}])
    aid2 = _criar_analise(client)
    hab = _get_loc(client, aid2)["habitacao"]
    assert hab["deficit"] == {"valor": 1234, "valor_fmt": "1.234", "fonte": "FJP", "ano": 2022}
    assert hab["fallback_estoque"] is None


def test_deficit_nunca_inventado(client, localizacao, aid):
    # Critério 3: município sem FJP → null, JAMAIS um número estimado.
    hab = _get_loc(client, aid)["habitacao"]
    assert hab["deficit"] is None


# ----- 4. Faixa etária: 4 grupos, Σ=1 (ouro de 2ª geração — % não cravado na spec) -----
def test_faixa_etaria_soma_um(client, localizacao, aid):
    fe = _get_loc(client, aid)["faixa_etaria"]
    assert fe["disponivel"] is True
    assert fe["fonte"] == "IBGE Censo 2022"
    assert [g["faixa"] for g in fe["grupos"]] == ["0-14", "15-29", "30-59", "60+"]
    assert abs(sum(g["pct"] for g in fe["grupos"]) - 1.0) < 0.001


# ----- 5. Comparação calculada no backend; ausência de linha → omitida com aviso -----
def test_comparacao_omitida_sem_linha_uf(client, localizacao, aid):
    dataset = {
        "_meta": {"data_geracao": "2026-06-12"},
        "registros": {
            r: v for r, v in LOCALIZACAO_DATASET["registros"].items() if r != "UF:SP"
        },
    }
    localizacao(dataset)
    body = _get_loc(client, aid)
    assert body["renda"]["vs_uf"] is None
    assert body["populacao"]["vs_uf"] is None
    assert any("UF" in a or "estado" in a for a in body["avisos"])


# ----- 6. Offline + embarcado: o arquivo seed bate os ouros de São Roque -----
def test_arquivo_embarcado_bate_ouros():
    fonte = motor.FonteLocalizacaoArquivo(motor._ARQUIVO_DEFAULT)
    dataset = fonte.carregar()
    assert dataset is not None, "arquivo embarcado deve carregar offline"
    sr = dataset["registros"]["3550605"]
    assert sr["pop_2022"] == 79484 and sr["pop_2010"] == 78821
    assert sr["pib_per_capita"] == 57024.90
    densidade = round(sr["pop_2022"] / sr["area_km2"], 2)
    assert abs(densidade - 258.98) < 0.01
    assert abs(sr["moradores_por_domicilio"] - 2.79) < 0.01
    assert abs(sum(sr["faixa_etaria"].values()) - 1.0) < 0.001


# ----- 7. Degradação honesta: não resolvido / fora do arquivo / bloco ausente -----
def test_municipio_nao_resolvido(client_producao, localizacao):
    # client_producao = sem malha → KMZ não resolve município (cod_ibge None).
    aid = _criar_analise(client_producao)
    body = _get_loc(client_producao, aid)
    assert body["avaliada"] is False
    assert body["cobertura"] == "INDISPONIVEL"
    assert body["populacao"]["disponivel"] is False
    assert any("resolva o município" in a.lower() for a in body["avisos"])


def test_municipio_fora_do_arquivo(client, localizacao, aid):
    dataset = {"_meta": {"data_geracao": "x"}, "registros": {}}  # São Roque ausente
    localizacao(dataset)
    body = _get_loc(client, aid)
    assert body["avaliada"] is True
    assert body["cobertura"] == "INDISPONIVEL"
    assert body["populacao"]["disponivel"] is False


def test_bloco_ausente_vira_parcial(client, localizacao, aid):
    reg = {k: dict(v) for k, v in LOCALIZACAO_DATASET["registros"].items()}
    reg["3550605"] = dict(reg["3550605"])
    reg["3550605"]["pib_per_capita"] = None  # renda indisponível
    localizacao({"_meta": {"data_geracao": "x"}, "registros": reg})
    body = _get_loc(client, aid)
    assert body["cobertura"] == "PARCIAL"
    assert body["renda"]["disponivel"] is False
    assert body["populacao"]["disponivel"] is True


def test_cobertura_completa(client, localizacao, aid):
    body = _get_loc(client, aid)
    assert body["cobertura"] == "COMPLETA"
    assert body["avaliada"] is True


# ----- 8. Critério-coração: informativo puro — não altera nenhum outro número -----
def test_nao_altera_aproveitamento(client, localizacao, aid):
    antes = client.post(f"/api/analises/{aid}/aproveitamento", json={"regime": "URBANO", "lote_min_m2": 200})
    _get_loc(client, aid)  # consulta a localização
    depois = client.post(f"/api/analises/{aid}/aproveitamento", json={"regime": "URBANO", "lote_min_m2": 200})
    assert antes.json() == depois.json()


def test_nenhum_campo_lido_por_outro_router():
    # Critério-coração nº 8: nenhum router (exceto o de localização) importa o motor/campos
    # desta fase. Garante que é enriquecimento, não insumo de cálculo.
    import pathlib

    routers = pathlib.Path(__file__).resolve().parent.parent / "app" / "routers"
    for arq in routers.glob("*.py"):
        if arq.name in ("localizacao.py", "__init__.py"):
            continue
        texto = arq.read_text(encoding="utf-8")
        assert "localizacao" not in texto, f"{arq.name} não pode depender da Localização"
        assert "LocalizacaoOut" not in texto


# ----- 9. Linguagem §1-A: sem "viável"/"inviável"; aviso informativo fixo presente -----
def test_linguagem_1a(client, localizacao, aid):
    body = _get_loc(client, aid)
    blob = str(body).lower()
    assert not re.search(r"\binvi[aá]vel\b", blob)
    assert not re.search(r"\bvi[aá]vel\b", blob)
    assert any("informativo" in a.lower() for a in body["avisos"])
    assert "SOB OS DADOS CENSITÁRIOS" in body["populacao"]["leitura"]


def test_leitura_demanda_fraca(client, localizacao, aid):
    # São Roque cresceu 0,84% vs SP ~7,6% → leitura aponta demanda fraca (sinal, não veredito).
    pop = _get_loc(client, aid)["populacao"]
    assert "fraca" in pop["leitura"]


# ----- 10. Determinismo + não-regressão (a suíte inteira cobre 1…5) -----
def test_determinismo(client, localizacao, aid):
    a = _get_loc(client, aid)
    b = _get_loc(client, aid)
    assert a == b
