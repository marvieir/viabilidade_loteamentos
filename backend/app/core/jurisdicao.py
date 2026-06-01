"""Resolvedor de jurisdição — interface com de-para centróide→município injetável.

DECISÃO DE IMPLEMENTAÇÃO (Fase 1, dentro do contrato):
- O de-para geográfico centróide→município é uma dependência *injetável*.
- COMPORTAMENTO DE PRODUÇÃO (sem de-para configurado): retorna municipio=None e
  cobertura=BASE_FEDERAL. Isto é o comportamento REAL, não um placeholder — é a
  degradação graciosa que a spec descreve. NUNCA "hardcodar" um município como
  fallback de produção (isso faria o critério de degradação mentir).
- A injeção de um município concreto (ex.: São Roque/SP/3550605) vive apenas nos
  testes, via dependency_overrides.
- Resolução geográfica real (malha municipal IBGE) entra na Fase 3 (Jurídica),
  quando o perfil municipal passa a ser efetivamente consumido.

Mesmo com o de-para presente, na Fase 1 nenhum perfil estadual/municipal está
populado, então a cobertura permanece BASE_FEDERAL.
"""

from dataclasses import dataclass, field
from typing import Callable, Optional

# Um de-para recebe (lon, lat) e devolve (municipio, uf, cod_ibge) ou None.
ResolvedorMunicipio = Callable[[float, float], Optional[tuple[str, str, str]]]

# O que o nível BASE_FEDERAL explicitamente NÃO considerou (critério de aceite #6).
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
    nao_considerado: list[str] = field(default_factory=list)


def resolver_jurisdicao(
    centroide,
    resolvedor: Optional[ResolvedorMunicipio] = None,
) -> Jurisdicao:
    """Resolve a jurisdição a partir do centróide do polígono.

    Sem ``resolvedor`` (default de produção) → BASE_FEDERAL com município nulo.
    """
    municipio = uf = cod_ibge = None
    if resolvedor is not None:
        resultado = resolvedor(centroide.x, centroide.y)
        if resultado:
            municipio, uf, cod_ibge = resultado

    # Fase 1: nenhum perfil estadual/municipal populado → sempre BASE_FEDERAL.
    return Jurisdicao(
        municipio=municipio,
        uf=uf,
        cod_ibge=cod_ibge,
        cobertura="BASE_FEDERAL",
        nao_considerado=list(NAO_CONSIDERADO_FEDERAL),
    )


def get_resolvedor_municipio() -> Optional[ResolvedorMunicipio]:
    """Dependência FastAPI do de-para municipal.

    PRODUÇÃO: devolve None (nenhum de-para configurado) → degradação graciosa.
    TESTES: sobrescrito via app.dependency_overrides para injetar um município.
    """
    return None
