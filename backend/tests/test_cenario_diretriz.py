"""Cenário diretriz (Fase 1.8) — núcleo determinístico: lote legal + doação da zona.

Reintroduz doação e lote mínimo LEGAL sobre o aproveitável físico (da 2.2), sem recalcular
o físico. Mesma (perfil, zona, modalidade, físico) → mesmo número (critério 5).
"""

from app.core import aproveitamento as m
from app.models.schemas import (
    ModalidadeOverride,
    ParamProv,
    PerfilMunicipal,
    ZonaParams,
    ZonaPerfil,
)


def _perfil(status="confirmado", *, doacao=None, base="total", lote=250.0, modalidades=None):
    """Perfil de teste com uma zona ZR1. ``doacao=None`` → sem doação na zona."""
    doa = (
        ParamProv(valor=doacao, base=base, artigo="Art. 20", pagina=14)
        if doacao is not None
        else None
    )
    zona = ZonaPerfil(
        codigo="ZR1",
        descricao="Zona Residencial 1",
        params=ZonaParams(
            lote_min_m2=ParamProv(valor=lote, artigo="Art. 12, I", pagina=8),
            doacao_pct=doa,
        ),
        modalidades=modalidades or {},
    )
    return PerfilMunicipal(
        cod_ibge="3550605",
        municipio="São Roque",
        uf="SP",
        status=status,
        validado_por="Fulano",
        data_referencia="2026-06-06",
        zonas=[zona],
    )


def test_valor_ouro_doacao_total():
    # doação 35% base "total" sobre a gleba (24.000 m²) = 8.400 m²; físico 20.000 →
    # diretriz 11.600 m²; lote legal 250 → floor(11600/250) = 46.
    perfil = _perfil(doacao=0.35, base="total", lote=250.0)
    dados, aviso = m.cenario_diretriz(perfil, "ZR1", None, 20_000.0, 24_000.0)
    assert aviso is None
    assert dados["doacao_m2"] == 8400.0
    assert dados["doacao_base"] == "total"
    assert dados["area_aproveitavel_m2"] == 11_600.0
    assert dados["lote_min_m2_legal"] == 250.0
    assert dados["n_lotes"] == 46


def test_base_liquida_incide_sobre_fisico():
    # 10% base "liquida" → 0,10 × físico (não sobre a gleba inteira).
    perfil = _perfil(doacao=0.10, base="liquida", lote=200.0)
    dados, _ = m.cenario_diretriz(perfil, "ZR1", None, 50_000.0, 80_000.0)
    assert dados["doacao_m2"] == 5_000.0
    assert dados["area_aproveitavel_m2"] == 45_000.0
    assert dados["n_lotes"] == 225


def test_modalidade_isenta_doacao_zero_e_valida():
    # Desmembramento isento (override doacao_pct=0): 0 aplicado, distinto de "não considerado".
    mods = {
        "desmembramento": ModalidadeOverride(
            doacao_pct=ParamProv(valor=0.0, artigo="Art. 22", pagina=15)
        )
    }
    perfil = _perfil(doacao=0.35, base="total", lote=250.0, modalidades=mods)
    dados, aviso = m.cenario_diretriz(perfil, "ZR1", "desmembramento", 20_000.0, 24_000.0)
    assert aviso is None
    assert dados["doacao_pct"] == 0.0
    assert dados["doacao_m2"] == 0.0
    assert dados["area_aproveitavel_m2"] == 20_000.0  # físico inteiro vira diretriz
    assert dados["n_lotes"] == 80


def test_determinismo():
    perfil = _perfil(doacao=0.35, base="total")
    a = m.cenario_diretriz(perfil, "ZR1", None, 20_000.0, 24_000.0)[0]
    b = m.cenario_diretriz(perfil, "ZR1", None, 20_000.0, 24_000.0)[0]
    assert a == b


def test_perfil_proposto_nao_alimenta_calculo():
    perfil = _perfil(status="proposto", doacao=0.35)
    dados, aviso = m.cenario_diretriz(perfil, "ZR1", None, 20_000.0, 24_000.0)
    assert dados is None
    assert "confirmado" in aviso.lower()


def test_zona_inexistente_nao_inventa():
    perfil = _perfil(doacao=0.35)
    dados, aviso = m.cenario_diretriz(perfil, "ZX9", None, 20_000.0, 24_000.0)
    assert dados is None
    assert "ZX9" in aviso


def test_sem_lote_legal_nao_chuta():
    perfil = _perfil(doacao=0.35, lote=None)  # lote_min sem valor
    dados, aviso = m.cenario_diretriz(perfil, "ZR1", None, 20_000.0, 24_000.0)
    assert dados is None
    assert "lote" in aviso.lower()


def test_doacao_ausente_nao_e_invencao():
    # Zona com lote legal mas sem doação confirmada → doação 0 aplicada + ressalva honesta.
    perfil = _perfil(doacao=None, lote=250.0)
    dados, aviso = m.cenario_diretriz(perfil, "ZR1", None, 20_000.0, 24_000.0)
    assert aviso is None
    assert dados["doacao_m2"] == 0.0
    assert "não informada" in dados["proveniencia"]
