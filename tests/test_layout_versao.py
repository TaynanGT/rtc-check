"""O literal ``SEM GTIN`` só existe a partir do layout 4.00.

Este arquivo existe por causa de um falso positivo real: rodando contra NF-e
públicas do repositório nfephp-org/nfephp (layouts 2.00, 3.00 e 3.10), a
ferramenta acusava "informe o literal 'SEM GTIN'" em notas de uma época em que
esse literal não existia. Cada teste aqui trava um lado da regra.
"""

from pathlib import Path

import pytest

from rtc_check.parser import ler_nota
from rtc_check.rules import Severidade, avaliar_nota

FIXTURES = Path(__file__).parent / "fixtures"


def codigos(achados):
    return {a.codigo for a in achados}


def test_layout_antigo_com_cean_vazio_nao_alerta():
    """O caso que era falso positivo. cEAN vazio em 3.10 é declaração válida."""
    nota = ler_nota(FIXTURES / "layout_antigo_v310.xml")
    assert nota.versao == "3.10"
    assert not nota.exige_literal_sem_gtin

    achados = avaliar_nota(nota)
    vazios = [a for a in achados if a.codigo == "GTIN001" and a.sku == "ANT-001"]
    assert vazios == [], f"cEAN vazio em layout 3.10 não deve alertar: {vazios}"


def test_layout_antigo_ainda_pega_gtin_com_dv_errado():
    """Afrouxar o cEAN vazio não pode afrouxar o dígito verificador."""
    achados = avaliar_nota(ler_nota(FIXTURES / "layout_antigo_v310.xml"))
    dv = [a for a in achados if a.codigo == "GTIN001" and a.sku == "ANT-002"]
    assert len(dv) == 1
    assert "dígito verificador" in dv[0].mensagem
    assert dv[0].severidade is Severidade.ALERTA


def test_layout_antigo_continua_gerando_bloqueio_de_rtc():
    """Nota antiga de CRT=3 ainda revela SKU que precisa de cClassTrib."""
    achados = avaliar_nota(ler_nota(FIXTURES / "layout_antigo_v310.xml"))
    assert "RTC001" in codigos(achados)


def test_layout_4_exige_o_literal():
    """No 4.00 o literal passa a ser obrigatório, e aí o alerta é correto."""
    nota = ler_nota(FIXTURES / "cadastro_sujo_crt3.xml")
    assert nota.exige_literal_sem_gtin

    achados = avaliar_nota(nota)
    vazios = [a for a in achados if a.codigo == "GTIN001" and a.sku == "SKU-4004"]
    assert len(vazios) == 1
    assert "SEM GTIN" in vazios[0].mensagem


@pytest.mark.parametrize(
    ("versao", "exige"),
    [
        ("2.00", False),
        ("3.00", False),
        ("3.10", False),
        ("4.00", True),
        ("4.10", True),
    ],
)
def test_limiar_da_versao(tmp_path, versao, exige):
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<NFe xmlns="http://www.portalfiscal.inf.br/nfe"><infNFe Id="NFe1" versao="{versao}">
<ide><mod>55</mod><nNF>1</nNF></ide>
<emit><CNPJ>1</CNPJ><xNome>T</xNome><CRT>3</CRT></emit>
<det nItem="1"><prod><cProd>S</cProd><cEAN></cEAN><xProd>P</xProd>
<NCM>12345678</NCM><CFOP>5102</CFOP></prod></det>
</infNFe></NFe>"""
    arq = tmp_path / "n.xml"
    arq.write_text(xml, encoding="utf-8")

    nota = ler_nota(arq)
    assert nota.exige_literal_sem_gtin is exige

    tem_alerta_de_vazio = any(
        a.codigo == "GTIN001" and "SEM GTIN" in a.mensagem for a in avaliar_nota(nota)
    )
    assert tem_alerta_de_vazio is exige


def test_versao_ausente_nao_exige_o_literal(tmp_path):
    """Sem o atributo versao, o conservador é não acusar."""
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<NFe xmlns="http://www.portalfiscal.inf.br/nfe"><infNFe Id="NFe1">
<ide><mod>55</mod><nNF>1</nNF></ide>
<emit><CNPJ>1</CNPJ><xNome>T</xNome><CRT>3</CRT></emit>
<det nItem="1"><prod><cProd>S</cProd><cEAN></cEAN><xProd>P</xProd>
<NCM>12345678</NCM><CFOP>5102</CFOP></prod></det>
</infNFe></NFe>"""
    arq = tmp_path / "n.xml"
    arq.write_text(xml, encoding="utf-8")

    nota = ler_nota(arq)
    assert nota.versao == ""
    assert not nota.exige_literal_sem_gtin
