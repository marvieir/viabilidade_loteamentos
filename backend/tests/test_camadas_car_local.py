"""CAR/Reserva Legal por ARQUIVO LOCAL (GeoJSON) — offline, sem rede.

O geoserver legado do CAR está fora do ar; o caminho realista é o operador apontar
``AMBIENTAL_CAR_RL_PATH`` p/ um GeoJSON do município. Testa o leitor (recorte por bbox)."""

import json

from app.core.camadas_inde import _geojson_local_no_bbox


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
    feats = _geojson_local_no_bbox(str(p), bbox)
    assert len(feats) == 1
    geom, props = feats[0]
    assert props["cod_imovel"] == "IM0"
    assert not geom.is_empty


def test_arquivo_vazio_nao_quebra(tmp_path):
    p = tmp_path / "vazio.geojson"
    p.write_text(json.dumps({"type": "FeatureCollection", "features": []}), encoding="utf-8")
    assert _geojson_local_no_bbox(str(p), (-47.14, -23.53, -47.12, -23.51)) == []
