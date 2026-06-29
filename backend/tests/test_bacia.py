"""Tier 2 — bacia hidrográfica (ANA) sobre a gleba."""

import json

from shapely.geometry import box, mapping

from app.core.bacia import FonteBaciaArquivo


def _grava(tmp_path, features):
    p = tmp_path / "bacias.geojson"
    p.write_text(json.dumps({"type": "FeatureCollection", "features": features}), encoding="utf-8")
    return str(p)


def test_extrai_niveis_e_pega_maior_intersecao(tmp_path):
    gleba = box(-47.10, -23.53, -47.09, -23.52)
    caminho = _grava(
        tmp_path,
        [
            {"type": "Feature",
             "properties": {"rhi_nm": "Atlântico Sudeste", "nm_bacia": "Tietê", "nm_sub_bac": "Sorocaba"},
             "geometry": mapping(box(-47.3, -23.7, -47.0, -23.4))},  # cobre a gleba
            {"type": "Feature",
             "properties": {"rhi_nm": "Paraná", "nm_bacia": "Paranapanema", "nm_sub_bac": "X"},
             "geometry": mapping(box(-46.0, -22.0, -45.9, -21.9))},  # longe
        ],
    )
    r = FonteBaciaArquivo(caminho).identificar(gleba)
    assert r.consultado is True
    assert r.regiao_hidrografica == "Atlântico Sudeste"
    assert r.bacia == "Tietê"
    assert r.sub_bacia == "Sorocaba"


def test_campo_nao_reconhecido_avisa(tmp_path):
    gleba = box(-47.10, -23.53, -47.09, -23.52)
    caminho = _grava(
        tmp_path,
        [{"type": "Feature", "properties": {"campo_exotico": "Foo"},
          "geometry": mapping(box(-47.2, -23.6, -47.0, -23.5))}],
    )
    r = FonteBaciaArquivo(caminho).identificar(gleba)
    assert r.consultado is True
    assert r.regiao_hidrografica is None and r.bacia is None and r.sub_bacia is None
    assert r.avisos  # avisa pra configurar AMBIENTAL_BACIA_CAMPO_*


def test_sem_intersecao_degrada(tmp_path):
    gleba = box(-47.10, -23.53, -47.09, -23.52)
    caminho = _grava(
        tmp_path,
        [{"type": "Feature", "properties": {"nm_bacia": "Outra"},
          "geometry": mapping(box(-46.0, -22.0, -45.9, -21.9))}],
    )
    r = FonteBaciaArquivo(caminho).identificar(gleba)
    assert r.bacia is None and r.avisos
