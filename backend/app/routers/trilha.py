"""Fase UX-1 — a Trilha da Análise (spec: docs/fase-ux-onboarding.md).

O usuário novo carrega o KMZ e vê oito portas sem ordem; a trilha diz qual é a próxima e o
porquê. O estado é DERIVADO no backend (mesma entrada → mesma trilha, regra inegociável de
que o front só renderiza JSON) a partir do que já existe: jurisdição/cobertura do registro,
perfil municipal, snapshot salvo e stores de urbanismo/jurídico/financeira.

A trilha é SUGERIDA — decisão do operador (21/07/2026): nenhum passo trava endpoint algum.
O passo "diretrizes" carrega o WARNING de cobertura (âmbar) em vez de bloquear.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.acesso import analise_do_dono
from app.core.auth import usuario_atual
from app.core.db import get_db
from app.core.financeira_store import FonteFinanceira, get_fonte_financeira
from app.core.juridico_store import FonteJuridica, get_fonte_juridica
from app.core.perfil_municipal import FontePerfilMunicipal, get_fonte_perfil
from app.core.urbanismo_store import FonteUrbanismo, get_fonte_urbanismo
from app.models.db_models import Analise, Usuario
from app.models.schemas import TrilhaOut, TrilhaPasso

router = APIRouter(prefix="/analises", tags=["trilha"])

_ORDEM = ("gleba", "diretrizes", "ambiental", "urbanismo", "juridico", "financeira")


def _fmt_ha(area_m2: float) -> str:
    return f"{area_m2 / 10000.0:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _snapshot_da_salva(db: Session, usuario: Usuario, analise_id: str) -> dict:
    """Resultados da salva vinculada (mesmo vínculo ``_analise_id`` da guarda de acesso)."""
    try:
        salvas = db.query(Analise).filter(Analise.usuario_id == usuario.id).all()
    except Exception:  # noqa: BLE001 — banco indisponível não derruba a trilha
        return {}
    for a in salvas:
        res = a.resultados if isinstance(a.resultados, dict) else {}
        if res.get("_analise_id") == analise_id:
            return res
    return {}


@router.get("/{analise_id}/trilha", response_model=TrilhaOut)
def trilha_da_analise(
    analise_id: str,
    registro: dict = Depends(analise_do_dono),
    usuario: Usuario = Depends(usuario_atual),
    db: Session = Depends(get_db),
    fonte_perfil: FontePerfilMunicipal | None = Depends(get_fonte_perfil),
    fonte_urbanismo: FonteUrbanismo = Depends(get_fonte_urbanismo),
    fonte_juridica: FonteJuridica = Depends(get_fonte_juridica),
    fonte_financeira: FonteFinanceira = Depends(get_fonte_financeira),
) -> TrilhaOut:
    jur = registro["jurisdicao"]
    snapshot = _snapshot_da_salva(db, usuario, analise_id)
    passos: list[TrilhaPasso] = []

    # 1) Gleba — a análise existe, logo o KMZ virou gleba medida.
    passos.append(TrilhaPasso(
        id="gleba", titulo="Gleba carregada", estado="concluido",
        motivo=f"{_fmt_ha(registro['area_m2'])} ha medidos por cálculo geodésico.",
    ))

    # 2) Município e diretrizes — o warning de cobertura mora aqui (nunca bloqueia).
    perfil = None
    if fonte_perfil is not None and getattr(jur, "cod_ibge", None):
        try:
            perfil = fonte_perfil.carregar(jur.cod_ibge)
        except Exception:  # noqa: BLE001 — fonte de perfil indisponível → segue sem perfil
            perfil = None
    perfil_ok = perfil is not None and getattr(perfil, "status", "") == "confirmado"
    if perfil_ok:
        passos.append(TrilhaPasso(
            id="diretrizes", titulo="Município e diretrizes", estado="concluido",
            motivo=(f"Perfil de {jur.municipio}/{jur.uf} confirmado — a análise usa o lote "
                    "mínimo, a doação e o zoneamento do município."),
            cobertura=jur.cobertura,
        ))
    elif getattr(jur, "municipio", None) is None:
        passos.append(TrilhaPasso(
            id="diretrizes", titulo="Município e diretrizes", estado="pendente",
            motivo=("O município não foi detectado. Selecione-o no painel da análise para a "
                    "jurisdição correta; sem ele a análise fica no piso federal."),
            cobertura=jur.cobertura,
        ))
    else:
        passos.append(TrilhaPasso(
            id="diretrizes", titulo="Município e diretrizes", estado="atencao",
            motivo=(f"{jur.municipio}/{jur.uf} detectado, mas sem o plano diretor/LUOS a "
                    "análise roda no nível federal: lote mínimo municipal, doação e zoneamento "
                    "não são considerados. Envie o PDF no menu Diretriz (LUOS) para a "
                    "cobertura completa."),
            cobertura=jur.cobertura,
        ))

    # 3) Ambiental — concluído quando o snapshot salvo tem o resultado.
    if snapshot.get("ambiental"):
        amb = TrilhaPasso(id="ambiental", titulo="Pré-análise ambiental", estado="concluido",
                          motivo="Alertas levantados com fonte e data de referência ao lado.")
    else:
        amb = TrilhaPasso(
            id="ambiental", titulo="Pré-análise ambiental", estado="disponivel",
            motivo=("Um clique: cruza APP, vegetação, declividade, unidades de conservação e "
                    "mineração — cada alerta com a fonte oficial e a data."),
        )
    passos.append(amb)

    # 4) Urbanismo — concluído quando existe proposta no store (sobrevive a restart).
    try:
        tem_urbanismo = bool(fonte_urbanismo.listar(analise_id))
    except Exception:  # noqa: BLE001
        tem_urbanismo = False
    passos.append(TrilhaPasso(
        id="urbanismo", titulo="Pré-projeto urbanístico",
        estado="concluido" if tem_urbanismo else "disponivel",
        motivo=("Proposta gerada — regenere para comparar objetivos (Rendimento × Paisagem)."
                if tem_urbanismo else
                "Gera o traçado esquemático com quadro de áreas fechando 100%, lotes, "
                "vias e verde — respeitando mata e declividade."),
    ))

    # 5) Jurídico — precisa de insumo do usuário (matrícula/certidão).
    try:
        fichas = fonte_juridica.carregar(analise_id)
    except Exception:  # noqa: BLE001
        fichas = []
    if any(getattr(f, "status", "") == "confirmado" for f in fichas):
        passos.append(TrilhaPasso(id="juridico", titulo="Pré-análise jurídica",
                                  estado="concluido",
                                  motivo="Ficha confirmada — ônus e riscos no relatório."))
    elif fichas:
        passos.append(TrilhaPasso(
            id="juridico", titulo="Pré-análise jurídica", estado="disponivel",
            motivo="Ficha extraída aguardando sua revisão — confira os campos e confirme.",
        ))
    else:
        passos.append(TrilhaPasso(
            id="juridico", titulo="Pré-análise jurídica", estado="pendente",
            motivo="Envie a matrícula (PDF ou foto) para extrair a ficha, os ônus e o "
                   "checklist de documentos.",
        ))

    # 6) Financeira — faz sentido depois do urbanismo (precisa de lotes para precificar).
    try:
        tem_financeira = fonte_financeira.carregar(analise_id) is not None
    except Exception:  # noqa: BLE001
        tem_financeira = False
    if tem_financeira:
        passos.append(TrilhaPasso(id="financeira", titulo="Análise financeira e laudo",
                                  estado="concluido",
                                  motivo="Fluxo salvo — exporte o laudo em PDF ou Excel."))
    elif tem_urbanismo:
        passos.append(TrilhaPasso(
            id="financeira", titulo="Análise financeira e laudo", estado="disponivel",
            motivo="Com o urbanismo pronto, o passo a passo da financeira monta VGV, margem "
                   "e fluxo a partir dos lotes gerados.",
        ))
    else:
        passos.append(TrilhaPasso(
            id="financeira", titulo="Análise financeira e laudo", estado="pendente",
            motivo="Gere o pré-projeto urbanístico primeiro — a financeira precifica os "
                   "lotes que ele produz.",
        ))

    por_id = {p.id: p for p in passos}
    passo_atual = next(
        (pid for pid in _ORDEM if por_id[pid].estado != "concluido"), _ORDEM[-1]
    )
    return TrilhaOut(passo_atual=passo_atual, passos=passos)
