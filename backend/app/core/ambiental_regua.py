"""AMB-EXC — RÉGUA LEGAL de supressão de vegetação nativa (dado versionado, não hardcode).

Princípio (spec fase-amb-exc.md, §3c): o laudo de vistoria declara FATOS (estágio de
regeneração, formação, achados de campo); a CONSEQUÊNCIA legal é aplicada AQUI, de forma
determinística e citando o dispositivo. A plataforma nunca autoriza nada — a autorização de
supressão é sempre do órgão competente (Lei 12.651/2012, art. 26; competências LC 140/2011).

Régua em 3 camadas com degradação honesta (padrão da casa):
  1. FEDERAL — vale em qualquer gleba do país (12.651 art. 26: CAR + autorização prévia);
  2. BIOMA — Mata Atlântica tem lei própria (11.428/2006, arts. 25/30/31 p/ área urbana);
     Pampa tem rito estadual RS (IN Conjunta SEMA-FEPAM 01/2021; campo nativo protegido);
  3. UF — código estadual (ex.: RS 15.434/2020: banhado é APP) e resolução de estágio.
     Sem dado da UF → aplica federal+bioma e ROTULA (nunca inventa).

Fontes verificadas: docs/pesquisa-legal-supressao-vegetacao.md (2 rodadas, 08/08/2026).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# ----------------------------- vocabulário -----------------------------

# Estágios de regeneração da Mata Atlântica (Lei 11.428; parâmetros botânicos são matéria do
# LAUDO, enquadrados pela resolução CONAMA da UF — ex.: 33/1994-RS, 1/1994-SP).
ESTAGIOS_MA = ("primaria", "sec_avancado", "sec_medio", "sec_inicial", "nao_nativa")

# Formações fora da Mata Atlântica (Pampa e regime geral do Código Florestal).
FORMACOES_GERAIS = ("florestal", "campestre", "nao_nativa")

ACAO_VEDADA = "vedada"                # supressão vedada para loteamento/edificação
ACAO_PRESERVAR = "preservar_pct"      # admitida preservando % mínima da vegetação
ACAO_AUTORIZACAO = "autorizacao"      # admitida mediante autorização do órgão competente
ACAO_LIBERADA = "liberada"            # fora do regime de vegetação nativa (anotado)


@dataclass(frozen=True)
class RegimeAmbiental:
    """Regime aplicável à gleba (resolvido por bioma/área de aplicação + UF)."""

    codigo: str            # "mata_atlantica" | "pampa" | "geral"
    rotulo: str
    rito: str              # texto do rito de autorização (proveniência)
    cobertura: str         # "FEDERAL" | "FEDERAL+BIOMA" | "FEDERAL+BIOMA+UF"
    avisos: tuple[str, ...] = ()


@dataclass(frozen=True)
class Consequencia:
    """Consequência legal aplicada ao fato declarado pelo laudo (com proveniência)."""

    acao: str                       # ACAO_*
    pct_preservar: Optional[float]  # fração mínima a preservar (0.5/0.3) quando ACAO_PRESERVAR
    base_legal: str                 # dispositivo citado
    leitura: str                    # frase honesta p/ tela/PDF
    avisos: tuple[str, ...] = ()


# ----------------------------- resolução de regime -----------------------------

# UFs com perfil estadual carregado (camada 3). Hoje: RS (pesquisa 08/08/2026). Adicionar UF =
# adicionar entrada aqui + regras específicas — NUNCA hardcode fora desta tabela.
_PERFIS_UF: dict[str, dict] = {
    "RS": {
        "banhado_app": "Lei estadual 15.434/2020 (Código Estadual do Meio Ambiente): banhado "
                       "é Área de Preservação Permanente",
        "rito_pampa": "IN Conjunta SEMA-FEPAM 01/2021 (critérios de supressão no Pampa); "
                      "conversão de área campestre: Diretriz Técnica FEPAM 15/2024",
        "resolucao_estagio_ma": "CONAMA 33/1994 (estágios da Mata Atlântica no RS)",
    },
    "SP": {
        "resolucao_estagio_ma": "CONAMA 1/1994 (estágios da Mata Atlântica em SP)",
    },
}

_RITO_FEDERAL = ("Lei 12.651/2012, art. 26: supressão de vegetação nativa exige CAR + "
                 "autorização prévia do órgão competente (competências: LC 140/2011)")


def resolver_regime(
    bioma: Optional[str],
    na_area_lei_ma: Optional[bool],
    uf: Optional[str],
) -> RegimeAmbiental:
    """Resolve o regime da gleba. ``na_area_lei_ma`` vem do mapa OFICIAL da área de aplicação
    da Lei 11.428 (IBGE) quando disponível; ``None`` → cai no bioma IBGE com aviso (o bioma
    Mata Atlântica está contido na área de aplicação, que é maior que o bioma)."""
    uf_norm = (uf or "").strip().upper() or None
    perfil_uf = _PERFIS_UF.get(uf_norm or "")
    avisos: list[str] = []
    bioma_norm = (bioma or "").strip().lower()

    if na_area_lei_ma is None and bioma_norm:
        ma = "mata atlântica" in bioma_norm or "mata atlantica" in bioma_norm
        avisos.append(
            "Área de aplicação da Lei 11.428 inferida pelo BIOMA (IBGE) — o mapa oficial da "
            "lei é mais abrangente que o bioma; confirmar no órgão ambiental."
        )
    else:
        ma = bool(na_area_lei_ma)

    if ma:
        cobertura = "FEDERAL+BIOMA" + ("+UF" if perfil_uf and perfil_uf.get("resolucao_estagio_ma") else "")
        rito = _RITO_FEDERAL + "; regime especial da Lei 11.428/2006 (Mata Atlântica)"
        if perfil_uf and perfil_uf.get("resolucao_estagio_ma"):
            rito += f"; estágios conforme {perfil_uf['resolucao_estagio_ma']}"
        else:
            avisos.append(
                "Resolução CONAMA de estágios da UF não carregada — o laudo deve indicar a "
                "resolução aplicável ao estado."
            )
        return RegimeAmbiental("mata_atlantica", "Mata Atlântica (Lei 11.428/2006)",
                               rito, cobertura, tuple(avisos))

    if "pampa" in bioma_norm:
        if perfil_uf and perfil_uf.get("rito_pampa"):
            return RegimeAmbiental(
                "pampa", "Bioma Pampa (rito estadual RS)",
                _RITO_FEDERAL + f"; {perfil_uf['rito_pampa']}",
                "FEDERAL+BIOMA+UF", tuple(avisos),
            )
        avisos.append("Perfil estadual não carregado para esta UF — aplicada a regra federal; "
                      "verificar o rito no órgão estadual.")
        return RegimeAmbiental("pampa", "Bioma Pampa", _RITO_FEDERAL,
                               "FEDERAL+BIOMA", tuple(avisos))

    if not bioma_norm:
        avisos.append("Bioma não identificado — aplicada a regra federal geral; verificar "
                      "regime especial (Mata Atlântica) no órgão ambiental.")
    return RegimeAmbiental("geral", f"Regime geral do Código Florestal"
                           + (f" (bioma {bioma})" if bioma_norm else ""),
                           _RITO_FEDERAL, "FEDERAL" + ("+BIOMA" if bioma_norm else ""),
                           tuple(avisos))


# ----------------------------- Mata Atlântica: arts. 25/30/31 -----------------------------

def consequencia_mata_atlantica(
    estagio: str,
    perimetro_urbano_pre_lei: Optional[bool],
) -> Consequencia:
    """Consequência p/ LOTEAMENTO/EDIFICAÇÃO em área urbana da Mata Atlântica, conforme o
    ESTÁGIO declarado no laudo e a data de aprovação do perímetro urbano (marco: 22/12/2006,
    vigência da Lei 11.428). ``perimetro_urbano_pre_lei=None`` (data não informada) → aplica a
    leitura MAIS CONSERVADORA com aviso (degradação honesta, nunca silêncio)."""
    if estagio not in ESTAGIOS_MA:
        raise ValueError(f"estágio desconhecido: {estagio!r} (válidos: {ESTAGIOS_MA})")

    avisos: tuple[str, ...] = ()
    if perimetro_urbano_pre_lei is None and estagio in ("sec_avancado", "sec_medio"):
        avisos = (
            "Data de aprovação do perímetro urbano NÃO informada — aplicada a leitura mais "
            "conservadora (perímetro pós-22/12/2006). Informe a data (lei municipal) para "
            "destravar a leitura correta.",
        )

    if estagio == "primaria":
        return Consequencia(
            ACAO_VEDADA, None,
            "Lei 11.428/2006, art. 30 (caput)",
            "Supressão de vegetação primária é VEDADA para fins de loteamento ou edificação.",
        )
    if estagio == "sec_avancado":
        if perimetro_urbano_pre_lei:
            return Consequencia(
                ACAO_PRESERVAR, 0.50,
                "Lei 11.428/2006, art. 30, I",
                "Admitida com autorização do órgão estadual, preservando ≥ 50% da área "
                "coberta por esta vegetação (perímetro urbano aprovado até 22/12/2006).",
            )
        return Consequencia(
            ACAO_VEDADA, None,
            "Lei 11.428/2006, art. 30, II",
            "Supressão VEDADA para loteamento/edificação em perímetro urbano aprovado após "
            "22/12/2006.",
            avisos,
        )
    if estagio == "sec_medio":
        if perimetro_urbano_pre_lei:
            return Consequencia(
                ACAO_PRESERVAR, 0.30,
                "Lei 11.428/2006, art. 31, § 1º",
                "Admitida com autorização do órgão estadual, conforme o plano diretor, "
                "preservando ≥ 30% da área coberta por esta vegetação (perímetro até "
                "22/12/2006).",
            )
        return Consequencia(
            ACAO_PRESERVAR, 0.50,
            "Lei 11.428/2006, art. 31, § 2º",
            "Admitida preservando ≥ 50% da área coberta por esta vegetação (perímetro "
            "delimitado após 22/12/2006).",
            avisos,
        )
    if estagio == "sec_inicial":
        return Consequencia(
            ACAO_AUTORIZACAO, None,
            "Lei 11.428/2006, art. 25",
            "Supressão admitida mediante autorização do órgão estadual competente.",
        )
    # nao_nativa
    return Consequencia(
        ACAO_LIBERADA, None,
        "Fora do regime da Lei 11.428 (constatação do laudo: não é vegetação nativa)",
        "Liberada para o estudo. Corte de plantio comercial (silvicultura) segue regras "
        "próprias — anotado na proveniência.",
    )


# ----------------------------- Pampa / regime geral -----------------------------

def consequencia_geral(formacao: str, regime: RegimeAmbiental) -> Consequencia:
    """Consequência fora da Mata Atlântica (Pampa e regime geral): o laudo declara a
    FORMAÇÃO; qualquer vegetação nativa (florestal OU campestre) só sai com autorização do
    órgão competente — no Pampa, o campo nativo também é protegido (DT FEPAM 15/2024)."""
    if formacao not in FORMACOES_GERAIS:
        raise ValueError(f"formação desconhecida: {formacao!r} (válidas: {FORMACOES_GERAIS})")
    if formacao == "nao_nativa":
        return Consequencia(
            ACAO_LIBERADA, None,
            "Fora do regime de vegetação nativa (constatação do laudo)",
            "Liberada para o estudo — anotado na proveniência.",
        )
    rotulo = "florestal" if formacao == "florestal" else "campestre (campo nativo)"
    return Consequencia(
        ACAO_AUTORIZACAO, None,
        regime.rito,
        f"Vegetação nativa {rotulo}: supressão admitida somente mediante autorização do "
        "órgão competente.",
    )


# ----------------------------- achados de campo (restrição nova) -----------------------------

def base_restricao_campo(tipo: str, uf: Optional[str]) -> str:
    """Base legal (proveniência) para restrições ACHADAS EM CAMPO pelo laudo. ``tipo``:
    'banhado' | 'nascente' | 'app_curso_dagua' | 'outro'."""
    uf_norm = (uf or "").strip().upper()
    perfil = _PERFIS_UF.get(uf_norm)
    if tipo == "banhado":
        if perfil and perfil.get("banhado_app"):
            return perfil["banhado_app"]
        return ("Área úmida constatada em campo — régua federal/estadual aplicável "
                "(verificar no órgão da UF; no RS, banhado é APP pela Lei 15.434/2020)")
    if tipo == "nascente":
        return "APP de nascente — Lei 12.651/2012, art. 4º, IV (raio mínimo de 50 m)"
    if tipo == "app_curso_dagua":
        return "APP de curso d'água — Lei 12.651/2012, art. 4º, I (faixa conforme largura)"
    return "Restrição constatada em laudo de vistoria de campo (base indicada no laudo)"
