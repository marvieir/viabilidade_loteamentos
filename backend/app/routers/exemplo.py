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

from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import requer_admin
from app.models import schemas
from app.models.db_models import Usuario

router = APIRouter()  # GET é PÚBLICO (é isso que ele serve); publicar/despublicar exigem admin


def _dir_exemplo() -> Path:
    import os
    d = os.getenv("EXEMPLO_DIR", "").strip()
    if d:
        return Path(d)
    return Path("/data/perfis/exemplo") if Path("/data/perfis").is_dir() \
        else Path("app/perfis/_dados/exemplo")


_ARQ_COMPLETO = "laudo_completo.json"

# Chaves que NUNCA saem numa página pública, onde quer que apareçam (defesa em profundidade —
# a seção jurídica já é removida INTEIRA; isto cobre regressões futuras em outras seções).
_CHAVES_PROIBIDAS = {"proprietario", "proprietarios", "cpf", "cnpj", "matricula",
                     "validado_por", "documentos", "checklist", "fonte_documento"}


def _remover_sensiveis(obj):
    """Remove recursivamente chaves sensíveis do snapshot público."""
    if isinstance(obj, dict):
        return {k: _remover_sensiveis(v) for k, v in obj.items()
                if k.lower() not in _CHAVES_PROIBIDAS}
    if isinstance(obj, list):
        return [_remover_sensiveis(x) for x in obj]
    return obj


def _camadas_ambientais(body: "ExemploPublicarIn") -> dict:
    """Junta as camadas que os cards do app mandam ao mapa, com as MESMAS chaves/cores."""
    saida: dict = {}
    amb = body.ambiental or {}
    for k, v in (amb.get("geojson_overlays") or {}).items():
        if v:
            saida[k] = v
    veg = body.vegetacao or {}
    sev = veg.get("severidade") or {}
    dura = (sev.get("restricao_dura") or {}).get("geojson")
    verif = (sev.get("a_verificar") or {}).get("geojson")
    if dura:
        saida["verde_dura"] = dura
    if verif:
        saida["verde_verificar"] = verif
    if not sev and veg.get("geojson_verde"):
        saida["verde"] = veg["geojson_verde"]
    dec = body.declividade or {}
    ved = (dec.get("flag_vedacao") or {}).get("geojson")
    if ved:
        saida["declividade_vedada"] = ved
    if dec.get("geojson_faixas"):
        saida["declividade_faixas"] = dec["geojson_faixas"]
    return saida


class ExemploPublicarIn(schemas.LaudoIn):
    """Mesmo corpo do laudo PDF (o front repassa os JSONs das dimensões) + a identidade da
    análise e a gleba para o mapa. Nada é recalculado aqui."""

    analise_id: str
    titulo: Optional[str] = None
    gleba_geojson: Optional[dict] = None


@router.post("/exemplo/publicar")
def publicar_exemplo(body: ExemploPublicarIn, _adm: Usuario = Depends(requer_admin)) -> dict:
    """ADMIN: promove uma análise real a EXEMPLO PÚBLICO da plataforma (decisão do operador,
    29/07). A seção jurídica é substituída por CONTAGENS por severidade — a classificação
    vem dos status que o produto já atribui (conforme/atencao/vedado), nunca de juízo novo —
    e nenhum detalhe de achado, nome, matrícula ou CPF entra no retrato."""
    from datetime import date

    from app.core import laudo as laudo_core
    from app.core.store import STORE
    from app.routers.laudo import _identificacao

    registro = STORE.get(body.analise_id)
    if registro is None:
        raise HTTPException(404, "Análise não encontrada no servidor — reabra-a e tente de novo.")

    ident = _identificacao(body.analise_id, registro)
    dims = {c: getattr(body, c) for c in schemas.LaudoIn.model_fields}
    laudo = laudo_core.montar_laudo_data(ident, dims, date.today().isoformat())

    # Jurídico público = só contagens, pelas classes que o produto JÁ usa nos ônus.
    jur = body.juridico or {}
    onus = jur.get("onus") or []
    contagens = {
        "criticos": sum(1 for o in onus if o.get("status") == "vedado"),
        "moderados": sum(1 for o in onus if o.get("status") == "atencao"),
        "sem_impacto": sum(1 for o in onus if o.get("status") == "conforme"),
        "n_documentos": len(jur.get("documentos") or []),
        "luz": next((l.luz for l in laudo.semaforo if "jur" in l.dimensao.lower()), "nao_analisada"),
    }

    ident_pub = {k: v for k, v in ident.items() if k != "analise_id"}
    urb = body.urbanismo or {}
    snapshot = _remover_sensiveis({
        "tipo": "completo",
        "titulo": (body.titulo or "").strip() or "Análise real publicada como exemplo",
        "publicado_em": date.today().isoformat(),
        "identificacao": ident_pub,
        "ressalva": laudo.ressalva_capa,
        "semaforo": [l.model_dump() for l in laudo.semaforo],
        # A seção jurídica sai INTEIRA; as demais vão como o laudo PDF as monta.
        "secoes": [s.model_dump() for s in laudo.secoes if s.chave != "juridico"],
        "juridico": contagens,
        "urbanismo": {
            "geometria": urb.get("geometria"),
            "quadro_areas": urb.get("quadro_areas"),
            "indicadores": urb.get("indicadores"),
        },
        # Camadas do MAPA AMBIENTAL (pedido do operador, 30/07): os cards já produzem
        # geojson_overlays (mineração/CAR/Mata Atlântica/verde/declividade) — só juntamos.
        # Cada card publica com um nome próprio (mesma lógica dos cards do app):
        #   ambiental → geojson_overlays; vegetação → severidade dura/a-verificar;
        #   declividade → vedada + faixas. Reunimos tudo sob as chaves do mapa.
        "ambiental_geo": _camadas_ambientais(body),
        "gleba_geojson": body.gleba_geojson,
        "proveniencia": (
            "Análise REAL feita na plataforma e publicada como exemplo pelo operador, com os "
            "detalhes dos documentos jurídicos suprimidos (apenas contagens por severidade)."
        ),
    })
    d = _dir_exemplo(); d.mkdir(parents=True, exist_ok=True)
    (d / _ARQ_COMPLETO).write_text(
        json.dumps(snapshot, ensure_ascii=False), encoding="utf-8"
    )
    return {"ok": True, "publicado_em": snapshot["publicado_em"]}


@router.delete("/exemplo/publicar")
def despublicar_exemplo(_adm: Usuario = Depends(requer_admin)) -> dict:
    """ADMIN: remove o exemplo completo — a página volta ao laudo simples gerado pelo motor."""
    arq = _dir_exemplo() / _ARQ_COMPLETO
    if arq.exists():
        arq.unlink()
    return {"ok": True}

_CACHE: Optional[dict] = None
_CACHE_COMPLETO: Optional[tuple] = None

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
    """Laudo de exemplo (público). Se o operador publicou uma análise REAL como exemplo,
    serve o retrato completo (sanitizado); senão, o laudo simples gerado pelo motor."""
    arq = _dir_exemplo() / _ARQ_COMPLETO
    if arq.exists():
        try:
            # Cache em memória invalidado por mtime: o retrato tem MBs de GeoJSON e era
            # relido+parseado a cada visita — parte dos ~10 s que o operador mediu no botão.
            global _CACHE_COMPLETO
            mtime = arq.stat().st_mtime
            if _CACHE_COMPLETO is None or _CACHE_COMPLETO[0] != mtime:
                _CACHE_COMPLETO = (mtime, json.loads(arq.read_text(encoding="utf-8")))
            return _CACHE_COMPLETO[1]
        except (OSError, ValueError):
            pass  # arquivo corrompido → cai no laudo simples (nunca quebra a página)
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
