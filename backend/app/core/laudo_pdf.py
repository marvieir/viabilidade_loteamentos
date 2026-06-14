"""Renderização do laudo (Fase 7) → PDF. Usa fpdf2 (Python puro, offline, determinístico —
nenhuma fonte externa nem rede). Apenas APRESENTA o ``LaudoData`` (composto em ``laudo.py``):
capa + semáforo + seções, com a ressalva §1-A na capa e no RODAPÉ de toda página, e
numeração. Não calcula nem reformata número (§2)."""

from __future__ import annotations

import datetime

from fpdf import FPDF
from fpdf.enums import XPos, YPos

from app.models import schemas

# Avança para a próxima linha na margem esquerda (defaults de cell/multi_cell mudaram no
# fpdf2 2.8 — explicitar evita o cursor "preso" na margem direita).
_NL = dict(new_x=XPos.LMARGIN, new_y=YPos.NEXT)
_INLINE = dict(new_x=XPos.RIGHT, new_y=YPos.TOP)

# Data de criação FIXA nos metadados → bytes reprodutíveis (determinismo, §2).
_DATA_FIXA = datetime.datetime(2024, 1, 1, 0, 0, 0)

# Cores do semáforo (RGB).
_COR_LUZ = {
    "favoravel": (16, 185, 129),
    "atencao": (245, 158, 11),
    "restricao": (239, 68, 68),
    "informativa": (100, 116, 139),
    "nao_analisada": (203, 213, 225),
}
_ROTULO_LUZ = {
    "favoravel": "FAVORAVEL",
    "atencao": "ATENCAO",
    "restricao": "RESTRICAO",
    "informativa": "INFORMATIVA",
    "nao_analisada": "NAO ANALISADA",
}

# Substituições para o conjunto latin-1 das fontes-núcleo (sem dependência de TTF externo).
_SUBS = {
    "≥": ">=", "≤": "<=", "→": "->", "÷": "/", "×": "x", "²": "2", "³": "3",
    "–": "-", "—": "-", "…": "...", "•": "-", "≠": "!=", "‐": "-",
    "“": '"', "”": '"', "‘": "'", "’": "'", " ": " ",
}


def _txt(s) -> str:
    """Sanitiza para latin-1 (fontes-núcleo do fpdf2). Mantém acentos pt-BR e §; troca os
    símbolos fora do latin-1 por equivalentes ASCII. Determinístico."""
    s = "" if s is None else str(s)
    for k, v in _SUBS.items():
        s = s.replace(k, v)
    return s.encode("latin-1", "replace").decode("latin-1")


class _Laudo(FPDF):
    def __init__(self, rodape: str):
        super().__init__(orientation="P", unit="mm", format="A4")
        self._rodape = rodape
        self.set_auto_page_break(auto=True, margin=22)

    def footer(self):
        # Rodapé §1-A em TODA página + numeração.
        self.set_y(-18)
        self.set_font("helvetica", size=7)
        self.set_text_color(120, 120, 120)
        self.multi_cell(0, 3.5, _txt(self._rodape), align="C", **_NL)
        self.set_y(-8)
        self.set_font("helvetica", size=7)
        self.cell(0, 4, _txt(f"Página {self.page_no()}"), align="C", **_NL)


def _badge(pdf: _Laudo, luz: str):
    cor = _COR_LUZ.get(luz, (203, 213, 225))
    rotulo = _ROTULO_LUZ.get(luz, luz.upper())
    pdf.set_fill_color(*cor)
    x, y = pdf.get_x(), pdf.get_y()
    pdf.rect(x, y + 1, 3, 3, style="F")
    pdf.set_x(x + 5)
    pdf.set_font("helvetica", "B", 8)
    pdf.set_text_color(70, 70, 70)
    pdf.cell(0, 5, _txt(rotulo), **_NL)
    pdf.ln(2)


def _capa(pdf: _Laudo, laudo: schemas.LaudoData):
    pdf.add_page()
    pdf.set_text_color(20, 20, 20)
    pdf.set_font("helvetica", "B", 18)
    pdf.multi_cell(0, 9, _txt(laudo.titulo), **_NL)
    pdf.ln(2)
    pdf.set_font("helvetica", size=9)
    pdf.set_text_color(90, 90, 90)
    pdf.cell(0, 5, _txt(f"Análise {laudo.analise_id}  ·  gerado em {laudo.data_geracao}"), **_NL)
    pdf.ln(10)

    # Painel de semáforo (uma luz por dimensão).
    pdf.set_font("helvetica", "B", 12)
    pdf.set_text_color(20, 20, 20)
    pdf.cell(0, 7, _txt("Semáforo de triagem (por dimensão)"), **_NL)
    pdf.ln(4)
    for luz in laudo.semaforo:
        cor = _COR_LUZ.get(luz.luz, (203, 213, 225))
        pdf.set_fill_color(*cor)
        x, y = pdf.get_x(), pdf.get_y()
        pdf.rect(x, y + 0.5, 4, 4, style="F")
        pdf.set_x(x + 6)
        pdf.set_font("helvetica", "B", 10)
        pdf.set_text_color(40, 40, 40)
        pdf.cell(52, 5, _txt(luz.dimensao), **_INLINE)
        pdf.set_font("helvetica", "B", 9)
        pdf.set_text_color(*cor)
        pdf.cell(30, 5, _txt(_ROTULO_LUZ.get(luz.luz, luz.luz)), **_INLINE)
        pdf.set_font("helvetica", size=8)
        pdf.set_text_color(110, 110, 110)
        pdf.multi_cell(0, 5, _txt(luz.justificativa), **_NL)
        pdf.ln(1)

    pdf.ln(4)
    # Ressalva-mestre §1-A na capa.
    pdf.set_draw_color(245, 158, 11)
    pdf.set_fill_color(255, 251, 235)
    pdf.set_font("helvetica", "B", 9)
    pdf.set_text_color(146, 64, 14)
    pdf.multi_cell(0, 5, _txt(laudo.ressalva_capa), border=1, fill=True, **_NL)


def _secao(pdf: _Laudo, sec: schemas.SecaoLaudo):
    pdf.set_font("helvetica", "B", 13)
    pdf.set_text_color(20, 20, 20)
    pdf.cell(0, 7, _txt(sec.titulo), **_NL)
    pdf.ln(2)
    _badge(pdf, sec.luz)

    if not sec.analisada:
        pdf.set_font("helvetica", "I", 9)
        pdf.set_text_color(120, 120, 120)
        pdf.multi_cell(0, 5, _txt("Não analisada nesta análise."), **_NL)
        pdf.ln(3)
        return

    for it in sec.itens:
        pdf.set_font("helvetica", "B", 9.5)
        pdf.set_text_color(40, 40, 40)
        pdf.multi_cell(0, 5, _txt(f"{it.rotulo}: {it.valor}"), **_NL)
        if it.proveniencia:
            pdf.set_font("helvetica", "I", 7.5)
            pdf.set_text_color(130, 130, 130)
            pdf.multi_cell(0, 4, _txt(f"   fonte: {it.proveniencia}"), **_NL)
        pdf.ln(0.5)

    if sec.avisos:
        pdf.ln(1)
        pdf.set_font("helvetica", size=8)
        pdf.set_text_color(146, 64, 14)
        for av in sec.avisos:
            pdf.multi_cell(0, 4, _txt(f"- {av}"), **_NL)
    pdf.ln(4)


def _proveniencia(pdf: _Laudo, laudo: schemas.LaudoData):
    if not laudo.proveniencia_consolidada:
        return
    pdf.set_font("helvetica", "B", 12)
    pdf.set_text_color(20, 20, 20)
    pdf.cell(0, 7, _txt("Proveniência consolidada"), **_NL)
    pdf.ln(3)
    for fc in laudo.proveniencia_consolidada:
        pdf.set_font("helvetica", "B", 8.5)
        pdf.set_text_color(60, 60, 60)
        pdf.multi_cell(0, 4.5, _txt(f"{fc.dimensao}: {fc.fonte}"), **_NL)
        pdf.ln(0.5)


def gerar_pdf(laudo: schemas.LaudoData) -> bytes:
    """``LaudoData`` → bytes de um PDF A4 (capa + seções + proveniência), §1-A em toda
    página, numeração. Determinístico."""
    pdf = _Laudo(rodape=laudo.rodape)
    # Data de criação fixa nos metadados → mesmos bytes para o mesmo conteúdo.
    pdf.set_creation_date(_DATA_FIXA)
    pdf.set_title(_txt(laudo.titulo))
    _capa(pdf, laudo)
    pdf.add_page()
    for sec in laudo.secoes:
        if sec.chave == "identificacao":
            _secao(pdf, sec)
    for sec in laudo.secoes:
        if sec.chave != "identificacao":
            _secao(pdf, sec)
    _proveniencia(pdf, laudo)
    saida = pdf.output()
    return bytes(saida)


def contar_paginas(pdf_bytes: bytes) -> int:
    """Conta páginas do PDF (para o teste de 'PDF válido com numeração'), sem dependências."""
    import re

    return len(re.findall(rb"/Type\s*/Page[^s]", pdf_bytes))
