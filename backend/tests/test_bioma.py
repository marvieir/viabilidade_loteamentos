"""Tier 2 — identificação de bioma (IBGE) sobre a gleba."""

import json

from shapely.geometry import box, mapping

from app.core.bioma import FonteBiomaArquivo


def _grava(tmp_path, features):
    fc = {"type": "FeatureCollection", "features": features}
    p = tmp_path / "biomas.geojson"
    p.write_text(json.dumps(fc), encoding="utf-8")
    return str(p)


def test_identifica_dominante_e_ignora_bioma_que_nao_cruza(tmp_path):
    gleba = box(-47.10, -23.53, -47.09, -23.52)
    caminho = _grava(
        tmp_path,
        [
            {"type": "Feature", "properties": {"Bioma": "Mata Atlântica"},
             "geometry": mapping(box(-47.2, -23.6, -47.05, -23.5))},
            {"type": "Feature", "properties": {"Bioma": "Cerrado"},
             "geometry": mapping(box(-46.0, -22.0, -45.9, -21.9))},  # longe, não cruza
        ],
    )
    r = FonteBiomaArquivo(caminho).identificar(gleba)
    assert r.consultado is True
    assert r.dominante == "Mata Atlântica"
    assert [b.nome for b in r.biomas] == ["Mata Atlântica"]  # Cerrado fora
    assert r.biomas[0].pct > 0.99


def test_dois_biomas_ordenados_por_area(tmp_path):
    gleba = box(-47.10, -23.53, -47.08, -23.52)  # metade em cada
    caminho = _grava(
        tmp_path,
        [
            {"type": "Feature", "properties": {"Bioma": "Mata Atlântica"},
             "geometry": mapping(box(-47.10, -23.53, -47.09, -23.52))},  # metade oeste
            {"type": "Feature", "properties": {"Bioma": "Cerrado"},
             "geometry": mapping(box(-47.09, -23.53, -47.08, -23.52))},  # metade leste
        ],
    )
    r = FonteBiomaArquivo(caminho).identificar(gleba)
    assert {b.nome for b in r.biomas} == {"Mata Atlântica", "Cerrado"}
    # ordenado por área desc; soma ~100%
    assert r.biomas == sorted(r.biomas, key=lambda b: b.area_m2, reverse=True)
    assert abs(sum(b.pct for b in r.biomas) - 1.0) < 0.05


def test_sem_intersecao_degrada_honesto(tmp_path):
    gleba = box(-47.10, -23.53, -47.09, -23.52)
    caminho = _grava(
        tmp_path,
        [{"type": "Feature", "properties": {"Bioma": "Cerrado"},
          "geometry": mapping(box(-46.0, -22.0, -45.9, -21.9))}],
    )
    r = FonteBiomaArquivo(caminho).identificar(gleba)
    # leu o arquivo mas nada cruza a janela → consultado, dominante None, aviso honesto
    assert r.dominante is None
    assert r.avisos
