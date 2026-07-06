"""Router da Fase 9 — Urbanismo (estudo de massa esquemático proposto por IA).

Endpoints:
  POST /analises/{id}/urbanismo/medir   → MEDE um layout (GeoJSON) — determinístico, SEM LLM.
                                           É o que os valores-ouro de São Roque aferem.
  POST /analises/{id}/urbanismo/propor  → IA propõe o PROGRAMA; Python gera+mede; snapshot
                                           versionado. 503 sem credencial de LLM.
  GET  /analises/{id}/urbanismo          → lista as propostas (snapshots) da análise.
  GET  /analises/{id}/urbanismo/{pid}    → uma proposta.

Fronteira do §2: o LLM só entra em /propor (programa); /medir e a geometria/medida são
Python puro. A Fase 9 NÃO altera nenhuma dimensão anterior (cenário aditivo).
"""

from __future__ import annotations

import dataclasses
import math
import os
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from shapely.ops import transform, unary_union

from app.core import conexao as conexao_mod
from app.core import urbanismo_geom as geom
from app.core import urbanismo_medida as medida
from app.core import uso_llm
from app.core.camadas import FonteCamadas, get_fonte_camadas
from app.core.declividade import FonteDEM, amostrar_declividade, get_fonte_dem
from app.core.perfil_municipal import FontePerfilMunicipal, get_fonte_perfil
from app.core.store import STORE
from app.core.urbanismo_diretrizes import resolver_diretrizes
from app.core.urbanismo_programa import (
    GeradorIndisponivel,
    GeradorPrograma,
    Programa,
    get_gerador_programa,
)
from app.core.urbanismo_memoria import FonteMemoriaUrbanismo, get_fonte_memoria_urbanismo
from app.core.urbanismo_store import FonteUrbanismo, get_fonte_urbanismo
from app.core.vias import FonteVias, get_fonte_vias
from app.core.vegetacao import FonteVegetacao, get_fonte_vegetacao
from app.models import schemas

from app.core.acesso import analise_do_dono
from app.core.auth import usuario_atual
from app.models.db_models import Usuario
router = APIRouter(dependencies=[Depends(analise_do_dono)])

# Faixas não-edificáveis que viram restrição (espelha o aproveitamento — Fase 2.2).
_CHAVES_RESTRITIVAS = ("app", "app_massa_dagua", "faixa_nao_edificavel", "linhas_transmissao")


def _programa_out(prog) -> schemas.ProgramaOut:
    return schemas.ProgramaOut(
        lote_alvo_m2=prog.lote_alvo_m2,
        densidade=prog.densidade,
        pct_lazer=prog.pct_lazer,
        amenidades=prog.amenidades,
        arquetipo_viario=prog.arquetipo_viario,
        largura_via_m=prog.largura_via_m,
        testada_m=prog.testada_m,
        profundidade_m=prog.profundidade_m,
        pct_institucional=prog.pct_institucional,
        publico_alvo=prog.publico_alvo,
        testada_alvo_m=prog.testada_alvo_m,
        faixa_lote_m2=list(prog.faixa_lote_m2),
        lote_alvo_origem=prog.lote_alvo_origem,
        heuristicas=dict(prog.heuristicas or {}),
        origem=prog.origem,
        justificativa=prog.justificativa,
    )


def _medicao_dicts(med: medida.Medicao):
    return (
        schemas.QuadroAreasOut(**med.quadro),
        schemas.IndicadoresUrbOut(**med.indicadores),
        schemas.HeatmapOut(**med.heatmap),
    )


# --------------------------------- /medir (sem LLM) ---------------------------------
@router.post("/analises/{analise_id}/urbanismo/medir", response_model=schemas.MedicaoUrbOut)
def medir_layout(analise_id: str, body: schemas.MedirUrbanismoIn):
    if STORE.get(analise_id) is None:
        raise HTTPException(404, "Análise não encontrada.")
    if not body.lotes and not body.arruamento and not body.areas_verdes:
        raise HTTPException(422, "Layout vazio — envie ao menos lotes ou áreas.")

    layout, to_wgs = medida.layout_de_geojson(
        body.lotes, body.arruamento, body.areas_verdes, body.sistema_lazer, body.institucional
    )
    med = medida.medir(layout)
    quadro, indicadores, heatmap = _medicao_dicts(med)
    return schemas.MedicaoUrbOut(
        geometria=medida.geojson_do_layout(layout, to_wgs, med.heatmap.get("por_lote")),
        quadro_areas=quadro,
        indicadores=indicadores,
        heatmap=heatmap,
        avisos=list(medida.AVISOS_1A),
    )


# --------------------------------- /propor (IA na borda) ---------------------------------
def _cota_sampler(fonte_dem, gleba_wgs, to_wgs):
    """Fase 10 (Parte 3) — amostra a cota (m) do DEM num ponto do frame métrico ``aprov_m``: métrico
    → WGS (``to_wgs``) → AEQD do DEM → bilinear. ``None`` se não há DEM (degradação honesta)."""
    if fonte_dem is None:
        return None
    try:
        dem = fonte_dem.amostrar(gleba_wgs)
    except Exception:  # noqa: BLE001 — DEM indisponível
        return None
    if dem is None or getattr(dem, "elevacao", None) is None:
        return None
    import numpy as np
    from pyproj import Transformer

    Z = np.asarray(dem.elevacao, dtype="float64")
    h, w = Z.shape
    px, x0, y0 = dem.px_m, dem.x0_m, dem.y0_m
    to_dem = Transformer.from_crs("EPSG:4326", dem.crs_proj4, always_xy=True).transform

    def cota(mx: float, my: float) -> float:
        lon, lat = to_wgs(mx, my)
        dx, dy = to_dem(lon, lat)
        c = min(max((dx - x0) / px - 0.5, 0.0), w - 1.001)
        r = min(max((y0 - dy) / px - 0.5, 0.0), h - 1.001)
        c0, r0 = int(c), int(r)
        fc, fr = c - c0, r - r0
        return float(Z[r0, c0] * (1 - fc) * (1 - fr) + Z[r0, c0 + 1] * fc * (1 - fr)
                     + Z[r0 + 1, c0] * (1 - fc) * fr + Z[r0 + 1, c0 + 1] * fc * fr)

    return cota


_NOTA_GEOTECNICA = (
    "via em corte/aterro sobre declividade ≥30% — exige projeto geométrico e laudo geotécnico "
    "(art. 3º, parág. único, III, Lei 6.766: exigências das autoridades competentes). "
    "Nenhum LOTE na faixa ≥30%; só a via de conexão a atravessa."
)


def _travessia_conexao(aprov_m, registro, to_wgs, fonte_dem, prog, restr_m=None):
    """Fase 10.3 — se a área aproveitável vem PARTIDA em porções, o Python acha o traçado DIAGONAL de
    menor greide que LIGA as porções, podendo CRUZAR a faixa ≥30%/mata (Lei 6.766 art. 3º veda LOTE,
    não via; a via cruza em corte/aterro com greide controlado) e MEDE o greide da via sobre o DEM
    (§1/§2 — nenhum número vem da IA). Devolve ``(eixo, diag)`` p/ a ``gerar_layout`` materializar a
    via-tronco; ``(None, None)`` se há só uma porção (já conexo). Sem DEM → modelo reto (honesto)."""
    # Fase 10.1 — porções por MORFOLOGIA (não só ≥2 componentes): pega também 1 peça com PESCOÇO.
    porcoes = conexao_mod.detectar_porcoes(aprov_m)
    if len(porcoes) <= 1:
        return None, None
    a, b = porcoes[0], porcoes[1]
    cota = _cota_sampler(fonte_dem, registro["poly"], to_wgs)
    if cota is None:
        # Sem DEM: greide indeterminado → NÃO inventa diagonal sobre relevo que não temos; modelo reto.
        flat = (lambda x, y: 0.0)
        tv_norm = getattr(prog, "travessia", None)
        if tv_norm and len(tv_norm) >= 2:
            minx, miny, maxx, maxy = aprov_m.bounds
            ponto = (minx + float(tv_norm[0]) * (maxx - minx), miny + float(tv_norm[1]) * (maxy - miny))
            tv = conexao_mod.avaliar_travessia(a, b, flat, ponto, "llm")
        else:
            tv = conexao_mod.travessia_otima(a, b, flat)
    else:
        # 10.3 — domínio da via = a gleba inteira (aproveitável + restrição); a via pode pisar no ≥30%.
        dominio = aprov_m if restr_m is None else unary_union([aprov_m, restr_m])
        tv = conexao_mod.travessia_diagonal(a, b, cota, dominio, restr_m)
    cruza = bool(getattr(tv, "cruza_restricao", False))
    diag = {
        "proposta_por": tv.proposta_por, "ponto": list(tv.ponto),
        "greide_medido_pct": tv.greide_pct, "extensao_m": tv.extensao_m,
        "desnivel_m": tv.desnivel_m, "veredicto": tv.veredicto,
        "caixa_via_m": conexao_mod.CAIXA_TRONCO_M, "alerta_topografia": True,
        "greide_indeterminado": cota is None or fonte_dem is None,
        "modelo": "diagonal_minimax" if tv.proposta_por == "diagonal" else "reto",
        "cruza_restricao": cruza,
        "exigencia_geotecnica": cruza,
        "nota_geotecnica": _NOTA_GEOTECNICA if cruza else None,
    }
    return tv.eixo, diag


def _dem_amostras_no_frame(dem, to_local):
    """LAB Opção B — amostras de ELEVAÇÃO do DEM já REPROJETADAS para o frame métrico do motor
    (o mesmo das geometrias do dump). Devolve ``{"pontos": [[x,y,z],...], "px_m": ...}`` ou None.
    Downsample p/ ~≤60×60 (dump enxuto). Assim o laboratório traça a curva de nível (Opção B —
    via serpenteando a cota) SEM reprojetar nada. Puro diagnóstico: qualquer falha → None."""
    try:
        if dem is None or getattr(dem, "elevacao", None) is None or not dem.crs_proj4:
            return None
        import numpy as _np
        from pyproj import Transformer as _Tr

        z = _np.asarray(dem.elevacao, dtype=float)
        if z.ndim != 2 or z.size == 0:
            return None
        nrow, ncol = z.shape
        passo = max(1, int(max(nrow, ncol) / 60))  # downsample p/ ≤ ~60×60
        dem2wgs = _Tr.from_crs(dem.crs_proj4, "EPSG:4326", always_xy=True).transform
        pontos: list[list[float]] = []
        for r in range(0, nrow, passo):
            for c in range(0, ncol, passo):
                zv = z[r, c]
                if zv is None or not _np.isfinite(zv):
                    continue
                xm = dem.x0_m + (c + 0.5) * dem.px_m
                ym = dem.y0_m - (r + 0.5) * dem.px_m  # row cresce p/ baixo (y decresce)
                lon, lat = dem2wgs(xm, ym)
                xe, ye = to_local(lon, lat)
                pontos.append([round(xe, 1), round(ye, 1), round(float(zv), 2)])
        if len(pontos) < 4:
            return None
        return {"pontos": pontos, "px_m": round(float(dem.px_m) * passo, 2),
                "fonte": dem.fonte, "n": len(pontos)}
    except Exception:  # noqa: BLE001 — diagnóstico; nunca derruba a proposta
        return None


def _dump_insumos_motor(
    analise_id: str, proposta_id: str, *, aprov_m, restr_m, decliv_lote_m,
    decliv_acentuada_m, orientacao, travessia_eixo, travessia_diag,
    acesso_externo_m, lago_param, estilo, diretrizes, prog, variante, publico_alvo,
    dem_amostras=None, contornos_b=None,
) -> None:
    """LAB do operador — grava os insumos EXATOS que o motor recebeu (WKT + JSON) para
    replay determinístico FORA do app (harness de render itera no MESMO desenho — a regra 4
    garante que mesma entrada → mesmo layout). Ferramenta de laboratório: falha de escrita
    nunca derruba a proposta."""
    try:
        import json
        from pathlib import Path
        from shapely import wkt as _shapely_wkt

        destino = Path(os.getenv("URBANISMO_DUMP_DIR", "/tmp/urbanismo_dumps"))
        destino.mkdir(parents=True, exist_ok=True)

        def _w(g):
            return _shapely_wkt.dumps(g) if (g is not None and not g.is_empty) else None

        dump = {
            "analise_id": analise_id,
            "proposta_id": proposta_id,
            "publico_alvo": publico_alvo,
            "orientacao_rad": orientacao,
            "variante": variante,
            "lago": lago_param,
            "estilo": estilo,
            "diretrizes": diretrizes,
            "travessia_diag": travessia_diag,
            "programa": dataclasses.asdict(prog),
            "wkt": {
                "aproveitavel": _w(aprov_m),
                "restricoes_lote": _w(decliv_lote_m),
                "declividade_acentuada": _w(decliv_acentuada_m),
                "restricao_externa": _w(restr_m),
                "travessia_eixo": _w(travessia_eixo),
                "acesso_externo": _w(acesso_externo_m),
            },
            # Opção B — as curvas de nível (via-tronco / bandas orgânicas) no frame do motor, p/ replay 1:1.
            "contornos_b": [_w(c) for c in (contornos_b or []) if c is not None and not c.is_empty],
            "dem_amostras": dem_amostras,  # LAB Opção B — elevação no frame do motor (ou None)
        }
        (destino / f"{analise_id}_{proposta_id}.json").write_text(
            json.dumps(dump, ensure_ascii=False, default=str), encoding="utf-8"
        )
    except Exception:  # noqa: BLE001 — dump é diagnóstico; nunca interfere na proposta
        pass


def _garantir_areas_canonicas(registro, fonte_veg, fonte_camadas, fonte_dem):
    """Fase 10 (Parte 1) — números canônicos de área (delegado ao helper único de analises)."""
    from app.routers.analises import garantir_areas_canonicas
    return garantir_areas_canonicas(registro, fonte_veg, fonte_camadas, fonte_dem)


def _aproveitavel_wgs(registro, fonte_veg, fonte_camadas, fonte_dem):
    """Área aproveitável (WGS84) = gleba − união(restrições já computadas). Devolve também a
    RESTRIÇÃO recortada (∩ gleba) e a lista de ORIGENS (Fase 9.8 — p/ o mapa rotular o que o
    motor não loteou, em vez do 'clarão'). Degrada honesto: sem fontes → a própria gleba."""
    from app.routers.analises import _coletar_geoms  # reuso (sem duplicar a coleta)  # noqa: F401

    gleba = registro["poly"]
    verde_geom, overlays, decliv_geom = _coletar_geoms(
        registro, fonte_veg, fonte_camadas, fonte_dem
    )
    # Fase 10.8 — DOIS regimes: mata/APP bloqueiam VIA e lote (saem do aproveitável); a declividade
    # ≥30% veda só LOTE, não via (Lei 6.766 art. 3º — parcelamento, não estrada). Então o ≥30% NÃO
    # sai do aproveitável (a malha viária o atravessa e junta a gleba); ele volta separado p/ o motor
    # tirar só dos LOTES (vira verde). Isso desfaz o "loteamento partido por uma diagonal".
    partes_via, origem = [], []
    if verde_geom is not None:
        partes_via.append(verde_geom)
        origem.append("vegetacao")
    for chave in _CHAVES_RESTRITIVAS:
        if overlays.get(chave) is not None:
            partes_via.append(overlays[chave])
            origem.append(chave)
    decliv_lote = decliv_geom.intersection(gleba) if decliv_geom is not None else None
    if decliv_lote is not None and not decliv_lote.is_empty:
        origem.append("declividade_30")
    else:
        decliv_lote = None
    restr_via = (unary_union([g.intersection(gleba) for g in partes_via if g is not None])
                 if partes_via else None)
    aprov = gleba.difference(restr_via) if (restr_via is not None and not restr_via.is_empty) else gleba
    if aprov.is_empty:
        return gleba, None, [], None
    # restrição COMPLETA (mata/APP ∪ ≥30%) p/ o mapa rotular a faixa não-edificável (Fase 9.8).
    full = [g for g in (restr_via, decliv_lote) if g is not None and not g.is_empty]
    restr_full = unary_union(full) if full else None
    return aprov, restr_full, origem, decliv_lote


# Fase U4 — as K variantes DETERMINÍSTICAS geradas por chamada de IA (1 chamada → K layouts):
# estratégia de posição do hub + rotação extra da grelha. Mesma variante → mesmo layout.
VARIANTES_U4: list[dict] = [
    {"id": "V1", "rotulo": "Base — topografia + hub por área",
     "orientacao_extra_rad": 0.0, "hub_estrategia": "area"},
    {"id": "V2", "rotulo": "Hub junto à entrada",
     "orientacao_extra_rad": 0.0, "hub_estrategia": "entrada"},
    {"id": "V3", "rotulo": "Hub central",
     "orientacao_extra_rad": 0.0, "hub_estrategia": "centro"},
    {"id": "V4", "rotulo": "Grelha girada 15°",
     "orientacao_extra_rad": math.radians(15.0), "hub_estrategia": "area"},
]


@router.post(
    "/analises/{analise_id}/urbanismo/propor",
    response_model=schemas.PropostaUrbanisticaOut,
)
def propor(
    analise_id: str,
    body: schemas.ProporUrbanismoIn,
    gerador: GeradorPrograma | None = Depends(get_gerador_programa),
    fonte_urb: FonteUrbanismo = Depends(get_fonte_urbanismo),
    fonte_veg: FonteVegetacao | None = Depends(get_fonte_vegetacao),
    fonte_camadas: FonteCamadas | None = Depends(get_fonte_camadas),
    fonte_dem: FonteDEM | None = Depends(get_fonte_dem),
    fonte_perfil: FontePerfilMunicipal | None = Depends(get_fonte_perfil),
    fonte_vias: FonteVias | None = Depends(get_fonte_vias),
    fonte_memoria: FonteMemoriaUrbanismo | None = Depends(get_fonte_memoria_urbanismo),
    usuario: Usuario = Depends(usuario_atual),
):
    registro = STORE.get(analise_id)
    if registro is None:
        raise HTTPException(404, "Análise não encontrada.")
    if gerador is None:
        raise HTTPException(
            503,
            "Geração de estudo de massa indisponível (sem credencial de IA). "
            "Configure ANTHROPIC_API_KEY ou use o endpoint /medir com um layout pronto.",
        )

    # Cap de fair-use POR ANÁLISE (por vida, não por dia): cada geração é uma chamada de IA
    # (custo + fila/rate-limit da org, compartilhada entre TODOS os usuários). 15 mudanças de
    # layout já são mais que suficientes para uma gleba — não é ferramenta de gerar em massa.
    # Barra loop/abuso; não é cobrança, é proteção. Fase U4: só GERAÇÕES COM IA contam —
    # materializar uma variante alternativa (geometria pura) não consome o cap.
    # ADMIN não tem cap (calibração/testes do operador consomem muitas gerações);
    # o custo continua medido no admin/custos (uso_llm) — visível, não silencioso.
    _max = 0 if getattr(usuario, "papel", "") == "admin" else int(
        os.getenv("URBANISMO_MAX_GERACOES", "15")
    )
    geracoes_ia = [
        p for p in fonte_urb.listar(analise_id)
        if (p.get("origem_geracao") or "llm") == "llm"
    ]
    if _max > 0 and len(geracoes_ia) >= _max:
        raise HTTPException(
            429,
            f"Limite de regenerações do estudo de massa desta análise atingido ({_max}). "
            "Reutilize um layout já gerado (ele fica salvo) ou fale com o suporte se precisar de mais.",
        )

    return _propor_impl(
        analise_id, body, registro,
        fonte_urb=fonte_urb, fonte_veg=fonte_veg, fonte_camadas=fonte_camadas,
        fonte_dem=fonte_dem, fonte_perfil=fonte_perfil, fonte_vias=fonte_vias,
        gerador=gerador, fonte_memoria=fonte_memoria,
    )


def _propor_impl(
    analise_id: str,
    body: schemas.ProporUrbanismoIn,
    registro: dict,
    *,
    fonte_urb: FonteUrbanismo,
    fonte_veg: FonteVegetacao | None,
    fonte_camadas: FonteCamadas | None,
    fonte_dem: FonteDEM | None,
    fonte_perfil: FontePerfilMunicipal | None,
    fonte_vias: FonteVias | None,
    gerador: GeradorPrograma | None = None,
    prog=None,
    variante_unica: dict | None = None,
    origem_geracao: str = "llm",
    fonte_memoria: FonteMemoriaUrbanismo | None = None,
) -> schemas.PropostaUrbanisticaOut:
    """Pipeline completo do estudo de massa (Fase U4): com ``prog`` fornecido NÃO chama a IA
    (materialização de variante); ``variante_unica`` restringe a UMA estratégia (senão gera as
    K de ``VARIANTES_U4`` e a função de valor escolhe). Determinístico dado o mesmo programa."""
    referencia: list = []  # U5 — programas bem avaliados usados como few-shot (p/ o aviso)
    # Movimento 2 — PERFIL DE ESTILO (regras por padrão, editáveis via ESTILO_URBANISMO_DIR):
    # carregado UMA vez e usado no prompt (regras) e no motor (knobs de composição).
    from app.core.urbanismo_estilo import carregar_estilo

    estilo, aviso_estilo = carregar_estilo(str(body.publico_alvo))
    # 1) Tela = área aproveitável (restrição já descontada); projeta para CRS métrico. A restrição
    # recortada (mata/declividade/APP) é guardada p/ o mapa rotular (Fase 9.8), não p/ recalcular.
    aprov_wgs, restr_wgs, restr_origem, decliv_wgs = _aproveitavel_wgs(
        registro, fonte_veg, fonte_camadas, fonte_dem
    )
    to_local, to_wgs = medida.transformadores([aprov_wgs])
    aprov_m = transform(to_local, aprov_wgs)
    restr_m = transform(to_local, restr_wgs) if restr_wgs is not None else None
    # Fase 10.8 — ≥30% (veta só LOTE) no frame métrico; o motor o desconta das quadras, não das vias.
    decliv_lote_m = transform(to_local, decliv_wgs) if decliv_wgs is not None else None
    # Declividade ACENTUADA (>20%, legal mas íngreme) — penalidade SUAVE: o motor prefere o terreno
    # plano para os lotes e reserva a encosta como verde. Cacheada por _coletar_geoms (via _aprov.).
    acentuada_wgs = registro.get("declividade_acentuada")
    decliv_acentuada_m = transform(to_local, acentuada_wgs) if acentuada_wgs is not None else None

    # 1b) (c) Topografia: orienta a grelha pela curva de nível do DEM (2.5), se disponível.
    # Amostra o DEM UMA vez (reuso p/ orientação e p/ a declividade por lote — Fase 11.13).
    orientacao = 0.0
    dem_recorte = None
    if fonte_dem is not None:
        try:
            dem_recorte = fonte_dem.amostrar(registro["poly"])
            ang = geom.orientacao_contorno(dem_recorte)
            orientacao = ang if ang is not None else 0.0
        except Exception:  # noqa: BLE001 — DEM indisponível → sem orientação (degrada honesto)
            dem_recorte, orientacao = None, 0.0

    # 2) BORDA: o LLM propõe o PROGRAMA (estratégia), nunca a geometria/número. Fase U4: na
    # materialização de variante o programa JÁ EXISTE (veio salvo) — zero chamada de IA.
    if prog is None:
        contexto = {
            "area_aproveitavel_m2": round(aprov_m.area, 2),
            "municipio": getattr(registro["jurisdicao"], "municipio", None),
        }
        # Movimento 1 — diretrizes LIVRES do operador → seção prioritária no prompt.
        if (body.instrucoes or "").strip():
            contexto["instrucoes_do_operador"] = body.instrucoes.strip()
        # Movimento 2 — regras de ESTILO do padrão entram em TODA proposta.
        if estilo.get("prompt_regras"):
            contexto["regras_de_estilo"] = estilo["prompt_regras"]
        # Fase U5 — MEMÓRIA: programas bem avaliados (≥4★) da mesma região/perfil entram
        # como referência (few-shot) no prompt. A IA calibra a ESTRATÉGIA; o Python segue
        # medindo tudo (nenhum número vem da memória). Falha na leitura nunca derruba.
        try:
            referencia = (
                fonte_memoria.melhores(contexto["municipio"], str(body.publico_alvo))
                if fonte_memoria is not None else []
            )
        except Exception:  # noqa: BLE001 — memória é um plus
            referencia = []
        if referencia:
            contexto["programas_bem_avaliados"] = referencia
        try:
            with uso_llm.contexto(
                "urbanismo",
                analise_id=analise_id,
                usuario_id=str(registro.get("usuario_id", "")),
                meta={
                    "tipo_loteamento": str(body.tipo_loteamento),
                    "publico_alvo": str(body.publico_alvo) if body.publico_alvo else "",
                },
            ):
                prog = gerador.propor(
                    contexto, body.tipo_loteamento, body.publico_alvo, body.overrides
                )
        except GeradorIndisponivel as exc:
            raise HTTPException(503, str(exc))

    # 2b) DIRETRIZES (Fase 9.4): hierarquia LUOS(1.8)→mercado→federal. Lei vence o mercado.
    jur = registro["jurisdicao"]
    perfil = (
        fonte_perfil.carregar(jur.cod_ibge)
        if (fonte_perfil is not None and getattr(jur, "cod_ibge", None) and body.zona)
        else None
    )
    diretrizes = resolver_diretrizes(
        perfil, body.zona, body.modalidade, body.publico_alvo, body.lote_max_m2
    )

    # 3) NÚCLEO: Python materializa (reserva conforme diretriz → subdivide → CLAMP legal) e MEDE.
    # Fase 10 (Parte 3) — LOTEAMENTO ÚNICO: se partido, a IA propôs o ponto de travessia e o Python
    # mediu o greide real (acima); passa o eixo p/ a via de conexão ligar as porções (§2 refinado).
    travessia_eixo, travessia_diag = _travessia_conexao(
        aprov_m, registro, to_wgs, fonte_dem, prog, restr_m)

    # Fase 11.5 — PÓRTICO de frente à VIA mais próxima (geral, p/ qualquer terreno): busca as ruas
    # do entorno (OSM) e acha o ponto da BORDA da gleba mais perto de uma via real. Esse é o alvo da
    # entrada — o motor põe a portaria no contato via-interna↔borda mais perto dele. Sem via/sem rede
    # → ``None`` e o motor usa o fallback (miolo loteado). Determinístico.
    acesso_externo_m = None
    avisos_vias: list[str] = []
    if body.acesso_ponto and len(body.acesso_ponto) == 2:
        # Dado do OPERADOR (clique no mapa) — âncora definitiva; não consulta OSM.
        from shapely.geometry import Point as _Ponto

        acesso_externo_m = transform(
            to_local, _Ponto(float(body.acesso_ponto[0]), float(body.acesso_ponto[1]))
        )
        avisos_vias.append(
            "Entrada ancorada no ponto de acesso marcado pelo operador no mapa "
            "(prioridade sobre o OSM)."
        )
    elif fonte_vias is not None:
        try:
            cob_vias = fonte_vias.vias(registro["poly"])
            if cob_vias.geometria is not None and not cob_vias.geometria.is_empty:
                vias_m = transform(to_local, cob_vias.geometria)
                gleba_m = transform(to_local, registro["poly"])
                from shapely.ops import nearest_points

                # VIA LINDEIRA de verdade: prioriza vias que correm JUNTO à divisa (até
                # VIAS_LINDEIRA_MAX_M). Só se nenhuma margeia o terreno usa a mais próxima —
                # e nesse caso DIZ a distância (transparência; pode ser acesso por servidão).
                borda = gleba_m.boundary
                lindeira_max = float(os.getenv("VIAS_LINDEIRA_MAX_M", "80"))
                lindeiras = vias_m.intersection(borda.buffer(lindeira_max))
                alvo_vias = lindeiras if not lindeiras.is_empty else vias_m
                acesso_externo_m = nearest_points(borda, alvo_vias)[0]
                dist_via = acesso_externo_m.distance(alvo_vias)
                if lindeiras.is_empty:
                    avisos_vias.append(
                        "Nenhuma via pública margeia a divisa (OSM): a via mais próxima está a "
                        f"~{dist_via:,.0f} m do terreno — o pórtico foi ancorado no ponto da divisa "
                        "mais perto dela. Confirme o acesso real (servidão/estrada não mapeada)."
                    )
            else:
                avisos_vias = list(cob_vias.avisos)
        except Exception as exc:  # noqa: BLE001 — vias são um PLUS; falha não derruba o urbanismo
            acesso_externo_m = None
            avisos_vias = [f"Vias do entorno indisponíveis ({type(exc).__name__})."]
    if acesso_externo_m is None:
        # NUNCA silencioso: sem via ancorada o pórtico usa o fallback (miolo loteado) e o usuário
        # precisa saber que a posição não está de frente à via lindeira — e que regenerar resolve
        # quando o OSM voltar (com o cache, a via fica gravada na 1ª consulta que responder).
        avisos_vias.append(
            "PÓRTICO SEM VIA ANCORADA: a via lindeira não foi obtida nesta geração "
            "(OSM/Overpass indisponível ou sem via mapeada) — a portaria foi posicionada pelo "
            "miolo do loteamento. Regenere o estudo para tentar ancorar à via de acesso real."
        )

    # Fase U3 — LAGO no ponto baixo do DEM (opt-in do operador): amostra a cota numa grade
    # determinística sobre a aproveitável (interior, longe da borda) e passa o ponto+área ao
    # motor. Sem DEM → degrada com aviso (não inventamos relevo).
    lago_param = None
    if body.criar_lago:
        cota = _cota_sampler(fonte_dem, registro["poly"], to_wgs)
        if cota is None:
            avisos_vias.append(
                "LAGO NÃO SINTETIZADO: DEM indisponível — o ponto baixo do terreno não pôde "
                "ser identificado (não inventamos relevo). Tente regenerar mais tarde."
            )
        else:
            from shapely.geometry import Point as _PontoLago

            minx, miny, maxx, maxy = aprov_m.bounds
            interior = aprov_m.buffer(-25.0)
            if interior.is_empty:
                interior = aprov_m
            melhor = None
            _N = 28  # grade fixa → determinístico (mesma gleba → mesmo ponto baixo)
            for i in range(_N):
                for j in range(_N):
                    x = minx + (i + 0.5) * (maxx - minx) / _N
                    y = miny + (j + 0.5) * (maxy - miny) / _N
                    if not interior.contains(_PontoLago(x, y)):
                        continue
                    z = cota(x, y)
                    if melhor is None or z < melhor[0]:
                        melhor = (z, x, y)
            if melhor is not None:
                # dimensão de triagem vem do PERFIL DE ESTILO (default ~3%, teto 12.000 m²)
                frac = float(estilo.get("lago_frac_aproveitavel", 0.03))
                teto = float(estilo.get("lago_max_m2", 12000.0))
                lago_param = {
                    "ponto": (melhor[1], melhor[2]),
                    "area_m2": max(min(frac * aprov_m.area, teto), 1500.0),
                    "cota_m": round(melhor[0], 1),
                }

    # Opção B — VIA-TRONCO na CURVA DE NÍVEL: quando o estilo pede o traçado serpenteante,
    # extrai a isolinha do DEM (mediana das cotas) já no frame do motor. Sem DEM/curva → None e
    # o motor degrada honesto para a GRADE LIMPA (Opção A). Determinístico (mesmo DEM → mesma via).
    contornos_b = None
    if str(estilo.get("tracado", "")) == "contorno_serpente" and dem_recorte is not None:
        try:
            from app.core import contorno_dem

            if estilo.get("ruas_locais_contorno"):
                # Opção B ORGÂNICA — VÁRIAS curvas de nível (ruas locais ao longo da encosta).
                bandas = contorno_dem.extrair_bandas(dem_recorte, to_local, dentro=aprov_m)
                contornos_b = bandas or None
            if not contornos_b:
                # B clássica (ou orgânica sem bandas suficientes) — só a via-tronco na cota mediana.
                espinha = contorno_dem.extrair_espinha(dem_recorte, to_local, dentro=aprov_m)
                if espinha is not None and not espinha.is_empty:
                    contornos_b = [espinha]
        except Exception:  # noqa: BLE001 — B degrada p/ A; nunca derruba a geração
            contornos_b = None

    # Fase U4 — K VARIANTES determinísticas por chamada de IA: o motor gera as estratégias e a
    # FUNÇÃO DE VALOR (Σ área×multiplicador do score v2 — proxy de VGV posicional) escolhe a
    # melhor; as alternativas ficam materializáveis depois SEM IA (POST /urbanismo/variante).
    candidatas = [variante_unica] if variante_unica is not None else VARIANTES_U4
    geradas: list[tuple[dict, object, object, float]] = []
    for var in candidatas:
        layout_v = geom.gerar_layout(
            aprov_m, prog, restricoes=decliv_lote_m, orientacao_rad=orientacao,
            diretrizes=diretrizes,
            travessia_eixo=travessia_eixo, travessia_diag=travessia_diag,
            declividade_acentuada=decliv_acentuada_m,
            # Fase 11.4 — a restrição (mata/APP/≥30%) é um BURACO na aproveitável; passa p/ o
            # motor vetar a portaria na frente da mata preservada.
            restricao_externa=restr_m,
            # Fase 11.5 — alvo da entrada = via de acesso mais próxima (OSM); None → fallback.
            acesso_externo=acesso_externo_m,
            variante=var,
            lago=lago_param,  # U3 — ponto baixo do DEM (None sem opt-in/DEM)
            estilo=estilo,  # Mov.2 — knobs de composição do perfil de estilo
            contornos=contornos_b,  # Opção B — via-tronco na curva de nível (None → grade limpa)
        )
        layout_v.restricao_recortada = restr_m  # Fase 9.8 — p/ o mapa rotular (não recalcula)
        layout_v.restricao_origem = restr_origem
        # Fase U1 — o perfil do público-alvo escolhe os PESOS do score de valor v2.
        med_v = medida.medir(layout_v, publico_alvo=body.publico_alvo)
        valor_v = sum(
            (p.get("area_m2") or 0.0) * (p.get("multiplicador") or 1.0)
            for p in med_v.heatmap.get("por_lote", [])
        )
        geradas.append((var, layout_v, med_v, valor_v))

    # Escolha: maior valor posicional; empate → mais lotes (yield). Determinístico.
    variante_escolhida, layout, med, valor_melhor = max(
        geradas, key=lambda t: (t[3], len(t[1].lotes))
    )
    variantes_out = [
        schemas.VarianteUrbOut(
            variante_id=str(var["id"]),
            rotulo=str(var["rotulo"]),
            n_lotes=len(lay.lotes),
            valor_indice=(round(100.0 * val / valor_melhor, 1) if valor_melhor > 0 else None),
            score_medio=m.heatmap.get("score_medio"),
            cobertura_400m_pct=(lay.sistema_lazer_diagnostico or {}).get("cobertura_400m_pct"),
            escolhida=(var is variante_escolhida),
        )
        for var, lay, m, val in geradas
    ]
    quadro, indicadores, heatmap = _medicao_dicts(med)

    # Fase 11.13 — declividade média por lote (orientativa, DSM 30 m): amostra o DEM nos lotes
    # (frame métrico → WGS) p/ o popup do mapa exibir. Sem DEM → tudo None (degrada honesto).
    lotes_wgs = [transform(to_wgs, g) for g in layout.lotes]
    decliv_por_lote = amostrar_declividade(dem_recorte, lotes_wgs)

    # Fase 9.10 — PONTE: teto regulatório (mesma fórmula/cenário do Aproveitamento) p/ a referência
    # cruzada. É só EXIBIÇÃO — o nº de lotes do estudo (medido acima) não usa este número.
    from app.core import aproveitamento as aprov_motor

    teto_reg = None
    if perfil is not None and body.zona:
        gleba_m2 = transform(to_local, registro["poly"]).area
        dados_teto, _ = aprov_motor.cenario_diretriz(
            perfil, body.zona, body.modalidade, aprov_m.area, gleba_m2
        )
        if dados_teto is not None:
            teto_reg = dados_teto["n_lotes"]
    reconciliacao = schemas.ReconciliacaoUrbanismoOut(
        **medida.reconciliacao_urbanismo(med, lotes_teto=teto_reg)
    )

    fidelidade = schemas.FidelidadeOut(**medida.construir_fidelidade(med, layout))
    distribuicao = schemas.DistribuicaoTamanhosOut(**medida.distribuicao_tamanhos(med, layout))
    diretrizes_out = schemas.DiretrizesOut(
        fonte=diretrizes["fonte"], cobertura=diretrizes["cobertura"],
        confirmada=diretrizes["confirmada"], lote_min_zona_m2=diretrizes["lote_min_zona_m2"],
        piso_lote_efetivo_m2=diretrizes["piso_lote_efetivo_m2"], teto_lote_m2=diretrizes["teto_lote_m2"],
        doacao_min_pct=diretrizes["doacao_min_pct"], doacao_split=diretrizes["doacao_split"],
        aviso=diretrizes["aviso"],
    )
    conf_legal = [
        schemas.ConformidadeLegalOut(**c) for c in medida.conformidade_legal(med, layout, diretrizes)
    ]

    versao = fonte_urb.proxima_versao(analise_id)
    proposta_id = f"u_{analise_id[:8]}_{versao:03d}"
    conformidade = _conformidade_programa(prog)
    aviso_variantes = (
        f"Otimizador (U4): {len(geradas)} variante(s) gerada(s) com UMA proposta de IA; "
        f"escolhida “{variante_escolhida['rotulo']}” pela função de valor posicional "
        "(Σ área × multiplicador do score v2). As alternativas podem ser abertas sem "
        "custo de IA e sem consumir o limite de gerações."
        if len(geradas) > 1 else
        f"Variante “{variante_escolhida['rotulo']}” materializada da proposta salva — "
        "sem chamada de IA e fora do limite de gerações."
    )
    avisos = [
        aviso_variantes,
        *([aviso_estilo] if aviso_estilo else []),
        *([f"Memória (U5): a proposta foi calibrada por {len(referencia)} programa(s) "
           "bem avaliado(s) pelo operador na mesma região/perfil (few-shot no gerador — "
           "os números continuam medidos pelo motor)."] if referencia else []),
        *avisos_vias,
        *medida.AVISOS_1A,
        *layout.avisos,
        "Fidelidade: o quadro de áreas converge para o programa quando a gleba comporta; "
        "divergências são rotuladas, nunca forçadas.",
        "Tamanho do lote = o que a quadra comporta (subdivisão), mirando a faixa do perfil; "
        "lote grande é exceção geométrica. Quem quer maior junta dois lotes.",
        "Valor da posição vai para o R$/m² (seu input por faixa de score), não para o tamanho.",
        "Dimensionamento ancorado em: diretrizes do município (LUOS/1.8) + piso legal 125 m² "
        "(Lei 6.766) + boas práticas de mercado. Nenhum lote fora da faixa legal.",
        "Mínimos de doação/área verde/institucional MEDIDOS contra a exigência do município — "
        "verificar na prefeitura (art. 6º Lei 6.766).",
    ]

    out = schemas.PropostaUrbanisticaOut(
        proposta_id=proposta_id,
        versao=versao,
        perfil={"tipo_loteamento": body.tipo_loteamento, "publico_alvo": body.publico_alvo},
        programa=_programa_out(prog),
        geometria=medida.geojson_do_layout(
            layout, to_wgs, med.heatmap.get("por_lote"), declividade_por_lote=decliv_por_lote
        ),
        quadro_areas=quadro,
        indicadores=indicadores,
        heatmap=heatmap,
        fidelidade=fidelidade,
        distribuicao_tamanhos=distribuicao,
        diretrizes=diretrizes_out,
        conformidade_legal=conf_legal,
        conformidade_programa=conformidade,
        reconciliacao=reconciliacao,  # Fase 9.10 — ponte (rotula o estudo + cita o teto)
        esqueleto_ignorado=layout.ignorados,
        # Fase 10 (Parte 1) — a líquida CANÔNICA (mesma das abas Ambiental/Aproveitamento).
        areas_canonicas=schemas.AreasCanonicasOut(
            **_garantir_areas_canonicas(registro, fonte_veg, fonte_camadas, fonte_dem).__dict__
        ),
        variantes=variantes_out,  # Fase U4 — resumo das K estratégias (esta = a escolhida)
        proveniencia=(
            f"Programa proposto por IA ({prog.origem}, perfil '{body.publico_alvo}') + "
            "geometria e medidas GERADAS/MEDIDAS em Python sobre a área aproveitável; "
            f"variante '{variante_escolhida['rotulo']}' escolhida pela função de valor entre "
            f"{len(geradas)} geradas (gerado em {date.today().isoformat()})."
        ),
        avisos=avisos,
    )
    # Persistência: além do payload, guarda o PROGRAMA do motor e o contexto do pedido para
    # rematerializar QUALQUER variante depois sem IA (chaves privadas "_" — uso interno).
    salvo = out.model_dump()
    salvo["origem_geracao"] = origem_geracao
    salvo["_programa_motor"] = dataclasses.asdict(prog)
    salvo["_contexto_variantes"] = {
        "tipo_loteamento": body.tipo_loteamento,
        "publico_alvo": body.publico_alvo,
        "zona": body.zona,
        "modalidade": body.modalidade,
        "lote_max_m2": body.lote_max_m2,
        "acesso_ponto": body.acesso_ponto,
        "criar_lago": body.criar_lago,  # U3 — a variante rematerializa com o mesmo lago
        "instrucoes": body.instrucoes,  # Mov.1 — proveniência do pedido do operador
    }
    fonte_urb.salvar(analise_id, salvo)
    # LAB — replay 1:1 fora do app (harness de render do operador). Nunca derruba a proposta.
    _dump_insumos_motor(
        analise_id, proposta_id, aprov_m=aprov_m, restr_m=restr_m,
        decliv_lote_m=decliv_lote_m, decliv_acentuada_m=decliv_acentuada_m,
        orientacao=orientacao, travessia_eixo=travessia_eixo, travessia_diag=travessia_diag,
        acesso_externo_m=acesso_externo_m, lago_param=lago_param, estilo=estilo,
        diretrizes=diretrizes, prog=prog, variante=variante_escolhida,
        publico_alvo=str(body.publico_alvo),
        dem_amostras=_dem_amostras_no_frame(dem_recorte, to_local),
        contornos_b=contornos_b,
    )
    return out


def _conformidade_programa(prog) -> list[schemas.ItemConformidadePrograma]:
    """Confronto do PROGRAMA com a triagem — §1-A: sinaliza, não decide aprovação."""
    return [
        schemas.ItemConformidadePrograma(
            item="lote_alvo",
            status="nao_avaliado",
            leitura=(
                f"lote-alvo {medida._fmt(prog.lote_alvo_m2)} m² — comparar com o lote legal "
                "da zona (LUOS) e as diretrizes da gleba com o urbanista."
            ),
        ),
        schemas.ItemConformidadePrograma(
            item="lazer",
            status="atencao",
            leitura=(
                f"lazer/verde proposto {medida._fmt(prog.pct_lazer * 100, 1)}% — verificar o "
                "mínimo da zona e a doação obrigatória com o urbanista/prefeitura."
            ),
        ),
    ]


# --------------------------------- GET (snapshots) ---------------------------------
# ------------------------------ /avaliar (Fase U5 — memória) ------------------------------
@router.post(
    "/analises/{analise_id}/urbanismo/avaliar",
    response_model=schemas.AvaliacaoUrbanismoOut,
)
def avaliar_proposta(
    analise_id: str,
    body: schemas.AvaliarUrbanismoIn,
    fonte_urb: FonteUrbanismo = Depends(get_fonte_urbanismo),
    fonte_memoria: FonteMemoriaUrbanismo = Depends(get_fonte_memoria_urbanismo),
):
    """Rating do OPERADOR (1–5) para um estudo de massa. Ratings ≥4 viram REFERÊNCIA
    (few-shot) nas próximas gerações da mesma região/perfil — aprendizado auditável."""
    registro = STORE.get(analise_id)
    if registro is None:
        raise HTTPException(404, "Análise não encontrada.")
    alvo = next(
        (p for p in fonte_urb.listar(analise_id) if p.get("versao") == body.versao), None
    )
    if alvo is None:
        raise HTTPException(404, f"Versão {body.versao} não encontrada nesta análise.")

    programa = alvo.get("programa") or {}
    perfil_prop = alvo.get("perfil") or {}
    reg = {
        "analise_id": analise_id,
        "versao": int(body.versao),
        "proposta_id": str(alvo.get("proposta_id", "")),
        "rating": int(body.rating),
        "comentario": body.comentario,
        "municipio": getattr(registro["jurisdicao"], "municipio", None),
        "uf": getattr(registro["jurisdicao"], "uf", None),
        "publico_alvo": perfil_prop.get("publico_alvo"),
        "tipo_loteamento": perfil_prop.get("tipo_loteamento"),
        # RESUMO do programa (estratégia, nunca medida — §2) que vira few-shot.
        "programa_resumo": {
            "lote_alvo_m2": programa.get("lote_alvo_m2"),
            "pct_lazer": programa.get("pct_lazer"),
            "arquetipo_viario": programa.get("arquetipo_viario"),
            "amenidades": programa.get("amenidades"),
            "largura_via_m": programa.get("largura_via_m"),
            "testada_m": programa.get("testada_m"),
            "profundidade_m": programa.get("profundidade_m"),
        },
        "data": date.today().isoformat(),
    }
    fonte_memoria.avaliar(reg)
    return schemas.AvaliacaoUrbanismoOut(
        analise_id=analise_id, versao=reg["versao"], proposta_id=reg["proposta_id"],
        rating=reg["rating"], comentario=reg["comentario"], municipio=reg["municipio"],
        publico_alvo=reg["publico_alvo"], data=reg["data"],
    )


@router.get("/analises/{analise_id}/urbanismo-avaliacoes")
def listar_avaliacoes(
    analise_id: str,
    fonte_memoria: FonteMemoriaUrbanismo = Depends(get_fonte_memoria_urbanismo),
):
    if STORE.get(analise_id) is None:
        raise HTTPException(404, "Análise não encontrada.")
    return fonte_memoria.avaliacoes(analise_id)


# ------------------------------- /variante (Fase U4 — sem LLM) -------------------------------
@router.post(
    "/analises/{analise_id}/urbanismo/variante",
    response_model=schemas.PropostaUrbanisticaOut,
)
def materializar_variante(
    analise_id: str,
    body: schemas.VarianteUrbIn,
    fonte_urb: FonteUrbanismo = Depends(get_fonte_urbanismo),
    fonte_veg: FonteVegetacao | None = Depends(get_fonte_vegetacao),
    fonte_camadas: FonteCamadas | None = Depends(get_fonte_camadas),
    fonte_dem: FonteDEM | None = Depends(get_fonte_dem),
    fonte_perfil: FontePerfilMunicipal | None = Depends(get_fonte_perfil),
    fonte_vias: FonteVias | None = Depends(get_fonte_vias),
):
    """Materializa uma VARIANTE alternativa de uma proposta já gerada: reusa o programa salvo
    (zero chamada de IA, FORA do cap de gerações) e roda só a geometria determinística."""
    registro = STORE.get(analise_id)
    if registro is None:
        raise HTTPException(404, "Análise não encontrada.")
    var = next((v for v in VARIANTES_U4 if v["id"] == body.variante_id), None)
    if var is None:
        raise HTTPException(404, f"Variante '{body.variante_id}' não existe.")

    propostas = fonte_urb.listar(analise_id)
    if body.versao is not None:
        base = next((p for p in propostas if p.get("versao") == body.versao), None)
        if base is None:
            raise HTTPException(404, f"Versão {body.versao} não encontrada nesta análise.")
    else:
        base = next(
            (p for p in reversed(propostas) if p.get("_programa_motor")), None
        )
    if base is None or not base.get("_programa_motor"):
        raise HTTPException(
            409,
            "Esta análise não tem proposta com programa salvo (gerada antes da U4) — "
            "regenere o estudo de massa para habilitar as variantes.",
        )

    campos = {f.name for f in dataclasses.fields(Programa)}
    prog = Programa(**{k: v for k, v in base["_programa_motor"].items() if k in campos})
    ctx = base.get("_contexto_variantes") or {}
    body_base = schemas.ProporUrbanismoIn(**{k: v for k, v in ctx.items() if v is not None})
    return _propor_impl(
        analise_id, body_base, registro,
        fonte_urb=fonte_urb, fonte_veg=fonte_veg, fonte_camadas=fonte_camadas,
        fonte_dem=fonte_dem, fonte_perfil=fonte_perfil, fonte_vias=fonte_vias,
        prog=prog, variante_unica=var, origem_geracao="variante",
    )


# --------------------------------- /valor (Fase U1 — sem LLM) ---------------------------------
@router.post(
    "/analises/{analise_id}/urbanismo/valor", response_model=schemas.ValorPosicionalOut
)
def valor_posicional(
    analise_id: str,
    body: schemas.ValorPosicionalIn,
    fonte_urb: FonteUrbanismo = Depends(get_fonte_urbanismo),
):
    """FUNÇÃO DE VALOR posicional: preço MÉDIO do operador × multiplicador do score v2 (já salvo
    na proposta). Determinístico, sem LLM e fora do cap de regenerações (não gera nada novo).
    O preço nunca é inventado — sem input do operador não há R$."""
    if STORE.get(analise_id) is None:
        raise HTTPException(404, "Análise não encontrada.")
    if (body.preco_lote_medio is None) == (body.preco_m2_medio is None):
        raise HTTPException(
            422, "Informe exatamente um preço: 'preco_lote_medio' OU 'preco_m2_medio'."
        )
    base = "por_lote" if body.preco_lote_medio is not None else "por_m2"
    preco_base = float(body.preco_lote_medio if base == "por_lote" else body.preco_m2_medio)
    if preco_base <= 0:
        raise HTTPException(422, "O preço médio deve ser maior que zero.")

    propostas = fonte_urb.listar(analise_id)
    if not propostas:
        raise HTTPException(
            404, "Nenhum estudo de massa nesta análise — gere o urbanismo antes de valorar."
        )
    if body.versao is not None:
        alvo = next((p for p in propostas if p.get("versao") == body.versao), None)
        if alvo is None:
            raise HTTPException(404, f"Versão {body.versao} não encontrada nesta análise.")
    else:
        alvo = propostas[-1]

    por_lote = (alvo.get("heatmap") or {}).get("por_lote") or []
    com_mult = [p for p in por_lote if p.get("multiplicador") is not None]
    if not com_mult:
        raise HTTPException(
            409,
            "Esta proposta foi salva antes do score de valor v2 (sem multiplicador posicional) — "
            "regenere o estudo de massa para habilitar o valor por lote.",
        )

    from app.core.financeira import brl

    lotes_out: list[schemas.LoteValorOut] = []
    for p in com_mult:
        mult = float(p["multiplicador"])
        area = float(p.get("area_m2") or 0.0)
        preco = preco_base * mult if base == "por_lote" else preco_base * area * mult
        lotes_out.append(
            schemas.LoteValorOut(
                lote_id=str(p.get("lote_id", "")), area_m2=area,
                score=float(p.get("score", 0.0)), multiplicador=mult,
                preco=round(preco, 2), preco_fmt=brl(preco),
            )
        )
    vgv = round(sum(item.preco for item in lotes_out), 2)
    preco_medio = round(vgv / len(lotes_out), 2)
    unidade = "/lote" if base == "por_lote" else "/m²"
    avisos = [
        "Estimativa POSICIONAL de triagem — não é avaliação de mercado; o preço médio é input "
        "do operador (pesquisa de preços local).",
        "O multiplicador tem média 1,0: redistribui o VGV entre os lotes conforme a posição, "
        "não infla o total." if base == "por_lote" else
        "Base por m²: o preço do lote = R$/m² × área × multiplicador (posição E tamanho).",
    ]
    return schemas.ValorPosicionalOut(
        proposta_id=str(alvo.get("proposta_id", "")),
        versao=int(alvo.get("versao", 0)),
        perfil=(alvo.get("heatmap") or {}).get("perfil"),
        base=base,
        preco_base=preco_base,
        n_lotes=len(lotes_out),
        vgv=vgv,
        vgv_fmt=brl(vgv),
        preco_medio=preco_medio,
        preco_medio_fmt=brl(preco_medio),
        lote_max=max(lotes_out, key=lambda item: item.preco),
        lote_min=min(lotes_out, key=lambda item: item.preco),
        por_lote=lotes_out,
        proveniencia=(
            f"Preço médio do operador ({brl(preco_base)}{unidade}) × multiplicador posicional "
            f"do score v2 (média 1,0) da proposta {alvo.get('proposta_id')} v{alvo.get('versao')} "
            f"— calculado em {date.today().isoformat()}. Âncoras dos pesos: "
            "docs/pesquisa-motor-urbanismo.md §1–§3."
        ),
        avisos=avisos,
    )


@router.get("/analises/{analise_id}/urbanismo")
def listar(analise_id: str, fonte_urb: FonteUrbanismo = Depends(get_fonte_urbanismo)):
    if STORE.get(analise_id) is None:
        raise HTTPException(404, "Análise não encontrada.")
    return fonte_urb.listar(analise_id)


@router.get(
    "/analises/{analise_id}/urbanismo/{proposta_id}",
    response_model=schemas.PropostaUrbanisticaOut,
)
def obter(
    analise_id: str, proposta_id: str, fonte_urb: FonteUrbanismo = Depends(get_fonte_urbanismo)
):
    if STORE.get(analise_id) is None:
        raise HTTPException(404, "Análise não encontrada.")
    snap = fonte_urb.carregar(analise_id, proposta_id)
    if snap is None:
        raise HTTPException(404, "Proposta não encontrada.")
    return snap
