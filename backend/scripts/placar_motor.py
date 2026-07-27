"""INTEL-1 — PLACAR do motor sobre o corpus de glebas-ouro (docs/fase-motor-intel.md).

Uso (no container):
    python -m scripts.placar_motor                     # roda e compara com a base
    python -m scripts.placar_motor --fixar-base        # promove o placar atual a base
    python -m scripts.placar_motor --publicos media    # restringe públicos (vírgula)
    python -m scripts.placar_motor --corpus /caminho   # corpus alternativo

Determinístico e SEM IA: programa do PRESET por público, K variantes de ``VARIANTES_U4``
e a função de valor escolhem — mesma entrada → mesmo placar (§4). Corpus: um JSON por
caso: ``{"gleba_wkt" | "gleba_geojson", "restricao_wkt"?, "publicos"?}``. Glebas de
clientes vivem só no volume do operador (privacidade) — o repositório traz sintéticas.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

PUBLICOS_DEFAULT = ("baixa", "media", "alta")
TOL_PP = 1.0  # pontos percentuais: piora acima disto vira REGRESSÃO no comparativo


def _dir_corpus(cli: str | None) -> Path:
    if cli:
        return Path(cli)
    env = os.getenv("CORPUS_MOTOR_DIR", "").strip()
    if env:
        return Path(env)
    return Path("/data/perfis/corpus") if os.path.isdir("/data/perfis") else Path("scripts/corpus")


def _carregar_gleba(entrada: dict):
    from shapely import wkt as _wkt
    from shapely.geometry import shape

    if entrada.get("gleba_wkt"):
        return _wkt.loads(entrada["gleba_wkt"])
    return shape(entrada["gleba_geojson"])


def medir_caso(entrada: dict, publico: str) -> dict:
    """KPIs do MELHOR layout (função de valor sobre as K variantes) para (gleba, público).
    Puro e determinístico — é a unidade que o teste-ouro e o placar compartilham."""
    from shapely import wkt as _wkt
    from shapely.ops import transform as sht

    from app.core import urbanismo_geom as geom
    from app.core import urbanismo_medida as medida
    from app.core.urbanismo_diretrizes import resolver_diretrizes
    from app.core.urbanismo_estilo import carregar_estilo
    from app.core.urbanismo_programa import programa_do_preset
    from app.routers.urbanismo import VARIANTES_U4

    gleba = _carregar_gleba(entrada)
    restr = _wkt.loads(entrada["restricao_wkt"]) if entrada.get("restricao_wkt") else None
    to_local, _ = medida.transformadores([gleba])
    gleba_m = sht(to_local, gleba)
    restr_m = sht(to_local, restr) if restr is not None else None
    aprov_m = gleba_m.difference(restr_m) if restr_m is not None else gleba_m

    prog = programa_do_preset(publico)
    estilo, _aviso = carregar_estilo(publico)
    diretrizes = resolver_diretrizes(None, None, None, publico)

    melhor = None
    for var in VARIANTES_U4:
        layout = geom.gerar_layout(
            aprov_m, prog, diretrizes=diretrizes, restricao_externa=restr_m,
            variante=var, estilo=estilo,
        )
        med = medida.medir(layout, publico_alvo=publico)
        valor = sum(
            (p.get("area_m2") or 0.0) * (p.get("multiplicador") or 1.0)
            for p in med.heatmap.get("por_lote", [])
        )
        cand = (valor, len(layout.lotes), str(var["id"]), layout, med)
        if melhor is None or (cand[0], cand[1]) > (melhor[0], melhor[1]):
            melhor = cand

    _valor, _n, var_id, layout, med = melhor
    q = med.quadro
    liq = q.get("area_liquida_m2") or 1.0

    def _pct(chave: str) -> float:
        item = q.get(chave) or {}
        return round(100.0 * (item.get("m2") or 0.0) / liq, 1)

    return {
        "variante": var_id,
        "n_lotes": int(med.indicadores.get("n_lotes") or 0),
        "area_media_m2": med.indicadores.get("area_media_m2"),
        "vendavel_pct": _pct("vendavel"),
        "sobra_pct": _pct("sobra_geometrica"),
        "viario_pct": _pct("arruamento"),
        "verde_pct": _pct("areas_verdes"),
        "lazer_pct": _pct("sistema_lazer"),
        "viario_conexo": bool((layout.viario_diagnostico or {}).get("conexo", False)),
    }


def rodar_placar(corpus: Path, publicos: tuple[str, ...]) -> dict:
    casos = sorted(corpus.glob("*.json"))
    casos = [c for c in casos if c.name not in ("placar.json", "placar_base.json")]
    if not casos:
        raise SystemExit(f"Corpus vazio em {corpus} — adicione casos (ver docs/fase-motor-intel.md).")
    placar: dict = {}
    for caso in casos:
        entrada = json.loads(caso.read_text(encoding="utf-8"))
        pubs = tuple(entrada.get("publicos") or publicos)
        for pub in pubs:
            if pub not in publicos:
                continue
            chave = f"{caso.stem}/{pub}"
            print(f"  medindo {chave}…", flush=True)
            placar[chave] = medir_caso(entrada, pub)
    return placar


# KPIs em que MAIOR é melhor / MENOR é melhor (p/ o comparativo com a base).
_MAIOR_MELHOR = ("vendavel_pct", "n_lotes")
_MENOR_MELHOR = ("sobra_pct", "viario_pct")


def comparar(base: dict, atual: dict) -> list[str]:
    linhas: list[str] = []
    for chave, kpis in atual.items():
        ref = base.get(chave)
        if ref is None:
            linhas.append(f"{chave}: NOVO caso (sem base)")
            continue
        difs = []
        regrediu = False
        for k in (*_MAIOR_MELHOR, *_MENOR_MELHOR):
            a, b = kpis.get(k), ref.get(k)
            if a is None or b is None:
                continue
            delta = round(float(a) - float(b), 1)
            if abs(delta) < 0.05:
                continue
            melhora = delta > 0 if k in _MAIOR_MELHOR else delta < 0
            seta = "▲" if melhora else "▼"
            if not melhora and abs(delta) > (TOL_PP if k.endswith("_pct") else 0):
                regrediu = True
            difs.append(f"{k} {seta}{delta:+g}")
        marca = "  ⚠️ REGRESSÃO" if regrediu else ""
        linhas.append(f"{chave}: {'; '.join(difs) or 'sem mudança'}{marca}")
    return linhas


def main() -> None:
    ap = argparse.ArgumentParser(description="Placar do motor (INTEL-1)")
    ap.add_argument("--corpus", default=None)
    ap.add_argument("--publicos", default=",".join(PUBLICOS_DEFAULT))
    ap.add_argument("--fixar-base", action="store_true")
    args = ap.parse_args()

    corpus = _dir_corpus(args.corpus)
    publicos = tuple(p.strip() for p in args.publicos.split(",") if p.strip())
    print(f"PLACAR DO MOTOR — corpus: {corpus} | públicos: {', '.join(publicos)}")
    placar = rodar_placar(corpus, publicos)

    print("\n== KPIs (melhor variante pela função de valor) ==")
    for chave, k in placar.items():
        print(f"{chave:32s} [{k['variante']}] lotes={k['n_lotes']:4d} "
              f"vendável={k['vendavel_pct']:5.1f}% sobra={k['sobra_pct']:5.1f}% "
              f"viário={k['viario_pct']:5.1f}% verde={k['verde_pct']:4.1f}% "
              f"lazer={k['lazer_pct']:4.1f}% conexo={'S' if k['viario_conexo'] else 'N'}")

    (corpus / "placar.json").write_text(
        json.dumps(placar, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    base_path = corpus / "placar_base.json"
    if base_path.exists():
        base = json.loads(base_path.read_text(encoding="utf-8"))
        print("\n== Comparação com a base ==")
        for linha in comparar(base, placar):
            print(linha)
    else:
        print("\n(sem placar_base.json — rode com --fixar-base para criar a referência)")
    if args.fixar_base:
        base_path.write_text(
            json.dumps(placar, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"\nBase fixada em {base_path}")


if __name__ == "__main__":
    sys.exit(main())
