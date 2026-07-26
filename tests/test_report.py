"""Testes do relatório: agregação, truncamentos e a saída para planilha.

O `report.py` era o módulo com mais galho não exercitado. Os caminhos que
faltavam não eram exóticos: o texto que o cliente aprovado vê, as duas
truncagens com aritmética de "e mais N", e o CSV — que existe para ser aberto
no Excel e não tinha o cuidado que a saída HTML já tinha.
"""

from __future__ import annotations

import csv
import io
from datetime import date

import pytest

from rtc_check.report import (
    Resumo,
    agregar,
    formatar_csv,
    formatar_html,
    formatar_texto,
)
from rtc_check.rules import Achado, Severidade


def _achado(
    sku: str = "SKU-1001",
    codigo: str = "RTC001",
    severidade: Severidade = Severidade.BLOQUEIO,
    descricao: str = "PRODUTO",
    ncm: str = "72104900",
    arquivo: str = "n.xml",
    mensagem: str = "mensagem",
) -> Achado:
    return Achado(
        severidade=severidade,
        codigo=codigo,
        mensagem=mensagem,
        sku=sku,
        descricao=descricao,
        ncm=ncm,
        arquivo=arquivo,
    )


def _linhas_csv(saida: str) -> list[list[str]]:
    """Lê o CSV de volta. ``newline=""`` para não traduzir o ``\\r`` dentro do campo."""
    return list(csv.reader(io.StringIO(saida, newline=""), delimiter=";"))


def _resumo(achados: list[Achado], **campos) -> Resumo:
    r = Resumo(**campos)
    for a in achados:
        r.por_severidade[a.severidade.value] += 1
    r.grupos = agregar(achados)
    return r


# --------------------------------------------------------------------------
# CSV: a saída que vai ser aberta numa planilha
# --------------------------------------------------------------------------


@pytest.mark.parametrize("gatilho", ["=", "+", "-", "@", "\t", "\r"])
def test_csv_neutraliza_formula_de_planilha(gatilho):
    """``cProd`` e ``xProd`` vêm de XML de terceiro e o CSV abre no Excel.

    A saída HTML já escapava; a CSV entregava a fórmula intacta para o time de
    cadastro executar com dois cliques.
    """
    payload = f"{gatilho}cmd|'/c calc'!A1"
    saida = formatar_csv(_resumo([_achado(sku=payload, descricao=payload)]))
    _, linha = _linhas_csv(saida)

    assert linha[0] == "'" + payload
    assert linha[1] == "'" + payload
    assert not linha[0].startswith(gatilho)


def test_csv_nao_mexe_em_valor_inofensivo():
    """A defesa não pode sujar o dado de quem está certo."""
    saida = formatar_csv(_resumo([_achado(sku="SKU-1001", descricao="CHAPA DE ACO")]))
    _, linha = _linhas_csv(saida)
    assert linha[0] == "SKU-1001"
    assert linha[1] == "CHAPA DE ACO"


def test_csv_escapa_o_proprio_delimitador():
    """Descrição com ponto e vírgula não pode virar coluna a mais."""
    saida = formatar_csv(_resumo([_achado(descricao="CHAPA; ACO; 2MM")]))
    cabecalho, linha = _linhas_csv(saida)
    assert len(linha) == len(cabecalho)
    assert linha[1] == "CHAPA; ACO; 2MM"


def test_csv_tem_uma_linha_por_sku():
    achados = [_achado(sku=f"SKU-{i}") for i in range(3)] + [_achado(sku="SKU-0")]
    linhas = formatar_csv(_resumo(achados)).strip().split("\n")
    assert len(linhas) == 1 + 3  # cabeçalho + 3 SKUs distintos


# --------------------------------------------------------------------------
# Texto: truncagens e o caminho de sucesso
# --------------------------------------------------------------------------


def test_texto_anuncia_acervo_limpo():
    """O que o cliente aprovado lê. Nenhum teste renderizava esta mensagem."""
    saida = formatar_texto(Resumo(arquivos_lidos=10), hoje=date(2026, 7, 25))
    assert "Nenhum bloqueio encontrado" in saida
    assert "SKUs que serão rejeitados" not in saida


def test_texto_trunca_lista_de_bloqueios_em_20():
    achados = [_achado(sku=f"SKU-{i:03d}") for i in range(25)]
    saida = formatar_texto(_resumo(achados), hoje=date(2026, 7, 25))

    assert "e mais 5 SKU(s)" in saida
    assert "SKU-019" in saida
    assert "SKU-020" not in saida
    assert "Nenhum bloqueio encontrado" not in saida


def test_texto_nao_trunca_exatamente_20():
    """A fronteira: com 20 não sobra nada para anunciar."""
    achados = [_achado(sku=f"SKU-{i:03d}") for i in range(20)]
    saida = formatar_texto(_resumo(achados), hoje=date(2026, 7, 25))
    assert "e mais" not in saida
    assert "SKU-019" in saida


def test_texto_trunca_lista_de_ilegiveis_em_5():
    invalidos = [(f"quebrado{i}.xml", "XML malformado") for i in range(8)]
    saida = formatar_texto(
        Resumo(arquivos_lidos=8, arquivos_invalidos=invalidos), hoje=date(2026, 7, 25)
    )

    assert "8 arquivo(s) ilegível(is)" in saida
    assert "quebrado0.xml" in saida
    assert "quebrado4.xml" in saida
    assert "quebrado5.xml" not in saida
    assert "e mais 3" in saida


def test_texto_nao_trunca_exatamente_5_ilegiveis():
    invalidos = [(f"q{i}.xml", "XML malformado") for i in range(5)]
    saida = formatar_texto(
        Resumo(arquivos_lidos=5, arquivos_invalidos=invalidos), hoje=date(2026, 7, 25)
    )
    assert "e mais" not in saida


# --------------------------------------------------------------------------
# Agregação
# --------------------------------------------------------------------------


def test_agregacao_usa_descricao_quando_o_sku_e_vazio():
    """Item sem ``cProd`` não pode colidir com os outros num grupo só."""
    grupos = agregar([
        _achado(sku="", descricao="PRODUTO SEM CODIGO DE CADASTRO NENHUM"),
        _achado(sku="", descricao="OUTRO PRODUTO IGUALMENTE SEM CODIGO"),
    ])
    assert len(grupos) == 2
    assert all(g.sku.startswith("(sem código)") for g in grupos)


def test_severidade_do_grupo_sobe_para_a_pior():
    """Um SKU com alerta numa nota e bloqueio noutra é bloqueio."""
    grupos = agregar([
        _achado(sku="K", codigo="GTIN001", severidade=Severidade.ALERTA, arquivo="a.xml"),
        _achado(sku="K", codigo="RTC001", severidade=Severidade.BLOQUEIO, arquivo="b.xml"),
    ])
    assert len(grupos) == 1
    assert grupos[0].severidade_max is Severidade.BLOQUEIO
    assert grupos[0].ocorrencias == 2
    assert len(grupos[0].arquivos) == 2


def test_severidade_do_grupo_nao_desce():
    """Ordem inversa da anterior: bloqueio primeiro, alerta depois."""
    grupos = agregar([
        _achado(sku="K", codigo="RTC001", severidade=Severidade.BLOQUEIO),
        _achado(sku="K", codigo="GTIN001", severidade=Severidade.ALERTA),
    ])
    assert grupos[0].severidade_max is Severidade.BLOQUEIO


def test_grupo_so_de_alerta_nao_conta_como_sku_bloqueado():
    r = _resumo([_achado(sku="K", codigo="GTIN001", severidade=Severidade.ALERTA)])
    assert r.skus_bloqueados == 0
    assert r.aprovado


def test_ordenacao_bloqueio_antes_de_alerta_mesmo_com_menos_ocorrencias():
    achados = [
        _achado(sku="ALERTA-MUITO", codigo="GTIN001", severidade=Severidade.ALERTA)
        for _ in range(10)
    ] + [_achado(sku="BLOQUEIO-POUCO")]

    grupos = agregar(achados)
    assert [g.sku for g in grupos] == ["BLOQUEIO-POUCO", "ALERTA-MUITO"]


def test_agregacao_e_estavel_para_empate_de_volume():
    """Empate desempata por SKU, senão o relatório muda de ordem a cada run."""
    achados = [_achado(sku=s) for s in ("SKU-C", "SKU-A", "SKU-B")]
    assert [g.sku for g in agregar(achados)] == ["SKU-A", "SKU-B", "SKU-C"]


def test_primeira_mensagem_do_codigo_e_a_que_fica():
    grupos = agregar([
        _achado(sku="K", codigo="NCM001", mensagem="primeira"),
        _achado(sku="K", codigo="NCM001", mensagem="segunda"),
    ])
    assert grupos[0].mensagens["NCM001"] == "primeira"
    assert grupos[0].ocorrencias == 2


def test_agregacao_de_lista_vazia():
    assert agregar([]) == []


# --------------------------------------------------------------------------
# HTML
# --------------------------------------------------------------------------


def test_html_sem_achados_tem_linha_de_vazio():
    saida = formatar_html(Resumo(arquivos_lidos=3), hoje=date(2026, 7, 25))
    assert "Nenhum achado." in saida
    assert saida.startswith("<!doctype html>")


def test_html_escapa_a_mensagem_e_o_ncm():
    """A descrição já era testada; mensagem e NCM entram no HTML pelo mesmo caminho."""
    saida = formatar_html(
        _resumo([_achado(ncm="<b>x</b>", mensagem="<img src=x onerror=alert(1)>")]),
        hoje=date(2026, 7, 25),
    )
    assert "<img src=x" not in saida
    assert "&lt;img" in saida
    assert "<b>x</b>" not in saida
