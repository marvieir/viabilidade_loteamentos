"""Valores-ouro da fonte de vias do pórtico (cadeia + cache) — sem rede (stubs).

O pórtico depende da via lindeira (OSM). A resiliência tem 3 camadas: cache persistente
por gleba → Overpass (espelhos) → backup Ohsome. Estes testes fixam o CONTRATO da cadeia:
falha passa pro próximo; resposta (mesmo 'sem via') PARA a cadeia; falha total agrega os
motivos; cache grava só resposta confirmada.
"""

from shapely.geometry import LineString, Polygon

from app.core.vias import CoberturaVias, FonteViasComCache, FonteViasEncadeada


def _gleba(dx=0.0):
    return Polygon([(dx, 0), (dx + 1, 0), (dx + 1, 1), (dx, 1)])


class _Responde:
    def __init__(self, rotulo="OSM-stub"):
        self.chamadas = 0
        self.rotulo = rotulo

    def vias(self, gleba):
        self.chamadas += 1
        return CoberturaVias(
            geometria=LineString([(0, 0), (1, 1)]), fonte=self.rotulo, data_referencia="2026-07-01"
        )


class _Falha:
    def __init__(self):
        self.chamadas = 0

    def vias(self, gleba):
        self.chamadas += 1
        return CoberturaVias(avisos=["primário fora (429)"])  # fonte=None = NÃO respondeu


class _SemVia:
    def vias(self, gleba):
        return CoberturaVias(fonte="OSM-stub", avisos=["Nenhuma via mapeada."])  # respondeu: vazio


def test_cadeia_cai_pro_backup_quando_primario_falha():
    primario, backup = _Falha(), _Responde("Ohsome-stub")
    cob = FonteViasEncadeada([primario, backup]).vias(_gleba())
    assert cob.fonte == "Ohsome-stub" and cob.geometria is not None
    assert any("429" in a for a in cob.avisos)  # motivo do primário preservado (transparência)


def test_sem_via_confirmado_para_a_cadeia():
    backup = _Responde("Ohsome-stub")
    cob = FonteViasEncadeada([_SemVia(), backup]).vias(_gleba())
    assert cob.fonte == "OSM-stub" and cob.geometria is None
    assert backup.chamadas == 0  # 'sem via' é resposta da MESMA base OSM — não consulta o backup


def test_falha_total_agrega_motivos():
    cob = FonteViasEncadeada([_Falha(), _Falha()]).vias(_gleba())
    assert cob.fonte is None and len(cob.avisos) == 2


def test_cache_uma_consulta_por_gleba(tmp_path):
    interna = _Responde()
    fonte = FonteViasComCache(interna, tmp_path)
    fonte.vias(_gleba())
    cob2 = fonte.vias(_gleba())
    assert interna.chamadas == 1  # 2ª veio do disco
    assert cob2.fonte.endswith("cache") and cob2.geometria is not None


def test_cache_nao_grava_falha(tmp_path):
    fonte = FonteViasComCache(_Falha(), tmp_path)
    fonte.vias(_gleba(dx=5))
    assert list(tmp_path.glob("*.json")) == []  # falha de rede não é cacheada (tenta de novo)


def test_filtro_padrao_exclui_trilha_de_fazenda():
    # Regressão do pórtico 'no meio do nada': `track` (trilha de pasto), `service` e `road`
    # NÃO qualificam entrada de loteamento — só via pública de verdade.
    from app.core.vias import _highways

    tipos = _highways().split("|")
    assert "track" not in tipos and "service" not in tipos and "road" not in tipos
    assert "residential" in tipos and "unclassified" in tipos and "tertiary" in tipos


def test_cache_invalida_quando_filtro_muda(tmp_path, monkeypatch):
    # Cache antigo (gravado com trilhas) não pode prender a âncora errada: mudar o filtro
    # muda a chave → reconsulta.
    interna = _Responde()
    fonte = FonteViasComCache(interna, tmp_path)
    fonte.vias(_gleba())
    monkeypatch.setenv("VIAS_OSM_HIGHWAYS", "residential")
    fonte.vias(_gleba())
    assert interna.chamadas == 2  # chave nova → não leu o cache antigo
