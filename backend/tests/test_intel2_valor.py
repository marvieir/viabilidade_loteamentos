"""INTEL-2 (docs/fase-motor-intel.md) — função de valor por público.

Valores-ouro da POLÍTICA de escolha: sobra e excesso de viário penalizam; amenidade
bonifica com peso maior no alto padrão; lote longe do alvo do público desconta;
determinismo e override auditável pelo perfil de estilo.
"""

from types import SimpleNamespace

from app.core.urbanismo_valor import PESOS_DEFAULT, pesos_do_publico, valor_variante


def _cenario(sobra_m2=0.0, viario_m2=2000.0, cobertura_pct=0.0, areas=(300.0, 300.0)):
    liq = 10_000.0
    med = SimpleNamespace(
        heatmap={"por_lote": [{"area_m2": a, "multiplicador": 1.0} for a in areas]},
        quadro={
            "area_liquida_m2": liq,
            "sobra_geometrica": {"m2": sobra_m2},
            "arruamento": {"m2": viario_m2},
        },
    )
    layout = SimpleNamespace(
        sistema_lazer_diagnostico={"cobertura_400m_pct": cobertura_pct}
    )
    return layout, med


def test_sobra_e_excesso_de_viario_penalizam():
    v_limpo, _ = valor_variante(*_cenario(sobra_m2=0.0), "media", alvo_lote_m2=300.0)
    v_sobra, _ = valor_variante(*_cenario(sobra_m2=3_000.0), "media", alvo_lote_m2=300.0)
    assert v_sobra < v_limpo
    # viário DENTRO do alvo (20% ≤ 24%) não penaliza; excesso (35%) penaliza.
    v_ok, _ = valor_variante(*_cenario(viario_m2=2_000.0), "media", alvo_lote_m2=300.0)
    v_excesso, _ = valor_variante(*_cenario(viario_m2=3_500.0), "media", alvo_lote_m2=300.0)
    assert v_excesso < v_ok


def test_amenidade_pesa_mais_no_alto_padrao():
    ganho = {}
    for pub in ("baixa", "alta"):
        v0, _ = valor_variante(*_cenario(cobertura_pct=0.0), pub, alvo_lote_m2=300.0)
        v100, _ = valor_variante(*_cenario(cobertura_pct=100.0), pub, alvo_lote_m2=300.0)
        ganho[pub] = v100 / v0
    assert ganho["alta"] > ganho["baixa"]  # alta valoriza amenidade; baixa valoriza yield


def test_dispersao_do_alvo_desconta():
    v_no_alvo, _ = valor_variante(*_cenario(areas=(300.0, 300.0)), "media", alvo_lote_m2=300.0)
    v_longe, d = valor_variante(*_cenario(areas=(150.0, 450.0)), "media", alvo_lote_m2=300.0)
    assert v_longe < v_no_alvo
    assert d["dispersao_alvo"] > 0


def test_override_do_estilo_e_determinismo():
    estilo = {"valor_pesos": {"amenidade": 2.0}}
    v1, d1 = valor_variante(*_cenario(cobertura_pct=50.0), "baixa", estilo=estilo,
                            alvo_lote_m2=300.0)
    v2, d2 = valor_variante(*_cenario(cobertura_pct=50.0), "baixa", estilo=estilo,
                            alvo_lote_m2=300.0)
    assert v1 == v2 and d1 == d2  # mesma entrada → mesmo valor, sempre (§4)
    assert d1["pesos"]["amenidade"] == 2.0  # override auditável do estilo
    assert pesos_do_publico("baixa")["amenidade"] == PESOS_DEFAULT["baixa"]["amenidade"]
