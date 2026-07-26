from datetime import date
from pathlib import Path

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


def test_grupo_rtc_sem_class_trib_e_bloqueio():
    """O caso do meio: ERP atualizado, grupo presente, cClassTrib esquecido.

    É o mais traiçoeiro do conjunto, porque o time olha a nota, vê o gIBSCBS e
    conclui que está pronto. A nota é rejeitada do mesmo jeito.
    """
    achados = avaliar_nota(ler_nota(FIXTURES / "rtc002_sem_class_trib.xml"))
    rtc002 = [a for a in achados if a.codigo == "RTC002"]

    assert len(rtc002) == 1
    assert rtc002[0].severidade is Severidade.BLOQUEIO
    assert rtc002[0].sku == "SKU-5005"
    assert "cClassTrib" in rtc002[0].mensagem


def test_item_com_grupo_completo_nao_gera_rtc001_nem_rtc002():
    """O contraste: no mesmo arquivo, o item que está certo fica calado."""
    achados = avaliar_nota(ler_nota(FIXTURES / "rtc002_sem_class_trib.xml"))
    do_item_bom = [a for a in achados if a.sku == "SKU-5006"]

    assert [a for a in do_item_bom if a.codigo in {"RTC001", "RTC002"}] == []


def test_rtc001_e_rtc002_sao_mutuamente_exclusivos():
    """Sem o grupo é RTC001; com o grupo e sem cClassTrib é RTC002. Nunca os dois."""
    for arquivo in ("legado_crt3.xml", "rtc002_sem_class_trib.xml"):
        achados = avaliar_nota(ler_nota(FIXTURES / arquivo))
        por_sku: dict[str, set[str]] = {}
        for a in achados:
            por_sku.setdefault(a.sku, set()).add(a.codigo)
        for sku, cods in por_sku.items():
            assert not {"RTC001", "RTC002"} <= cods, f"{arquivo}: {sku} acusou os dois"


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


def test_dias_ate_corte():
    assert dias_ate_corte(date(2026, 7, 25)) == 9
    assert dias_ate_corte(date(2026, 8, 3)) == 0
    assert dias_ate_corte(date(2026, 8, 10)) == -7
