"""Fase 3.B — checklist do roteiro personalizado por dono/jurisdição (determinístico)."""

from app.core import juridico_checklist as ck
from app.models import schemas


def _ficha_pj():
    return schemas.FichaJuridica(
        tipo="matricula",
        status="confirmado",
        fonte_documento="m30488.pdf",
        identificacao=schemas.IdentificacaoMatricula(
            matricula=schemas.CampoDoc(valor="30488"),
            proprietarios=[
                schemas.ProprietarioDoc(
                    nome="Paduca Administração e Participações LTDA",
                    documento="12.345.678/0001-90",
                    tipo="pj",
                    ato="R-1",
                )
            ],
        ),
        validado_por="marco",
    )


def _ficha_pf():
    return schemas.FichaJuridica(
        tipo="matricula",
        status="confirmado",
        fonte_documento="m30489.pdf",
        identificacao=schemas.IdentificacaoMatricula(
            matricula=schemas.CampoDoc(valor="30489"),
            proprietarios=[
                schemas.ProprietarioDoc(nome="João da Silva", documento="123.456.789-00")
            ],
        ),
        validado_por="marco",
    )


def _chaves(itens):
    return {i.chave for i in itens}


def test_consolida_proprietarios_dedup_e_tipo_por_doc():
    props = ck.consolidar_proprietarios([_ficha_pj(), _ficha_pf()])
    assert len(props) == 2
    pj = next(p for p in props if p.tipo == "pj")
    pf = next(p for p in props if p.tipo == "pf")
    assert "Paduca" in pj.nome and pj.matriculas == ["30488"]
    # tipo PF inferido pelo CPF (11 dígitos) mesmo sem 'tipo' explícito
    assert pf.tipo == "pf" and pf.matriculas == ["30489"]


def test_mesmo_dono_em_duas_matriculas_nao_duplica():
    f1 = _ficha_pj()
    f2 = _ficha_pj()
    f2.fonte_documento = "m99999.pdf"
    f2.identificacao.matricula = schemas.CampoDoc(valor="99999")
    props = ck.consolidar_proprietarios([f1, f2])
    assert len(props) == 1
    assert sorted(props[0].matriculas) == ["30488", "99999"]


def test_pj_gera_contrato_social_fgts_inss_sem_anuencia_conjuge():
    props = ck.consolidar_proprietarios([_ficha_pj()])
    itens = ck.gerar_checklist(props, uf="SP")
    ch = _chaves(itens)
    assert {"contrato_social", "fgts", "inss"} <= ch
    assert "anuencia_conjuge" not in ch
    assert "declaracao_nao_empregador" not in ch
    # personalização: o contrato social está em nome da PJ
    cs = next(i for i in itens if i.chave == "contrato_social")
    assert any("Paduca" in n for n in cs.em_nome_de)


def test_pf_gera_anuencia_e_declaracao_sem_fgts_inss():
    props = ck.consolidar_proprietarios([_ficha_pf()])
    itens = ck.gerar_checklist(props, uf="SP")
    ch = _chaves(itens)
    assert {"anuencia_conjuge", "declaracao_nao_empregador"} <= ch
    assert "fgts" not in ch and "inss" not in ch
    assert "contrato_social" not in ch


def test_graprohab_so_em_sp():
    props = ck.consolidar_proprietarios([_ficha_pj()])
    assert "graprohab" in _chaves(ck.gerar_checklist(props, uf="SP"))
    assert "graprohab" not in _chaves(ck.gerar_checklist(props, uf="MG"))
    assert "graprohab" not in _chaves(ck.gerar_checklist(props, uf=None))


def test_familia_b_marcada_auto_disponivel():
    props = ck.consolidar_proprietarios([_ficha_pj()])
    itens = {i.chave: i for i in ck.gerar_checklist(props, uf="SP")}
    # chaveáveis por CPF/CNPJ → auto na Fase C
    for k in ("cnd_federal", "fgts", "fazenda_estadual", "protesto"):
        assert itens[k].auto_disponivel is True, k
    # por nome / produzidos → não-auto
    for k in ("distribuidores", "planta_memorial", "contrato_padrao"):
        assert itens[k].auto_disponivel is False, k


def test_itr_condicional_nao_obrigatorio():
    props = ck.consolidar_proprietarios([_ficha_pj()])
    itr = next(i for i in ck.gerar_checklist(props, uf="SP") if i.chave == "itr")
    assert itr.obrigatorio is False
    assert itr.condicional and "rural" in itr.condicional.lower()


def test_sem_proprietarios_checklist_vazio_pelo_router():
    # gerar_checklist sempre devolve itens; o router só chama se houver proprietários.
    assert ck.consolidar_proprietarios([]) == []


# ---- item 2: donos atuais × anteriores (cadeia 10 anos) ----
def _ficha_atual_e_anterior():
    return schemas.FichaJuridica(
        tipo="matricula",
        status="confirmado",
        fonte_documento="m1.pdf",
        identificacao=schemas.IdentificacaoMatricula(
            matricula=schemas.CampoDoc(valor="111"),
            proprietarios=[
                schemas.ProprietarioDoc(
                    nome="Paduca LTDA", documento="04.597.242/0001-65",
                    tipo="pj", situacao="vigente",
                ),
                schemas.ProprietarioDoc(
                    nome="Antonio Blanco", documento="248.730.398-00",
                    tipo="pf", situacao="anterior",  # transferiu a fração (R-6)
                ),
            ],
        ),
        validado_por="marco",
    )


def test_anterior_fica_fora_das_tributarias_mas_entra_nos_distribuidores():
    props = ck.consolidar_proprietarios([_ficha_atual_e_anterior()])
    paduca = next(p for p in props if p.tipo == "pj")
    antonio = next(p for p in props if p.tipo == "pf")
    assert paduca.vigente is True
    assert antonio.vigente is False
    itens = {i.chave: i for i in ck.gerar_checklist(props, uf="SP")}
    # tributárias federais: só o dono ATUAL
    fed = " ".join(itens["cnd_federal"].em_nome_de)
    assert "Paduca" in fed and "Antonio" not in fed
    # distribuidores: titulares de 10 anos → inclui o anterior
    dist = " ".join(itens["distribuidores"].em_nome_de)
    assert "Paduca" in dist and "Antonio" in dist
    # protesto idem
    prot = " ".join(itens["protesto"].em_nome_de)
    assert "Antonio" in prot


def test_vigente_em_qualquer_matricula_conta_como_atual():
    # mesmo dono: anterior na matrícula A, vigente na matrícula B → ATUAL
    fa = _ficha_atual_e_anterior()
    fa.identificacao.proprietarios[1].situacao = "anterior"  # Antonio anterior aqui
    fb = schemas.FichaJuridica(
        tipo="matricula", status="confirmado", fonte_documento="m2.pdf",
        identificacao=schemas.IdentificacaoMatricula(
            matricula=schemas.CampoDoc(valor="222"),
            proprietarios=[
                schemas.ProprietarioDoc(
                    nome="Antonio Blanco", documento="248.730.398-00",
                    tipo="pf", situacao="vigente",  # vigente aqui
                )
            ],
        ),
        validado_por="marco",
    )
    props = ck.consolidar_proprietarios([fa, fb])
    antonio = next(p for p in props if p.tipo == "pf")
    assert antonio.vigente is True  # vigente em B vence


def test_compat_sem_situacao_default_vigente():
    # proprietário antigo sem 'situacao' explícita → vigente (não quebra fluxo existente)
    p = schemas.ProprietarioDoc(nome="X", documento="111.222.333-44")
    assert p.situacao == "vigente"
