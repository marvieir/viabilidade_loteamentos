"""Fase 6 — Localização (enriquecimento socioeconômico IBGE).

Dimensão **puramente informativa** (§1-A): contexto socioeconômico do município da
gleba. **Não entra em nenhum cálculo de viabilidade** — nenhum campo daqui é lido por
outro router (critério-coração nº 8). Lê um **arquivo embarcado** consolidado
(municípios + 27 UFs + Brasil), sem rede e sem LLM em runtime; as razões UF/Brasil e as
leituras são calculadas aqui no backend a partir das próprias linhas do arquivo.

Tudo formatável carrega o par ``valor`` + ``*_fmt`` pt-BR gerado aqui (o front só
renderiza, §2). O dado é estático → o GET recalcula do arquivo a cada chamada, sem
persistência (decisão §3.7 da spec).
"""

from __future__ import annotations

import gzip
import json
import os
from pathlib import Path
from typing import Optional, Protocol, runtime_checkable

from app.models import schemas

_ARQUIVO_DEFAULT = (
    Path(__file__).resolve().parent.parent / "dados" / "localizacao_municipios.json"
)

# Aviso §1-A fixo — herdado por toda dimensão: o card é contexto, não veredito.
AVISO_INFORMATIVO = (
    "Enriquecimento INFORMATIVO (§1-A): contexto socioeconômico do município — não "
    "entra em nenhum cálculo de viabilidade e não é análise de mercado."
)


# ----- Formatação pt-BR (no backend; o front não reformata, §2) -----
def _int_br(v: int) -> str:
    return f"{v:,}".replace(",", ".")


def _dec_br(v: float, casas: int = 2) -> str:
    return f"{v:,.{casas}f}".replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def _pct_br(frac: float, casas: int = 2) -> str:
    return _dec_br(frac * 100, casas) + "%"


def _brl(v: float) -> str:
    return "R$ " + _dec_br(v, 2)


# ----- Acesso ao arquivo embarcado (fonte injetável) -----
@runtime_checkable
class FonteLocalizacao(Protocol):
    """Dataset de localização (municípios + UFs + Brasil). Real: ``FonteLocalizacaoArquivo``."""

    def carregar(self) -> Optional[dict]:
        """Dataset completo ``{_meta, registros}`` ou None se indisponível."""


class FonteLocalizacaoArquivo:
    """Lê o JSON embarcado (aceita ``.json`` ou ``.json.gz``). Degrada honesto → None."""

    def __init__(self, caminho: str | os.PathLike):
        self.caminho = Path(caminho)

    def carregar(self) -> Optional[dict]:
        try:
            if self.caminho.suffix == ".gz":
                with gzip.open(self.caminho, "rt", encoding="utf-8") as fh:
                    return json.load(fh)
            return json.loads(self.caminho.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None


class FonteLocalizacaoMemoria:
    """Dataset em memória (injetável nos testes) — sem arquivo/rede."""

    def __init__(self, dataset: Optional[dict]):
        self._dataset = dataset

    def carregar(self) -> Optional[dict]:
        return self._dataset


def get_fonte_localizacao() -> FonteLocalizacao:
    caminho = os.getenv("LOCALIZACAO_ARQUIVO", str(_ARQUIVO_DEFAULT))
    return FonteLocalizacaoArquivo(caminho)


# ----- Montagem da resposta (PURA: dataset + cod_ibge → LocalizacaoOut) -----
def _crescimento(p2022: Optional[int], p2010: Optional[int]) -> Optional[tuple[float, float]]:
    """(variação total, CAGR a.a. 12 anos) ou None se faltar base. CAGR = (P2022/P2010)^(1/12)−1."""
    if not p2022 or not p2010 or p2010 <= 0:
        return None
    total = p2022 / p2010 - 1
    cagr = (p2022 / p2010) ** (1 / 12) - 1
    return total, cagr


def _leitura_populacao(cresc_total: float, cresc_uf: Optional[float]) -> str:
    base = (
        f"Crescimento de {_pct_br(cresc_total)} entre os Censos 2010 e 2022 "
        f"(≈{_pct_br((1 + cresc_total) ** (1 / 12) - 1)} a.a.)"
    )
    if cresc_uf is not None:
        if cresc_total < cresc_uf - 0.005:
            comp = " — abaixo da média estadual; sinal de demanda demográfica fraca"
        elif cresc_total > cresc_uf + 0.005:
            comp = " — acima da média estadual; sinal de demanda demográfica aquecida"
        else:
            comp = " — em linha com a média estadual"
    else:
        comp = ""
    return base + comp + ", SOB OS DADOS CENSITÁRIOS."


def _leitura_renda(vs_uf: Optional[float]) -> str:
    if vs_uf is None:
        return "PIB per capita do município (IBGE — PIB dos Municípios)."
    razao_pct = _pct_br(vs_uf, 0)
    rel = "da" if abs(vs_uf - 1) < 0.005 else ("acima da" if vs_uf > 1 else "")
    if vs_uf > 1.005:
        return f"PIB per capita {_pct_br(vs_uf - 1, 0)} acima da média estadual, SOB OS DADOS DO IBGE."
    if vs_uf < 0.995:
        return f"PIB per capita em {razao_pct} da média estadual, SOB OS DADOS DO IBGE."
    return "PIB per capita em linha com a média estadual, SOB OS DADOS DO IBGE."


def _populacao(reg: dict, uf_reg: Optional[dict]) -> schemas.PopulacaoOut:
    p22, p10 = reg.get("pop_2022"), reg.get("pop_2010")
    area = reg.get("area_km2")
    if not p22:
        return schemas.PopulacaoOut(
            disponivel=False, aviso="População indisponível na fonte para este município."
        )
    cr = _crescimento(p22, p10)
    cr_uf = _crescimento(uf_reg.get("pop_2022"), uf_reg.get("pop_2010")) if uf_reg else None
    densidade = round(p22 / area, 2) if area else None
    vs_uf = round(p22 / uf_reg["pop_2022"], 6) if uf_reg and uf_reg.get("pop_2022") else None
    return schemas.PopulacaoOut(
        disponivel=True,
        censo_2022=p22,
        censo_2022_fmt=_int_br(p22),
        censo_2010=p10,
        censo_2010_fmt=_int_br(p10) if p10 else None,
        crescimento_total_pct=round(cr[0], 6) if cr else None,
        crescimento_total_fmt=_pct_br(cr[0]) if cr else None,
        crescimento_aa_pct=round(cr[1], 6) if cr else None,
        crescimento_aa_fmt=_pct_br(cr[1]) if cr else None,
        densidade_hab_km2=densidade,
        densidade_fmt=f"{_dec_br(densidade)} hab/km²" if densidade is not None else None,
        area_km2=area,
        vs_uf=vs_uf,
        fonte="IBGE Censo 2022/2010",
        leitura=_leitura_populacao(cr[0], cr_uf[0] if cr_uf else None) if cr else None,
    )


def _renda(reg: dict, uf_reg: Optional[dict], br_reg: Optional[dict]) -> schemas.RendaOut:
    pib = reg.get("pib_per_capita")
    if pib is None:
        return schemas.RendaOut(
            disponivel=False, aviso="PIB per capita indisponível na fonte para este município."
        )
    vs_uf = (
        round(pib / uf_reg["pib_per_capita"], 6)
        if uf_reg and uf_reg.get("pib_per_capita")
        else None
    )
    vs_br = (
        round(pib / br_reg["pib_per_capita"], 6)
        if br_reg and br_reg.get("pib_per_capita")
        else None
    )
    ano = reg.get("pib_ano")
    return schemas.RendaOut(
        disponivel=True,
        pib_per_capita=pib,
        pib_per_capita_fmt=_brl(pib),
        ano=ano,
        vs_uf=vs_uf,
        vs_uf_fmt=_pct_br(vs_uf, 0) if vs_uf is not None else None,
        vs_brasil=vs_br,
        vs_brasil_fmt=_pct_br(vs_br, 0) if vs_br is not None else None,
        fonte=f"IBGE — PIB dos Municípios{f' {ano}' if ano else ''}",
        leitura=_leitura_renda(vs_uf),
    )


def _habitacao(reg: dict) -> schemas.HabitacaoOut:
    deficit = reg.get("deficit")
    dom = reg.get("domicilios_ocupados")
    mpd = reg.get("moradores_por_domicilio")
    if deficit and isinstance(deficit, dict) and deficit.get("valor") is not None:
        # Município no recorte FJP → exibe o déficit com fonte+ano.
        return schemas.HabitacaoOut(
            disponivel=True,
            deficit=schemas.DeficitOut(
                valor=int(deficit["valor"]),
                valor_fmt=_int_br(int(deficit["valor"])),
                fonte=deficit.get("fonte", "FJP"),
                ano=int(deficit["ano"]),
            ),
            fonte=f"Fundação João Pinheiro (FJP) {deficit.get('ano')}",
        )
    # Fora do recorte FJP → NUNCA estima: deficit=null + fallback de estoque rotulado.
    if dom is None or mpd is None:
        return schemas.HabitacaoOut(
            disponivel=False,
            aviso="Déficit habitacional (FJP) e estoque de domicílios indisponíveis para este município.",
        )
    return schemas.HabitacaoOut(
        disponivel=True,
        deficit=None,
        fallback_estoque=schemas.FallbackEstoqueOut(
            domicilios_ocupados=int(dom),
            domicilios_ocupados_fmt=_int_br(int(dom)),
            moradores_por_domicilio=mpd,
            moradores_por_domicilio_fmt=_dec_br(mpd, 2),
            fonte="IBGE Censo 2022",
        ),
        aviso=(
            "Déficit habitacional (FJP) indisponível para este município — exibindo o "
            "estoque de domicílios ocupados (Censo 2022) como referência de contexto; "
            "NÃO é o déficit."
        ),
    )


def _faixa_etaria(reg: dict) -> schemas.FaixaEtariaOut:
    fe = reg.get("faixa_etaria")
    if not fe:
        return schemas.FaixaEtariaOut(
            disponivel=False, aviso="Distribuição etária indisponível na fonte para este município."
        )
    ordem = ["0-14", "15-29", "30-59", "60+"]
    grupos = [
        schemas.GrupoEtarioOut(faixa=f, pct=round(fe[f], 6), pct_fmt=_pct_br(fe[f], 1))
        for f in ordem
        if f in fe
    ]
    return schemas.FaixaEtariaOut(disponivel=True, fonte="IBGE Censo 2022", grupos=grupos)


def montar_localizacao(
    dataset: Optional[dict], cod_ibge: Optional[str], uf: Optional[str], municipio: Optional[str]
) -> schemas.LocalizacaoOut:
    """Monta a resposta a partir do dataset embarcado. Sempre 200; degrada honesto."""
    mun_ref = schemas.LocalizacaoMunicipioOut(cod_ibge=cod_ibge, nome=municipio, uf=uf)
    vazio_pop = schemas.PopulacaoOut(disponivel=False)
    vazio_renda = schemas.RendaOut(disponivel=False)
    vazio_hab = schemas.HabitacaoOut(disponivel=False)
    vazio_fe = schemas.FaixaEtariaOut(disponivel=False)
    prov_base = "Arquivo embarcado localizacao_municipios.json"
    if dataset and dataset.get("_meta", {}).get("data_geracao"):
        prov_base += f" — gerado em {dataset['_meta']['data_geracao']} de {dataset['_meta'].get('fontes', 'IBGE/FJP')}"

    # Município não resolvido na análise → avaliada=false + motivo acionável.
    if not cod_ibge:
        return schemas.LocalizacaoOut(
            avaliada=False,
            cobertura="INDISPONIVEL",
            municipio=mun_ref,
            populacao=vazio_pop,
            renda=vazio_renda,
            habitacao=vazio_hab,
            faixa_etaria=vazio_fe,
            proveniencia=prov_base,
            avisos=[
                "Município não resolvido nesta análise — resolva o município (detecção ou "
                "busca por nome) para o enriquecimento de localização.",
                AVISO_INFORMATIVO,
            ],
        )

    registros = (dataset or {}).get("registros", {})
    reg = registros.get(str(cod_ibge))
    if reg is None:
        return schemas.LocalizacaoOut(
            avaliada=True,
            cobertura="INDISPONIVEL",
            municipio=mun_ref,
            populacao=vazio_pop,
            renda=vazio_renda,
            habitacao=vazio_hab,
            faixa_etaria=vazio_fe,
            proveniencia=prov_base,
            avisos=[
                f"Município {municipio or cod_ibge} ainda não consta no arquivo embarcado de "
                "localização (gere o arquivo completo com scripts/gerar_localizacao_ibge.py).",
                AVISO_INFORMATIVO,
            ],
        )

    uf_reg = registros.get(f"UF:{reg.get('uf') or uf}")
    br_reg = registros.get("BR")

    populacao = _populacao(reg, uf_reg)
    renda = _renda(reg, uf_reg, br_reg)
    habitacao = _habitacao(reg)
    faixa = _faixa_etaria(reg)

    blocos = [populacao.disponivel, renda.disponivel, habitacao.disponivel, faixa.disponivel]
    cobertura = "COMPLETA" if all(blocos) else "PARCIAL"

    avisos: list[str] = []
    if not all(blocos):
        faltam = [
            nome
            for nome, ok in zip(("população", "renda", "habitação", "faixa etária"), blocos)
            if not ok
        ]
        avisos.append("Indicadores indisponíveis na fonte: " + ", ".join(faltam) + ".")
    if uf_reg is None:
        avisos.append(
            "Linha da UF ausente no arquivo — comparação município × estado omitida."
        )
    if br_reg is None:
        avisos.append("Linha do Brasil ausente no arquivo — comparação com o país omitida.")
    avisos.append(AVISO_INFORMATIVO)

    return schemas.LocalizacaoOut(
        avaliada=True,
        cobertura=cobertura,
        municipio=schemas.LocalizacaoMunicipioOut(
            cod_ibge=reg.get("cod", cod_ibge), nome=reg.get("nome", municipio), uf=reg.get("uf", uf)
        ),
        populacao=populacao,
        renda=renda,
        habitacao=habitacao,
        faixa_etaria=faixa,
        proveniencia=prov_base,
        avisos=avisos,
    )
