"""Fase 9.4 — Urbanismo: diretrizes municipais + CLAMP legal (substitui os testes de tamanho
da 9.3). Ancorado em FONTE: piso federal 125 m² (Lei 6.766), lote legal da zona (LUOS/1.8),
boas práticas de mercado. Calibrado no São Roque real + zona MUE. Os lotes de 50 e 850 da
tela ficam IMPOSSÍVEIS por construção (clamp). Fronteira do §2 intacta.
"""

import re

from shapely.geometry import Polygon, box

from app.core import urbanismo_geom as geom
from app.core import urbanismo_medida as medida
from app.core.urbanismo_diretrizes import PISO_FEDERAL_M2, resolver_diretrizes
from app.models.schemas import (
    DoacaoSplit,
    ParamProv,
    PerfilMunicipal,
    ZonaParams,
    ZonaPerfil,
)
from tests.conftest import RET_RETANGULO, make_kmz

SAO_ROQUE = box(0.0, 0.0, 343.0, 172.0)  # área aproveitável ~59 mil m²


def _perfil_mue():
    """LUOS confirmada de São Roque, zona MUE: lote 360 m², doação 20%, split 10/6/4."""
    return PerfilMunicipal(
        cod_ibge="3550605", municipio="São Roque", uf="SP", status="confirmado",
        zonas=[ZonaPerfil(codigo="MUE", params=ZonaParams(
            lote_min_m2=ParamProv(valor=360, artigo="Art.X", pagina=1, trecho="t", origem="editado_humano"),
            doacao_pct=ParamProv(valor=0.20, base="total", artigo="Art.Y", pagina=1, trecho="t", origem="editado_humano"),
            doacao_split=DoacaoSplit(viario=0.10, verde=0.06, institucional=0.04)))],
        validado_por="teste", data_referencia="2026-06-16")


def _dist(aprov, publico="alta", perfil=None, zona=None, overrides=None, estilo=None):
    from app.core.urbanismo_programa import programa_do_preset
    prog = programa_do_preset(publico, {"pct_lazer": 0.2, **(overrides or {})})
    dd = resolver_diretrizes(perfil, zona, None, publico)
    layout = geom.gerar_layout(aprov, prog, diretrizes=dd, estilo=estilo)
    med = medida.medir(layout)
    return layout, medida.distribuicao_tamanhos(med, layout), med, dd


# --------------------------- clamp legal (o coração da 9.4) ---------------------------
def test_clamp_legal_inviolavel():
    """Critério 1: nenhum lote fora de [piso, teto]; fora_da_faixa == 0 (os 50 e 850 da tela
    são impossíveis). Com MUE (360) → min ≥ 360; com teto alto 640 → max ≤ 640."""
    _, d, _, dd = _dist(SAO_ROQUE, "alta", _perfil_mue(), "MUE")
    assert d["fora_da_faixa"] == 0
    assert d["min_m2"] >= dd["piso_lote_efetivo_m2"] - 0.5
    assert d["max_m2"] <= dd["teto_lote_m2"] + 0.5
    assert d["min_m2"] >= 360 - 0.5  # piso da zona MUE respeitado


def test_diretriz_municipio_e_piso():
    """Critério 2/6: a zona é piso (MUE 360); o mercado é só referência subordinado. Sem LUOS →
    piso federal/mercado + cobertura BASE_FEDERAL."""
    dd = resolver_diretrizes(_perfil_mue(), "MUE", None, "alta")
    assert dd["piso_lote_efetivo_m2"] == 360.0  # zona, não o mercado (450)
    assert dd["cobertura"] == "COMPLETA"
    df = resolver_diretrizes(None, None, None, "alta")
    assert df["cobertura"] == "BASE_FEDERAL"
    assert df["piso_lote_efetivo_m2"] >= PISO_FEDERAL_M2


def test_clamp_federal_125():
    """Critério 1: mesmo no perfil baixo, nenhum lote < 125 m² (piso federal Lei 6.766)."""
    _, d, _, dd = _dist(box(0.0, 0.0, 200.0, 120.0), "baixa")
    assert dd["piso_lote_efetivo_m2"] >= 125.0
    assert d["fora_da_faixa"] == 0
    assert d["min_m2"] >= 125.0 - 0.5


def test_remate_ponta_sem_absurdo():
    """Critério 3: numa quadra trapezoidal (ponta estreita), nenhuma fatia < piso nem > teto —
    funde/subdivide; nada de lote de 50 ou de 850."""
    quadra = Polygon([(0, 0), (300, 0), (300, 60), (0, 18)])  # ponta esquerda rasa
    lotes, _ = geom._subdividir_quadra(quadra, 0.0, 60.0, 15.0, 465.0, 360.0, 640.0)
    assert lotes
    for l in lotes:
        assert 360.0 - 0.5 <= l.area <= 640.0 + 0.5  # todos na faixa legal


def test_reserva_e_conformidade():
    """Critério 4: verde/institucional reservados conforme o split da 1.8 ANTES de lotear; a
    conformidade mede cada item × exigência (atende/não atende)."""
    layout, _, med, dd = _dist(SAO_ROQUE, "alta", _perfil_mue(), "MUE")
    conf = medida.conformidade_legal(med, layout, dd)
    itens = {c["item"]: c for c in conf}
    assert set(itens) == {"lote_minimo", "doacao", "area_verde", "institucional"}
    assert itens["lote_minimo"]["status"] in ("atende", "atende_com_folga")
    assert itens["doacao"]["status"] in ("atende", "atende_com_folga")
    assert itens["area_verde"]["medido"] >= (dd["doacao_split"]["verde"] - 1e-6)


def _perfil_mue_com_normas():
    """MUE + normas urbanísticas do condomínio (São Roque LC 106/2020) p/ conformidade citar TODOS
    os requisitos coletados do LUOS — incl. a testada mínima em via pública (Art. 11 §1)."""
    from app.models.schemas import NormasUrbanisticas, ParamBoolProv

    perfil = _perfil_mue()
    perfil.normas_urbanisticas = NormasUrbanisticas(
        via_local_sem_estac_m=ParamProv(valor=6.0, artigo="Art. 11, I", pagina=6, trecho="6 m"),
        via_local_estac_1lado_m=ParamProv(valor=9.0, artigo="Art. 11, II", pagina=6, trecho="9 m"),
        area_comum_m2_por_unidade=ParamProv(valor=6.0, artigo="Art. 11, V", pagina=6, trecho="6 m²/un"),
        testada_min_via_publica_m=ParamProv(valor=20.0, artigo="Art. 11, § 1°", pagina=6, trecho="20 m"),
        cul_de_sac_obrigatorio=ParamBoolProv(valor=True, artigo="Art. 11, IX", pagina=6, trecho="cul de sac"),
    )
    return perfil


def test_conformidade_inclui_todos_requisitos_luos():
    """Guardrail do operador: a conformidade SEMPRE inclui TODOS os requisitos coletados do LUOS.
    Regressão do achado: a testada mínima em via pública (Art. 11 §1) estava sendo COLETADA mas não
    aparecia na conformidade — agora aparece, medida e com o artigo citado. Cul-de-sac, área comum e
    largura de via também presentes."""
    layout, _, med, dd = _dist(SAO_ROQUE, "alta", _perfil_mue_com_normas(), "MUE")
    itens = {c["item"]: c for c in medida.conformidade_legal(med, layout, dd)}
    # cada requisito coletado do LUOS tem uma linha na conformidade
    for req in ("testada_min_via_publica", "cul_de_sac", "area_comum_por_unidade", "largura_via_local"):
        assert req in itens, f"requisito do LUOS ausente na conformidade: {req}"
    # a testada é MEDIDA e cita o artigo da diretriz (não some em silêncio)
    tst = itens["testada_min_via_publica"]
    assert tst["exigido"] == 20.0 and tst["medido"] is not None
    assert "§ 1" in tst["leitura"] and tst["status"] in ("atende", "atende_com_folga", "nao_atende")
    # cul-de-sac citado com o artigo (Art. 11 IX) — atendido por construção pelo motor
    assert "11" in itens["cul_de_sac"]["leitura"] and itens["cul_de_sac"]["status"] == "atende"


def test_sobra_de_ponta_vai_para_area_verde():
    """Regressão (achado de campo): a sobra de ponta (quadra − lotes) é DEVOLVIDA à área verde,
    nunca contabilizada como retalho perdido nem inflada no viário (§4 da spec). retalho≈0,
    soma das classes = 100%, e a fidelidade do lazer usa a RESERVA (não a sobra)."""
    layout, d, med, _ = _dist(SAO_ROQUE, "alta", _perfil_mue(), "MUE")
    q = med.quadro
    assert d["retalho_perdido_pct"] <= 0.005  # praticamente zero — a sobra foi destinada
    soma = (q["vendavel"]["pct_apo"] + q["areas_verdes"]["pct_apo"] + q["sistema_lazer"]["pct_apo"]
            + q["institucional"]["pct_apo"] + q["arruamento"]["pct_apo"])
    assert abs(soma - 1.0) < 0.001  # sem double-counting nem área perdida
    fid = medida.construir_fidelidade(med, layout)
    lazer = next(a for a in fid["areas"] if a["item"] == "lazer")
    # reserva ~alvo (não inflada pela sobra); com o traçado curvo (9.9) a face discreta pode dar
    # "atenção" em vez de "atendido" — o que importa é que NÃO está degradada.
    assert lazer["status"] in ("atendido", "atencao")


def test_subdivisao_preservada_calibrada():
    """Calibração da GRADE (9.12) — estilo de grade EXPLÍCITO: o default do alto virou faixas
    (U8, aprovado); este ouro afere a subdivisão da GRADE (baixa/média ainda a usam).
    Critério 5: tamanho emerge da quadra (lotes diferentes), média na faixa, cv contido,
    retalho ≤1,5%, viário medido (malha 9.7) ≤~25% — calibrado no São Roque/MUE real.

    Fase 9.7: numa gleba RETANGULAR perfeita a malha gera quadras (faces) iguais → lotes muito
    uniformes (cv baixo, honesto); a variação cresce em gleba irregular. O cv continua > 0 (os
    tamanhos EMERGEM da quadra, não são impostos) — a amarra é o clamp legal, não a uniformidade."""
    layout, d, _, _ = _dist(SAO_ROQUE, "alta", _perfil_mue(), "MUE",
                            estilo={"tracado": "", "gramatica": "", "ruas_locais_contorno": False,
                                    "arquetipo": ""})
    assert 430 <= d["media_m2"] <= 560  # 9.12 — testada por faixa (preferência) → lote um pouco maior
    assert 0.02 <= d["cv"] <= 0.18
    assert d["retalho_perdido_pct"] <= 0.015
    assert d["viario_pct"] <= 0.27  # 9.12 — viário é a MALHA que SERVE todo lote (consequência adaptativa)
    assert len({round(l.area) for l in layout.lotes}) > 1  # tamanhos diferentes


def test_mercado_subordinado_a_lei():
    """Critério 6: zona (360) > piso de mercado médio (300) → piso efetivo 360; perfil só dá
    teto/alvo, nunca rebaixa o lote abaixo da zona."""
    dd = resolver_diretrizes(_perfil_mue(), "MUE", None, "media")
    assert dd["piso_lote_efetivo_m2"] == 360.0  # a lei (zona) vence o mercado (300)
    assert dd["lote_min_zona_m2"] == 360.0


def test_tamanho_score_desacoplado():
    """Critério 7: tamanho vem da quadra, score da posição — não há amarra 'grande = score alto'."""
    _, d, _, _ = _dist(SAO_ROQUE, "alta", _perfil_mue(), "MUE")
    assert d["correlacao_tamanho_score"] < 0.4


def test_degradacao_sem_luos():
    """Critério 9: sem LUOS → BASE_FEDERAL + rótulo; mínimos não confirmados marcados, não
    inventados."""
    layout, d, med, dd = _dist(SAO_ROQUE, "alta")
    assert dd["cobertura"] == "BASE_FEDERAL"
    assert d["fora_da_faixa"] == 0
    conf = {c["item"]: c for c in medida.conformidade_legal(med, layout, dd)}
    assert conf["doacao"]["status"] == "nao_avaliado"  # sem LUOS → não inventa exigência


def test_fronteira_e_1a(client, gerador_urbanismo, fonte_urbanismo):
    """Critério 8/10: stub fornece o programa; nenhum tamanho vem dele; diretrizes +
    conformidade_legal na resposta; §1-A; regex sem 'aprovado/viável/regular'."""
    r = client.post(
        "/api/analises",
        files={"kmz": ("g.kmz", make_kmz([RET_RETANGULO]), "application/vnd.google-earth.kmz")},
    )
    aid = r.json()["analise_id"]
    resp = client.post(f"/api/analises/{aid}/urbanismo/propor", json={"publico_alvo": "alta"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["diretrizes"] is not None
    assert body["distribuicao_tamanhos"]["fora_da_faixa"] == 0
    assert isinstance(body["conformidade_legal"], list)
    texto = " ".join(body["avisos"]).lower()
    assert "verificar na prefeitura" in texto or "verificar com urbanista" in texto
    assert not re.search(r"\b(aprovad|viáve|viave|regular)", texto)


def test_determinismo():
    prog_args = (SAO_ROQUE, "alta", _perfil_mue(), "MUE")
    a = _dist(*prog_args)[1]
    b = _dist(*prog_args)[1]
    assert a["media_m2"] == b["media_m2"] and a["faixas"] == b["faixas"]


def test_piso_e_lei_nao_mercado_e_teto_do_usuario_vale_em_qualquer_padrao():
    """Decisão do operador (27/07, base legal verificada): o piso do lote é a LEI — 125 m²
    federal (Lei 6.766/79, art. 4º, II) ou o mínimo da zona quando a LUOS está confirmada.
    O 'piso de mercado' do perfil NÃO restringe (vira só a mira/alvo): alta renda com teto
    345 do usuário gera janela [125, 345] com alvo 345 — nunca mais [450, 450] colapsada
    (1 lote / 63% de sobra em silêncio)."""
    from app.core.urbanismo_diretrizes import resolver_diretrizes

    d = resolver_diretrizes(None, None, None, "alta", lote_max_m2=345.0)
    assert d["piso_lote_efetivo_m2"] == 125.0  # só a lei federal (sem LUOS confirmada)
    assert d["teto_lote_m2"] == 345.0  # o teto do usuário vale em QUALQUER padrão
    assert d["alvo_lote_m2"] == 345.0  # mercado vira MIRA, clampada à janela do usuário
    assert "IGNORADO" not in d["aviso"].upper() or "MÍNIMO LEGAL" not in d["aviso"]
    # Sem teto do usuário, a mira de mercado do alto padrão segue orientando (465 m²).
    d2 = resolver_diretrizes(None, None, None, "alta")
    assert d2["piso_lote_efetivo_m2"] == 125.0 and d2["alvo_lote_m2"] == 465.0
    # Só fere a LEI se o teto ficar abaixo de 125 m² — aí sim avisa e corrige.
    d3 = resolver_diretrizes(None, None, None, "alta", lote_max_m2=100.0)
    assert d3["teto_lote_m2"] > 125.0 and "MÍNIMO LEGAL" in d3["aviso"]
    # Piso INFORMADO (27/07): sobe o piso acima do federal; abaixo do legal → ignora e avisa.
    d4 = resolver_diretrizes(None, None, None, "media", lote_min_m2=300.0)
    assert d4["piso_lote_efetivo_m2"] == 300.0
    d5 = resolver_diretrizes(None, None, None, "media", lote_min_m2=90.0)
    assert d5["piso_lote_efetivo_m2"] == 125.0
    assert "abaixo do mínimo legal" in d5["aviso"]


def test_sem_lote_minimo_na_lei_sempre_cai_no_federal_125():
    """REGRA GERAL (decisão do operador, 28/07): quando o lote mínimo NÃO for encontrado na
    diretriz municipal carregada, o motor usa SEMPRE o piso federal de 125 m² (Lei 6.766/79,
    art. 4º, II). Nada de número por município no código — o que não está no documento não
    vira restrição.

    Três caminhos levam ao mesmo piso:
      a) sem perfil nenhum, em QUALQUER público;
      b) perfil existente mas ainda em rascunho (não confirmado);
      c) perfil CONFIRMADO cuja zona não traz lote_min_m2 (caso real: plano diretor que
         delega os índices para uma LUOS que o município não publicou).
    """
    from app.core.urbanismo_diretrizes import PISO_FEDERAL_M2, resolver_diretrizes
    from app.models.schemas import PerfilMunicipal

    # (a) sem jurisdição: o piso é o federal em todos os padrões — mercado não restringe.
    for publico in ("baixa", "media", "alta"):
        d = resolver_diretrizes(None, None, None, publico)
        assert d["piso_lote_efetivo_m2"] == PISO_FEDERAL_M2 == 125.0
        assert d["cobertura"] == "BASE_FEDERAL"

    # (b) rascunho não confirmado não alimenta o cálculo (gate da 1.8).
    rascunho = PerfilMunicipal.model_validate(
        {"cod_ibge": "0000000", "status": "proposto",
         "zonas": [{"codigo": "ZR1", "params": {"lote_min_m2": {"valor": 400, "artigo": "Art. 1"}}}]}
    )
    d = resolver_diretrizes(rascunho, "ZR1", None, "media")
    assert d["piso_lote_efetivo_m2"] == 125.0 and d["cobertura"] == "BASE_FEDERAL"

    # (c) LUOS confirmada SEM lote mínimo na zona: usa a doação que a lei traz, mas o piso
    # continua o federal — ausência de índice não vira índice inventado.
    confirmado = PerfilMunicipal.model_validate(
        {"cod_ibge": "0000000", "status": "confirmado",
         "zonas": [{"codigo": "MACROZONA_URBANA",
                    "params": {"doacao_pct": {"valor": 0.35, "artigo": "Art. 28"}}}]}
    )
    d = resolver_diretrizes(confirmado, "MACROZONA_URBANA", None, "media")
    assert d["piso_lote_efetivo_m2"] == 125.0
    assert d["lote_min_zona_m2"] is None  # não encontrado ≠ zero, ≠ chute
    assert d["doacao_min_pct"] == 0.35  # o que a lei traz, vale
