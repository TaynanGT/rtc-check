import json
from datetime import date
from pathlib import Path

import pytest

from rtc_check.cli import analisar, main
from rtc_check.report import formatar_html, formatar_texto
from rtc_check.rules import Severidade

FIXTURES = Path(__file__).parent / "fixtures"

TOTAL_FIXTURES = len(list(FIXTURES.glob("*.xml")))
# malformado.xml e nao_e_nfe.xml sao ilegiveis de proposito.
ILEGIVEIS = 2


def test_analise_completa_do_acervo():
    r = analisar(FIXTURES)
    assert r.arquivos_lidos == TOTAL_FIXTURES
    assert len(r.arquivos_invalidos) == ILEGIVEIS
    assert r.notas_em_escopo >= 3  # legado, cadastro sujo, conforme, layout antigo
    assert r.total_itens >= 6
    assert r.por_severidade[Severidade.BLOQUEIO.value] > 0


def _nota_crt3(sku: str, ncm: str = "72104900") -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<NFe xmlns="http://www.portalfiscal.inf.br/nfe"><infNFe Id="NFe1" versao="4.00">
<ide><mod>55</mod><nNF>1</nNF></ide>
<emit><CNPJ>1</CNPJ><xNome>T</xNome><CRT>3</CRT></emit>
<det nItem="1"><prod><cProd>{sku}</cProd><cEAN>SEM GTIN</cEAN>
<xProd>PRODUTO {sku}</xProd><NCM>{ncm}</NCM><CFOP>5102</CFOP></prod></det>
</infNFe></NFe>"""


def _nota_conforme(sku: str) -> str:
    """Nota CRT=3 que não gera achado nenhum: grupo RTC completo, NCM e GTIN ok."""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<NFe xmlns="http://www.portalfiscal.inf.br/nfe"><infNFe Id="NFe1" versao="4.00">
<ide><mod>55</mod><nNF>1</nNF></ide>
<emit><CNPJ>1</CNPJ><xNome>T</xNome><CRT>3</CRT></emit>
<det nItem="1"><prod><cProd>{sku}</cProd><cEAN>SEM GTIN</cEAN>
<xProd>PRODUTO {sku}</xProd><NCM>72104900</NCM><CFOP>5102</CFOP></prod>
<imposto><IBSCBS><CST>000</CST><cClassTrib>000001</cClassTrib>
<gIBSCBS><vBC>1.00</vBC></gIBSCBS></IBSCBS></imposto></det>
</infNFe></NFe>"""


def test_agregacao_junta_o_mesmo_sku_de_notas_diferentes(tmp_path):
    """O mesmo SKU quebrado em 3 notas é UM item de trabalho, não três."""
    for i in range(3):
        (tmp_path / f"nota{i}.xml").write_text(_nota_crt3("SKU-X"), encoding="utf-8")

    r = analisar(tmp_path)
    grupos = {g.sku: g for g in r.grupos}

    assert list(grupos) == ["SKU-X"]
    assert grupos["SKU-X"].ocorrencias == 3
    assert len(grupos["SKU-X"].arquivos) == 3
    assert r.skus_bloqueados == 1  # o número que vai para o relatório


def test_ordenacao_prioriza_bloqueio_e_depois_volume(tmp_path):
    """Quem aparece mais vezes sobe na lista, mas bloqueio vem antes de alerta."""
    for i in range(5):
        (tmp_path / f"a{i}.xml").write_text(_nota_crt3("SKU-MUITO"), encoding="utf-8")
    (tmp_path / "b.xml").write_text(_nota_crt3("SKU-POUCO"), encoding="utf-8")

    grupos = analisar(tmp_path).grupos
    assert [g.sku for g in grupos] == ["SKU-MUITO", "SKU-POUCO"]


def test_arquivos_ilegiveis_nao_derrubam_a_analise():
    r = analisar(FIXTURES)
    nomes = {n for n, _ in r.arquivos_invalidos}
    assert nomes == {"malformado.xml", "nao_e_nfe.xml"}
    assert r.arquivos_lidos == TOTAL_FIXTURES


def test_pasta_vazia_e_aprovada(tmp_path):
    r = analisar(tmp_path)
    assert r.arquivos_lidos == 0
    assert r.aprovado
    assert r.skus_bloqueados == 0


def test_saida_json_e_valida():
    r = analisar(FIXTURES)
    from rtc_check.report import formatar_json

    dados = json.loads(formatar_json(r))
    assert dados["corte"] == "2026-08-03"
    assert dados["arquivos_lidos"] == TOTAL_FIXTURES
    assert isinstance(dados["itens"], list)


def test_saida_csv_tem_cabecalho_e_linhas():
    from rtc_check.report import formatar_csv

    linhas = formatar_csv(analisar(FIXTURES)).strip().split("\n")
    assert linhas[0].startswith("sku;descricao;ncm")
    assert len(linhas) > 1


def test_html_escapa_conteudo(tmp_path):
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<NFe xmlns="http://www.portalfiscal.inf.br/nfe"><infNFe Id="NFe1" versao="4.00">
<ide><mod>55</mod><nNF>1</nNF></ide>
<emit><CNPJ>1</CNPJ><xNome>T</xNome><CRT>3</CRT></emit>
<det nItem="1"><prod><cProd>&lt;script&gt;x&lt;/script&gt;</cProd>
<cEAN>SEM GTIN</cEAN><xProd>P</xProd><NCM>1234</NCM><CFOP>5102</CFOP></prod></det>
</infNFe></NFe>"""
    (tmp_path / "x.xml").write_text(xml, encoding="utf-8")
    saida = formatar_html(analisar(tmp_path))
    assert "<script>x</script>" not in saida
    assert "&lt;script&gt;" in saida


def test_texto_mostra_contagem_regressiva():
    saida = formatar_texto(analisar(FIXTURES), hoje=date(2026, 7, 25))
    assert "9 dias" in saida
    assert "03/08/2026" in saida


def test_main_grava_arquivo(tmp_path, capsys):
    destino = tmp_path / "r.html"
    assert main([str(FIXTURES), "-f", "html", "-o", str(destino)]) == 0
    assert destino.exists()
    assert destino.read_text(encoding="utf-8").startswith("<!doctype html>")


def test_main_falha_em_bloqueio_quando_pedido(capsys):
    assert main([str(FIXTURES), "--falhar-em-bloqueio"]) == 1
    assert main([str(FIXTURES)]) == 0


@pytest.mark.parametrize(
    ("formato", "marca"),
    [
        ("texto", "RTC Check | prontidão"),
        ("json", '"corte": "2026-08-03"'),
        ("csv", "sku;descricao;ncm"),
        ("html", "<!doctype html>"),
    ],
)
def test_main_despacha_cada_formato(formato, marca, capsys):
    """Só o html passava por ``main()``: o dicionário de despacho era um ponto cego."""
    assert main([str(FIXTURES), "-f", formato]) == 0
    assert marca in capsys.readouterr().out


def test_main_imprime_no_stdout_quando_nao_ha_saida(capsys):
    assert main([str(FIXTURES)]) == 0
    capturado = capsys.readouterr()
    assert "RTC Check" in capturado.out
    assert capturado.err == ""


def test_main_sem_recursao_nao_entra_em_subpasta(tmp_path, capsys):
    """A flag inverte um booleano (``recursivo=not args.sem_recursao``).

    Trocar o sentido da inversão passava em todos os testes anteriores, porque
    nenhum exercitava a flag pela linha de comando.
    """
    (tmp_path / "raiz.xml").write_text(_nota_crt3("SKU-RAIZ"), encoding="utf-8")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "filho.xml").write_text(_nota_crt3("SKU-FILHO"), encoding="utf-8")

    assert main([str(tmp_path), "-f", "json", "--sem-recursao"]) == 0
    com_flag = json.loads(capsys.readouterr().out)

    assert main([str(tmp_path), "-f", "json"]) == 0
    sem_flag = json.loads(capsys.readouterr().out)

    assert com_flag["arquivos_lidos"] == 1
    assert sem_flag["arquivos_lidos"] == 2
    assert {i["sku"] for i in com_flag["itens"]} == {"SKU-RAIZ"}


def test_main_version(capsys):
    from rtc_check import __version__

    with pytest.raises(SystemExit) as saida:
        main(["-V"])
    assert saida.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_main_grava_arquivo_avisa_no_stderr(tmp_path, capsys):
    destino = tmp_path / "r.csv"
    assert main([str(FIXTURES), "-f", "csv", "-o", str(destino)]) == 0
    capturado = capsys.readouterr()
    assert capturado.out.strip() == ""
    assert str(destino) in capturado.err
    assert destino.read_text(encoding="utf-8").startswith("sku;descricao;ncm")


def test_main_falha_em_bloqueio_nao_afeta_acervo_limpo(tmp_path, capsys):
    """Pasta sem bloqueio sai 0 mesmo com a flag: é o cenário de CI verde."""
    (tmp_path / "ok.xml").write_text(_nota_conforme("SKU-OK"), encoding="utf-8")

    assert main([str(tmp_path), "--falhar-em-bloqueio"]) == 0
    assert "Nenhum bloqueio encontrado" in capsys.readouterr().out


def test_main_pasta_inexistente(tmp_path, capsys):
    assert main([str(tmp_path / "nao_existe")]) == 2
    assert "não encontrada" in capsys.readouterr().err


def test_main_caminho_e_arquivo_nao_pasta(tmp_path, capsys):
    arq = tmp_path / "a.xml"
    arq.write_text("<a/>", encoding="utf-8")
    assert main([str(arq)]) == 2
    assert "não é uma pasta" in capsys.readouterr().err


def test_executavel_como_modulo(tmp_path):
    """``python -m rtc_check`` é caminho documentado e nunca era executado.

    Vale o subprocess: é a única forma de provar que o ``__main__`` propaga o
    código de saída em vez de engolir e sair 0.
    """
    import subprocess
    import sys

    (tmp_path / "n.xml").write_text(_nota_crt3("SKU-M"), encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, "-m", "rtc_check", str(tmp_path), "--falhar-em-bloqueio"],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 1, proc.stderr
    assert "RTC Check" in proc.stdout
