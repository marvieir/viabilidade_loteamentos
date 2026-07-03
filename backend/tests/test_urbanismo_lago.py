"""Fase U3 — Lago no ponto baixo do DEM (amenidade valorizadora — pesquisa §1).

Valores-ouro:
- o lago nasce como PARQUE (corpo d'água + orla pública) na face do ponto baixo;
- a lâmina d'água ganha linha PRÓPRIA no quadro (fora da doação verde — aviso rotula);
- o fator "agua" do score v2 LIGA sozinho (anel de 274 m: perto > longe);
- sem DEM/opt-out → sem lago, sem silêncio; face pequena demais → degrada com aviso;
- Custo de Infra: disciplina do lago só entra quando HÁ lâmina (não polui a cobertura).
"""

from shapely.geometry import box

from app.core import custo_infra as custo_motor
from app.core import urbanismo_geom as geom
from app.core import urbanismo_medida as medida
from app.core.urbanismo_programa import programa_do_preset

GLEBA = box(0.0, 0.0, 1100.0, 220.0)
LAGO = {"ponto": (900.0, 110.0), "area_m2": 6000.0, "cota_m": 712.4}


def _layout(lago=None, publico="alta"):
    prog = programa_do_preset(publico, {"pct_lazer": 0.12})
    return geom.gerar_layout(GLEBA, prog, lago=lago)


def test_lago_nasce_como_parque_no_ponto_baixo():
    layout = _layout(LAGO)
    d = layout.sistema_lazer_diagnostico
    assert layout.agua is not None and not layout.agua.is_empty
    assert d["lago_m2"] and abs(d["lago_m2"] - 6000.0) < 6000.0 * 0.5  # corpo ~alvo
    assert d["orla_m2"] and d["orla_m2"] > 0  # orla-parque pública (nunca lago "pelado")
    assert d["lago_cota_m"] == 712.4
    # o lago cai perto do ponto pedido (face viável mais próxima)
    assert abs(layout.agua.centroid.x - 900.0) < 150.0
    # nenhum lote dentro d'água
    assert all(l.intersection(layout.agua).area < 1e-6 for l in layout.lotes)
    assert any("LAGO SINTETIZADO" in a for a in layout.avisos)
    # orla entra no lazer rotulado (tooltip do mapa)
    tipos = {f["tipo"] for f in layout.lazer_features}
    assert "agua" in tipos and "orla" in tipos


def test_lamina_dagua_no_quadro_fora_da_doacao():
    layout = _layout(LAGO)
    med = medida.medir(layout, publico_alvo="alta")
    lam = med.quadro["lamina_dagua"]
    assert lam is not None and lam["m2"] > 0
    # sem lago → linha None (não polui o quadro)
    med2 = medida.medir(_layout(None), publico_alvo="alta")
    assert med2.quadro["lamina_dagua"] is None


def test_fator_agua_liga_com_anel_274m():
    med = medida.medir(_layout(LAGO), publico_alvo="alta")
    assert "agua" not in med.heatmap["fatores_ausentes"]
    fatores = [p["fatores"]["agua"] for p in med.heatmap["por_lote"]]
    assert max(fatores) > 0.8 and min(fatores) == 0.0  # anel: perto premia, longe não
    # sem lago o fator fica AUSENTE (não zero em silêncio)
    med2 = medida.medir(_layout(None), publico_alvo="alta")
    assert "agua" in med2.heatmap["fatores_ausentes"]


def test_lago_deterministico_e_prioridade_por_perfil():
    a = _layout(LAGO)
    b = _layout(LAGO)
    assert a.agua.wkt == b.agua.wkt
    # Mov.1 — ALTO PADRÃO: lago maior que as quadras → REDIMENSIONA e materializa (o lago
    # tem prioridade sobre lotes; o prêmio do anel paga o sacrifício).
    grande_alta = _layout({"ponto": (900.0, 110.0), "area_m2": 500000.0}, publico="alta")
    assert grande_alta.agua is not None and not grande_alta.agua.is_empty
    assert grande_alta.agua.area < 500000.0  # redimensionado p/ a quadra disponível
    assert any("dimensionado para a quadra disponível" in a for a in grande_alta.avisos)
    # médio/econômico: lotes seguem prioritários → degrada com aviso
    grande_media = _layout({"ponto": (900.0, 110.0), "area_m2": 500000.0}, publico="media")
    assert grande_media.agua is None or grande_media.agua.is_empty
    assert any("LAGO NÃO SINTETIZADO" in a for a in grande_media.avisos)


def test_custo_infra_disciplina_lago_condicional():
    perfil = {"disciplinas": {
        "terraplanagem": {"custo": {"medio": 30.0}},
        "lago_paisagismo": {"custo": {"medio": 120.0}},
    }, "bdi_pct": 0.0}
    q_sem = custo_motor.Quantidades(area_urbanizada_m2=100000.0, n_lotes=100)
    r_sem = custo_motor.calcular(q_sem, perfil, "medio")
    chaves_sem = {d.chave for d in r_sem.disciplinas}
    assert "lago_paisagismo" not in chaves_sem  # sem lâmina, nem aparece

    q_com = custo_motor.Quantidades(
        area_urbanizada_m2=100000.0, n_lotes=100, lamina_dagua_m2=6000.0
    )
    r_com = custo_motor.calcular(q_com, perfil, "medio")
    linha = next(d for d in r_com.disciplinas if d.chave == "lago_paisagismo")
    assert linha.subtotal == 6000.0 * 120.0


# ------------------------- Movimento 1 — lazer espalhado + instruções -------------------------
def test_alta_renda_espalha_pracas_mesmo_com_cobertura_ok():
    """Mov.1: no alto padrão há PISO de praças (1 a cada ~10 quadras) mesmo quando o hub já
    cobre os 400 m — o lazer espalha (padrão dos master plans), não só cobre."""
    from shapely.geometry import box as _box

    compacta = _box(0.0, 0.0, 480.0, 300.0)  # tudo a <400 m do centro
    lay_alta = geom.gerar_layout(compacta, programa_do_preset("alta", {"pct_lazer": 0.15}))
    d = lay_alta.sistema_lazer_diagnostico
    assert d.get("n_pracas", 0) >= 1  # piso do perfil (antes: 0, cobertura já ok)
    # rótulo com PROGRAMA sugerido (esquemático) da biblioteca
    pracas = [f for f in lay_alta.lazer_features if f["tipo"] == "praca"]
    assert pracas and all("—" in p["rotulo"] for p in pracas)


def test_instrucoes_do_operador_entram_no_prompt():
    from app.core import urbanismo_programa as programa_mod

    ctx = {"area_aproveitavel_m2": 100000.0}
    sem = programa_mod._prompt_usuario(ctx, "aberto", "alta")
    assert "DIRETRIZES DO OPERADOR" not in sem
    com = programa_mod._prompt_usuario(
        {**ctx, "instrucoes_do_operador": "inclua 3 quadras, academia e mirante"},
        "aberto", "alta",
    )
    assert "DIRETRIZES DO OPERADOR" in com and "mirante" in com
    assert "instrucoes_do_operador" not in com.split("DIRETRIZES")[0]  # sem duplicar no ctx


def test_biblioteca_mapeia_amenidades_de_bolso():
    from app.core import urbanismo_amenidades as amen

    sel, fora, sem = amen.mapear_amenidades(
        ["mirante com deck", "redário para descanso", "horta comunitária", "quiosques"],
        "alta",
    )
    chaves = {a.chave for a in sel}
    assert {"mirante_estar", "redario", "horta_pomar", "quiosque"} <= chaves
    assert not sem  # tudo reconhecido (mirante saiu do fora_do_hub — agora materializa)
