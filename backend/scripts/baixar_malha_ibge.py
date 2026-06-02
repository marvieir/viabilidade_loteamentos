#!/usr/bin/env python3
"""Pipeline de aquisição da malha municipal IBGE → GeoJSON local (não agente).

Baixa, junta e cacheia a malha que `app.core.malha_ibge.FonteMalhaArquivo` consome,
ligando a DETECÇÃO AUTOMÁTICA de município (plano A da Fase 1.7). Use uma vez (ou em
refresh agendado); aponte o resultado em `MALHA_IBGE_PATH`.

    python -m scripts.baixar_malha_ibge --saida app/perfis/malha_ibge.geojson
    export MALHA_IBGE_PATH=app/perfis/malha_ibge.geojson

Fontes (IBGE servicodados):
  - Nomes/UF:   /api/v1/localidades/municipios
  - Geometria:  /api/v3/malhas/estados/{UF}?formato=application/vnd.geo+json
                &intrarregiao=municipio   (por UF; concatenadas)

ATENÇÃO: o egress de rede deste ambiente está bloqueado (HTTP 403), então este script
**não foi validado ao vivo** aqui. A LÓGICA DE JUNÇÃO está coberta por teste offline
(`tests/test_malha_ibge.py`); apenas as chamadas HTTP dependem de rede liberada
(rode localmente ou habilite o acesso a servicodados.ibge.gov.br).
"""

import argparse
import json
import sys
import time
import urllib.request

from app.core import malha_ibge

BASE = "https://servicodados.ibge.gov.br"
UFS = [
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS",
    "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC",
    "SP", "SE", "TO",
]


def _get_json(url: str, tentativas: int = 4) -> object:
    espera = 2
    for i in range(tentativas):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "viab-malha/1.7"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001 — pipeline de linha de comando
            if i == tentativas - 1:
                raise
            print(f"  retry {i + 1}/{tentativas} ({exc}); aguardando {espera}s", file=sys.stderr)
            time.sleep(espera)
            espera *= 2
    raise RuntimeError("inalcançável")


def baixar(saida: str) -> None:
    print("→ localidades (nomes/UF)…", file=sys.stderr)
    localidades = _get_json(f"{BASE}/api/v1/localidades/municipios")

    features: list[dict] = []
    for uf in UFS:
        print(f"→ malha {uf}…", file=sys.stderr)
        url = (
            f"{BASE}/api/v3/malhas/estados/{uf}"
            "?formato=application/vnd.geo+json&intrarregiao=municipio"
        )
        fc = _get_json(url)
        features.extend(fc.get("features", []))

    geojson = malha_ibge.montar_geojson(localidades, features)
    n = len(geojson["features"])
    with open(saida, "w", encoding="utf-8") as fh:
        json.dump(geojson, fh, ensure_ascii=False)
    print(f"✓ {n} municípios escritos em {saida}", file=sys.stderr)
    if n < 5000:
        print("⚠ esperado ~5.570 municípios; verifique a cobertura.", file=sys.stderr)


def main() -> None:
    ap = argparse.ArgumentParser(description="Baixa a malha municipal IBGE → GeoJSON.")
    ap.add_argument("--saida", default="app/perfis/malha_ibge.geojson")
    baixar(ap.parse_args().saida)


if __name__ == "__main__":
    main()
