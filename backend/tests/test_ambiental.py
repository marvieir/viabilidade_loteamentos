"""Critérios de aceite das Fases 2 e 2.1 — Ambiental, offline com camadas-stub."""

from app.core.ambiental import faixa_servidao
from app.core.camadas import (
    Camadas,
    FeicaoHidrografia,
    FeicaoLinhaTransmissao,
    FeicaoMassaDagua,
    FeicaoMineracao,
    FeicaoUC,
)
from tests.conftest import (
    DATA_REF,
    LAGO_SOBREPOE,
    LT_CRUZA,
    MINA_SOBREPOE,
    RET_RETANGULO,
    RIO_CRUZA,
    UC_COBRE,
    make_kmz,
)


def _criar_analise(client) -> str:
    kmz = make_kmz([RET_RETANGULO])
    r = client.post(
        "/api/analises",
        files={"kmz": ("gleba.kmz", kmz, "application/vnd.google-earth.kmz")},
    )
    assert r.status_code == 200, r.text
    return r.json()["analise_id"]


def _ambiental(client, fonte, camadas: Camadas):
    fonte(camadas)
    aid = _criar_analise(client)
    r = client.get(f"/api/analises/{aid}/ambiental")
    assert r.status_code == 200, r.text
    return r.json()


def _do_tipo(data, tipo):
    return [a for a in data["alertas"] if a["tipo"] == tipo]


# 1 -------------------------------------------------------------------------
def test_mineracao_intersecta(client, fonte):
    data = _ambiental(
        client,
        fonte,
        Camadas(
            mineracao=[
                FeicaoMineracao(
                    MINA_SOBREPOE, processo="826.123/2020", fase="concessão de lavra"
                )
            ],
            data_mineracao=DATA_REF,
        ),
    )
    al = _do_tipo(data, "MINERACAO")
    assert al, data
    assert al[0]["intersecta"] is True
    assert "826.123/2020" in al[0]["detalhe"]
    assert "SIGMINE" in al[0]["proveniencia"]["camada"]
    assert al[0]["area_afetada_m2"] > 0
    assert "mineracao" in data["geojson_overlays"]


# 2 -------------------------------------------------------------------------
def test_unidade_conservacao_intersecta(client, fonte):
    data = _ambiental(
        client,
        fonte,
        Camadas(
            unidades_conservacao=[
                FeicaoUC(UC_COBRE, nome="APA Teste", grupo="Uso Sustentável")
            ],
            data_uc=DATA_REF,
        ),
    )
    al = _do_tipo(data, "UNIDADE_CONSERVACAO")
    assert al, data
    assert "APA Teste" in al[0]["detalhe"]
    assert "uc" in data["geojson_overlays"]


# 3 -------------------------------------------------------------------------
def test_app_largura_conhecida_30m(client, fonte):
    data = _ambiental(
        client,
        fonte,
        Camadas(
            hidrografia=[FeicaoHidrografia(RIO_CRUZA, largura_m=8.0, nome="Córrego")],
            data_hidrografia=DATA_REF,
        ),
    )
    al = _do_tipo(data, "APP_HIDROGRAFIA")
    assert al, data
    assert al[0]["largura_confirmada"] is True
    # Rio cruza a gleba (~2041 m de largura) com buffer de 30 m de cada lado (banda 60 m):
    # área ≈ 2041 × 60 ≈ 122 000 m². Validação geométrica por faixa plausível.
    area = al[0]["area_afetada_m2"]
    assert 110_000 <= area <= 135_000, area


# 4 -------------------------------------------------------------------------
def test_app_largura_desconhecida_minimo(client, fonte):
    data = _ambiental(
        client,
        fonte,
        Camadas(
            hidrografia=[FeicaoHidrografia(RIO_CRUZA, largura_m=None)],
            data_hidrografia=DATA_REF,
        ),
    )
    al = _do_tipo(data, "APP_HIDROGRAFIA")
    assert al, data
    assert al[0]["largura_confirmada"] is False
    assert any("não confirmada" in a.lower() for a in data["avisos"]), data["avisos"]
    # mínimo de 30 m → mesma banda do teste de largura conhecida pequena.
    assert 110_000 <= al[0]["area_afetada_m2"] <= 135_000


# 5 -------------------------------------------------------------------------
def test_faixa_nao_edificavel_e_app_maior(client, fonte):
    data = _ambiental(
        client,
        fonte,
        Camadas(
            hidrografia=[FeicaoHidrografia(RIO_CRUZA, largura_m=8.0)],
            data_hidrografia=DATA_REF,
        ),
    )
    faixa = _do_tipo(data, "FAIXA_NAO_EDIFICAVEL")
    app = _do_tipo(data, "APP_HIDROGRAFIA")
    assert faixa and app, data
    # APP (30 m) é o maior buffer: área da APP ≥ área da faixa não-edificável (15 m).
    assert app[0]["area_afetada_m2"] >= faixa[0]["area_afetada_m2"]
    assert "app" in data["geojson_overlays"]
    assert "faixa_nao_edificavel" in data["geojson_overlays"]


# 6 -------------------------------------------------------------------------
def test_sem_sobreposicao(client, fonte):
    data = _ambiental(
        client,
        fonte,
        Camadas(data_hidrografia=DATA_REF, data_uc=DATA_REF, data_mineracao=DATA_REF),
    )
    assert data["sem_alertas"] is True
    assert data["alertas"] == []


# 7 -------------------------------------------------------------------------
def test_proveniencia_obrigatoria(client, fonte):
    data = _ambiental(
        client,
        fonte,
        Camadas(
            hidrografia=[FeicaoHidrografia(RIO_CRUZA, largura_m=8.0)],
            unidades_conservacao=[FeicaoUC(UC_COBRE, nome="APA Teste")],
            mineracao=[FeicaoMineracao(MINA_SOBREPOE, processo="1/2020")],
            data_hidrografia=DATA_REF,
            data_uc=DATA_REF,
            data_mineracao=DATA_REF,
        ),
    )
    assert data["alertas"]
    for a in data["alertas"]:
        p = a["proveniencia"]
        assert p["camada"]
        assert p["data_referencia"] == DATA_REF
        assert "informativo" in p["ressalva"].lower()


# 8 -------------------------------------------------------------------------
def test_determinismo(client, fonte):
    camadas = Camadas(
        hidrografia=[FeicaoHidrografia(RIO_CRUZA, largura_m=8.0)],
        mineracao=[FeicaoMineracao(MINA_SOBREPOE, processo="1/2020")],
        data_hidrografia=DATA_REF,
        data_mineracao=DATA_REF,
    )
    fonte(camadas)
    aid = _criar_analise(client)
    r1 = client.get(f"/api/analises/{aid}/ambiental")
    r2 = client.get(f"/api/analises/{aid}/ambiental")
    assert r1.status_code == r2.status_code == 200
    assert r1.json() == r2.json()


# 9 -------------------------------------------------------------------------
def test_offline_sem_fonte_degrada(client):
    """Sem fonte injetada (default de produção): nada é consultado, sem rede, honesto."""
    aid = _criar_analise(client)
    r = client.get(f"/api/analises/{aid}/ambiental")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["sem_alertas"] is True
    assert data["alertas"] == []
    assert any("não consultad" in a.lower() for a in data["avisos"]), data["avisos"]


def test_ambiental_analise_inexistente_404(client):
    r = client.get("/api/analises/nao-existe/ambiental")
    assert r.status_code == 404


# ======================= Fase 2.1 — dados reais + ANEEL =======================


# 2.1-a) Faixa de servidão por tensão (NBR 5422 / ARCHITECTURE §5) -----------
def test_faixa_servidao_por_tensao():
    assert faixa_servidao(69) == 20.0     # ≤ 69 kV
    assert faixa_servidao(138) == 40.0    # 69–230 kV
    assert faixa_servidao(500) == 70.0    # > 230 kV
    assert faixa_servidao(None) == 70.0   # desconhecida → máxima (conservadora)


# 2.1-b) Critério nº2: LT cruza a gleba → FAIXA_SERVIDAO_LT + overlay --------
def test_lt_servidao_intersecta(client, fonte):
    data = _ambiental(
        client,
        fonte,
        Camadas(
            linhas_transmissao=[
                FeicaoLinhaTransmissao(LT_CRUZA, tensao_kv=230, nome="LT Teste")
            ],
            data_lt=DATA_REF,
            consultadas=["ANEEL"],
        ),
    )
    al = _do_tipo(data, "FAIXA_SERVIDAO_LT")
    assert al, data
    assert al[0]["intersecta"] is True
    assert al[0]["area_afetada_m2"] > 0
    assert "ANEEL" in al[0]["proveniencia"]["camada"]
    assert "linhas_transmissao" in data["geojson_overlays"]
    assert "ANEEL" in data["camadas_consultadas"]


def test_lt_tensao_desconhecida_aplica_maxima(client, fonte):
    base = _ambiental(
        client,
        fonte,
        Camadas(
            linhas_transmissao=[FeicaoLinhaTransmissao(LT_CRUZA, tensao_kv=230)],
            data_lt=DATA_REF,
        ),
    )
    sem_t = _ambiental(
        client,
        fonte,
        Camadas(
            linhas_transmissao=[FeicaoLinhaTransmissao(LT_CRUZA, tensao_kv=None)],
            data_lt=DATA_REF,
        ),
    )
    a230 = _do_tipo(base, "FAIXA_SERVIDAO_LT")[0]["area_afetada_m2"]
    a_none = _do_tipo(sem_t, "FAIXA_SERVIDAO_LT")[0]["area_afetada_m2"]
    assert a_none > a230  # 70 m cobre mais que 40 m
    assert any("tensão" in a.lower() for a in sem_t["avisos"]), sem_t["avisos"]


# 2.1-b2) Massa d'água (lago/represa) → APP marginal (gap do Curso_dÁgua só-linha) ---
def test_massa_dagua_app_intersecta(client, fonte):
    data = _ambiental(
        client,
        fonte,
        Camadas(
            massas_dagua=[
                FeicaoMassaDagua(LAGO_SOBREPOE, nome="Represa Teste", tipo="artificial")
            ],
            data_massa_dagua=DATA_REF,
            consultadas=["Massa d'água"],
        ),
    )
    al = _do_tipo(data, "APP_MASSA_DAGUA")
    assert al, data
    assert al[0]["intersecta"] is True
    assert al[0]["area_afetada_m2"] > 0
    assert "massa" in al[0]["proveniencia"]["camada"].lower()
    assert "app_massa_dagua" in data["geojson_overlays"]


# 2.1-c) Critério nº4: degradação por camada (consultadas vs indisponíveis) --
def test_degradacao_por_camada(client, fonte):
    data = _ambiental(
        client,
        fonte,
        Camadas(
            mineracao=[FeicaoMineracao(MINA_SOBREPOE, processo="1/2020")],
            data_mineracao=DATA_REF,
            consultadas=["SIGMINE"],
            indisponiveis=["ICMBio"],
        ),
    )
    assert "SIGMINE" in data["camadas_consultadas"]
    assert "ICMBio" in data["camadas_indisponiveis"]
    # com fonte configurada, NÃO se diz "fonte não configurada"
    assert not any("não configurada" in a.lower() for a in data["avisos"]), data["avisos"]
    # a camada consultada segue produzindo alerta
    assert _do_tipo(data, "MINERACAO"), data


# 2.1-d) "não configurada" só aparece quando NÃO há fonte (não com degradação) -
def test_nao_configurada_apenas_sem_fonte(client):
    aid = _criar_analise(client)
    data = client.get(f"/api/analises/{aid}/ambiental").json()
    assert data["camadas_consultadas"] == []
    assert any("não configurada" in a.lower() for a in data["avisos"]), data["avisos"]


# Não-regressão (Fases 1, 1.5, 1.7): verificada rodando a suíte completa.
