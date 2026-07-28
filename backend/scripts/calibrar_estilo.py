"""INTEL-4 — CLI da calibração do estilo pelos projetos importados (spec: docs/fase-intel-4.md).

Varre o store de urbanismo, extrai as métricas de cada PROJETO IMPORTADO, agrega por padrão
e imprime o relatório + as propostas de ajuste. Grava ``proposta_estilo.json`` no diretório
de estilo.

**NÃO altera o estilo vigente.** Quem promove é o operador, com ``--aplicar`` — e mesmo aí a
gravação é explícita, arquivo por arquivo, com o antes e o depois impressos.

Uso (dentro do container da api):

    python -m scripts.calibrar_estilo                 # relatório + proposta_estilo.json
    python -m scripts.calibrar_estilo --aplicar       # promove as propostas para {perfil}.json

Variáveis: ``URBANISMO_DIR`` (store das propostas) e ``ESTILO_URBANISMO_DIR`` (perfis de
estilo) — as mesmas do compose.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core import urbanismo_calibracao as calib  # noqa: E402
from app.core.urbanismo_estilo import carregar_estilo  # noqa: E402


def _snapshots(diretorio: Path):
    """Todas as propostas salvas no store (um arquivo JSON por análise, lista de propostas)."""
    for arq in sorted(diretorio.glob("*.json")):
        try:
            dados = json.loads(arq.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            print(f"  ! {arq.name} ignorado ({exc})")
            continue
        for prop in dados if isinstance(dados, list) else [dados]:
            if isinstance(prop, dict):
                yield prop


def _fmt_pct(v) -> str:
    return f"{v * 100:.1f}%" if isinstance(v, (int, float)) else "—"


def _fmt_num(v) -> str:
    return f"{v:,.1f}".replace(",", ".") if isinstance(v, (int, float)) else "—"


def main() -> int:
    ap = argparse.ArgumentParser(description="Calibração do estilo pelos projetos importados")
    ap.add_argument("--aplicar", action="store_true",
                    help="promove as propostas para os {perfil}.json (o padrão é só propor)")
    args = ap.parse_args()

    store = Path(os.getenv("URBANISMO_DIR", "/data/perfis/urbanismo"))
    dir_estilo = Path(os.getenv("ESTILO_URBANISMO_DIR", "/data/perfis/estilo-urbanismo"))
    if not store.exists():
        print(f"Store de urbanismo não encontrado: {store}")
        return 1

    metricas = [
        m for m in (calib.metricas_do_projeto(s) for s in _snapshots(store)) if m
    ]
    if not metricas:
        print("Nenhum projeto IMPORTADO no store — a calibração aprende com DWG de cliente.")
        print("Importe projetos pelo card Urbanismo e rode de novo.")
        return 0

    print(f"\nProjetos importados encontrados: {len(metricas)}\n")
    for m in metricas:
        origem = "declarado" if m["padrao_origem"] == "declarado" else "INFERIDO"
        print(f"  · {m['arquivo']}  [{m['padrao']} — {origem}]  {m['n_lotes']} lotes")
        print(f"      lote  mediana {_fmt_num(m['lote_area_mediana_m2'])} m²  "
              f"testada {_fmt_num(m['lote_testada_mediana_m'])} m  "
              f"prof {_fmt_num(m['lote_prof_mediana_m'])} m")
        print(f"      quadra {_fmt_num(m['quadra_area_mediana_m2'])} m² / "
              f"{_fmt_num(m['quadra_lotes_mediana'])} lotes  |  "
              f"vendável {_fmt_pct(m['vendavel_frac'])}  verde {_fmt_pct(m['verde_frac'])}  "
              f"lazer {_fmt_pct(m['lazer_frac'])}  viário {_fmt_pct(m['viario_frac'])}")

    agregado = calib.agregar(metricas)
    print("\nAgregado por padrão:")
    for padrao, bloco in agregado.items():
        marca = "✓ evidência suficiente" if bloco["suficiente"] else (
            f"insuficiente (mínimo {calib.MIN_PROJETOS} projetos) — mostra, não propõe"
        )
        print(f"\n  [{padrao}] {bloco['n_projetos']} projeto(s) — {marca}")
        for campo, r in bloco["metricas"].items():
            print(f"      {campo:26s} mediana {_fmt_num(r['mediana'])} "
                  f"(faixa {_fmt_num(r['min'])}–{_fmt_num(r['max'])}, n={r['n']})")

    estilos = {p: carregar_estilo(p)[0] for p in ("baixa", "media", "alta")}
    propostas = calib.propor_ajustes(agregado, estilos)

    print("\n" + "=" * 72)
    if not propostas:
        print("NENHUMA proposta de ajuste — ou falta evidência, ou o estilo vigente já está")
        print("dentro do que os projetos importados mostram.")
    else:
        print(f"PROPOSTAS DE AJUSTE ({len(propostas)}):\n")
        for p in propostas:
            print(f"  [{p['padrao']}] {p['knob']}: {p['vigente']} → {p['proposto']} "
                  f"(delta {p['delta']:+.4f})")
            print(f"      {p['proveniencia']}")
            print(f"      dispersão {p['dispersao'][0]}–{p['dispersao'][1]} | "
                  f"projetos: {', '.join(p['projetos'])}")

    dir_estilo.mkdir(parents=True, exist_ok=True)
    destino = dir_estilo / "proposta_estilo.json"
    destino.write_text(
        json.dumps({"agregado": agregado, "propostas": propostas}, ensure_ascii=False,
                   indent=2, default=str),
        encoding="utf-8",
    )
    print(f"\nRelatório completo: {destino}")

    if not args.aplicar:
        if propostas:
            print("Para promover: python -m scripts.calibrar_estilo --aplicar")
        return 0

    if not propostas:
        print("Nada a aplicar.")
        return 0

    for padrao in sorted({p["padrao"] for p in propostas}):
        caminho = dir_estilo / f"{padrao}.json"
        atual = {}
        if caminho.exists():
            try:
                atual = json.loads(caminho.read_text(encoding="utf-8"))
            except ValueError:
                atual = {}
        for p in (x for x in propostas if x["padrao"] == padrao):
            print(f"  {padrao}.{p['knob']}: {p['vigente']} → {p['proposto']}")
            atual[p["knob"]] = p["proposto"]
        caminho.write_text(json.dumps(atual, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  gravado: {caminho}")
    print("\nAplicado. Rode o placar (python -m scripts.placar_motor) para medir o efeito.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
