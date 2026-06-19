"""Fase 10.3 — VIA de conexão DIAGONAL cruzando a faixa ≥30%.

Correção conceitual (confirmada por pesquisa + Lei 6.766 art. 3º, parág. único, III): a faixa ≥30%
veda LOTE, não VIA. Uma via cruza terreno ≥30% na DIAGONAL com greide controlado (corte/aterro):
greide_via = s·sen θ. Logo a conexão entre porções não se decide por "a faixa é ≥30%", e sim pelo
GREIDE DA VIA no melhor traçado diagonal — que o Python acha por busca minimax e MEDE (§1/§2).

Valores-ouro: terreno-rampa de 30% (cota = 0,30·x) com duas porções separadas por uma faixa de
120 m. O cruzamento RETO (vão mais curto) é 30% → inviável (escadaria). A via DIAGONAL desce o
greide para ≤15% (via), atravessando a mesma faixa ≥30%, e marca a exigência geotécnica.
"""

from shapely.geometry import box

from app.core import conexao


def _cota_rampa(x, y):
    """Terreno-rampa: 30% na direção x (cota sobe 0,30 m por metro). Independe de y → atravessar na
    diagonal (ganhando x devagar, andando em y) reduz o greide da VIA; atravessar reto não."""
    return 0.30 * x


PORCAO_A = box(0, 0, 40, 200)        # oeste (cota 0–12 m)
PORCAO_B = box(160, 0, 200, 200)     # leste (cota 48–60 m)
FAIXA = box(40, 0, 160, 200)         # faixa ≥30% entre elas (120 m de vão)
GLEBA = box(0, 0, 200, 200)


def test_reto_e_inviavel():
    """O modelo reto (vão mais curto) sobe 36 m em 120 m = 30% → escadaria, não via (catálogo §2.3)."""
    tv = conexao.travessia_otima(PORCAO_A, PORCAO_B, _cota_rampa)
    assert tv.greide_pct >= 25.0
    assert tv.veredicto == "inviavel"


def test_diagonal_conecta_cruzando_faixa():
    """10.3 — a via DIAGONAL atravessa a MESMA faixa ≥30%, mas com greide da via ≤15% (não inviável).
    Marca ``cruza_restricao`` (laudo geotécnico) e o eixo é mais longo que o vão reto (serpenteia)."""
    tv = conexao.travessia_diagonal(PORCAO_A, PORCAO_B, _cota_rampa, GLEBA, FAIXA)
    assert tv.proposta_por == "diagonal"
    assert tv.greide_pct <= conexao.GREIDE_ALERTA_PCT          # ≤15% = via (não escadaria)
    assert tv.veredicto != "inviavel"
    reto = conexao.travessia_otima(PORCAO_A, PORCAO_B, _cota_rampa)
    assert tv.greide_pct < reto.greide_pct                     # diagonal é MAIS suave que reto
    assert tv.cruza_restricao is True                          # cruza a faixa ≥30% → exige laudo
    assert tv.eixo.length > 120.0                              # serpenteia (mais longo que o vão reto)
    # liga de fato as duas porções (eixo toca A e B)
    assert tv.eixo.intersects(PORCAO_A.buffer(conexao.PASSO_GRADE_M))
    assert tv.eixo.intersects(PORCAO_B.buffer(conexao.PASSO_GRADE_M))


def test_diagonal_degrada_sem_porcoes():
    """Robustez: se a grade não pega as duas porções (passo grosso/sliver), degrada p/ reto — não
    quebra nem inventa caminho. Aqui forço passo gigante → grade não resolve → fallback."""
    tv = conexao.travessia_diagonal(PORCAO_A, PORCAO_B, _cota_rampa, GLEBA, FAIXA, passo=500.0)
    assert tv.eixo is not None and not tv.eixo.is_empty
