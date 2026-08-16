"""LAUDO-INV — relatório detalhado do estudo para investidores (fase-laudo-inv.md).

  POST /api/analises/{id}/relatorio        → compõe o relatório (JSON; o front renderiza
       a página imprimível e o navegador salva o PDF). Gate de PLANO PAGO sem prévia
       (decisão do operador, 16/08): bloqueado → payload só com o gate.
  PUT  /api/relatorio/liberacao/{usuario}  → alavanca manual do admin (sem billing ainda).

Composição PURA (core/relatorio.py): dimensões vêm do corpo (o front repassa o que o
backend devolveu, §2 — mesmo contrato do laudo) e os snapshots ricos vêm dos stores
(urbanismo com planta/heatmap, financeira, econômica, reconciliação ambiental).
"""

from __future__ import annotations

import os
import re
from datetime import date

from fastapi import APIRouter, Depends, HTTPException

from app.core import reconciliacao_store
from app.core import relatorio as motor
from app.core.auth import requer_admin, usuario_atual
from app.core.economica_store import FonteEconomica, get_fonte_economica
from app.core.financeira_store import FonteFinanceira, get_fonte_financeira
from app.core.portfolio_store import FontePortfolio, FontePortfolioArquivo
from app.core.store import STORE
from app.core.urbanismo_store import FonteUrbanismo, get_fonte_urbanismo
from app.models import schemas
from app.models.db_models import Usuario
from app.routers.laudo import _identificacao

from app.core.acesso import analise_do_dono

router = APIRouter()

_GATE_DIR_DEFAULT = "/data/perfis/relatorio_gate"


def get_fonte_gate_relatorio() -> FontePortfolio:
    """Gate comercial do relatório (estado próprio, mecânica do portfólio)."""
    return FontePortfolioArquivo(os.getenv("LAUDOINV_GATE_DIR", _GATE_DIR_DEFAULT))


def _resolver_gate_pago(usuario: Usuario, fonte: FontePortfolio) -> schemas.PortfolioGateOut:
    """SEM prévia (difere do portfólio/AMB-EXC — decisão do operador, 16/08): gratuito vê
    a mensagem de recurso pago desde o primeiro acesso; admin tem bypass; liberação
    manual do admin enquanto não existe billing."""
    if usuario.papel == "admin":
        return schemas.PortfolioGateOut(status="liberado", motivo="conta administradora")
    reg = fonte.carregar(str(usuario.id)) or {}
    if reg.get("liberado") is True:
        return schemas.PortfolioGateOut(
            status="liberado", motivo="acesso liberado pelo administrador"
        )
    return schemas.PortfolioGateOut(
        status="bloqueado",
        motivo="recurso dos planos pagos — disponível ao contratar um plano",
    )


@router.post(
    "/analises/{analise_id}/relatorio",
    response_model=schemas.RelatorioOut,
    dependencies=[Depends(analise_do_dono)],
)
def gerar_relatorio(
    analise_id: str,
    body: schemas.RelatorioIn,
    usuario: Usuario = Depends(usuario_atual),
    fonte_gate: FontePortfolio = Depends(get_fonte_gate_relatorio),
    fonte_urb: FonteUrbanismo = Depends(get_fonte_urbanismo),
    fonte_fin: FonteFinanceira = Depends(get_fonte_financeira),
    fonte_eco: FonteEconomica = Depends(get_fonte_economica),
    fonte_rec: reconciliacao_store.FonteReconciliacao = Depends(
        reconciliacao_store.get_fonte_reconciliacao
    ),
):
    registro = STORE.get(analise_id)
    if registro is None:
        raise HTTPException(404, "Análise não encontrada.")

    gate = _resolver_gate_pago(usuario, fonte_gate)
    if gate.status == "bloqueado":
        # Bloqueio REAL no servidor: só o gate — o front mostra a mensagem de plano pago.
        return schemas.RelatorioOut(gate=gate)

    snapshots = fonte_urb.listar(analise_id)
    snapshot_urb = None
    if snapshots:
        # Último snapshot, sem as chaves privadas (_programa_motor etc.) — payload limpo.
        snapshot_urb = {k: v for k, v in snapshots[-1].items() if not k.startswith("_")}

    versoes_rec = fonte_rec.carregar(analise_id)

    dims = schemas.LaudoIn(**body.model_dump(include=set(schemas.LaudoIn.model_fields)))
    return motor.montar_relatorio(
        _identificacao(analise_id, registro),
        dims.model_dump(),
        gate=gate,
        preparado_por=(body.preparado_por or "").strip() or None,
        titulo_estudo=(body.titulo_estudo or "").strip() or None,
        snapshot_urb=snapshot_urb,
        fin=fonte_fin.carregar(analise_id),
        eco=fonte_eco.carregar(analise_id),
        reconciliacao=versoes_rec[-1] if versoes_rec else None,
        data_geracao=date.today().isoformat(),
    )


@router.put("/relatorio/liberacao/{usuario_id}", response_model=schemas.PortfolioLiberacaoOut)
def liberar_relatorio(
    usuario_id: str,
    body: schemas.PortfolioLiberacaoIn,
    _admin: Usuario = Depends(requer_admin),
    fonte_gate: FontePortfolio = Depends(get_fonte_gate_relatorio),
):
    """Destrava (ou re-trava) o relatório para um cliente — alavanca manual do admin
    enquanto não existe billing (mesmo padrão do portfólio)."""
    if not re.fullmatch(r"[A-Za-z0-9-]{1,64}", usuario_id):
        raise HTTPException(status_code=422, detail="usuario_id inválido.")
    reg = fonte_gate.carregar(usuario_id) or {}
    reg["liberado"] = body.liberado
    fonte_gate.salvar(usuario_id, reg)
    return schemas.PortfolioLiberacaoOut(usuario_id=usuario_id, liberado=body.liberado)
