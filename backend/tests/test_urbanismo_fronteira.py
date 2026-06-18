"""Fase 9 — Urbanismo: a FRONTEIRA §2 (LLM propõe programa; Python gera+mede) + integração.

Cobre os critérios: 3 (recorte contra restrições), 4 (nenhum número do LLM; esqueleto inválido
ignorado), 5 (versionamento), 8 (aditivo — sem regressão), 10 (503 sem credencial).
"""

from shapely.geometry import box

from app.core import urbanismo_geom as geom
from app.core import urbanismo_medida as medida
from app.core.urbanismo_programa import Programa, programa_do_preset
from tests.conftest import RET_RETANGULO, make_kmz


def _criar_analise(client):
    r = client.post(
        "/api/analises",
        files={"kmz": ("g.kmz", make_kmz([RET_RETANGULO]), "application/vnd.google-earth.kmz")},
    )
    assert r.status_code == 200, r.text
    return r.json()["analise_id"]


# --------------------------- núcleo puro (offline) ---------------------------
def test_recorte_contra_restricoes():
    """Critério 3: nenhum lote gerado intersecta a restrição (recorte geométrico, não aviso)."""
    aprov = box(0.0, 0.0, 500.0, 500.0)
    restricao = box(0.0, 0.0, 150.0, 500.0)  # faixa vedada à esquerda
    prog = programa_do_preset("media")
    layout = geom.gerar_layout(aprov, prog, restricoes=restricao)
    assert layout.lotes, "deveria gerar lotes na área livre"
    soma_invasao = sum(l.intersection(restricao).area for l in layout.lotes)
    assert soma_invasao < 1e-6


def test_loteia_todas_as_ilhas():
    """Regressão (achado de campo): quando a restrição PARTE a gleba em duas ilhas, AMBAS são
    loteadas — versões anteriores ficavam só com a maior (metade do terreno vazia)."""
    gleba = box(0.0, 0.0, 1000.0, 300.0)
    restr = box(480.0, 0.0, 520.0, 300.0)  # faixa vedada no "pescoço" → esquerda + direita
    layout = geom.gerar_layout(gleba, programa_do_preset("alta"), restricoes=restr)
    esquerda = sum(1 for l in layout.lotes if l.centroid.x < 480)
    direita = sum(1 for l in layout.lotes if l.centroid.x > 520)
    assert esquerda > 0 and direita > 0  # nenhuma ilha foi descartada
    assert sum(l.intersection(restr).area for l in layout.lotes) < 1e-6


def test_esqueleto_invalido_ignorado_nao_propaga():
    """Critério 4: polilinha auto-intersectada do LLM é IGNORADA e registrada; a geometria CRUA do
    LLM não propaga. Fase 9.9: em arquétipo curvo, o esqueleto inválido vira FALLBACK de curva
    explícito (não grade silenciosa) — mas a curva é do Python (suave/simples), não a crua."""
    aprov = box(0.0, 0.0, 400.0, 400.0)
    bowtie = [[0.0, 0.0], [400.0, 400.0], [0.0, 400.0], [400.0, 0.0]]  # auto-intersecta
    prog = programa_do_preset("media", {"esqueleto": [bowtie]})
    layout = geom.gerar_layout(aprov, prog)
    assert layout.ignorados, "esqueleto inválido deveria ser registrado"
    assert "esqueleto[0]" in layout.ignorados[0]
    assert all(c.is_simple for c in layout.centerlines)  # nada CRU (auto-intersectado) entrou
    assert layout.viario_diagnostico["esqueleto_origem"] == "fallback_curva"
    assert layout.lotes  # o Python ainda produz lotes


def test_programa_nao_carrega_numero_de_medida():
    """Critério 4: o artefato da borda (Programa) não tem nº de lotes/área vendável — esses
    EMERGEM da medição do Python."""
    prog = programa_do_preset("alta")
    assert not hasattr(prog, "n_lotes")
    assert not hasattr(prog, "area_vendavel_m2")
    layout = geom.gerar_layout(box(0.0, 0.0, 600.0, 600.0), prog)
    med = medida.medir(layout)
    assert med.indicadores["n_lotes"] > 0  # número computado, não fornecido


# --------------------------- endpoint /propor (stub na borda) ---------------------------
def test_propor_mede_a_partir_do_programa(client, gerador_urbanismo, fonte_urbanismo):
    """Critério 4 (ponta a ponta): stub devolve PROGRAMA; a resposta traz números MEDIDOS."""
    aid = _criar_analise(client)
    r = client.post(
        f"/api/analises/{aid}/urbanismo/propor",
        json={"tipo_loteamento": "fechado", "publico_alvo": "alta"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["programa"]["origem"] == "proposto_llm"
    assert body["indicadores"]["n_lotes"] > 0
    assert body["quadro_areas"]["vendavel"]["m2"] > 0
    assert body["rotulo"] == "ESTUDO DE MASSA ESQUEMÁTICO"
    assert len(body["avisos"]) >= 3


def test_propor_versiona_snapshots(client, gerador_urbanismo, fonte_urbanismo):
    """Critério 5: regerar cria nova versão (não sobrescreve); GET lista/uma."""
    aid = _criar_analise(client)
    p1 = client.post(f"/api/analises/{aid}/urbanismo/propor", json={"publico_alvo": "media"}).json()
    p2 = client.post(f"/api/analises/{aid}/urbanismo/propor", json={"publico_alvo": "baixa"}).json()
    assert p1["versao"] == 1 and p2["versao"] == 2
    assert p1["proposta_id"] != p2["proposta_id"]

    lista = client.get(f"/api/analises/{aid}/urbanismo").json()
    assert len(lista) == 2
    um = client.get(f"/api/analises/{aid}/urbanismo/{p1['proposta_id']}")
    assert um.status_code == 200
    assert um.json()["proposta_id"] == p1["proposta_id"]


def test_propor_sem_credencial_503(client, gerador_urbanismo_indisponivel, fonte_urbanismo):
    """Critério 10: sem credencial de IA → 503 honesto (não inventa traçado)."""
    aid = _criar_analise(client)
    r = client.post(f"/api/analises/{aid}/urbanismo/propor", json={"publico_alvo": "media"})
    assert r.status_code == 503


def test_aditivo_nao_regride_aproveitamento(client, gerador_urbanismo, fonte_urbanismo):
    """Critério 8: a Fase 9 é aditiva — o CÁLCULO do aproveitamento é idêntico com/sem o urbanismo.

    Fase 9.10: a ÚNICA diferença permitida é a ponte de reconciliação (texto/ref cruzada) — que
    passa a citar o estudo de massa quando ele existe. Os NÚMEROS não se movem (n_lotes_teto,
    área, cenário); só a leitura/ref da ponte ganha o número do estudo (apresentação)."""
    aid = _criar_analise(client)
    payload = {"regime": "URBANO", "modalidade": "loteamento_aberto", "lote_min_m2": 250}
    antes = client.post(f"/api/analises/{aid}/aproveitamento", json=payload).json()
    client.post(f"/api/analises/{aid}/urbanismo/propor", json={"publico_alvo": "alta"})
    depois = client.post(f"/api/analises/{aid}/aproveitamento", json=payload).json()
    # tudo idêntico EXCETO a ponte (que agora cita o estudo de massa — é o objetivo da 9.10).
    assert {k: v for k, v in antes.items() if k != "reconciliacao"} == \
           {k: v for k, v in depois.items() if k != "reconciliacao"}
    # os NÚMEROS da ponte não mudam; só a referência cruzada + leitura ganham o estudo.
    assert antes["reconciliacao"]["lotes_teto"] == depois["reconciliacao"]["lotes_teto"]
    assert antes["reconciliacao"]["ref_estudo_massa"] is None
    assert depois["reconciliacao"]["ref_estudo_massa"]["fonte"] == "urbanismo"
    assert depois["reconciliacao"]["ref_estudo_massa"]["lotes"] > 0
