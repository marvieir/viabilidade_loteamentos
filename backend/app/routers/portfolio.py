"""AI Portfolio Insights — ``/api/portfolio`` (fase Dashboard-Portfólio, spec 05/08/2026).

Agrega POR USUÁRIO as análises salvas (tabela ``analises``) em KPIs comparáveis:
risco (ambiental/jurídico), aproveitamento (urbanismo) e retorno (financeira/econômica).
TODA a agregação acontece aqui (regra 1 do projeto); o front só renderiza o JSON.

Honestidade do quadro (lições de 28-30/07):
- Dimensão não calculada → KPI ``None`` ("não calculado"), NUNCA zero.
- Percentuais saem SEMPRE em 0-100 (as fontes internas misturam fração 0-1 e 0-100 —
  a normalização mora aqui, num lugar só).
- Premissas divergentes (TMA) viram AVISO de comparabilidade, não silêncio.
- Radar de risco com fórmula DECLARADA no payload (régua nossa de triagem, não veredito).

Gate comercial (decisão do operador 05/08): gratuito tem prévia de 30 dias contada do
PRIMEIRO ACESSO ao painel (persistido no store por usuário); depois bloqueia (as linhas
saem VAZIAS do servidor — o bloqueio não é cosmético). Admin tem bypass; enquanto não há
billing, o admin libera cliente pago manualmente via PUT /portfolio/liberacao/{usuario_id}.

Urbanismo NÃO vive no snapshot ``resultados`` (o front não o inclui) — vem do store de
propostas via ``resultados._analise_id`` (último snapshot da lista).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.auth import requer_admin, usuario_atual
from app.core.db import get_db
from app.core.portfolio_store import FontePortfolio, get_fonte_portfolio
from app.core.urbanismo_store import FonteUrbanismo, get_fonte_urbanismo
from app.models import schemas
from app.models.db_models import Analise, Usuario

router = APIRouter(prefix="/portfolio", tags=["portfolio"])

PREVIA_DIAS = 30

RADAR_FORMULA = {
    "ambiental": "100 − % restrito da gleba bruta (união mata/APP/declividade ≥30%)",
    "juridico": "nível da pré-análise jurídica: baixo=100, médio=50, alto=10",
    "urbanistico": "% de área vendável sobre a área líquida do estudo urbanístico",
    "financeiro": "margem sobre o VGV próprio × 2, limitado a 100",
}


# ----------------------------- utilitários ---------------------------------------


def _brl(v: float) -> str:
    return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _dinheiro_curto(v: float) -> str:
    """Formato dos cards: R$ 42,5 mi / R$ 121 mil / R$ 850,00."""
    if abs(v) >= 1_000_000:
        return ("R$ " + f"{v / 1_000_000:,.1f}").replace(".", ",") + " mi"
    if abs(v) >= 1_000:
        return "R$ " + f"{v / 1_000:,.0f}".replace(",", ".") + " mil"
    return _brl(v)


def _pct_fmt(v: float, casas: int = 1) -> str:
    return f"{v:.{casas}f}".replace(".", ",") + "%"


def _agora() -> datetime:
    return datetime.now(timezone.utc)


def _parse_utc(iso: str) -> Optional[datetime]:
    try:
        dt = datetime.fromisoformat(iso)
    except (TypeError, ValueError):
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def _d(obj, *chaves, default=None):
    """Navegação defensiva em dicts aninhados (snapshots heterogêneos entre fases)."""
    atual = obj
    for c in chaves:
        if not isinstance(atual, dict):
            return default
        atual = atual.get(c)
    return default if atual is None else atual


def _num(v) -> Optional[float]:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


# ----------------------------- gate ----------------------------------------------


def _resolver_gate(usuario: Usuario, fonte: FontePortfolio) -> schemas.PortfolioGateOut:
    if usuario.papel == "admin":
        return schemas.PortfolioGateOut(status="liberado", motivo="conta administradora")
    reg = fonte.carregar(usuario.id) or {}
    if reg.get("liberado") is True:
        return schemas.PortfolioGateOut(
            status="liberado",
            motivo="acesso liberado pelo administrador",
            primeiro_acesso=reg.get("primeiro_acesso"),
        )
    primeiro = reg.get("primeiro_acesso")
    if not primeiro:
        primeiro = _agora().isoformat()
        fonte.salvar(usuario.id, {**reg, "primeiro_acesso": primeiro})
    inicio = _parse_utc(primeiro) or _agora()
    dias_passados = max((_agora() - inicio).days, 0)
    restantes = PREVIA_DIAS - dias_passados
    if restantes <= 0:
        return schemas.PortfolioGateOut(
            status="bloqueado",
            primeiro_acesso=primeiro,
            motivo="prévia gratuita de 30 dias encerrada",
        )
    return schemas.PortfolioGateOut(
        status="previa",
        dias_restantes=restantes,
        primeiro_acesso=primeiro,
        motivo="prévia gratuita do plano gratuito",
    )


# ----------------------------- extração por dimensão ------------------------------


def _kpis_urbanismo(res: dict, fonte_urb: FonteUrbanismo, kpis: dict, prov: dict) -> bool:
    aid = res.get("_analise_id")
    if not isinstance(aid, str) or not aid:
        return False
    snaps = fonte_urb.listar(aid)
    if not snaps:
        return False
    snap = snaps[-1]  # último snapshot (versão mais recente gerada/importada)
    kpis["urbanismo_versao"] = snap.get("versao") if isinstance(snap.get("versao"), int) else len(snaps)
    origem = snap.get("origem_geracao")
    kpis["urbanismo_origem"] = origem if isinstance(origem, str) else None

    n_lotes = snap.get("indicadores", {}).get("n_lotes") if isinstance(snap.get("indicadores"), dict) else None
    if isinstance(n_lotes, int):
        kpis["n_lotes"] = n_lotes
    kpis["area_media_m2"] = _num(_d(snap, "indicadores", "area_media_m2"))

    # Quadro: pct_apo é FRAÇÃO 0-1 sobre a área LÍQUIDA → normaliza para 0-100.
    for chave_kpi, linha in (
        ("pct_vendavel", "vendavel"),
        ("pct_viario", "arruamento"),
        ("pct_sobra", "sobra_geometrica"),
    ):
        frac = _num(_d(snap, "quadro_areas", linha, "pct_apo"))
        if frac is not None:
            kpis[chave_kpi] = round(frac * 100, 1)
    # Verde consolidado: pct_apo aqui é fração da gleba BRUTA.
    frac_verde = _num(_d(snap, "verde_consolidado", "total", "pct_apo"))
    if frac_verde is not None:
        kpis["pct_verde_bruta"] = round(frac_verde * 100, 1)

    rotulo_origem = {"llm": "gerada", "variante": "variante", "importado": "importada"}.get(
        kpis["urbanismo_origem"] or "", kpis["urbanismo_origem"] or "?"
    )
    prov["urbanismo"] = f"proposta v{kpis['urbanismo_versao']} ({rotulo_origem}) do estudo urbanístico"
    return True


def _kpis_risco(res: dict, kpis: dict, prov: dict, dims: list[str]) -> None:
    amb = res.get("ambiental")
    if isinstance(amb, dict):
        dims.append("ambiental")
        alertas = amb.get("alertas") or []
        if isinstance(alertas, list):
            kpis["alertas_criticos"] = sum(
                1 for a in alertas if isinstance(a, dict) and a.get("severidade") == "ALERTA"
            )
            kpis["alertas_informativos"] = sum(
                1 for a in alertas if isinstance(a, dict) and a.get("severidade") == "INFORMATIVO"
            )
        prov["ambiental"] = "camadas oficiais cruzadas na análise ambiental"

    # % restrito consolidado: preferência = aproveitamento.descontos (JÁ em 0-100);
    # fallback = areas_canonicas (m² → %). Fontes com sobreposição já descontada.
    aprov = res.get("aproveitamento")
    if isinstance(aprov, dict):
        dims.append("aproveitamento")
        pct = _num(_d(aprov, "descontos", "percentual_restritivo"))
        if pct is not None:
            kpis["pct_restrito"] = round(pct, 1)
            prov["restricoes"] = "aproveitamento (união vegetação/APP/declividade, sem dupla contagem)"
    if kpis.get("pct_restrito") is None:
        for dim in ("aproveitamento", "vegetacao"):
            can = _d(res.get(dim) if isinstance(res.get(dim), dict) else {}, "areas_canonicas")
            bruta = _num(_d(can or {}, "gleba_bruta_m2"))
            restr = _num(_d(can or {}, "restricoes_fisicas_m2"))
            if bruta and restr is not None and bruta > 0:
                kpis["pct_restrito"] = round(restr / bruta * 100, 1)
                prov["restricoes"] = "áreas canônicas (união das restrições físicas)"
                break

    if isinstance(res.get("vegetacao"), dict):
        dims.append("vegetacao")
    if isinstance(res.get("declividade"), dict):
        dims.append("declividade")

    jur = res.get("juridico")
    if isinstance(jur, dict):
        dims.append("juridico")
        nivel = _d(jur, "sintese_risco", "nivel")
        if nivel in ("baixo", "medio", "alto"):
            kpis["juridico_nivel"] = nivel
        div = _num(_d(jur, "area_check", "divergencia_pct"))  # fração 0-1; null = sem matrícula
        if div is not None:
            kpis["divergencia_area_pct"] = round(div * 100, 1)
        prov["juridico"] = "pré-análise documental (matrículas confirmadas pelo usuário)"


def _kpis_retorno(res: dict, kpis: dict, prov: dict, dims: list[str], area_ha) -> None:
    fin = res.get("financeira")
    if isinstance(fin, dict):
        dims.append("financeira")
        vgv = _num(_d(fin, "vgv", "bruto"))
        kpis["vgv"] = vgv
        kpis["vgv_proprio"] = _num(_d(fin, "vgv", "proprio"))
        modo = _d(fin, "vgv", "permuta", "modo")
        if isinstance(modo, str) and modo not in ("", "nenhuma"):
            kpis["permuta_modo"] = modo
            pct = _num(_d(fin, "vgv", "permuta", "pct"))
            kpis["permuta_pct"] = round(pct * 100, 1) if pct is not None and pct <= 1 else pct
        margem = _num(_d(fin, "indicadores", "margem_sobre_vgv_proprio"))  # fração
        if margem is not None:
            kpis["margem_pct"] = round(margem * 100, 1)
        kpis["lucro"] = _num(_d(fin, "indicadores", "resultado_nominal"))
        kpis["exposicao_maxima"] = _num(_d(fin, "indicadores", "exposicao_maxima", "valor"))
        mes_exp = _d(fin, "indicadores", "exposicao_maxima", "mes")
        kpis["exposicao_mes"] = mes_exp if isinstance(mes_exp, int) else None
        if kpis["lucro"] is not None and kpis["exposicao_maxima"]:
            kpis["multiplo_capital"] = round(kpis["lucro"] / abs(kpis["exposicao_maxima"]), 1)
        lotes_vend = _d(fin, "caso_base", "lotes_vendaveis")
        base_lotes = lotes_vend if isinstance(lotes_vend, int) and lotes_vend > 0 else kpis.get("n_lotes")
        if vgv is not None and base_lotes:
            kpis["receita_por_lote"] = round(vgv / base_lotes, 2)
        if vgv is not None and area_ha:
            kpis["vgv_por_ha"] = round(vgv / area_ha, 2)
        prov["financeira"] = "estudo financeiro da análise (fluxo com premissas declaradas)"

    eco = res.get("economica")
    if isinstance(eco, dict):
        dims.append("economica")
        kpis["vpl"] = _num(_d(eco, "vpl", "valor"))
        tir = _num(_d(eco, "tir", "aa"))
        if tir is not None:
            kpis["tir_aa_pct"] = round(tir * 100, 1)
        status_tir = _d(eco, "tir", "status")
        kpis["tir_status"] = status_tir if isinstance(status_tir, str) else None
        tma = _num(_d(eco, "tma", "aa_real"))
        if tma is not None:
            kpis["tma_aa_pct"] = round(tma * 100, 1)
        pb = _d(eco, "payback", "simples_mes")
        kpis["meses_negativo"] = pb if isinstance(pb, int) else None
        pbd = _d(eco, "payback", "descontado_mes")
        kpis["payback_descontado_mes"] = pbd if isinstance(pbd, int) else None
        prov["economica"] = "avaliação econômica (VPL/TIR/payback à TMA declarada)"

    # Fallback do "meses no negativo": varre o fluxo nominal da Financeira.
    if kpis.get("meses_negativo") is None and isinstance(fin, dict):
        fluxo = fin.get("fluxo")
        if isinstance(fluxo, list) and fluxo:
            for linha in fluxo:
                ac = _num(linha.get("acumulado")) if isinstance(linha, dict) else None
                mes = linha.get("mes") if isinstance(linha, dict) else None
                if ac is not None and ac >= 0 and isinstance(mes, int):
                    kpis["meses_negativo"] = mes
                    break

    # (A dimensão de contexto socioeconômico fica FORA do portfólio de propósito: o
    # critério-coração da fase 6 proíbe qualquer outro router de depender dela — é
    # enriquecimento informativo, nunca insumo de comparação.)


def _radar(kpis: dict) -> schemas.PortfolioRadarOut:
    r = schemas.PortfolioRadarOut()
    if kpis.get("pct_restrito") is not None:
        r.ambiental = round(max(0.0, min(100.0, 100.0 - kpis["pct_restrito"])), 1)
    nivel = kpis.get("juridico_nivel")
    if nivel:
        r.juridico = {"baixo": 100.0, "medio": 50.0, "alto": 10.0}[nivel]
    if kpis.get("pct_vendavel") is not None:
        r.urbanistico = round(max(0.0, min(100.0, kpis["pct_vendavel"])), 1)
    if kpis.get("margem_pct") is not None:
        r.financeiro = round(max(0.0, min(100.0, kpis["margem_pct"] * 2)), 1)
    return r


def _formatar_dinheiro(kpis: dict) -> None:
    if kpis.get("vgv") is not None:
        kpis["vgv_fmt"] = _dinheiro_curto(kpis["vgv"])
    if kpis.get("vgv_proprio") is not None:
        kpis["vgv_proprio_fmt"] = _dinheiro_curto(kpis["vgv_proprio"])
    if kpis.get("vgv_por_ha") is not None:
        kpis["vgv_por_ha_fmt"] = _dinheiro_curto(kpis["vgv_por_ha"]) + "/ha"
    if kpis.get("lucro") is not None:
        kpis["lucro_fmt"] = _dinheiro_curto(kpis["lucro"])
    if kpis.get("exposicao_maxima") is not None:
        kpis["exposicao_maxima_fmt"] = _dinheiro_curto(abs(kpis["exposicao_maxima"]))
    if kpis.get("receita_por_lote") is not None:
        kpis["receita_por_lote_fmt"] = _dinheiro_curto(kpis["receita_por_lote"])
    if kpis.get("vpl") is not None:
        kpis["vpl_fmt"] = _dinheiro_curto(kpis["vpl"])


def _montar_linha(salva: Analise, fonte_urb: FonteUrbanismo) -> schemas.PortfolioLinhaOut:
    res = salva.resultados if isinstance(salva.resultados, dict) else {}
    kpis: dict = {}
    prov: dict = {}
    dims: list[str] = []

    if _kpis_urbanismo(res, fonte_urb, kpis, prov):
        dims.append("urbanismo")
    _kpis_risco(res, kpis, prov, dims)
    _kpis_retorno(res, kpis, prov, dims, salva.area_ha)
    if kpis.get("n_lotes") and salva.area_ha:
        kpis["lotes_por_ha"] = round(kpis["n_lotes"] / salva.area_ha, 1)
    _formatar_dinheiro(kpis)

    atualizada = salva.atualizada_em.isoformat() if salva.atualizada_em else ""
    return schemas.PortfolioLinhaOut(
        id=salva.id,
        titulo=salva.titulo,
        cidade=salva.cidade,
        uf=salva.uf,
        atualizada_em=atualizada,
        area_ha=salva.area_ha,
        dimensoes=dims,
        kpis=schemas.PortfolioKpisOut(**kpis),
        radar=_radar(kpis),
        proveniencia=prov,
    )


# ----------------------------- destaques e avisos ---------------------------------

_DESTAQUES = [
    # (chave, rotulo, atributo do kpi, melhor=max?, formatador, fonte)
    ("maior_vgv", "Maior VGV", "vgv", True, _dinheiro_curto, "Financeira"),
    ("maior_vgv_ha", "Maior VGV por hectare", "vgv_por_ha", True,
     lambda v: _dinheiro_curto(v) + "/ha", "Financeira ÷ área bruta"),
    ("mais_lotes", "Mais lotes", "n_lotes", True,
     lambda v: f"{int(v)} lotes", "Estudo urbanístico"),
    ("menor_exposicao", "Menor exposição de caixa", "exposicao_maxima", False,
     lambda v: _dinheiro_curto(abs(v)), "Financeira (exposição máxima)"),
    ("positivo_mais_cedo", "Vira positivo mais cedo", "meses_negativo", False,
     lambda v: f"{int(v)} meses", "Fluxo nominal (payback simples)"),
    ("menor_risco_ambiental", "Menor risco ambiental", "pct_restrito", False,
     lambda v: _pct_fmt(v) + " restrito", "Restrições físicas sobre a gleba bruta"),
    ("melhor_tir", "Melhor TIR", "tir_aa_pct", True,
     lambda v: _pct_fmt(v) + " a.a.", "Econômica (à TMA declarada)"),
    ("maior_multiplo", "Maior múltiplo de capital", "multiplo_capital", True,
     lambda v: f"{v:.1f}×".replace(".", ","), "Lucro ÷ exposição máxima"),
]


def _destaques(linhas: list[schemas.PortfolioLinhaOut]) -> list[schemas.PortfolioDestaqueOut]:
    out: list[schemas.PortfolioDestaqueOut] = []
    for chave, rotulo, attr, maior, fmt, fonte in _DESTAQUES:
        candidatas = [(getattr(l.kpis, attr), l) for l in linhas if getattr(l.kpis, attr) is not None]
        if not candidatas:
            continue
        # Exposição compara em valor absoluto (a máxima vem como magnitude do caixa no fundo).
        valor_ord = (lambda v: abs(v)) if attr == "exposicao_maxima" else (lambda v: v)
        v, linha = (max if maior else min)(candidatas, key=lambda par: valor_ord(par[0]))
        out.append(
            schemas.PortfolioDestaqueOut(
                chave=chave, rotulo=rotulo, valor_fmt=fmt(v), analise_id=linha.id,
                titulo=linha.titulo, cidade=linha.cidade, uf=linha.uf, fonte=fonte,
            )
        )
    return out


def _avisos(linhas: list[schemas.PortfolioLinhaOut]) -> list[str]:
    avisos: list[str] = []
    tmas = sorted({l.kpis.tma_aa_pct for l in linhas if l.kpis.tma_aa_pct is not None})
    if len(tmas) > 1:
        valores = " e ".join(_pct_fmt(t) for t in tmas)
        avisos.append(
            f"Comparabilidade: as análises usam TMA diferentes ({valores} a.a.) — "
            "TIR e VPL entre elas não são diretamente comparáveis."
        )
    sem_dados = sum(1 for l in linhas if not l.dimensoes)
    if sem_dados:
        avisos.append(
            f"{sem_dados} análise(s) ainda sem dimensão calculada — as células aparecem "
            "vazias até você rodar e salvar as análises."
        )
    return avisos


# ----------------------------- endpoints ------------------------------------------


@router.get("", response_model=schemas.PortfolioOut)
def portfolio(
    usuario: Usuario = Depends(usuario_atual),
    db: Session = Depends(get_db),
    fonte_gate: FontePortfolio = Depends(get_fonte_portfolio),
    fonte_urb: FonteUrbanismo = Depends(get_fonte_urbanismo),
):
    gate = _resolver_gate(usuario, fonte_gate)
    salvas = (
        db.query(Analise)
        .filter(Analise.usuario_id == usuario.id)
        .order_by(Analise.atualizada_em.desc())
        .all()
    )
    if gate.status == "bloqueado":
        # Bloqueio REAL no servidor: nenhuma linha sai; só o tamanho do portfólio,
        # para a tela dizer "suas N áreas continuam guardadas".
        return schemas.PortfolioOut(gate=gate, total_analises=len(salvas))

    linhas = [_montar_linha(s, fonte_urb) for s in salvas]
    return schemas.PortfolioOut(
        gate=gate,
        total_analises=len(salvas),
        com_dados=sum(1 for l in linhas if l.dimensoes),
        linhas=linhas,
        destaques=_destaques(linhas),
        radar_formula=RADAR_FORMULA,
        avisos=_avisos(linhas),
    )


@router.put("/liberacao/{usuario_id}", response_model=schemas.PortfolioLiberacaoOut)
def liberar(
    usuario_id: str,
    body: schemas.PortfolioLiberacaoIn,
    _admin: Usuario = Depends(requer_admin),
    fonte_gate: FontePortfolio = Depends(get_fonte_portfolio),
):
    """Destrava (ou re-trava) o painel para um cliente — a alavanca manual do admin
    enquanto não existe billing (cliente pagou → admin libera)."""
    # O id vira nome de arquivo no store: só aceita o formato de id da casa (uuid hex/hífen).
    if not re.fullmatch(r"[A-Za-z0-9-]{1,64}", usuario_id):
        raise HTTPException(status_code=422, detail="usuario_id inválido.")
    reg = fonte_gate.carregar(usuario_id) or {}
    reg["liberado"] = body.liberado
    fonte_gate.salvar(usuario_id, reg)
    return schemas.PortfolioLiberacaoOut(usuario_id=usuario_id, liberado=body.liberado)
