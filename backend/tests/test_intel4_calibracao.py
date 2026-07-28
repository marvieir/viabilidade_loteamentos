"""INTEL-4 — testes-ouro da calibração do estilo pelos projetos importados.

Cobre o que a spec (docs/fase-intel-4.md) fixou como inegociável:
- padrão DECLARADO por quem carrega vence a inferência (decisão do operador, 28/07);
- piso de evidência: com menos de 3 projetos, mostra mas NÃO propõe;
- estudo GERADO por nós nunca vira insumo (o motor não aprende com o próprio motor);
- determinismo: mesma entrada → mesma proposta.
"""

from app.core import urbanismo_calibracao as calib


def _snapshot(
    arquivo: str,
    areas: list[float],
    *,
    publico_alvo=None,
    verde=0.18,
    lazer=0.09,
    origem="importado",
    quadras: list[str] | None = None,
):
    """Snapshot de proposta no formato que o store guarda (só o que a calibração lê)."""
    feats = []
    for i, a in enumerate(areas):
        feats.append({
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": []},
            "properties": {
                "lote_id": f"L{i+1:03d}",
                "area_m2": a,
                "testada_m": 12.0,
                "profundidade_m": round(a / 12.0, 2),
                "quadra_id": (quadras[i] if quadras and i < len(quadras) else "Q1"),
            },
        })
    def _uso(pct):
        return {"m2": 1000.0 * pct, "pct_apo": pct}
    return {
        "arquivo": arquivo,
        "proposta_id": f"imp_{arquivo}",
        "origem_geracao": origem,
        "publico_alvo": publico_alvo,
        "geometria": {"lotes_features": {"type": "FeatureCollection", "features": feats}},
        "quadro_areas": {
            "vendavel": _uso(0.55),
            "area_verde_reserva": _uso(verde),
            "sistema_lazer": _uso(lazer),
            "institucional": _uso(0.05),
            "arruamento": _uso(0.20),
        },
    }


def test_declarado_vence_inferido():
    """Decisão do operador (28/07): quem carrega o DWG conhece o empreendimento. Um projeto
    de alto padrão com lotes medianos de 340 m² (quadras econômicas puxando a mediana) seria
    classificado como 'media' pela área — a declaração corrige isso."""
    snap = _snapshot("nobre.dwg", [340.0] * 9, publico_alvo="alta")
    m = calib.metricas_do_projeto(snap)
    assert m["padrao"] == "alta"
    assert m["padrao_origem"] == "declarado"
    # Sem declaração (importação anterior ao campo), cai na inferência — e rotula.
    m2 = calib.metricas_do_projeto(_snapshot("legado.dwg", [340.0] * 9))
    assert m2["padrao"] == "media" and m2["padrao_origem"] == "inferido"


def test_inferencia_fora_das_faixas_nao_chuta():
    """Mediana fora de qualquer faixa conhecida → 'indefinido'. Não empurra para a faixa mais
    próxima: etiqueta inventada contaminaria a mediana daquele padrão."""
    assert calib.inferir_padrao(275.0) == "indefinido"  # entre baixa (≤250) e media (≥300)
    assert calib.inferir_padrao(None) == "indefinido"
    assert calib.inferir_padrao(180.0) == "baixa"
    assert calib.inferir_padrao(400.0) == "media"
    assert calib.inferir_padrao(700.0) == "alta"


def test_estudo_gerado_nunca_vira_insumo():
    """Só projeto IMPORTADO calibra. Aprender com o próprio estudo gerado seria o motor
    confirmando as próprias premissas."""
    assert calib.metricas_do_projeto(
        _snapshot("nosso.kmz", [340.0] * 5, origem="llm")
    ) is None
    assert calib.metricas_do_projeto({"origem_geracao": "importado"}) is None  # sem lote


def test_piso_de_evidencia_bloqueia_proposta():
    """Com menos de MIN_PROJETOS, o bloco aparece no relatório (o operador vê as métricas)
    mas não gera proposta — dizer 'seu alvo está errado' com 1 projeto seria chute."""
    dois = [
        calib.metricas_do_projeto(_snapshot(f"p{i}.dwg", [340.0] * 6, publico_alvo="media"))
        for i in range(2)
    ]
    ag = calib.agregar(dois)
    assert ag["media"]["n_projetos"] == 2
    assert ag["media"]["suficiente"] is False
    assert ag["media"]["metricas"]["verde_frac"]["mediana"] == 0.18  # mostra a métrica
    assert calib.propor_ajustes(ag, {"media": {"verde_min_pct": 0.30}}) == []


def test_propoe_com_evidencia_e_carrega_proveniencia():
    """Com 3 projetos, propõe — e a proposta traz de onde o número veio (§3 proveniência)."""
    tres = [
        calib.metricas_do_projeto(
            _snapshot(f"p{i}.dwg", [700.0] * 6, publico_alvo="alta", verde=v)
        )
        for i, v in enumerate((0.26, 0.28, 0.30))
    ]
    ag = calib.agregar(tres)
    assert ag["alta"]["suficiente"] is True
    assert ag["alta"]["declarados"] == 3 and ag["alta"]["inferidos"] == 0
    props = calib.propor_ajustes(ag, {"alta": {"verde_min_pct": 0.20}})
    verde = [p for p in props if p["knob"] == "verde_min_pct"]
    assert len(verde) == 1
    p = verde[0]
    assert p["vigente"] == 0.20 and p["proposto"] == 0.28  # mediana de 0,26/0,28/0,30
    assert p["dispersao"] == [0.26, 0.30] and p["n_projetos"] == 3
    assert "declarado" in p["proveniencia"]
    assert sorted(p["projetos"]) == ["p0.dwg", "p1.dwg", "p2.dwg"]


def test_diferenca_irrelevante_nao_vira_proposta():
    """Delta abaixo de DELTA_MIN (1 p.p.) é ruído de medição — não gera trabalho de revisão."""
    tres = [
        calib.metricas_do_projeto(
            _snapshot(f"q{i}.dwg", [700.0] * 6, publico_alvo="alta", verde=0.205)
        )
        for i in range(3)
    ]
    props = calib.propor_ajustes(calib.agregar(tres), {"alta": {"verde_min_pct": 0.20}})
    assert [p for p in props if p["knob"] == "verde_min_pct"] == []


def test_knobs_legais_e_de_composicao_ficam_fora():
    """A calibração nunca propõe piso de lote (natureza LEGAL — erro de 27/07) nem traçado/
    gramática/prompt (composição, não medida)."""
    proibidos = {"piso_lote", "lote_min_m2", "tracado", "gramatica", "arquetipo",
                 "prompt_regras"}
    calibraveis = {k for knobs in calib.KNOB_POR_METRICA.values() for k in knobs}
    assert not (calibraveis & proibidos)
    tres = [
        calib.metricas_do_projeto(_snapshot(f"r{i}.dwg", [700.0] * 6, publico_alvo="alta"))
        for i in range(3)
    ]
    props = calib.propor_ajustes(
        calib.agregar(tres),
        {"alta": {"verde_min_pct": 0.05, "tracado": "contorno_serpente",
                  "prompt_regras": "texto"}},
    )
    assert {p["knob"] for p in props} <= calibraveis


def test_determinismo():
    """Mesma entrada → mesma proposta, sempre (inegociável §4)."""
    def _rodar():
        ms = [
            calib.metricas_do_projeto(
                _snapshot(f"d{i}.dwg", [700.0, 690.0, 710.0], publico_alvo="alta", verde=v)
            )
            for i, v in enumerate((0.26, 0.28, 0.30))
        ]
        return calib.propor_ajustes(calib.agregar(ms), {"alta": {"verde_min_pct": 0.20}})

    assert _rodar() == _rodar()


def test_quadra_agrega_lotes_contiguos():
    """Módulo de quadra sai do agrupamento por quadra_id que o motor já carimba."""
    m = calib.metricas_do_projeto(
        _snapshot("q.dwg", [300.0] * 6, publico_alvo="media",
                  quadras=["Q1", "Q1", "Q1", "Q2", "Q2", "Q2"])
    )
    assert m["quadra_area_mediana_m2"] == 900.0  # 3 lotes × 300 em cada quadra
    assert m["quadra_lotes_mediana"] == 3.0
