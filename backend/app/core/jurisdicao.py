"""Resolvedor de jurisdição — detecção real de município por malha IBGE (injetável).

DECISÃO DE IMPLEMENTAÇÃO (Fase 1.7 — promove o stub da Fase 1):
- A malha municipal é uma **fonte injetável** (``FonteMalha``), igual ao padrão da
  Fase 2 para camadas ambientais. Em PRODUÇÃO o default tenta carregar a malha de um
  arquivo local (ver ``malha_ibge.py``); ausente → ``None`` → **degradação honesta**
  (município nulo, ``BASE_FEDERAL``). NUNCA se "hardcoda" um município de fallback.
- Detecção com **override**: o município detectado por point-in-polygon do centróide é
  mostrado; o usuário pode corrigir por ``POST /analises/{id}/municipio`` (proveniência
  ``detectado`` → ``informado``). Se o **polígono inteiro** cruza >1 município, sinaliza
  ``cruza_divisa`` e devolve os candidatos — nunca crava em silêncio.
- Pipeline, não agente: a aquisição da malha é download+cache de arquivo oficial.

A cobertura permanece ``BASE_FEDERAL`` na 1.7 (nenhum perfil estadual/municipal é
consumido ainda; a LUOS entra na Fase 1.8).
"""

from dataclasses import dataclass, field
from typing import Optional, Protocol, runtime_checkable
import unicodedata


def normalizar_nome(s: str) -> str:
    """Normaliza para busca tolerante a acento/caixa: 'São Roque' == 'sao roque'."""
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.casefold().strip()


@dataclass(frozen=True)
class Municipio:
    cod_ibge: str
    municipio: str
    uf: str


@dataclass(frozen=True)
class Candidato:
    """Município candidato na divisa, com a fração da gleba que cai nele (%)."""

    cod_ibge: str
    municipio: str
    uf: str
    pct_area: float  # 0–100, 1 casa decimal


@runtime_checkable
class FonteMalha(Protocol):
    """Acesso à malha GEOMÉTRICA municipal (só DETECTAR). Real em ``malha_ibge.py``.

    A busca/correção por NOME usa a lista leve (``lista_municipios.py``), desacoplada —
    por isso o override sobrevive mesmo sem a malha (decisão #2 da 1.7).
    """

    def municipio_no_ponto(self, lon: float, lat: float) -> Optional[Municipio]:
        """Município que contém o ponto (centróide), ou None se fora da malha."""

    def intersecoes(self, poly) -> list[tuple[Municipio, object]]:
        """``(Municipio, geometria_da_interseção)`` para cada município que toca o polígono.

        A geometria da interseção alimenta o cálculo do % de área por município na divisa.
        """


# O que o nível BASE_FEDERAL explicitamente NÃO considerou (critério de aceite).
NAO_CONSIDERADO_FEDERAL = [
    "Lote mínimo municipal não considerado (sem perfil do município carregado).",
    "Percentual de doação pública municipal não considerado (sem perfil do município).",
    "Zoneamento/LUOS municipal não considerado.",
]


@dataclass
class Jurisdicao:
    municipio: Optional[str]
    uf: Optional[str]
    cod_ibge: Optional[str]
    cobertura: str  # BASE_FEDERAL | PARCIAL_UF | COMPLETA
    origem: str = "detectado"  # detectado | aproximado | informado
    cruza_divisa: bool = False
    candidatos: list[Candidato] = field(default_factory=list)
    nao_considerado: list[str] = field(default_factory=list)


def _base_federal(
    municipio: Optional[Municipio],
    origem: str,
    cruza_divisa: bool = False,
    candidatos: Optional[list[Candidato]] = None,
) -> Jurisdicao:
    return Jurisdicao(
        municipio=municipio.municipio if municipio else None,
        uf=municipio.uf if municipio else None,
        cod_ibge=municipio.cod_ibge if municipio else None,
        cobertura="BASE_FEDERAL",
        origem=origem,
        cruza_divisa=cruza_divisa,
        candidatos=candidatos or [],
        nao_considerado=list(NAO_CONSIDERADO_FEDERAL),
    )


def _candidatos_por_area(intersecoes, area_poly: float) -> list[Candidato]:
    """Converte ``(Municipio, geom_interseção)`` em candidatos com % de área, desc.

    O % é a fração da gleba (área geodésica) que cai em cada município. Empate de %
    desempata por código IBGE → saída determinística.
    """
    from app.core.geometria import area_geodesica

    out: list[Candidato] = []
    for mun, geom_int in intersecoes:
        pct = round(100.0 * area_geodesica(geom_int) / area_poly, 1) if area_poly > 0 else 0.0
        out.append(Candidato(mun.cod_ibge, mun.municipio, mun.uf, pct))
    out.sort(key=lambda c: (-c.pct_area, c.cod_ibge))
    return out


def resolver_jurisdicao(
    poly,
    fonte: Optional[FonteMalha] = None,
) -> Jurisdicao:
    """Resolve a jurisdição a partir do polígono da gleba (apenas DETECÇÃO).

    Sem ``fonte`` (produção sem malha) → ``BASE_FEDERAL`` município nulo. Com fonte:
    - >1 município → **divisa**: candidatos com % de área, ordenados desc, default no maior;
      exige confirmação humana (decisão #4). Origem ``detectado``.
    - 1 município: se o centróide cai dentro dele → ``detectado``; se cai num gap de
      generalização na borda → fallback **nearest** (o único que a gleba toca), ``aproximado``
      (decisão #5) — nunca "não resolvido" quando a gleba claramente toca um município.
    - 0 município (gleba fora de tudo) → município nulo, sem inventar.
    """
    if fonte is None:
        return _base_federal(None, "detectado")

    intersecoes = list(fonte.intersecoes(poly))
    if not intersecoes:
        return _base_federal(None, "detectado")

    if len(intersecoes) > 1:
        from app.core.geometria import area_geodesica

        candidatos = _candidatos_por_area(intersecoes, area_geodesica(poly))
        maior = candidatos[0]
        principal = Municipio(maior.cod_ibge, maior.municipio, maior.uf)
        return _base_federal(principal, "detectado", True, candidatos)

    (mun, _geom), = intersecoes
    no_centro = fonte.municipio_no_ponto(poly.centroid.x, poly.centroid.y)
    contido = no_centro is not None and no_centro.cod_ibge == mun.cod_ibge
    return _base_federal(mun, "detectado" if contido else "aproximado")


def atualizar_municipio(cod_ibge: str, fonte) -> Jurisdicao:
    """Seleção/correção manual: resolve o município pelo código (na LISTA LEVE) e marca
    ``informado``. Levanta ``ValueError`` se o código não existe (router → 422).

    Usa a lista leve (não a malha) → o override funciona mesmo sem a malha geométrica.
    """
    municipio = fonte.por_codigo(cod_ibge) if fonte else None
    if municipio is None:
        raise ValueError(f"Código IBGE não encontrado: {cod_ibge!r}")
    return _base_federal(municipio, "informado")


def get_fonte_malha() -> Optional[FonteMalha]:
    """Dependência FastAPI da malha municipal.

    PRODUÇÃO: tenta carregar a malha de arquivo local (``malha_ibge.from_env``);
    ausente → None (degradação honesta). TESTES: sobrescrito via dependency_overrides.
    """
    from app.core import malha_ibge

    return malha_ibge.from_env()
