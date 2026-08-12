"""Router da dimensão Financeira (Fase 4) — monta o fluxo de caixa do empreendimento.

  POST /api/analises/{id}/financeira  → calcula e persiste (premissas no corpo)
  GET  /api/analises/{id}/financeira  → última execução persistida (404 se não houver)

Aritmética PURA (sem LLM/rede). Resolve os lotes do caso-base pela regra §3.1 a partir do
contexto que o front repassa (n_diretriz/n_teto do aproveitamento já calculado — o front não
recalcula, §2). NÃO altera o aproveitamento. Degrada honesto: premissa essencial ausente → 422.
"""

import os

from fastapi import APIRouter, Depends, HTTPException

from app.core import financeira as motor
from app.core import tributario
from app.core.auth import usuario_atual
from app.core.financeira_store import FonteFinanceira, get_fonte_financeira
from app.core.portfolio_store import FontePortfolio, FontePortfolioArquivo
from app.core.store import STORE
from app.models import schemas
from app.models.db_models import Usuario
from app.routers.portfolio import _resolver_gate

from app.core.acesso import analise_do_dono
router = APIRouter(dependencies=[Depends(analise_do_dono)])

_FIN25_GATE_DIR_DEFAULT = "/data/perfis/fin25_gate"


def get_fonte_gate_fin25() -> FontePortfolio:
    """Gate comercial do comparador tributário FIN2-5 (plano pago — decisão do operador,
    11/08): mesma mecânica do portfólio/AMB-EXC (prévia 30 dias + liberação do admin),
    estado separado. Bloqueado → o comparativo sai SÓ com o gate (o front mostra o item
    bloqueado); o restante da Financeira segue aberto."""
    return FontePortfolioArquivo(os.getenv("FIN25_GATE_DIR", _FIN25_GATE_DIR_DEFAULT))


def _comparativo_tributario(
    body: schemas.PremissasFinanceiraIn,
    resultado: schemas.FinanceiraOut,
    gate: schemas.PortfolioGateOut,
) -> schemas.ComparativoTributarioOut:
    """Monta as entradas do comparador a partir do resultado (nunca recalcula VGV aqui)."""
    t = body.tributos
    aq = body.aquisicao
    vendaveis = resultado.caso_base.lotes_vendaveis
    vgv = resultado.vgv.bruto
    preco = round(vgv / vendaveis, 2) if vendaveis else 0.0

    avisos_extra: list[str] = []
    if aq.modo == "compra" and aq.valor:
        terreno, origem_terreno = float(aq.valor), "compra declarada na Parceria"
    else:
        terreno, origem_terreno = 0.0, "sem compra declarada"
        if aq.modo in ("permuta_vgv", "permuta_lotes"):
            avisos_extra.append(
                "Aquisição por PERMUTA: o valor do terreno não entra como redutor de "
                "ajuste nesta conta (estrutura de permuta — consulte tributarista)."
            )
    if t.itbi_laudemio is not None:
        itbi, origem_itbi = float(t.itbi_laudemio), "declarado"
    elif aq.modo == "compra" and aq.valor and aq.itbi_pct:
        itbi = round(float(aq.valor) * float(aq.itbi_pct), 2)
        origem_itbi = "derivado da aquisição (itbi_pct × compra)"
    else:
        itbi, origem_itbi = 0.0, "não informado"

    return tributario.comparar_regimes(
        gate=gate,
        n_lotes=vendaveis,
        preco_lote=preco,
        vgv=vgv,
        carga_atual=t.aliquota_pct,
        carga_atual_declarada="aliquota_pct" in t.model_fields_set,
        valor_terreno=terreno,
        origem_terreno=origem_terreno,
        itbi_laudemio=itbi,
        origem_itbi=origem_itbi,
        contrapartidas=t.contrapartidas,
        correcao=t.correcao_acumulada_pct / 100.0,
        aliquota_padrao=t.aliquota_padrao_ref_pct / 100.0,
        lotes_residenciais=t.lotes_residenciais,
        avisos_extra=avisos_extra,
    )


def _resolver_lotes(lotes: schemas.LotesIn) -> tuple[int, str, str | None]:
    """Regra §3.1: declarado > (auto: diretriz > teto físico+aviso)."""
    if lotes.origem == "declarado":
        if lotes.n is None:
            raise HTTPException(
                422, "lotes.origem='declarado' exige 'lotes.n' (nº de lotes do caso-base)."
            )
        return lotes.n, "declarado", None
    if lotes.n_diretriz is not None:
        return lotes.n_diretriz, "diretriz", None
    if lotes.n_teto is not None:
        return lotes.n_teto, "teto_fisico", motor.AVISO_TETO_FISICO
    raise HTTPException(
        422,
        "Sem lotes para o caso-base: rode o Aproveitamento e repasse 'lotes.n_diretriz' "
        "ou 'lotes.n_teto', ou informe 'lotes.origem=declarado' + 'lotes.n'.",
    )


@router.post(
    "/analises/{analise_id}/financeira",
    response_model=schemas.FinanceiraOut,
)
def calcular_financeira(
    analise_id: str,
    body: schemas.PremissasFinanceiraIn,
    fonte: FonteFinanceira = Depends(get_fonte_financeira),
    usuario: Usuario = Depends(usuario_atual),
    fonte_gate: FontePortfolio = Depends(get_fonte_gate_fin25),
):
    if STORE.get(analise_id) is None:
        raise HTTPException(404, "Análise não encontrada.")

    # FIN2-5 — gate do comparador decidido no SERVIDOR (padrão AMB-EXC/portfólio).
    gate = _resolver_gate(usuario, fonte_gate)
    if gate.status == "bloqueado" and body.tributos.cenario_fluxo == "ibs_cbs":
        raise HTTPException(
            402, "Comparador tributário é recurso de plano pago — prévia gratuita encerrada."
        )

    lotes_base, origem, aviso = _resolver_lotes(body.lotes)
    ctx = motor.ContextoFinanceira(
        lotes_base=lotes_base,
        origem_lotes=origem,
        aviso_lotes=aviso,
        area_aproveitavel_m2=body.area_aproveitavel_m2,
        rotulo_origem={
            "diretriz": "cenário diretriz (com doação/lote legal)",
            "teto_fisico": "teto físico (sem doação/vias)",
            "declarado": "informado pelo usuário",
        }.get(origem, origem),
    )
    try:
        resultado, fluxos_cenarios = motor.montar_com_cenarios(body, ctx)

        # FIN2-5 — comparador tributário: bloqueado → só o gate (sem números).
        if gate.status == "bloqueado":
            comparativo = schemas.ComparativoTributarioOut(gate=gate)
        else:
            comparativo = _comparativo_tributario(body, resultado, gate)
            if body.tributos.cenario_fluxo == "ibs_cbs":
                # Cenário escolhido alimenta o fluxo (spec §2): recalcula com a carga
                # efetiva do regime novo na linha de tributos — mesma semântica de hoje
                # (% sobre a receita própria recebida), rotulada nos avisos.
                pct_b = next(
                    (r.pct_efetivo_vgv for r in comparativo.regimes if r.codigo == "ibs_cbs"),
                    None,
                )
                if pct_b is not None:
                    body_b = body.model_copy(update={
                        "tributos": body.tributos.model_copy(update={"aliquota_pct": pct_b})
                    })
                    resultado, fluxos_cenarios = motor.montar_com_cenarios(body_b, ctx)
                    comparativo = comparativo.model_copy(update={"avisos": [
                        "Linha 'tributos' do fluxo usa a carga efetiva do CENÁRIO B "
                        f"(IBS/CBS) = {round(pct_b * 100, 2)}% do VGV — escolha do usuário "
                        "(cenario_fluxo=ibs_cbs).",
                        *comparativo.avisos,
                    ]})
        resultado = resultado.model_copy(update={"comparativo_tributario": comparativo})
    except motor.PremissaFaltando as exc:
        raise HTTPException(422, f"Premissa essencial ausente: {exc}")
    except motor.InadimplenciaNaoConfirmada as exc:
        # 4.1: inadimplência alta nunca passa em silêncio (a lição do −19M).
        raise HTTPException(422, str(exc))
    except motor.CurvaInvalida as exc:
        raise HTTPException(422, str(exc))

    fonte.salvar(
        analise_id,
        {
            "premissas": body.model_dump(),
            "resultado": resultado.model_dump(),
            # FIN2-1 — fluxos por cenário (a Econômica avalia VPL/TIR de todos)
            "cenarios_fluxos": fluxos_cenarios,
        },
    )
    return resultado


@router.get(
    "/analises/{analise_id}/financeira",
    response_model=schemas.FinanceiraOut,
)
def obter_financeira(
    analise_id: str,
    fonte: FonteFinanceira = Depends(get_fonte_financeira),
):
    if STORE.get(analise_id) is None:
        raise HTTPException(404, "Análise não encontrada.")
    dados = fonte.carregar(analise_id)
    if dados is None or "resultado" not in dados:
        raise HTTPException(404, "Nenhuma análise financeira executada para esta gleba.")
    return schemas.FinanceiraOut.model_validate(dados["resultado"])
