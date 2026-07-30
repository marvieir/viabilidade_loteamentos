"""Laudo de EXEMPLO — página pública (sem login) que mostra o que a plataforma entrega.

Pedido do operador (29/07): o botão "Ver um laudo de exemplo" resolve a objeção que trava
conversão — "não vou subir minha gleba sem saber o que sai daí". Usa a gleba REAL de São
Roque que já mora nas fixtures (3 matrículas, zona MUE confirmada).

Inegociáveis respeitados:
- **Todo número sai do MOTOR**, não de um JSON escrito à mão: se o motor melhorar, o exemplo
  melhora junto e nunca desatualiza. É a diferença entre exemplo vivo e captura de tela.
- Determinístico: mesma fixture → mesmo laudo, sempre.
- Cache em memória por processo: gerar layout custa segundos e a página é pública (não vamos
  rodar shapely a cada visita de curioso). O cache não persiste — reinício regenera.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException

router = APIRouter()  # SEM dependência de auth — a página é pública, é isso que ela serve

_CACHE: Optional[dict] = None

# Fixture da gleba real (a mesma dos testes-ouro do motor).
_FIXTURE = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / \
    "sao_roque_aproveitavel_decliv.json"


def _perfil_sao_roque():
    """Perfil municipal CONFIRMADO de São Roque/SP (zona MUE) — os mesmos índices que os
    testes usam: lote mínimo 360 m² e doação de 20% repartida em viário/verde/institucional."""
    from app.models.schemas import (
        DoacaoSplit, ParamProv, PerfilMunicipal, ZonaParams, ZonaPerfil,
    )

    def p(valor):
        return ParamProv(valor=valor, artigo="LC 106/2020", pagina=1,
                         trecho="índice da zona MUE", origem="editado_humano")

    return PerfilMunicipal(
        cod_ibge="3550605", municipio="São Roque", uf="SP", status="confirmado",
        zonas=[ZonaPerfil(codigo="MUE", params=ZonaParams(
            lote_min_m2=p(360),
            doacao_pct=ParamProv(valor=0.20, base="total", artigo="LC 106/2020", pagina=1,
                                 trecho="doação ao município", origem="editado_humano"),
            doacao_split=DoacaoSplit(viario=0.10, verde=0.06, institucional=0.04)))],
        validado_por="exemplo da plataforma", data_referencia="2026-07-29",
    )


def _gerar() -> dict:
    """Roda o motor sobre a fixture e monta o laudo. Puro — sem rede, sem IA."""
    from shapely import wkb

    from app.core import urbanismo_geom as geom
    from app.core import urbanismo_medida as medida
    from app.core.urbanismo_diretrizes import resolver_diretrizes
    from app.core.urbanismo_programa import programa_do_preset

    dados = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    aprov = wkb.loads(dados["aproveitavel_wkb_hex"], hex=True)
    diretrizes = resolver_diretrizes(_perfil_sao_roque(), "MUE", None, "alta")
    layout = geom.gerar_layout(
        aprov, programa_do_preset("alta", {"pct_lazer": 0.2}),
        orientacao_rad=float(dados["orientacao_rad"]), diretrizes=diretrizes,
    )
    med = medida.medir(layout)
    return {
        "gleba": {
            "rotulo": "Gleba Urbanisi — 3 matrículas",
            "municipio": "São Roque", "uf": "SP", "cod_ibge": "3550605",
            "aproveitavel_m2": round(aprov.area, 2),
            "aproveitavel_ha": round(aprov.area / 10000, 2),
            "publico_alvo": "alta",
            "tipo": "Loteamento fechado · alto padrão",
        },
        "quadro_areas": med.quadro,
        "indicadores": med.indicadores,
        "diretrizes": {
            "cobertura": diretrizes["cobertura"],
            "fonte": diretrizes["fonte"],
            "lote_min_zona_m2": diretrizes["lote_min_zona_m2"],
            "piso_lote_efetivo_m2": diretrizes["piso_lote_efetivo_m2"],
            "doacao_min_pct": diretrizes["doacao_min_pct"],
            "doacao_split": diretrizes["doacao_split"],
            "aviso": diretrizes["aviso"],
        },
        "proveniencia": (
            "Laudo gerado pelo MESMO motor determinístico que atende os clientes, sobre uma "
            "gleba real de São Roque/SP com diretriz municipal confirmada. Nenhum número foi "
            "escrito à mão: melhorou o motor, melhora o exemplo."
        ),
    }


@router.get("/exemplo/laudo")
def laudo_exemplo() -> dict:
    """Laudo de exemplo (público). Gera na primeira chamada e serve do cache depois."""
    global _CACHE
    if _CACHE is None:
        if not _FIXTURE.exists():
            raise HTTPException(
                503,
                "O laudo de exemplo está indisponível neste servidor (a gleba de referência "
                "não foi encontrada). Crie uma conta para analisar a sua própria gleba.",
            )
        try:
            _CACHE = _gerar()
        except Exception as exc:  # noqa: BLE001 — página pública nunca devolve 500 cru
            raise HTTPException(
                503,
                "Não foi possível montar o laudo de exemplo agora. Tente novamente em alguns "
                f"minutos ou crie uma conta para analisar a sua gleba. ({type(exc).__name__})",
            ) from exc
    return _CACHE
