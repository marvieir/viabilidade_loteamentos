"""Núcleo determinístico da pré-análise jurídica documental (Fase 3).

Tudo aqui é **puro** (sem I/O, sem LLM): consolida as fichas CONFIRMADAS, faz o cross-check
de área (matrícula × KMZ da Fase 1) e o roll-up de risco (achados dominiais + alertas geo já
calculados em 2.1/2.3/2.5). Mesma entrada → mesma saída.

Fronteira inegociável: NUNCA afirma "imóvel livre". Ausência de achado ≠ imóvel limpo — os
avisos de §4.3 acompanham toda saída; a síntese 'baixo' vem sempre com a ressalva.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.models import schemas

TOL_AREA_DEFAULT = 0.05  # 5% (configurável pelo chamador)

# Ônus que travam a transação → entram em 'criticos' do roll-up (nível alto).
ONUS_BLOQUEANTES = {
    "hipoteca",
    "alienacao_fiduciaria",
    "penhora",
    "arresto",
    "indisponibilidade",
}

_ROTULO_ONUS = {
    "hipoteca": "Hipoteca",
    "alienacao_fiduciaria": "Alienação fiduciária",
    "penhora": "Penhora",
    "arresto": "Arresto",
    "usufruto": "Usufruto",
    "servidao": "Servidão",
    "inalienabilidade": "Cláusula de inalienabilidade",
    "impenhorabilidade": "Cláusula de impenhorabilidade",
}

# Avisos obrigatórios (§4.3) — SEMPRE presentes; pré-análise nunca certifica ausência.
AVISOS_OBRIGATORIOS = [
    "PRÉ-ANÁLISE — extrai o que CONSTA nos documentos apresentados; NÃO substitui parecer "
    "de advogado.",
    "Ausência de ônus na lista NÃO significa imóvel livre: depende dos documentos carregados "
    "e de certidões atualizadas.",
    "Cadeia dominial e certidões pessoais do vendedor devem ser verificadas por profissional.",
]


@dataclass
class AlertaGeo:
    """Alerta geo já calculado (mineração/2.1, verde-em-APP/2.3, ≥30%/2.5) para o roll-up."""

    chave: str
    descricao: str
    nivel: str  # "vedado" | "atencao"


def _rotulo_onus(tipo: str) -> str:
    return _ROTULO_ONUS.get(tipo, tipo.replace("_", " ").capitalize())


def cross_check_area(
    area_matricula_m2: float | None,
    area_kmz_m2: float,
    tol: float = TOL_AREA_DEFAULT,
    n_matriculas: int = 0,
) -> schemas.AreaCheckOut:
    """divergencia = |area_matricula − area_kmz| / area_kmz. ≤ tol → conforme; senão atenção.
    Multi-matrícula: ``area_matricula_m2`` é a SOMA das matrículas (item 7c do roteiro).
    Sem área de matrícula confirmada → indisponível (nunca inventa)."""
    if area_matricula_m2 is None:
        return schemas.AreaCheckOut(
            area_matricula_m2=None,
            area_kmz_m2=round(area_kmz_m2, 2),
            divergencia_pct=None,
            status="indisponivel",
            n_matriculas=n_matriculas,
            proveniencia="Área da matrícula não confirmada; apenas a medição do KMZ (Fase 1).",
        )
    div = abs(area_matricula_m2 - area_kmz_m2) / area_kmz_m2 if area_kmz_m2 else 0.0
    base = (
        f"Soma de {n_matriculas} matrículas (área registrada)"
        if n_matriculas > 1
        else "Matrícula (área registrada)"
    )
    return schemas.AreaCheckOut(
        area_matricula_m2=round(area_matricula_m2, 2),
        area_kmz_m2=round(area_kmz_m2, 2),
        divergencia_pct=round(div, 4),
        status="conforme" if div <= tol else "atencao",
        n_matriculas=n_matriculas,
        proveniencia=f"{base} × medição do KMZ (Fase 1).",
    )


def consolidar_fichas(fichas: list[schemas.FichaJuridica]) -> dict:
    """Achata as fichas CONFIRMADAS em saídas com proveniência. Determinístico.

    Retorna dict com: documentos, onus, averbacoes, certidoes, area_matricula_m2,
    indisponivel_consta.
    """
    documentos: list[schemas.DocumentoResumoOut] = []
    onus_out: list[schemas.OnusOut] = []
    averbacoes_out: list[schemas.AverbacaoOut] = []
    certidoes_out: list[schemas.CertidaoOut] = []
    # Multi-matrícula: SOMA das áreas (não "a última") + contagem, p/ cruzar a soma com o total
    # da gleba (item 7c do roteiro). area_matricula_total_m2 fica None se NENHUMA matrícula trouxe
    # área — pra distinguir "sem área" de "soma zero".
    area_matricula_total_m2: float | None = None
    n_matriculas = 0
    indisponivel_consta = False

    for f in fichas:
        if f.status != "confirmado":
            continue  # gate: só ficha confirmada entra
        ref_doc = f.fonte_documento or f.tipo
        n_mat = None
        if f.identificacao and f.identificacao.matricula:
            n_mat = f.identificacao.matricula.valor
        prop = None
        if f.identificacao and f.identificacao.proprietario_atual:
            prop = f.identificacao.proprietario_atual.valor
        area_doc: float | None = None
        if (
            f.tipo == "matricula"
            and f.identificacao
            and f.identificacao.area_registrada_m2
        ):
            v = f.identificacao.area_registrada_m2.valor
            if v is not None:
                area_doc = float(v)

        documentos.append(
            schemas.DocumentoResumoOut(
                tipo=f.tipo,
                status=f.status,
                fonte=f.fonte_documento,
                validado_por=f.validado_por,
                data_referencia=f.data_referencia,
                matricula=n_mat,
                proprietario=prop,
                area_m2=round(area_doc, 2) if area_doc is not None else None,
            )
        )

        if f.tipo == "matricula":
            if area_doc is not None:
                area_matricula_total_m2 = (area_matricula_total_m2 or 0.0) + area_doc
                n_matriculas += 1
            for o in f.onus:
                # Ato administrativo/benigno (cancelamento, baixa, denominação, CAR…) não é
                # gravame ativo, mesmo com situacao='consta' — não polui o risco.
                ativo = o.situacao == "consta" and not _ato_neutro(o.tipo)
                onus_out.append(
                    schemas.OnusOut(
                        tipo=o.tipo,
                        descricao=o.descricao,
                        ato=o.ato,
                        situacao=o.situacao,
                        status="atencao" if ativo else "conforme",
                        proveniencia=_prov_ato(n_mat, ref_doc, o.ato, o.pagina),
                    )
                )
            for a in f.averbacoes:
                averbacoes_out.append(
                    schemas.AverbacaoOut(
                        tipo=a.tipo,
                        descricao=a.descricao,
                        ato=a.ato,
                        proveniencia=_prov_ato(n_mat, ref_doc, a.ato, a.pagina),
                    )
                )
            if f.indisponibilidade and f.indisponibilidade.consta:
                indisponivel_consta = True

        elif f.tipo == "certidao":
            positiva = f.resultado == "positiva"
            certidoes_out.append(
                schemas.CertidaoOut(
                    orgao=f.orgao.valor if f.orgao else None,
                    especie=f.especie.valor if f.especie else None,
                    resultado=f.resultado,
                    status="atencao" if positiva else "conforme",
                    proveniencia=f"Certidão {ref_doc}"
                    + (f" — {f.orgao.valor}" if f.orgao and f.orgao.valor else ""),
                )
            )

    return {
        "documentos": documentos,
        "onus": onus_out,
        "averbacoes": averbacoes_out,
        "certidoes": certidoes_out,
        "area_matricula_m2": area_matricula_total_m2,  # SOMA das matrículas (não "a última")
        "n_matriculas": n_matriculas,
        "indisponivel_consta": indisponivel_consta,
    }


def _prov_ato(n_mat: str | None, ref_doc: str, ato: str | None, pagina: int | None) -> str:
    base = f"Matrícula {n_mat}" if n_mat else ref_doc
    partes = [base]
    if ato:
        partes.append(ato)
    if pagina:
        partes.append(f"p.{pagina}")
    return ", ".join(partes)


def roll_up_risco(
    onus_out: list[schemas.OnusOut],
    averbacoes_out: list[schemas.AverbacaoOut],
    area_check: schemas.AreaCheckOut | None,
    certidoes_out: list[schemas.CertidaoOut],
    indisponivel_consta: bool,
    alertas_geo: list[AlertaGeo],
) -> schemas.SinteseRiscoOut:
    """Roll-up determinístico (§3.4). alto se ônus que trava / divergência / vedado geo;
    médio se só atenção; baixo se nada relevante CONSTA (com a ressalva de §1)."""
    criticos: list[str] = []
    atencao: list[str] = []

    for o in onus_out:
        if o.situacao != "consta" or _ato_neutro(o.tipo):
            continue  # cancelamento/baixa/ato administrativo não é gravame ativo
        rot = f"{_rotulo_onus(o.tipo)}" + (f" ({o.ato})" if o.ato else "")
        (criticos if o.tipo in ONUS_BLOQUEANTES else atencao).append(rot)

    if indisponivel_consta:
        criticos.append("Indisponibilidade averbada")

    if area_check is not None and area_check.status == "atencao":
        pct = (area_check.divergencia_pct or 0) * 100
        criticos.append(f"Divergência de área {pct:.1f}% (matrícula × KMZ)")

    for a in averbacoes_out:
        if not _averbacao_e_risco(a.tipo):
            continue  # cancelamento/casamento/retificação/georref = histórico, não risco
        rot = _rotulo_averbacao(a.tipo) + (f" ({a.ato})" if a.ato else "")
        atencao.append(rot)

    for c in certidoes_out:
        if c.status == "atencao":
            atencao.append(
                f"Certidão positiva{f' — {c.orgao}' if c.orgao else ''}"
            )

    for g in alertas_geo:
        (criticos if g.nivel == "vedado" else atencao).append(g.descricao)

    if criticos:
        nivel = "alto"
        resumo = (
            "Constam ônus e/ou restrições que exigem due diligence jurídica antes de avançar."
        )
    elif atencao:
        nivel = "medio"
        resumo = "Constam pontos de atenção a verificar com profissional antes de avançar."
    else:
        nivel = "baixo"
        resumo = (
            "Nada relevante consta nos documentos apresentados — o que NÃO significa imóvel "
            "livre (ver avisos)."
        )

    return schemas.SinteseRiscoOut(
        nivel=nivel, criticos=criticos, atencao=atencao, resumo=resumo
    )


# Atos que NÃO são risco — histórico/administrativo de cartório (cancelamentos, baixa, estado
# civil, retificação, georreferenciamento, denominação do imóvel, registro no CAR). Ficam na
# ficha, mas fora do painel de risco. Vale p/ ônus E averbações (um cancelamento mal-tipado como
# ônus não pode inflar o risco).
_ATOS_NEUTROS = (
    "cancelament",
    "baixa",
    "casament",
    "divorcio",
    "obito",
    "estado_civil",
    "estado civil",
    "retifica",
    "georref",
    "denominac",          # denominacao / alteracao_denominacao (nome do imóvel)
    "cadastro_ambiental",  # cadastro_ambiental_rural (registro no CAR = informativo)
)


def _ato_neutro(tipo: str) -> bool:
    """Ato administrativo/informativo (não onera nem reduz a gleba) → fora do risco."""
    t = (tipo or "").lower().strip()
    if t in ("car", "car_imovel"):  # CAR (registro ambiental) = informativo, não gravame
        return True
    return any(k in t for k in _ATOS_NEUTROS)


def _averbacao_e_risco(tipo: str) -> bool:
    """Averbação relevante para a triagem (reduz/onera a gleba: reserva legal, APP,
    servidão, restrição, construção). Atos meramente administrativos → False."""
    return not _ato_neutro(tipo)


def _rotulo_averbacao(tipo: str) -> str:
    mapa = {
        "reserva_legal": "Reserva legal averbada",
        "app": "APP averbada",
        "georreferenciamento": "Georreferenciamento",
        "construcao": "Construção averbada",
    }
    return mapa.get(tipo, tipo.replace("_", " ").capitalize())
