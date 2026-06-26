"""Camada por ARQUIVO LOCAL — leitura por JANELA (bbox) via pyogrio. Offline, sem rede.

O leitor lê só a janela da gleba de um vetor local (GeoJSON p/ recortes pequenos; GeoPackage/
shapefile p/ arquivos de estado/Brasil, usando ÍNDICE espacial). Testa ambos os formatos."""

import json

from app.core.camadas_inde import _ler_vetor_local_bbox


def _fc(*polys):
    return {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "properties": {"cod_imovel": f"IM{i}"},
             "geometry": {"type": "Polygon", "coordinates": [p]}}
            for i, p in enumerate(polys)
        ],
    }


def test_le_e_recorta_por_bbox(tmp_path):
    dentro = [(-47.14, -23.53), (-47.13, -23.53), (-47.13, -23.52), (-47.14, -23.52), (-47.14, -23.53)]
    fora = [(-40.0, -10.0), (-39.9, -10.0), (-39.9, -9.9), (-40.0, -9.9), (-40.0, -10.0)]
    p = tmp_path / "rl.geojson"
    p.write_text(json.dumps(_fc(dentro, fora)), encoding="utf-8")

    bbox = (-47.14, -23.53, -47.12, -23.51)  # bbox da gleba (só pega o polígono "dentro")
    feats = _ler_vetor_local_bbox(str(p), bbox)
    assert len(feats) == 1
    geom, props = feats[0]
    assert props["cod_imovel"] == "IM0"
    assert not geom.is_empty


def test_arquivo_vazio_nao_quebra(tmp_path):
    p = tmp_path / "vazio.geojson"
    p.write_text(json.dumps({"type": "FeatureCollection", "features": []}), encoding="utf-8")
    assert _ler_vetor_local_bbox(str(p), (-47.14, -23.53, -47.12, -23.51)) == []


def test_geopackage_le_so_a_janela_pelo_indice(tmp_path):
    """Escala estado/Brasil: num GeoPackage (com índice espacial) o bbox lê SÓ a janela da gleba —
    não carrega o arquivo todo. Mesma API do leitor; aqui prova o formato indexado."""
    import numpy as np
    from pyogrio.raw import write
    from shapely import wkb as _wkb
    from shapely.geometry import Polygon

    dentro = Polygon([(-47.14, -23.53), (-47.13, -23.53), (-47.13, -23.52), (-47.14, -23.52)])
    fora = Polygon([(-40.0, -10.0), (-39.9, -10.0), (-39.9, -9.9), (-40.0, -9.9)])
    gpkg = str(tmp_path / "rl.gpkg")
    write(
        gpkg,
        geometry=np.array([_wkb.dumps(dentro), _wkb.dumps(fora)], dtype=object),
        field_data=[np.array(["IM0", "IM1"])],
        fields=["cod_imovel"],
        geometry_type="Polygon",
        crs="EPSG:4326",
        driver="GPKG",
    )
    feats = _ler_vetor_local_bbox(gpkg, (-47.14, -23.53, -47.12, -23.51))
    assert len(feats) == 1
    geom, props = feats[0]
    assert props["cod_imovel"] == "IM0"
    assert not geom.is_empty
