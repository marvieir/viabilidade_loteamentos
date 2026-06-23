"""Fase 12 — slope-aware: a seleção de verde reserva a ENCOSTA antes do terreno plano.

Testa `_selecionar_verde` diretamente (núcleo determinístico): entre duas faces igualmente
aptas (mesma forma e área), a que está sobre declividade >20% vira VERDE; a plana fica p/ lote.
Sem a faixa íngreme, o comportamento é o de antes (não regride).
"""

from shapely.geometry import box

from app.core.urbanismo_geom import _selecionar_verde


def test_face_ingreme_vira_verde_antes_da_plana():
    # Duas faces quadradas idênticas (mesma forma/área), lado a lado.
    plana = box(0, 0, 30, 30)      # terreno plano (fora da faixa íngreme)
    encosta = box(100, 0, 130, 30)  # mesma face, mas sobre a encosta
    pool = [plana, encosta]
    # Banda íngreme cobre só a face 'encosta'.
    ingreme = box(95, -5, 135, 35)

    # Orçamento de verde = uma face. A íngreme deve ser escolhida.
    verdes, resto = _selecionar_verde(pool, alvo=plana.area, ingreme=ingreme)
    assert len(verdes) == 1 and len(resto) == 1
    assert verdes[0].equals(encosta), "a encosta deveria virar verde"
    assert resto[0].equals(plana), "o terreno plano deveria sobrar p/ lote"


def test_sem_faixa_ingreme_nao_regride():
    # Sem 'ingreme', cai na ordenação por forma/área de antes (faces iguais → escolhe uma só).
    plana = box(0, 0, 30, 30)
    outra = box(100, 0, 130, 30)
    verdes, resto = _selecionar_verde([plana, outra], alvo=plana.area, ingreme=None)
    assert len(verdes) == 1 and len(resto) == 1


def test_face_pouco_ingreme_nao_e_penalizada():
    # Cobertura íngreme abaixo do limiar (FRAC_FACE_INGREME) não marca a face como encosta.
    plana = box(0, 0, 30, 30)
    quase_plana = box(100, 0, 130, 30)
    # Cobre só um cantinho (~11% < 25%) da 'quase_plana' → não conta como íngreme.
    ingreme = box(100, 0, 110, 10)
    verdes, _ = _selecionar_verde([plana, quase_plana], alvo=plana.area, ingreme=ingreme)
    # Como nenhuma é "íngreme o bastante", o desempate volta a ser forma/área (não força a encosta).
    assert len(verdes) == 1
