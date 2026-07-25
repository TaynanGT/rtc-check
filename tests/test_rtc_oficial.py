from pathlib import Path

import pytest

from rtc_check.parser import ler_nota
from rtc_check.rules import avaliar_nota
from rtc_check.tabelas_rtc import CSTS_EXIGEM_GIBSCBS, CSTS_PROIBEM_GIBSCBS


def _xml_rtc(
    *,
    incluir_ibscbs: bool = True,
    cst: str | None = "000",
    cclass: str | None = "000001",
    incluir_gibscbs: bool = True,
    finalidade: str = "1",
    referencia: str = "",
    tipo_nota_debito: str = "",
    cprod_anp: str = "",
) -> str:
    ref = f"<NFref><refNFe>{referencia}</refNFe></NFref>" if referencia else ""
    debito = f"<tpNFDebito>{tipo_nota_debito}</tpNFDebito>" if tipo_nota_debito else ""
    comb = f"<comb><cProdANP>{cprod_anp}</cProdANP></comb>" if cprod_anp else ""
    campo_cst = f"<CST>{cst}</CST>" if cst is not None else ""
    campo_cclass = f"<cClassTrib>{cclass}</cClassTrib>" if cclass is not None else ""
    gibscbs = "<gIBSCBS/>" if incluir_gibscbs else ""
    ibscbs = (
        f"<IBSCBS>{campo_cst}{campo_cclass}{gibscbs}</IBSCBS>"
        if incluir_ibscbs
        else ""
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<NFe xmlns="http://www.portalfiscal.inf.br/nfe"><infNFe Id="NFe1" versao="4.00">
<ide><mod>55</mod><nNF>1</nNF><finNFe>{finalidade}</finNFe>{debito}{ref}</ide>
<emit><CNPJ>11111111000111</CNPJ><xNome>T</xNome><CRT>3</CRT></emit>
<det nItem="1"><prod><cProd>SKU</cProd><cEAN>SEM GTIN</cEAN>
<xProd>PRODUTO</xProd><NCM>72104900</NCM><CFOP>5102</CFOP>{comb}</prod>
<imposto>{ibscbs}</imposto></det>
</infNFe></NFe>"""


def _avaliar(tmp_path: Path, **kwargs: object) -> set[str]:
    arquivo = tmp_path / "nota.xml"
    arquivo.write_text(_xml_rtc(**kwargs), encoding="utf-8")
    return {achado.codigo for achado in avaliar_nota(ler_nota(arquivo))}


def test_ub12_exige_grupo_pai_ibscbs(tmp_path):
    codigos = _avaliar(tmp_path, incluir_ibscbs=False)
    assert "RTC001" in codigos


def test_ub12_nao_confunde_ibscbs_com_gibscbs(tmp_path):
    codigos = _avaliar(
        tmp_path,
        cst="400",
        cclass="400001",
        incluir_gibscbs=False,
    )
    assert not codigos & {"RTC001", "RTC003", "RTC004", "RTC005"}


@pytest.mark.parametrize("cst", sorted(CSTS_EXIGEM_GIBSCBS))
def test_ub13_30_csts_que_exigem_gibscbs(tmp_path, cst):
    codigos = _avaliar(
        tmp_path,
        cst=cst,
        cclass=f"{cst}001",
        incluir_gibscbs=False,
    )
    assert "RTC004" in codigos


@pytest.mark.parametrize("cst", sorted(CSTS_PROIBEM_GIBSCBS))
def test_ub13_20_csts_que_proibem_gibscbs(tmp_path, cst):
    codigos = _avaliar(
        tmp_path,
        cst=cst,
        cclass=f"{cst}001",
        incluir_gibscbs=True,
    )
    assert "RTC005" in codigos


def test_ub13_10_rejeita_cst_ausente_ou_inexistente(tmp_path):
    assert "RTC003" in _avaliar(tmp_path, cst=None)
    assert "RTC003" in _avaliar(tmp_path, cst="999")


def test_layout_exige_cclass_trib_no_pai(tmp_path):
    codigos = _avaliar(tmp_path, cclass=None)
    assert "RTC002" in codigos


def test_ub13_30_excecao_perda_em_estoque(tmp_path):
    codigos = _avaliar(
        tmp_path,
        cst="000",
        incluir_gibscbs=False,
        tipo_nota_debito="07",
    )
    assert "RTC004" not in codigos


def test_ub12_excecao_referencia_nfe_anterior_a_2026(tmp_path):
    # Na chave, as posições 3-4 representam o ano de emissão (25 = 2025).
    chave_2025 = "352501" + "0" * 38
    codigos = _avaliar(
        tmp_path,
        incluir_ibscbs=False,
        finalidade="4",
        referencia=chave_2025,
    )
    assert "RTC001" not in codigos


def test_ub12_excecao_combustivel_monofasico(tmp_path):
    codigos = _avaliar(
        tmp_path,
        incluir_ibscbs=False,
        cprod_anp="210203001",
    )
    assert "RTC001" not in codigos
