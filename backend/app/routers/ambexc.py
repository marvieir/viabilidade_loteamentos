"""AMB-EXC — Reconciliação ambiental pós-vistoria (spec fase-amb-exc.md; mockups aprovados).

  GET  /api/analises/{id}/ambiental/manchas → manchas do "verde a verificar" + 2ª opinião
       por mancha + regime legal da gleba + reconciliação vigente (se houver).
  POST /api/analises/{id}/ambiental/laudo   → registra o laudo (PDF + metadados) e aplica os
       ajustes; recalcula tudo (limpa o cache canônico); histórico versionado (append).

Papel: TRIAGEM + registro com proveniência. O laudo declara FATOS; a consequência vem da
régua (``ambiental_regua``) citando o dispositivo; a AUTORIZAÇÃO é sempre do órgão
competente (Lei 12.651, art. 26). Feature de PLANOS PAGOS (decisão do operador, 08/08):
gate no padrão do portfólio (prévia de 30 dias + liberação manual do admin), decidido no
SERVIDOR. Quem reconcilia é o CLIENTE dono da análise (o RT do laudo responde pelo conteúdo).
"""

from __future__ import annotations

import json
import os
from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from shapely.geometry import shape

from app.core import ambiental_manchas as manchas_mod
from app.core import ambiental_reconciliacao as arc
from app.core import ambiental_regua as regua
from app.core import reconciliacao_store
from app.core.acesso import analise_do_dono
from app.core.auth import usuario_atual
from app.core.bioma import FonteBioma, get_fonte_bioma
from app.core.camadas import FonteCamadas, get_fonte_camadas
from app.core.juridico_anexos import FonteAnexos, FonteAnexosArquivo
from app.core.portfolio_store import FontePortfolio, FontePortfolioArquivo
from app.core.store import STORE
from app.core.uploads import ler_upload_limitado
from app.core.vegetacao import FonteVegetacao, get_fonte_vegetacao
from app.models import schemas
from app.models.db_models import Usuario
from app.routers.portfolio import _resolver_gate

router = APIRouter(dependencies=[Depends(analise_do_dono)])

_GATE_DIR_DEFAULT = "/data/perfis/ambexc_gate"
_ANEXOS_DIR_DEFAULT = "/data/perfis/ambexc"


def get_fonte_gate_ambexc() -> FontePortfolio:
    """Gate comercial próprio do AMB-EXC (mesma mecânica do portfólio, estado separado)."""
    return FontePortfolioArquivo(os.getenv("AMBEXC_GATE_DIR", _GATE_DIR_DEFAULT))


def get_fonte_anexos_ambexc() -> FonteAnexos:
    """Anexos (PDF do laudo) — reusa a infra de anexos do jurídico com diretório próprio."""
    return FonteAnexosArquivo(os.getenv("AMBEXC_DIR", _ANEXOS_DIR_DEFAULT))


def _registro_ou_404(analise_id: str) -> dict:
    registro = STORE.get(analise_id)
    if registro is None:
        raise HTTPException(404, "Análise não encontrada.")
    return registro


def _severidade_a_verificar(registro, fonte_veg, fonte_camadas):
    """Reusa o pipeline da 2.3 para obter o balde 'a verificar' (WGS84) SEM reconciliação
    (as manchas são sempre as do satélite original; a reconciliação sobrepõe, não apaga)."""
    from app.core import ambiental as ambiental_motor
    from app.core.severidade_verde import classificar_severidade_verde

    gleba = registro["poly"]
    if fonte_veg is None:
        return None, None, "Vegetação não consultada (fonte não configurada)."
    cobertura = fonte_veg.cobertura_verde(gleba)
    if cobertura is None or cobertura.geometria is None:
        return None, None, "Sem cobertura vegetal detectada na gleba."
    if fonte_camadas is None:
        return None, None, "Camadas ambientais não consultadas; manchas indisponíveis."
    camadas = fonte_camadas.coletar(gleba.bounds, registro["jurisdicao"].uf)
    from app.core import ambiental as _amb
    overlays = _amb.analisar(gleba, camadas).geojson_overlays
    geoms = {k: shape(v) for k, v in overlays.items() if v}
    sev = classificar_severidade_verde(gleba, cobertura.geometria, geoms)
    averif = shape(sev.a_verificar.geojson) if sev.a_verificar.geojson else None
    rl = geoms.get("reserva_legal")
    return averif, rl, None


def _regime_da_analise(registro, fonte_bioma) -> regua.RegimeAmbiental:
    gleba = registro["poly"]
    bioma = None
    if fonte_bioma is not None:
        rb = fonte_bioma.identificar(gleba)
        bioma = rb.dominante if rb.consultado else None
    uf = registro["jurisdicao"].uf if registro.get("jurisdicao") else None
    # na_area_lei_ma=None: o mapa oficial da 11.428 ainda não é fonte carregada — a régua
    # infere pelo bioma e ROTULA (degradação honesta; plugar o mapa IBGE é evolução).
    return regua.resolver_regime(bioma, None, uf)


def _resumo_out(snap: dict, versao: int) -> schemas.ReconciliacaoResumoOut:
    return schemas.ReconciliacaoResumoOut(
        versao=versao,
        itens=[schemas.ItemReconciliadoOut(**i) for i in snap.get("itens", [])],
        saldo_m2=snap.get("saldo_m2", 0.0),
        saldo_otimista_m2=snap.get("saldo_otimista_m2", 0.0),
        laudo=snap.get("laudo", {}),
        avisos=snap.get("avisos", []),
        liberadas_geojson=snap.get("liberadas"),
        preservacao_geojson=snap.get("preservacao"),
        novas_restricoes_geojson=snap.get("novas_restricoes"),
        leitura=(
            "A BASE só conta o que o laudo constatou NÃO ser vegetação nativa (decisão do "
            "operador, 09/08). Nativa suprimível 'mediante autorização' entra apenas no "
            "CENÁRIO OTIMISTA do Aproveitamento — e vale SE o órgão competente autorizar "
            "(Lei 12.651, art. 26); a autorização não é da plataforma. Vedadas e preservação "
            "obrigatória ficam fora até do otimista. O satélite original fica no histórico."
        ),
    )


@router.get(
    "/analises/{analise_id}/ambiental/manchas",
    response_model=schemas.ManchasAmbientaisOut,
)
def listar_manchas(
    analise_id: str,
    usuario: Usuario = Depends(usuario_atual),
    fonte_veg: FonteVegetacao | None = Depends(get_fonte_vegetacao),
    fonte_camadas: FonteCamadas | None = Depends(get_fonte_camadas),
    fonte_bioma: FonteBioma | None = Depends(get_fonte_bioma),
    fonte_gate: FontePortfolio = Depends(get_fonte_gate_ambexc),
    fonte_rec: reconciliacao_store.FonteReconciliacao = Depends(
        reconciliacao_store.get_fonte_reconciliacao
    ),
):
    registro = _registro_ou_404(analise_id)
    gate = _resolver_gate(usuario, fonte_gate)
    if gate.status == "bloqueado":
        # Bloqueio REAL no servidor (padrão portfólio): só o gate, sem dados.
        return schemas.ManchasAmbientaisOut(gate=gate)

    averif, rl, aviso = _severidade_a_verificar(registro, fonte_veg, fonte_camadas)
    regime = _regime_da_analise(registro, fonte_bioma)
    avisos = list(regime.avisos)
    if aviso:
        avisos.append(aviso)

    gleba = registro["poly"]
    manchas = manchas_mod.extrair_manchas(gleba, averif)
    fonte_classes = manchas_mod.get_fonte_classes_vegetacao()
    fracoes = (fonte_classes.fracoes_por_mancha(gleba, manchas)
               if fonte_classes is not None else None)
    rotulo_classes = fonte_classes.rotulo if fonte_classes is not None else "MapBiomas"
    opinioes = manchas_mod.segunda_opiniao(
        gleba, manchas, fracoes, rotulo_classes, rl, rl is not None
    )

    versoes = fonte_rec.carregar(analise_id)
    vigente_out = _resumo_out(versoes[-1], len(versoes)) if versoes else None

    return schemas.ManchasAmbientaisOut(
        gate=gate,
        regime=schemas.RegimeAmbientalOut(
            codigo=regime.codigo, rotulo=regime.rotulo, rito=regime.rito,
            cobertura=regime.cobertura, avisos=list(regime.avisos),
        ),
        manchas=[
            schemas.ManchaOut(
                mancha_id=o.mancha.mancha_id, assinatura=o.mancha.assinatura,
                area_m2=o.mancha.area_m2, geojson=o.mancha.geojson,
                leituras=[schemas.LeituraFonteOut(**le.__dict__) for le in o.leituras],
                concordancia=o.concordancia, motivo=o.motivo,
            )
            for o in opinioes
        ],
        reconciliacao_vigente=vigente_out,
        avisos=avisos,
        proveniencia=(
            "Manchas do 'verde a verificar' (WorldCover × APP/UC) com 2ª opinião "
            f"{rotulo_classes} + CAR. Triagem — nenhuma mancha é liberada sem laudo; a "
            "autorização é do órgão competente."
        ),
    )


@router.post(
    "/analises/{analise_id}/ambiental/laudo",
    response_model=schemas.ReconciliacaoResumoOut,
)
async def registrar_laudo(
    analise_id: str,
    dados: str = Form(...),   # JSON de LaudoReconciliacaoIn (multipart: arquivo + dados)
    arquivo: UploadFile | None = File(default=None),
    usuario: Usuario = Depends(usuario_atual),
    fonte_veg: FonteVegetacao | None = Depends(get_fonte_vegetacao),
    fonte_camadas: FonteCamadas | None = Depends(get_fonte_camadas),
    fonte_bioma: FonteBioma | None = Depends(get_fonte_bioma),
    fonte_gate: FontePortfolio = Depends(get_fonte_gate_ambexc),
    fonte_rec: reconciliacao_store.FonteReconciliacao = Depends(
        reconciliacao_store.get_fonte_reconciliacao
    ),
    fonte_anexos: FonteAnexos = Depends(get_fonte_anexos_ambexc),
):
    registro = _registro_ou_404(analise_id)
    gate = _resolver_gate(usuario, fonte_gate)
    if gate.status == "bloqueado":
        raise HTTPException(402, "Recurso de plano pago — prévia gratuita encerrada.")

    try:
        corpo = schemas.LaudoReconciliacaoIn(**json.loads(dados))
    except (ValueError, TypeError) as exc:
        raise HTTPException(422, f"Dados do laudo inválidos: {exc}") from exc
    if not corpo.responsavel.strip():
        raise HTTPException(422, "Responsável técnico é obrigatório.")
    if not corpo.ajustes:
        raise HTTPException(422, "Nenhum ajuste informado — nada a reconciliar.")

    # Anexo do laudo (PDF) — opcional mas recomendado; registro/ART opcional SEM alarde.
    nome_arquivo = None
    if arquivo is not None:
        conteudo = await ler_upload_limitado(arquivo)
        if conteudo:
            anexo = fonte_anexos.salvar(
                analise_id, "laudo_vistoria", arquivo.filename or "laudo.pdf",
                conteudo, date.today().isoformat(),
            )
            nome_arquivo = getattr(anexo, "nome", None) or (arquivo.filename or "laudo.pdf")

    averif, _rl, aviso = _severidade_a_verificar(registro, fonte_veg, fonte_camadas)
    if averif is None:
        raise HTTPException(
            409, aviso or "Sem manchas de vegetação a verificar nesta análise."
        )
    regime = _regime_da_analise(registro, fonte_bioma)
    gleba = registro["poly"]
    manchas = manchas_mod.extrair_manchas(gleba, averif)
    uf = registro["jurisdicao"].uf if registro.get("jurisdicao") else None

    ajustes = [
        arc.AjusteLaudo(
            acao=a.acao, mancha_id=a.mancha_id, assinatura=a.assinatura,
            estagio=a.estagio, formacao=a.formacao,
            tipo_restricao=a.tipo_restricao, geojson=a.geojson, observacao=a.observacao,
        )
        for a in corpo.ajustes
    ]
    rec = arc.reconciliar(
        gleba, manchas, ajustes, regime, corpo.perimetro_urbano_pre_lei, uf
    )
    if not rec.itens:
        raise HTTPException(422, "Nenhum ajuste pôde ser aplicado: " + "; ".join(rec.avisos))

    snap = arc.serializar(rec)
    snap["laudo"] = {
        "responsavel": corpo.responsavel.strip(),
        "registro": corpo.registro.strip(),
        "data_vistoria": corpo.data_vistoria,
        "arquivo": nome_arquivo,
        "registrado_por": getattr(usuario, "email", None),
        "registrado_em": date.today().isoformat(),
        "regime": regime.rotulo,
        "perimetro_urbano_pre_lei": corpo.perimetro_urbano_pre_lei,
        "perimetro_urbano_fonte": corpo.perimetro_urbano_fonte,
    }
    versao = fonte_rec.salvar(analise_id, snap)

    # Invalida o cache canônico: a próxima leitura de QUALQUER aba recalcula com o laudo.
    registro.pop("areas_canonicas", None)

    return _resumo_out(snap, versao)
