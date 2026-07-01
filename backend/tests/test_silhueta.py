"""Valores-ouro da silhueta (thumbnail da gleba nas 'Minhas análises')."""

from app.core.silhueta import silhueta


def _quadrado(x0=0.0, y0=0.0, lado=1.0):
    return {
        "type": "Polygon",
        "coordinates": [[[x0, y0], [x0 + lado, y0], [x0 + lado, y0 + lado], [x0, y0 + lado], [x0, y0]]],
    }


def test_quadrado_normalizado_no_viewbox():
    aneis = silhueta(_quadrado())
    assert aneis is not None and len(aneis) == 1
    xs = [p[0] for p in aneis[0]]
    ys = [p[1] for p in aneis[0]]
    # Dentro do viewBox com margem (6..94) e usando a área útil toda.
    assert min(xs) == 6.0 and max(xs) == 94.0
    assert min(ys) == 6.0 and max(ys) == 94.0


def test_y_invertido_para_svg():
    # Ponto de MAIOR latitude (norte) tem o MENOR y no SVG.
    aneis = silhueta({"type": "Polygon", "coordinates": [[[0, 0], [2, 0], [2, 1], [0, 1], [0, 0]]]})
    ys = [p[1] for p in aneis[0]]
    assert min(ys) < 50 < max(ys)  # forma 2:1 centralizada — topo acima do meio, base abaixo


def test_multipoligono_mesma_escala():
    g = {
        "type": "MultiPolygon",
        "coordinates": [_quadrado()["coordinates"], _quadrado(x0=3.0)["coordinates"]],
    }
    aneis = silhueta(g)
    assert aneis is not None and len(aneis) == 2


def test_entrada_invalida_degrada_none():
    assert silhueta(None) is None
    assert silhueta({}) is None
    assert silhueta({"type": "Polygon", "coordinates": []}) is None
