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


@runtime_checkable
class FonteMalha(Protocol):
    """Acesso à malha municipal. Implementação real em ``malha_ibge.py``."""

    def municipio_no_ponto(self, lon: float, lat: float) -> Optional[Municipio]:
        """Município que contém o ponto (centróide), ou None se fora da malha."""

    def municipios_que_intersectam(self, poly) -> list[Municipio]:
        """Todos os municípios que o polígono intersecta (para alerta de divisa)."""

    def por_codigo(self, cod_ibge: str) -> Optional[Municipio]:
        """Município pelo código IBGE (para override/seleção manual)."""

    def buscar_por_nome(self, termo: str, limite: int = 10) -> list[Municipio]:
        """Busca por nome (tolerante a acento/caixa), para o autocomplete do override."""


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
    origem: str = "detectado"  # detectado | informado
    cruza_divisa: bool = False
    municipios_candidatos: list[Municipio] = field(default_factory=list)
    nao_considerado: list[str] = field(default_factory=list)


def _base_federal(
    municipio: Optional[Municipio],
    origem: str,
    cruza_divisa: bool,
    candidatos: list[Municipio],
) -> Jurisdicao:
    return Jurisdicao(
        municipio=municipio.municipio if municipio else None,
        uf=municipio.uf if municipio else None,
        cod_ibge=municipio.cod_ibge if municipio else None,
        cobertura="BASE_FEDERAL",
        origem=origem,
        cruza_divisa=cruza_divisa,
        municipios_candidatos=candidatos,
        nao_considerado=list(NAO_CONSIDERADO_FEDERAL),
    )


def resolver_jurisdicao(
    poly,
    fonte: Optional[FonteMalha] = None,
) -> Jurisdicao:
    """Resolve a jurisdição a partir do polígono da gleba.

    Sem ``fonte`` (default de produção sem malha configurada) → ``BASE_FEDERAL`` com
    município nulo. Com fonte: detecta por centróide e verifica cruzamento de divisa
    sobre o polígono inteiro.
    """
    if fonte is None:
        return _base_federal(None, "detectado", False, [])

    centro = poly.centroid
    intersectados = list(fonte.municipios_que_intersectam(poly))

    if len(intersectados) > 1:
        # Divisa: ordena por código para saída determinística; principal = o do centróide
        # quando entre os candidatos, senão o primeiro candidato.
        candidatos = sorted(intersectados, key=lambda m: m.cod_ibge)
        no_centro = fonte.municipio_no_ponto(centro.x, centro.y)
        principal = no_centro if no_centro in candidatos else candidatos[0]
        return _base_federal(principal, "detectado", True, candidatos)

    no_centro = fonte.municipio_no_ponto(centro.x, centro.y)
    return _base_federal(no_centro, "detectado", False, [])


def atualizar_municipio(cod_ibge: str, fonte: Optional[FonteMalha]) -> Jurisdicao:
    """Seleção/correção manual: resolve o município pelo código e marca ``informado``.

    Levanta ``ValueError`` se o código não existe na malha (router → 404/422).
    """
    municipio = fonte.por_codigo(cod_ibge) if fonte else None
    if municipio is None:
        raise ValueError(f"Código IBGE não encontrado na malha: {cod_ibge!r}")
    return _base_federal(municipio, "informado", False, [])


def get_fonte_malha() -> Optional[FonteMalha]:
    """Dependência FastAPI da malha municipal.

    PRODUÇÃO: tenta carregar a malha de arquivo local (``malha_ibge.from_env``);
    ausente → None (degradação honesta). TESTES: sobrescrito via dependency_overrides.
    """
    from app.core import malha_ibge

    return malha_ibge.from_env()
