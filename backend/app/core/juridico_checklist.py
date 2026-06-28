"""Fase 3.B — checklist de documentos do parcelamento, personalizado por dono/jurisdição.

Determinístico (regras do ROTEIRO da advogada; sem LLM, sem I/O). A partir dos proprietários
extraídos+confirmados das matrículas (PF/PJ + CPF/CNPJ) e da UF, monta a lista de documentos
exigidos — dizendo, em cada item, EM NOME DE QUEM e se a Fase C poderá puxá-lo por CPF/CNPJ.

Fronteira: é um CHECKLIST de triagem, não parecer. Não certifica regularidade; só organiza o
que o roteiro pede. ``status`` nasce 'pendente' (anexar/auto-download virão depois).
"""

from __future__ import annotations

from app.models import schemas


def consolidar_proprietarios(
    fichas: list[schemas.FichaJuridica],
) -> list[schemas.ProprietarioOut]:
    """Junta os proprietários de TODAS as matrículas confirmadas, deduplicando por documento
    (CPF/CNPJ) ou, na falta dele, por nome. Mantém em quais matrículas cada dono aparece."""
    por_chave: dict[str, schemas.ProprietarioOut] = {}
    for f in fichas:
        if f.status != "confirmado" or f.tipo != "matricula" or not f.identificacao:
            continue
        n_mat = f.identificacao.matricula.valor if f.identificacao.matricula else None
        props = list(f.identificacao.proprietarios)
        # Compat: matrícula antiga só com proprietario_atual (texto) → vira um dono sem doc.
        if not props and f.identificacao.proprietario_atual:
            nome = f.identificacao.proprietario_atual.valor
            if nome:
                props = [schemas.ProprietarioDoc(nome=nome)]
        for p in props:
            chave = _norm(p.documento) or _norm(p.nome)
            if not chave:
                continue
            alvo = por_chave.get(chave)
            if alvo is None:
                alvo = schemas.ProprietarioOut(
                    nome=p.nome,
                    documento=p.documento,
                    tipo=p.tipo or _tipo_por_doc(p.documento),
                    vigente=False,  # vira True se vigente em QUALQUER matrícula (abaixo)
                    matriculas=[],
                    proveniencia=_prov(p),
                )
                por_chave[chave] = alvo
            if n_mat and n_mat not in alvo.matriculas:
                alvo.matriculas.append(n_mat)
            # completa campos faltantes se outra matrícula trouxe mais detalhe
            alvo.tipo = alvo.tipo or p.tipo or _tipo_por_doc(p.documento)
            alvo.documento = alvo.documento or p.documento
            # atual se for vigente em ALGUMA matrícula (dono de uma área ainda que tenha saído
            # de outra). situacao default é 'vigente', então a compat antiga continua atual.
            if p.situacao == "vigente":
                alvo.vigente = True
    return list(por_chave.values())


def gerar_checklist(
    proprietarios: list[schemas.ProprietarioOut],
    uf: str | None = None,
) -> list[schemas.ItemChecklistOut]:
    """Monta o checklist do roteiro, personalizado pelos donos e pela UF. Determinístico.

    Fidelidade ao roteiro: tributárias/registro/título são em nome dos donos ATUAIS; já
    distribuidores e protesto pedem os titulares dos últimos 10 anos (atuais + anteriores)."""
    # Donos ATUAIS (vigentes). Defensivo: se a extração não marcou nenhum vigente, trata todos
    # como atuais (melhor sobre-incluir do que esvaziar as certidões obrigatórias).
    atuais_props = [p for p in proprietarios if p.vigente] or list(proprietarios)
    nomes = [_rotulo(p) for p in atuais_props]
    pjs = [_rotulo(p) for p in atuais_props if p.tipo == "pj"]
    pfs = [_rotulo(p) for p in atuais_props if p.tipo == "pf"]
    # Titulares dos últimos 10 anos = atuais + anteriores (todos os que constam).
    nomes_10anos = [_rotulo(p) for p in proprietarios]
    uf_norm = (uf or "").strip().upper()
    itens: list[schemas.ItemChecklistOut] = []

    def add(**kw):
        itens.append(schemas.ItemChecklistOut(**kw))

    # 1) Requerimento / registro
    add(
        chave="requerimento_registro",
        titulo="Requerimento de registro (descrição do imóvel + pedido de abertura de "
        "matrícula dos lotes e áreas públicas)",
        categoria="registro",
        em_nome_de=nomes,
        fonte_legal="Roteiro, item 1d",
    )
    if pjs:
        add(
            chave="contrato_social",
            titulo="Contratos sociais + certidão da Junta Comercial (última alteração) — "
            "conferir sócios/representantes e sede/filiais",
            categoria="registro",
            em_nome_de=pjs,
            fonte_legal="Roteiro, item 1a/1b",
            observacao="Se a PJ tiver sócia que também é PJ, trazer os contratos sociais dela.",
        )
    if pfs:
        add(
            chave="anuencia_conjuge",
            titulo="Declaração de anuência do cônjuge (firma reconhecida)",
            categoria="registro",
            em_nome_de=pfs,
            condicional="se o proprietário PF for casado",
            fonte_legal="Roteiro, item 1c",
        )

    # 2-3) Título de propriedade + cadeia dominial
    add(
        chave="titulo_propriedade",
        titulo="Certidão da matrícula (vintenária) em nome do proprietário — expedida há ≤30 dias",
        categoria="titulo",
        em_nome_de=nomes,
        fonte_legal="Roteiro, itens 2 e 3d",
    )
    add(
        chave="cadeia_dominial_20",
        titulo="Histórico dos títulos dos últimos 20 anos + comprovantes (escrituras, formais "
        "de partilha), subscrito pelo loteador com firma reconhecida",
        categoria="titulo",
        em_nome_de=nomes,
        fonte_legal="Roteiro, item 3",
    )

    # 4) Certidões tributárias (família B — chaveáveis por CPF/CNPJ → auto na Fase C)
    add(
        chave="cnd_federal",
        titulo="Certidão negativa de tributos federais + Dívida Ativa da União (RFB/PGFN)",
        categoria="tributarias",
        em_nome_de=nomes,
        auto_disponivel=True,
        fonte_legal="Roteiro, item 4a",
    )
    if pjs:
        add(
            chave="fgts",
            titulo="Certificado de Regularidade do FGTS (CRF — Caixa)",
            categoria="tributarias",
            em_nome_de=pjs,
            auto_disponivel=True,
            fonte_legal="Roteiro, item 4a",
        )
        add(
            chave="inss",
            titulo="Certidão negativa do INSS",
            categoria="tributarias",
            em_nome_de=pjs,
            auto_disponivel=True,
            fonte_legal="Roteiro, item 4a",
        )
    if pfs:
        add(
            chave="declaracao_nao_empregador",
            titulo="Declaração de que não é empregador nem contribuinte do INSS (substitui a "
            "certidão do INSS quando o loteador é PF)",
            categoria="tributarias",
            em_nome_de=pfs,
            fonte_legal="Roteiro, item 4c",
        )
    add(
        chave="fazenda_estadual",
        titulo="Certidão negativa da Fazenda Estadual",
        categoria="tributarias",
        em_nome_de=nomes,
        auto_disponivel=True,
        fonte_legal="Roteiro, item 4a/4d",
    )
    add(
        chave="fazenda_municipal",
        titulo="Certidões municipais: tributos imobiliários (imóvel) e mobiliários (loteador)",
        categoria="tributarias",
        em_nome_de=nomes,
        fonte_legal="Roteiro, item 4a/4d",
    )
    add(
        chave="itr",
        titulo="Certidão negativa de imóvel rural (ITR — Receita Federal)",
        categoria="tributarias",
        em_nome_de=nomes,
        obrigatorio=False,
        condicional="se o imóvel foi rural há menos de 5 anos",
        auto_disponivel=True,
        fonte_legal="Roteiro, item 4b",
    )

    # 5) Distribuidores cíveis/criminais (família C — por NOME, 10 anos → não auto)
    add(
        chave="distribuidores",
        titulo="Certidões dos distribuidores cíveis e criminais (Justiça Estadual, Federal e "
        "do Trabalho) — busca retroativa de 10 anos, em nome dos titulares do período "
        "(+ sócios/representantes, se PJ)",
        categoria="distribuidores",
        em_nome_de=nomes_10anos,
        fonte_legal="Roteiro, item 5",
        observacao="Atenção a homônimos e variações de nome (solteira/casada, Luís/Luiz); se "
        "constar processo, juntar certidão de objeto e pé. Validade 3 meses.",
    )

    # 6) Protesto (CENPROT — por CPF/CNPJ → auto na Fase C)
    add(
        chave="protesto",
        titulo="Certidões de protesto (busca retroativa de 10 anos), em nome dos titulares",
        categoria="protesto",
        em_nome_de=nomes_10anos,
        auto_disponivel=True,
        fonte_legal="Roteiro, item 6",
    )

    # 7) Aprovação municipal / estadual
    add(
        chave="alvara_loteamento",
        titulo="Alvará de loteamento (validade 180 dias) — conferir área = matrícula e soma do "
        "quadro de áreas; constar hipoteca/caução se houver",
        categoria="aprovacao",
        em_nome_de=[],
        fonte_legal="Roteiro, item 7",
    )
    if uf_norm == "SP":
        add(
            chave="graprohab",
            titulo="Certificado do GRAPROHAB (validade 2 anos) + análise das ressalvas no verso",
            categoria="aprovacao",
            em_nome_de=[],
            condicional="Estado de São Paulo",
            fonte_legal="Roteiro, item 7f/7g",
        )
        add(
            chave="parecer_meio_ambiente",
            titulo="Parecer da Secretaria de Meio Ambiente (registro especial de desmembramento)",
            categoria="aprovacao",
            em_nome_de=[],
            obrigatorio=False,
            condicional="SP, em caso de desmembramento",
            fonte_legal="Roteiro, item 7h",
        )

    # 8-11) Projeto e instrumentos
    add(
        chave="planta_memorial",
        titulo="Planta e memorial (assinatura do engenheiro, aprovação/carimbo da prefeitura, "
        "ART) — perimetrais iguais às da matrícula; soma das áreas ≤ imóvel",
        categoria="projeto",
        em_nome_de=[],
        fonte_legal="Roteiro, item 8",
    )
    add(
        chave="cronograma_obras",
        titulo="Cronograma de obras (≤ 4 anos, visto da prefeitura, subscrito pelo loteador)",
        categoria="projeto",
        em_nome_de=[],
        fonte_legal="Roteiro, item 9",
    )
    add(
        chave="hipoteca_caucao",
        titulo="Escritura de hipoteca/caução (garantia das obras de infraestrutura futuras)",
        categoria="projeto",
        em_nome_de=[],
        obrigatorio=False,
        condicional="se as obras de infraestrutura serão implantadas no futuro",
        fonte_legal="Roteiro, item 10",
    )
    add(
        chave="contrato_padrao",
        titulo="Contrato-padrão (sem cláusulas abusivas; art. 25+ da Lei 6.766; CDC)",
        categoria="projeto",
        em_nome_de=[],
        fonte_legal="Roteiro, item 11",
    )

    # 12) Observações de triagem
    add(
        chave="faixas_restricoes",
        titulo="Verificar faixas non aedificandi / servidão administrativa / prolongamento de "
        "vias; restrições de uso devem constar do memorial e do contrato-padrão",
        categoria="observacao",
        em_nome_de=[],
        obrigatorio=False,
        fonte_legal="Roteiro, item 12a-c",
    )
    add(
        chave="rural_urbano",
        titulo="Confirmar perímetro urbano × rural; se rural, alterar destinação (INCRA + "
        "prefeitura + certidão negativa do imóvel)",
        categoria="observacao",
        em_nome_de=[],
        obrigatorio=False,
        fonte_legal="Roteiro, item 12d",
    )
    return itens


# ---- helpers ----
def _norm(s: str | None) -> str:
    return "".join(ch for ch in (s or "").lower() if ch.isalnum())


def _tipo_por_doc(doc: str | None) -> str | None:
    """Heurística: 14 dígitos → CNPJ (pj); 11 → CPF (pf). Sem doc → None (não chuta)."""
    digs = "".join(ch for ch in (doc or "") if ch.isdigit())
    if len(digs) == 14:
        return "pj"
    if len(digs) == 11:
        return "pf"
    return None


def _rotulo(p: schemas.ProprietarioOut) -> str:
    nome = p.nome or "(proprietário sem nome no documento)"
    return f"{nome} ({p.documento})" if p.documento else nome


def _prov(p: schemas.ProprietarioDoc) -> str:
    partes = ["Matrícula"]
    if p.ato:
        partes.append(p.ato)
    if p.pagina:
        partes.append(f"p.{p.pagina}")
    return ", ".join(partes)
