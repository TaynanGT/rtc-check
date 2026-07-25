from datetime import date
from pathlib import Path

from rtc_check.normativa import NORMATIVA_RTC
from rtc_check.parser import ler_nota
from rtc_check.rules import Severidade, avaliar_nota, dias_ate_corte

FIXTURES = Path(__file__).parent / "fixtures"


def codigos(achados):
    return {a.codigo for a in achados}


def test_crt3_sem_grupo_rtc_e_bloqueio():
    achados = avaliar_nota(ler_nota(FIXTURES / "legado_crt3.xml"))
    assert "RTC001" in codigos(achados)
    rtc = [a for a in achados if a.codigo == "RTC001"]
    assert len(rtc) == 2  # os dois itens
    assert all(a.severidade is Severidade.BLOQUEIO for a in rtc)


def test_nota_conforme_nao_gera_bloqueio():
    achados = avaliar_nota(ler_nota(FIXTURES / "conforme_crt3.xml"))
    assert not [a for a in achados if a.severidade is Severidade.BLOQUEIO]


def test_simples_nacional_nao_gera_bloqueio_de_rtc():
    """CRT=1 não entra no corte de agosto, mesmo sem o grupo gIBSCBS."""
    achados = avaliar_nota(ler_nota(FIXTURES / "simples_crt1.xml"))
    assert "RTC001" not in codigos(achados)
    assert "RTC002" not in codigos(achados)


def test_ncm_invalido_e_bloqueio():
    achados = avaliar_nota(ler_nota(FIXTURES / "cadastro_sujo_crt3.xml"))
    ncm = [a for a in achados if a.codigo == "NCM001"]
    assert len(ncm) == 1
    assert ncm[0].severidade is Severidade.BLOQUEIO
    assert ncm[0].sku == "SKU-3003"
    assert "8311" in ncm[0].mensagem


def test_gtin_invalido_e_alerta_nao_bloqueio():
    achados = avaliar_nota(ler_nota(FIXTURES / "cadastro_sujo_crt3.xml"))
    gtins = [a for a in achados if a.codigo == "GTIN001"]
    assert len(gtins) == 2  # DV errado + cEAN vazio
    assert all(a.severidade is Severidade.ALERTA for a in gtins)


def test_achado_carrega_contexto_para_o_relatorio():
    achados = avaliar_nota(ler_nota(FIXTURES / "legado_crt3.xml"))
    a = achados[0]
    assert a.sku == "SKU-1001"
    assert a.descricao
    assert a.ncm
    assert a.arquivo == "legado_crt3.xml"
    assert a.chave_sku == ("12345678000199", "SKU-1001", a.codigo)


def test_dias_ate_corte():
    assert dias_ate_corte(date(2026, 7, 25)) == 9
    assert dias_ate_corte(date(2026, 8, 3)) == 0
    assert dias_ate_corte(date(2026, 8, 10)) == -7


def test_referencia_normativa_e_auditavel():
    assert NORMATIVA_RTC.rotulo == "Nota Técnica 2025.002-RTC v1.50"
    assert NORMATIVA_RTC.tabela_versao == "1.60"
    assert NORMATIVA_RTC.corte_obrigatoriedade == date(2026, 8, 3)
    assert NORMATIVA_RTC.como_json()["fonte"].startswith("https://www.nfe.fazenda.gov.br/")
