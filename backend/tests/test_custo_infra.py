"""Valores-ouro do motor de custo de infraestrutura (Tier 3).

Testa o determinismo e a degradação honesta: sem perfil → INDISPONIVEL; perfil parcial →
PARCIAL; perfil completo → COMPLETA com totais exatos (quantidade × unitário + canteiro + BDI).
"""

from app.core import custo_infra as motor


def _quantidades():
    # Layout-exemplo: 100 lotes, 5.000 m de via, 27.500 m² de leito, 50.000 m² urbanizados,
    # 1.200 m de perímetro.
    return motor.Quantidades(
        area_urbanizada_m2=50_000.0,
        leito_carrocavel_m2=27_500.0,
        comprimento_vias_m=5_000.0,
        n_lotes=100,
        perimetro_m=1_200.0,
    )


def _perfil_completo():
    return {
        "bdi_pct": 20.0,
        "data_referencia": "2026-06",
        "uf": "SP",
        "fonte": "perfil do operador",
        "disciplinas": {
            "terraplanagem": {"base": "por_m2_area", "custo": {"medio": 10.0}},      # 50.000*10 = 500.000
            "pavimentacao": {"base": "por_m2_leito", "custo": {"medio": 100.0}},     # 27.500*100 = 2.750.000
            "drenagem": {"base": "por_m_via", "custo": {"medio": 200.0}},            # 5.000*200 = 1.000.000
            "agua": {"base": "por_lote", "custo": {"medio": 3_000.0}},               # 100*3.000 = 300.000
            "esgoto": {"base": "por_lote", "custo": {"medio": 4_000.0}},             # 100*4.000 = 400.000
            "energia_iluminacao": {"base": "por_lote", "custo": {"medio": 5_000.0}}, # 100*5.000 = 500.000
            "reservatorios": {"base": "por_lote", "custo": {"medio": 500.0}},        # 100*500 = 50.000
            "cercamento": {"base": "por_m_perimetro", "custo": {"medio": 250.0}},    # 1.200*250 = 300.000
            "canteiro": {"base": "percentual_subtotal", "custo": {"medio": 5.0}},    # 5% do subtotal
        },
    }


def test_sem_perfil_degrada_honesto():
    out = motor.calcular(_quantidades(), None, "medio")
    assert out.cobertura == "INDISPONIVEL"
    assert out.total is None
    assert out.custo_por_lote is None
    assert any("não preenchido" in a.lower() for a in out.avisos)


def test_completo_valores_ouro():
    out = motor.calcular(_quantidades(), _perfil_completo(), "medio")
    assert out.cobertura == "COMPLETA"
    # Subtotal das 8 disciplinas físicas:
    fisico = 500_000 + 2_750_000 + 1_000_000 + 300_000 + 400_000 + 500_000 + 50_000 + 300_000
    assert fisico == 5_800_000
    canteiro = 0.05 * fisico  # 290.000
    subtotal_direto = fisico + canteiro  # 6.090.000
    bdi = 0.20 * subtotal_direto  # 1.218.000
    total = subtotal_direto + bdi  # 7.308.000
    assert abs(out.subtotal_direto - subtotal_direto) < 1e-6
    assert abs(out.bdi_valor - bdi) < 1e-6
    assert abs(out.total - total) < 1e-6
    assert abs(out.custo_por_lote - total / 100) < 1e-6
    assert abs(out.custo_por_m2 - total / 50_000) < 1e-6
    # Determinismo: mesma entrada → mesma saída.
    out2 = motor.calcular(_quantidades(), _perfil_completo(), "medio")
    assert out2.total == out.total


def test_parcial_marca_cobertura_e_soma_so_o_preenchido():
    perfil = {
        "bdi_pct": 0.0,
        "disciplinas": {
            "terraplanagem": {"base": "por_m2_area", "custo": {"medio": 10.0}},  # 500.000
            "pavimentacao": {"base": "por_m2_leito", "custo": {"medio": 100.0}},  # 2.750.000
        },
    }
    out = motor.calcular(_quantidades(), perfil, "medio")
    assert out.cobertura == "PARCIAL"
    assert abs(out.subtotal_direto - 3_250_000) < 1e-6  # só as 2 preenchidas, sem BDI
    assert abs(out.total - 3_250_000) < 1e-6


def test_custo_sem_quantidade_vira_aviso_nao_zero():
    # Perfil pede pavimentação (por_m2_leito) mas o layout não mediu o leito.
    q = motor.Quantidades(area_urbanizada_m2=50_000.0, n_lotes=100)  # sem leito/vias/perímetro
    perfil = {
        "bdi_pct": 0.0,
        "disciplinas": {
            "terraplanagem": {"base": "por_m2_area", "custo": {"medio": 10.0}},   # tem qtd → 500.000
            "pavimentacao": {"base": "por_m2_leito", "custo": {"medio": 100.0}},  # SEM qtd → aviso
        },
    }
    out = motor.calcular(q, perfil, "medio")
    assert abs(out.subtotal_direto - 500_000) < 1e-6  # pavimentação não entrou no total
    pav = next(d for d in out.disciplinas if d.chave == "pavimentacao")
    assert pav.preenchido is True and pav.subtotal is None and pav.aviso is not None


def test_perfil_out_traz_todas_disciplinas_para_o_editor():
    out = motor.montar_perfil_out(None)
    assert out.configurado is False
    assert len(out.disciplinas) == len(motor.DISCIPLINAS_DEFAULT)
    assert [p.chave for p in out.padroes] == ["economico", "medio", "alto"]
    pav = next(d for d in out.disciplinas if d.chave == "pavimentacao")
    assert pav.base == "por_m2_leito"
    assert any(b.chave == "por_m_via" for b in pav.bases_disponiveis)
