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
    python3 -m pip install openpyxl   # só se for usar --fjp
    python3 scripts/gerar_localizacao_ibge.py --fjp ./dados_brutos/deficit_fjp.xlsx
    # sem --fjp: gera com deficit=null em todos (fallback de estoque assume)
    # --pib-ano: período do PIB dos Municípios (default 2023 = ano do ouro)
    # --gzip: grava .json.gz se o arquivo passar de alguns MB

Requer egress a `servicodados.ibge.gov.br`. O déficit FJP não tem API pública estável:
baixe a planilha municipal da FJP e PREPARE uma aba com as colunas `cod_ibge` (7 díg.),
`deficit` (inteiro) e `ano` — o download bruto da FJP não vem nesse layout.
"""

from __future__ import annotations

import argparse
import gzip
import json
import re
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
    req = urllib.request.Request(url, headers={"Accept-Encoding": "identity"})
    with urllib.request.urlopen(req, timeout=300) as resp:  # noqa: S310 (URL fixa do IBGE)
        bruto = resp.read()
    if bruto[:2] == b"\x1f\x8b":  # alguns endpoints respondem gzip mesmo pedindo identity
        bruto = gzip.decompress(bruto)
    return json.loads(bruto.decode("utf-8"))


def _variavel_por_nome(agregado: str, trecho: str, fallback: str) -> str:
    """Resolve o id da variável pelos METADADOS do agregado (não chuta id fixo).

    Caso real: no 5938, a v37 é o PIB *total* (mil R$); o per capita é outra variável.
    Buscar por nome ("per capita") torna a geração imune a esse engano.
    """
    try:
        meta = _get(f"{API}/{agregado}/metadados")
        for v in meta.get("variaveis", []):
            if trecho.lower() in str(v.get("nome", "")).lower():
                print(f"  variável {v['id']} = “{v['nome']}”", file=sys.stderr)
                return str(v["id"])
        print(f"  (aviso: nenhuma variável com “{trecho}” no agregado {agregado}; uso v{fallback})", file=sys.stderr)
    except Exception as exc:  # noqa: BLE001
        print(f"  (aviso: metadados do agregado {agregado} indisponíveis: {exc}; uso v{fallback})", file=sys.stderr)
    return fallback


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


def coletar_ibge(pib_ano: str) -> dict[str, dict]:
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

    # PIB per capita — PIB dos Municípios (agregado 5938). A variável é resolvida
    # pelos metadados ("per capita" no nome): a v37 é o PIB TOTAL em mil R$ — usar
    # ela quebra o gate de São Roque (3.450.779 ≠ 57.024,90), como visto na 1ª rodada.
    print(f"→ PIB per capita (agregado 5938, {pib_ano})…", file=sys.stderr)
    var_pib = _variavel_por_nome("5938", "per capita", fallback="593")
    pib = {}
    for nivel in ("N6", "N3", "N1"):
        pib.update(_valores_por_localidade("5938", var_pib, pib_ano, nivel))

    print("→ domicílios e moradores/domicílio (Censo 2022)…", file=sys.stderr)
    # Agregado 4712 = domicílios; v5930 moradores/domicílio (ajuste conforme o recorte real).
    dom = {}
    mpd = {}
    for nivel in ("N6", "N3", "N1"):
        dom.update(_valores_por_localidade("4712", "381", "2022", nivel))
        mpd.update(_valores_por_localidade("4712", "5930", "2022", nivel))

    print("→ faixa etária (Censo 2022, agregado 9514)…", file=sys.stderr)
    faixas = _coletar_faixa_etaria()

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
            "pib_ano": int(pib_ano),
            "domicilios_ocupados": int(dom[cod]) if cod in dom else None,
            "moradores_por_domicilio": round(mpd[cod], 2) if cod in mpd else None,
            "deficit": None,
            "faixa_etaria": faixas.get(cod),
        }
    _nomear(registros)
    return registros


def _coletar_faixa_etaria() -> dict[str, dict]:
    """Distribuição em 4 grupos a partir das faixas quinquenais do Censo 2022 (agregado 9514).

    Retorna {cod: {"0-14":.., "15-29":.., "30-59":.., "60+":..}} com Σ=1 (normalizado pelo
    próprio total dos grupos). A classificação de idade e as categorias quinquenais são
    resolvidas pelos METADADOS (sem id chutado): pega a classificação que contém a
    categoria "0 a 4 anos" e filtra "N a N+4 anos" + "100 anos ou mais" — evita somar
    grupos sobrepostos (ex.: "0 a 14 anos") em dobro. Best-effort: falhou → {} (faixa
    etária fica indisponível; o runtime degrada honesto para PARCIAL)."""
    agregado = "9514"
    try:
        meta = _get(f"{API}/{agregado}/metadados")
    except Exception as exc:  # noqa: BLE001
        print(f"  (aviso: metadados do {agregado} indisponíveis: {exc} — faixa etária fica null)", file=sys.stderr)
        return {}

    classif = None
    for c in meta.get("classificacoes", []):
        if any(str(cat.get("nome", "")).strip() == "0 a 4 anos" for cat in c.get("categorias", [])):
            classif = c
            break
    if classif is None:
        print("  (aviso: classificação de idade não encontrada no 9514 — faixa etária fica null)", file=sys.stderr)
        return {}

    # Só as quinquenais exatas (lb..lb+4) + "100 anos ou mais"; {id_categoria: idade_inicial}.
    cats: dict[str, int] = {}
    for cat in classif["categorias"]:
        nome = str(cat.get("nome", "")).strip()
        m = re.match(r"^(\d+) a (\d+) anos$", nome)
        if m and int(m.group(2)) == int(m.group(1)) + 4:
            cats[str(cat["id"])] = int(m.group(1))
        elif re.match(r"^100 anos ou mais$", nome):
            cats[str(cat["id"])] = 100
    if len(cats) < 21:
        print(f"  (aviso: só {len(cats)} categorias quinquenais no 9514 — confira o recorte)", file=sys.stderr)

    def _grupo(lb: int) -> str:
        return "0-14" if lb < 15 else "15-29" if lb < 30 else "30-59" if lb < 60 else "60+"

    somas: dict[str, dict[str, float]] = {}
    ids = ",".join(cats)
    for nivel in ("N6", "N3", "N1"):
        url = (
            f"{API}/{agregado}/periodos/2022/variaveis/93"
            f"?localidades={nivel}&classificacao={classif['id']}[{ids}]"
        )
        dados = _get(url)
        for var in dados:
            for res in var.get("resultados", []):
                # categoria deste resultado (a chave do dict 'categoria' é o id)
                cat_id = None
                for cl in res.get("classificacoes", []):
                    if str(cl.get("id")) == str(classif["id"]):
                        cat_id = next(iter(cl.get("categoria", {})), None)
                if cat_id not in cats:
                    continue
                grupo = _grupo(cats[cat_id])
                for serie in res.get("series", []):
                    cod = serie["localidade"]["id"]
                    bruto = serie.get("serie", {}).get("2022")
                    if bruto in (None, "...", "-", "X"):
                        continue
                    try:
                        v = float(bruto)
                    except ValueError:
                        continue
                    g = somas.setdefault(cod, {"0-14": 0.0, "15-29": 0.0, "30-59": 0.0, "60+": 0.0})
                    g[grupo] += v

    if "1" in somas:  # sanidade visível: Σ idades Brasil deve ≈ população 2022 (203.080.756)
        total_br = int(sum(somas["1"].values()))
        print(f"  Σ idades Brasil = {total_br:,} pessoas".replace(",", "."), file=sys.stderr)

    faixas: dict[str, dict] = {}
    for cod, g in somas.items():
        total = sum(g.values())
        if total <= 0:
            continue
        faixas[cod] = {k: round(v / total, 6) for k, v in g.items()}
    return faixas


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
        print(
            "  (aviso: openpyxl ausente — pulei o FJP; deficit fica null.\n"
            "   Para incluir o déficit: python3 -m pip install openpyxl  e rode de novo.)",
            file=sys.stderr,
        )
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
    if not fe:
        print(
            "⚠ AVISO: faixa etária veio VAZIA — o arquivo será aceito (degradação honesta → "
            "PARCIAL no runtime), mas confira a coleta do agregado 9514.",
            file=sys.stderr,
        )
    print("✓ valores-ouro de São Roque validados.", file=sys.stderr)


def main() -> None:
    ap = argparse.ArgumentParser(description="Gera o arquivo embarcado da Localização (Fase 6).")
    ap.add_argument("--fjp", type=Path, help="Planilha FJP do déficit habitacional municipal (.xlsx).")
    ap.add_argument("--gzip", action="store_true", help="Grava .json.gz em vez de .json.")
    ap.add_argument(
        "--pib-ano",
        default="2023",
        help="Período do PIB dos Municípios (default 2023 — é o ano do valor-ouro de São "
        "Roque; se mudar, atualize OURO_SAO_ROQUE junto, senão o gate recusa).",
    )
    ap.add_argument("--saida", type=Path, default=DESTINO)
    args = ap.parse_args()

    if args.pib_ano != "2023":
        print(
            f"⚠ AVISO: --pib-ano {args.pib_ano} ≠ 2023 (ano do ouro de São Roque). "
            "O gate vai recusar a menos que OURO_SAO_ROQUE['pib_per_capita'] seja atualizado.",
            file=sys.stderr,
        )

    registros = coletar_ibge(args.pib_ano)
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
