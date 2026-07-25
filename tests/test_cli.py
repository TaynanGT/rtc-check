import json
from datetime import date
from pathlib import Path

from rtc_check.cli import analisar, main
from rtc_check.report import formatar_html, formatar_texto
from rtc_check.rules import Severidade

FIXTURES = Path(__file__).parent / "fixtures"


def test_analise_completa_do_acervo():
    r = analisar(FIXTURES)
    assert r.arquivos_lidos == 6
    assert len(r.arquivos_invalidos) == 2  # malformado + nao_e_nfe
    assert r.notas_em_escopo == 3  # os três CRT=3
    assert r.total_itens == 6
    assert r.por_severidade[Severidade.BLOQUEIO.value] > 0


def _nota_crt3(sku: str, ncm: str = "72104900") -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<NFe xmlns="http://www.portalfiscal.inf.br/nfe"><infNFe Id="NFe1" versao="4.00">
<ide><mod>55</mod><nNF>1</nNF></ide>
<emit><CNPJ>1</CNPJ><xNome>T</xNome><CRT>3</CRT></emit>
<det nItem="1"><prod><cProd>{sku}</cProd><cEAN>SEM GTIN</cEAN>
<xProd>PRODUTO {sku}</xProd><NCM>{ncm}</NCM><CFOP>5102</CFOP></prod></det>
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
    assert r.arquivos_lidos == 6


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
    assert dados["arquivos_lidos"] == 6
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


def test_main_pasta_inexistente(tmp_path, capsys):
    assert main([str(tmp_path / "nao_existe")]) == 2
    assert "não encontrada" in capsys.readouterr().err


def test_main_caminho_e_arquivo_nao_pasta(tmp_path, capsys):
    arq = tmp_path / "a.xml"
    arq.write_text("<a/>", encoding="utf-8")
    assert main([str(arq)]) == 2
    assert "não é uma pasta" in capsys.readouterr().err
