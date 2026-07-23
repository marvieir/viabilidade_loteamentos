"""Regime do projeto (URBANO × RURAL) — fonte única da intenção declarada.

A intenção não é conhecível no upload (não há zoneamento nacional carregável); ela fica
REGISTRADA na última proposta de urbanismo (o usuário escolhe "Loteamento rural" ao gerar).
Trilha, alertas geo, conformidade e demais consumidores leem DAQUI — uma regra, um lugar.
Sem proposta → False (régua urbana, conservador e rotulado; nunca se esconde restrição).
"""

from __future__ import annotations


def projeto_rural(analise_id: str, fonte=None) -> bool:
    """A última proposta de urbanismo desta análise é 'loteamento_rural'?

    ``fonte``: FonteUrbanismo já injetada (rotas FastAPI passam a sua, para o override de
    teste valer); ``None`` → resolve a default do ambiente (uso fora de rota).
    """
    try:
        if fonte is None:
            from app.core.urbanismo_store import get_fonte_urbanismo

            fonte = get_fonte_urbanismo()
        props = fonte.listar(analise_id)
        ult = props[-1] if props else {}
        tipo = ((ult.get("perfil") or {}).get("tipo_loteamento")
                or (ult.get("_contexto_variantes") or {}).get("tipo_loteamento") or "")
        return tipo == "loteamento_rural"
    except Exception:  # noqa: BLE001 — na dúvida, régua urbana (conservador)
        return False
