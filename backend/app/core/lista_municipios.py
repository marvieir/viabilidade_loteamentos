"""Lista leve de municípios (``cod_ibge + nome + UF``) — para BUSCAR/CORRIGIR por nome.

Decisão #2 da 1.7: a peça de **corrigir** (busca por nome + override) usa esta lista
leve, **desacoplada** da malha geométrica pesada (que só serve para DETECTAR). Por isso o
autocomplete e o override funcionam **mesmo sem a malha carregada** (o plano B sobrevive).

A lista é minúscula (``~150 KB`` quando completa) e **embarcada no repo**
(``perfis/lista_municipios.json``); injetável nos testes. Fonte: IBGE
``/localidades/municipios`` (id→nome, UF), sem geometria — emitida pelo pipeline
``scripts/baixar_malha_ibge.py --lista``. O seed versionado cobre os municípios já usados
em testes/demos reais (São Roque/SP, Bocaina/SP); a população completa vem do pipeline
(egress bloqueado neste ambiente — ver ARCHITECTURE.md, histórico da 1.7).
"""

import json
import os
from pathlib import Path
from typing import Optional, Protocol, runtime_checkable

from app.core.jurisdicao import Municipio, normalizar_nome

_SEED = Path(__file__).resolve().parent.parent / "perfis" / "lista_municipios.json"


def filtrar_por_nome(muns: list[Municipio], termo: str, limite: int = 10) -> list[Municipio]:
    """Busca tolerante a acento/caixa: prefixo primeiro, depois substring. Determinística."""
    alvo = normalizar_nome(termo)
    if not alvo:
        return []
    prefixo = [m for m in muns if normalizar_nome(m.municipio).startswith(alvo)]
    contem = [
        m for m in muns if alvo in normalizar_nome(m.municipio) and m not in prefixo
    ]
    ordenados = sorted(prefixo, key=lambda m: (m.municipio, m.uf)) + sorted(
        contem, key=lambda m: (m.municipio, m.uf)
    )
    return ordenados[:limite]


@runtime_checkable
class FonteLista(Protocol):
    """Lista leve de municípios (nome/código). Implementação real: ``FonteListaArquivo``."""

    def buscar_por_nome(self, termo: str, limite: int = 10) -> list[Municipio]:
        """Autocomplete por nome (o usuário nunca digita código)."""

    def por_codigo(self, cod_ibge: str) -> Optional[Municipio]:
        """Município pelo código IBGE (resolução interna do override)."""


class FonteListaArquivo:
    """Lista leve a partir de ``[{cod_ibge, municipio, uf}, ...]`` (JSON)."""

    def __init__(self, registros: list[dict]):
        self._muns = [
            Municipio(
                cod_ibge=str(r["cod_ibge"]), municipio=r["municipio"], uf=r["uf"]
            )
            for r in registros
        ]
        self._por_cod = {m.cod_ibge: m for m in self._muns}

    def buscar_por_nome(self, termo: str, limite: int = 10) -> list[Municipio]:
        return filtrar_por_nome(self._muns, termo, limite)

    def por_codigo(self, cod_ibge: str) -> Optional[Municipio]:
        return self._por_cod.get(str(cod_ibge))


def get_fonte_lista() -> Optional[FonteLista]:
    """Dependência FastAPI da lista leve.

    PRODUÇÃO: carrega ``perfis/lista_municipios.json`` (embarcado) ou
    ``LISTA_MUNICIPIOS_PATH``. Diferente da malha, a lista **está sempre presente** no
    repo → busca/override não dependem da malha. TESTES: sobrescrito via overrides.
    """
    caminho = os.getenv("LISTA_MUNICIPIOS_PATH", str(_SEED))
    if not os.path.exists(caminho):
        return None
    try:
        with open(caminho, encoding="utf-8") as fh:
            return FonteListaArquivo(json.load(fh))
    except (OSError, ValueError):
        return None
