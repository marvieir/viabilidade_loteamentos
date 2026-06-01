"""Armazenamento em memória das análises da sessão.

Simples e suficiente para a Fase 1: guarda a geometria medida e a jurisdição
resolvida, indexadas pelo analise_id (derivado deterministicamente do conteúdo do
KMZ). Sem persistência, sem cache distribuído — a fase não pede isso.
"""

from typing import TypedDict

from shapely.geometry import Polygon

from app.core.jurisdicao import Jurisdicao


class Registro(TypedDict):
    poly: Polygon
    area_m2: float
    perimetro_m: float
    jurisdicao: Jurisdicao


STORE: dict[str, Registro] = {}
