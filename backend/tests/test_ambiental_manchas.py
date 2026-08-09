"""AMB-EXC — testes das manchas + segunda opinião (incremento 2). Tudo offline/determinístico."""

from shapely.geometry import MultiPolygon, box

from app.core import ambiental_manchas as am

# Gleba sintética ~440×440 m perto de Alegrete (1° ≈ 111 km; 0.004° ≈ 440 m).
LON, LAT = -55.79, -29.78
D = 0.004
GLEBA = box(LON, LAT, LON + D, LAT + D)


def _quad(fx: float, fy: float, fw: float, fh: float):
    """Sub-retângulo da gleba em frações (0..1)."""
    return box(LON + fx * D, LAT + fy * D, LON + (fx + fw) * D, LAT + (fy + fh) * D)


def test_extrair_manchas_determinismo_e_assinatura():
    averif = MultiPolygon([
        _quad(0.05, 0.05, 0.30, 0.30),   # ~130×130 m — a maior → M1
        _quad(0.60, 0.60, 0.20, 0.20),   # média → M2
        _quad(0.05, 0.60, 0.10, 0.10),   # pequena → M3
    ])
    m1 = am.extrair_manchas(GLEBA, averif)
    m2 = am.extrair_manchas(GLEBA, averif)
    assert [m.mancha_id for m in m1] == ["M1", "M2", "M3"]
    assert m1[0].area_m2 > m1[1].area_m2 > m1[2].area_m2
    # Assinatura estável entre requests (o laudo referencia com segurança).
    assert [m.assinatura for m in m1] == [m.assinatura for m in m2]
    assert all(m.geojson.get("type") == "Polygon" for m in m1)


def test_extrair_manchas_filtra_ruido_de_pixel():
    averif = MultiPolygon([
        _quad(0.1, 0.1, 0.3, 0.3),
        _quad(0.8, 0.8, 0.015, 0.015),   # ~44 m² < 100 m² → ruído, fora
    ])
    ms = am.extrair_manchas(GLEBA, averif)
    assert len(ms) == 1


def test_sem_a_verificar_sem_manchas():
    assert am.extrair_manchas(GLEBA, None) == []


def _manchas_padrao():
    averif = MultiPolygon([
        _quad(0.05, 0.05, 0.30, 0.30),  # M1
        _quad(0.60, 0.60, 0.20, 0.20),  # M2
        _quad(0.05, 0.60, 0.14, 0.14),  # M3
        _quad(0.60, 0.05, 0.14, 0.14),  # M4
    ])
    return am.extrair_manchas(GLEBA, averif)


def test_segunda_opiniao_vereditos():
    ms = _manchas_padrao()
    a1, a2, a3, a4 = (m.assinatura for m in ms)
    fracoes = {
        a1: {3: 0.92, 15: 0.08},    # formação florestal dominante
        a2: {9: 0.81, 3: 0.19},     # silvicultura → diverge (WorldCover disse verde)
        a3: {12: 0.77},             # campestre nativa
        a4: {3: 0.45, 15: 0.40, 21: 0.15},  # sem dominante → mosaico
    }
    # CAR: RL cobre a M1 inteira (reforço) e nada das outras.
    rl = _quad(0.0, 0.0, 0.45, 0.45)
    ops = am.segunda_opiniao(GLEBA, ms, fracoes, "MapBiomas Col.10 (2024)", rl, True)
    por_id = {o.mancha.mancha_id: o for o in ops}
    assert por_id["M1"].concordancia == am.V_MATA_ALTA
    assert por_id["M2"].concordancia == am.V_DIVERGEM
    assert "silvicultura" in por_id["M2"].motivo
    assert por_id["M3"].concordancia == am.V_CAMPESTRE
    assert por_id["M4"].concordancia == am.V_DIVERGEM
    # Toda mancha tem as 3 leituras (WorldCover, CAR, MapBiomas) com proveniência.
    for o in ops:
        fontes = [le.fonte for le in o.leituras]
        assert fontes[0] == "WorldCover" and "CAR" in fontes


def test_segunda_opiniao_mata_provavel_sem_car():
    ms = _manchas_padrao()[:1]
    fr = {ms[0].assinatura: {3: 0.95}}
    (op,) = am.segunda_opiniao(GLEBA, ms, fr, "MapBiomas", None, False)
    assert op.concordancia == am.V_MATA_PROVAVEL
    assert any(le.fonte == "CAR" and le.valor == "não consultado" for le in op.leituras)


def test_fonte_indisponivel_degrada_para_insuficiente():
    """MapBiomas fora do ar → nada é liberado; tudo 'dados insuficientes' rotulado."""
    ms = _manchas_padrao()
    ops = am.segunda_opiniao(GLEBA, ms, None, "MapBiomas", None, False)
    assert all(o.concordancia == am.V_INSUFICIENTE for o in ops)
    assert all(any(le.valor == "não consultado" and le.fonte == "MapBiomas"
                   for le in o.leituras) for o in ops)


def test_mancha_menor_que_pixel_insuficiente():
    ms = _manchas_padrao()[:1]
    ops = am.segunda_opiniao(GLEBA, ms, {ms[0].assinatura: {}}, "MapBiomas", None, False)
    assert ops[0].concordancia == am.V_INSUFICIENTE
