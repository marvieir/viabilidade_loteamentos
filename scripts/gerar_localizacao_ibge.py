#!/usr/bin/env python3
"""Pipeline (OFFLINE do runtime) — gera o arquivo embarcado da Fase 6 (Localização).

Consolida, por município + 27 UFs + Brasil:
  • população 2022 e 2010, área e densidade        — IBGE/SIDRA (Censo)
  • PIB per capita (ano mais recente do recorte)    — IBGE/SIDRA (PIB dos Municípios)
  • domicílios ocupados + moradores/domicílio       — IBGE/SIDRA (Censo 2022)
  • distribuição etária (0-14·15-29·30-59·60+)       — IBGE/SIDRA (Censo 2022)
  • déficit habitacional (quando no recorte)         — Fundação João Pinheiro (planilha local)

**Aquisição é pipeline, não agente** (ARCHITECTURE §2.5): roda na máquina do operador
(que tem egress ao IBGE), grava `backend/app/dados/localizacao_municipios.json[.gz]` com
cabeçalho de proveniência e **valida os valores-ouro de São Roque/SP antes de aceitar**.
O runtime nunca chama a rede — só lê o arquivo gerado.

Uso (no Mac do operador, a partir da raiz do repo):
    cd /caminho/para/viabilidade_loteamentos
    python3 scripts/gerar_localizacao_ibge.py --fjp ./dados_brutos/deficit_fjp.xlsx
    # sem --fjp: gera com deficit=null em todos (fallback de estoque assume)
    # --gzip: grava .json.gz se o arquivo passar de alguns MB

Requer egress a `servicodados.ibge.gov.br`. O déficit FJP não tem API pública estável:
baixe a planilha municipal da FJP e aponte com --fjp (colunas cod_ibge, deficit, ano).
"""

from __future__ import annotations

import argparse
import gzip
import json
import sys
import urllib.request
from datetime import date
from pathlib import Path
from typing import Optional

API = "https://servicodados.ibge.gov.br/api/v3/agregados"
RAIZ = Path(__file__).resolve().parent.parent
DESTINO = RAIZ / "backend" / "app" / "dados" / "localizacao_municipios.json"

# Valores-ouro (São Roque/SP, 3550605, fonte IBGE) — gate de aceite da geração.
OURO_SAO_ROQUE = {
    "pop_2022": 79484,
    "pop_2010": 78821,
    "densidade": 258.98,
    "pib_per_capita": 57024.90,
    "moradores_por_domicilio": 2.79,
}


def _get(url: str) -> list | dict:
    with urllib.request.urlopen(url, timeout=60) as resp:  # noqa: S310 (URL fixa do IBGE)
        return json.loads(resp.read().decode("utf-8"))


def _valores_por_localidade(agregado: str, variavel: str, periodo: str, nivel: str) -> dict[str, float]:
    """Retorna {cod_localidade: valor} para um agregado/variável/período do SIDRA v3."""
    url = f"{API}/{agregado}/periodos/{periodo}/variaveis/{variavel}?localidades={nivel}"
    dados = _get(url)
    out: dict[str, float] = {}
    for var in dados:
        for res in var.get("resultados", []):
            for serie in res.get("series", []):
                cod = serie["localidade"]["id"]
                valores = serie.get("serie", {})
                bruto = valores.get(periodo)
                if bruto not in (None, "...", "-", "X"):
                    try:
                        out[cod] = float(bruto)
                    except ValueError:
                        pass
    return out


def coletar_ibge() -> dict[str, dict]:
    """Monta os registros por município/UF/Brasil a partir do SIDRA. Best-effort por bloco."""
    # Níveis SIDRA: N6 = município, N3 = UF, N1 = Brasil.
    registros: dict[str, dict] = {}

    print("→ população 2022 (Censo, agregado 4714 v93)…", file=sys.stderr)
    pop22 = {}
    for nivel in ("N6", "N3", "N1"):
        pop22.update(_valores_por_localidade("4714", "93", "2022", nivel))
    print("→ densidade 2022 (agregado 4714 v614)…", file=sys.stderr)
    dens = {}
    for nivel in ("N6", "N3", "N1"):
        dens.update(_valores_por_localidade("4714", "614", "2022", nivel))
    print("→ população 2010 (Censo, agregado 1378 v93)…", file=sys.stderr)
    pop10 = {}
    for nivel in ("N6", "N3", "N1"):
        pop10.update(_valores_por_localidade("1378", "93", "2010", nivel))

    # PIB per capita — PIB dos Municípios (agregado 5938, variável 37 = PIB per capita).
    # Ajuste o período para o ano mais recente disponível no recorte.
    print("→ PIB per capita (agregado 5938 v37, 2021)…", file=sys.stderr)
    pib = {}
    for nivel in ("N6", "N3", "N1"):
        pib.update(_valores_por_localidade("5938", "37", "2021", nivel))
    pib_ano = 2021

    print("→ domicílios e moradores/domicílio (Censo 2022)…", file=sys.stderr)
    # Agregado 4712 = domicílios; v5930 moradores/domicílio (ajuste conforme o recorte real).
    dom = {}
    mpd = {}
    for nivel in ("N6", "N3", "N1"):
        dom.update(_valores_por_localidade("4712", "381", "2022", nivel))
        mpd.update(_valores_por_localidade("4712", "5930", "2022", nivel))

    print("→ faixa etária (Censo 2022, agregado 9514)…", file=sys.stderr)
    faixas = _coletar_faixa_etaria()

    def _chave(cod: str) -> str:
        if len(cod) == 7:
            return cod  # município
        return "BR" if cod == "1" else None  # Brasil; UF tratada à parte

    todos_cods = set(pop22) | set(pop10) | set(pib)
    for cod in todos_cods:
        if len(cod) == 7:
            chave, nivel = cod, "municipio"
        elif len(cod) == 2:
            chave, nivel = f"UF:{_sigla_uf(cod)}", "uf"
        elif cod == "1":
            chave, nivel = "BR", "brasil"
        else:
            continue
        registros[chave] = {
            "nivel": nivel,
            "cod": cod,
            "nome": None,  # preenchido abaixo pelos metadados de localidades
            "uf": _sigla_uf(cod[:2]) if nivel == "municipio" else (_sigla_uf(cod) if nivel == "uf" else None),
            "pop_2022": int(pop22[cod]) if cod in pop22 else None,
            "pop_2010": int(pop10[cod]) if cod in pop10 else None,
            "area_km2": round(pop22[cod] / dens[cod], 3) if cod in dens and cod in pop22 and dens.get(cod) else None,
            "pib_per_capita": round(pib[cod], 2) if cod in pib else None,
            "pib_ano": pib_ano,
            "domicilios_ocupados": int(dom[cod]) if cod in dom else None,
            "moradores_por_domicilio": round(mpd[cod], 2) if cod in mpd else None,
            "deficit": None,
            "faixa_etaria": faixas.get(cod),
        }
    _nomear(registros)
    return registros


def _coletar_faixa_etaria() -> dict[str, dict]:
    """Distribuição em 4 grupos a partir das faixas quinquenais do Censo 2022.

    Retorna {cod: {"0-14":.., "15-29":.., "30-59":.., "60+":..}} com Σ=1 (normalizado).
    Ajuste o agregado/variável/classificação ao recorte real do SIDRA antes de rodar.
    """
    # Implementação dependente do recorte do SIDRA (agregado 9514, classificação de idade).
    # Mantida como gancho explícito: some as quinquenais nos 4 grupos e normalize Σ=1.
    return {}


def _sigla_uf(cod2: str) -> Optional[str]:
    return _UF_POR_COD.get(cod2)


def _nomear(registros: dict[str, dict]) -> None:
    """Preenche os nomes a partir de /localidades (município e UF)."""
    try:
        muns = {str(m["id"]): m["nome"] for m in _get("https://servicodados.ibge.gov.br/api/v1/localidades/municipios")}
        ufs = {str(u["id"]): u["nome"] for u in _get("https://servicodados.ibge.gov.br/api/v1/localidades/estados")}
    except Exception as exc:  # noqa: BLE001
        print(f"  (aviso: nomes não resolvidos: {exc})", file=sys.stderr)
        return
    for chave, reg in registros.items():
        if reg["nivel"] == "municipio":
            reg["nome"] = muns.get(reg["cod"], reg["nome"])
        elif reg["nivel"] == "uf":
            reg["nome"] = ufs.get(reg["cod"], reg["nome"])
        elif reg["nivel"] == "brasil":
            reg["nome"] = "Brasil"


def aplicar_fjp(registros: dict[str, dict], caminho: Path) -> int:
    """Carrega déficit habitacional municipal da FJP (planilha) → preenche reg['deficit'].

    Espera colunas: cod_ibge (7 díg.), deficit (inteiro), ano. Município ausente fica null
    (fallback de estoque assume no runtime). NUNCA estima.
    """
    try:
        import openpyxl  # opcional; só o operador com a planilha precisa
    except ImportError:
        print("  (aviso: openpyxl ausente — pulei o FJP; deficit fica null)", file=sys.stderr)
        return 0
    wb = openpyxl.load_workbook(caminho, read_only=True, data_only=True)
    ws = wb.active
    cabecalho = [str(c.value).strip().lower() if c.value else "" for c in next(ws.iter_rows(max_row=1))]
    try:
        i_cod = cabecalho.index("cod_ibge")
        i_def = cabecalho.index("deficit")
        i_ano = cabecalho.index("ano")
    except ValueError:
        print("  (aviso: planilha FJP sem colunas cod_ibge/deficit/ano — pulei)", file=sys.stderr)
        return 0
    n = 0
    for row in ws.iter_rows(min_row=2):
        cod = str(row[i_cod].value).split(".")[0].zfill(7) if row[i_cod].value else None
        if cod and cod in registros and row[i_def].value is not None:
            registros[cod]["deficit"] = {
                "valor": int(row[i_def].value),
                "fonte": "FJP",
                "ano": int(row[i_ano].value),
            }
            n += 1
    return n


def validar_ouro(registros: dict[str, dict]) -> None:
    """Gate: o arquivo só é aceito se São Roque bater os valores-ouro (±tolerância)."""
    reg = registros.get("3550605")
    if reg is None:
        raise SystemExit("ERRO: São Roque (3550605) ausente do recorte — não gravo.")
    densidade = round(reg["pop_2022"] / reg["area_km2"], 2) if reg.get("area_km2") else None
    checks = {
        "pop_2022": (reg.get("pop_2022"), OURO_SAO_ROQUE["pop_2022"], 0),
        "pop_2010": (reg.get("pop_2010"), OURO_SAO_ROQUE["pop_2010"], 0),
        "densidade": (densidade, OURO_SAO_ROQUE["densidade"], 0.05),
        "pib_per_capita": (reg.get("pib_per_capita"), OURO_SAO_ROQUE["pib_per_capita"], 0.01),
        "moradores_por_domicilio": (reg.get("moradores_por_domicilio"), OURO_SAO_ROQUE["moradores_por_domicilio"], 0.01),
    }
    erros = []
    for nome, (obtido, esperado, tol) in checks.items():
        if obtido is None or abs(obtido - esperado) > tol:
            erros.append(f"  {nome}: obtido {obtido} ≠ ouro {esperado} (tol {tol})")
    fe = reg.get("faixa_etaria")
    if fe and abs(sum(fe.values()) - 1.0) > 0.001:
        erros.append(f"  faixa_etaria Σ = {sum(fe.values()):.4f} ≠ 1,000")
    if erros:
        raise SystemExit("ERRO: São Roque não bateu os valores-ouro — NÃO gravei:\n" + "\n".join(erros))
    print("✓ valores-ouro de São Roque validados.", file=sys.stderr)


def main() -> None:
    ap = argparse.ArgumentParser(description="Gera o arquivo embarcado da Localização (Fase 6).")
    ap.add_argument("--fjp", type=Path, help="Planilha FJP do déficit habitacional municipal (.xlsx).")
    ap.add_argument("--gzip", action="store_true", help="Grava .json.gz em vez de .json.")
    ap.add_argument("--saida", type=Path, default=DESTINO)
    args = ap.parse_args()

    registros = coletar_ibge()
    n_fjp = aplicar_fjp(registros, args.fjp) if args.fjp else 0
    validar_ouro(registros)

    dataset = {
        "_meta": {
            "data_geracao": date.today().isoformat(),
            "fontes": "IBGE — SIDRA (Censo Demográfico 2022 e 2010; PIB dos Municípios) e "
            "Fundação João Pinheiro (Déficit Habitacional Municipal)",
            "nota": f"Gerado por scripts/gerar_localizacao_ibge.py. {n_fjp} municípios com déficit FJP; "
            "os demais usam fallback de estoque de domicílios (NÃO é o déficit).",
            "niveis": ["municipio", "uf", "brasil"],
        },
        "registros": registros,
    }

    saida = args.saida
    if args.gzip:
        saida = saida.with_suffix(".json.gz")
        with gzip.open(saida, "wt", encoding="utf-8") as fh:
            json.dump(dataset, fh, ensure_ascii=False)
    else:
        saida.write_text(json.dumps(dataset, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✓ gravado {saida} ({len(registros)} registros).", file=sys.stderr)


_UF_POR_COD = {
    "11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP", "17": "TO",
    "21": "MA", "22": "PI", "23": "CE", "24": "RN", "25": "PB", "26": "PE", "27": "AL",
    "28": "SE", "29": "BA", "31": "MG", "32": "ES", "33": "RJ", "35": "SP", "41": "PR",
    "42": "SC", "43": "RS", "50": "MS", "51": "MT", "52": "GO", "53": "DF",
}


if __name__ == "__main__":
    main()
