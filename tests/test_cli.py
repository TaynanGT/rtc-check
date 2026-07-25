import json
from datetime import date
from pathlib import Path

from rtc_check.cli import analisar, main
from rtc_check.report import (
    comparar,
    formatar_html,
    formatar_json,
    formatar_texto,
    rotulo_dos_emitentes,
)
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


def _nota_crt3(sku: str, ncm: str = "72104900", documento: str = "1") -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<NFe xmlns="http://www.portalfiscal.inf.br/nfe"><infNFe Id="NFe1" versao="4.00">
<ide><mod>55</mod><nNF>1</nNF></ide>
<emit><CNPJ>{documento}</CNPJ><xNome>T</xNome><CRT>3</CRT></emit>
<det nItem="1"><prod><cProd>{sku}</cProd><cEAN>SEM GTIN</cEAN>
<xProd>PRODUTO {sku}</xProd><NCM>{ncm}</NCM><CFOP>5102</CFOP></prod></det>
</infNFe></NFe>"""


def _acervo_emitente_unico(pasta: Path) -> Path:
    (pasta / "nota.xml").write_text(_nota_crt3("SKU-X"), encoding="utf-8")
    return pasta


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


def test_arquivos_homonimos_em_subpastas_contam_como_notas_distintas(tmp_path):
    for nome in ("filial-a", "filial-b"):
        pasta = tmp_path / nome
        pasta.mkdir()
        (pasta / "nota.xml").write_text(_nota_crt3("SKU-X"), encoding="utf-8")

    grupo = analisar(tmp_path).grupos[0]

    assert grupo.arquivos == {"filial-a/nota.xml", "filial-b/nota.xml"}
    assert len(grupo.arquivos) == 2


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
    assert dados["normativa"]["corte_obrigatoriedade"] == "2026-08-03"
    assert dados["normativa"]["versao"] == "1.50"
    assert dados["normativa"]["tabela_versao"] == "1.60"
    assert dados["arquivos_lidos"] == TOTAL_FIXTURES
    assert isinstance(dados["itens"], list)


def test_saida_csv_tem_cabecalho_e_linhas():
    from rtc_check.report import formatar_csv

    linhas = formatar_csv(analisar(FIXTURES)).strip().split("\n")
    assert linhas[0].startswith("sku;descricao;ncm")
    assert linhas[0].endswith(
        "emitente_documento;normativa;fonte_normativa;"
        "tabela_normativa;fonte_tabela_normativa"
    )
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
    assert "Nota Técnica 2025.002-RTC v1.50" in saida


def test_texto_mostra_contagem_regressiva():
    saida = formatar_texto(analisar(FIXTURES), hoje=date(2026, 7, 25))
    assert "9 dias" in saida
    assert "03/08/2026" in saida
    assert "Nota Técnica 2025.002-RTC v1.50" in saida


def test_main_grava_arquivo(tmp_path, capsys, licenciado):
    destino = tmp_path / "r.html"
    assert main([str(_acervo_emitente_unico(tmp_path)), "-f", "html", "-o", str(destino)]) == 0
    assert destino.exists()
    assert destino.read_text(encoding="utf-8").startswith("<!doctype html>")


def test_main_falha_em_bloqueio_quando_pedido(tmp_path, capsys, licenciado):
    pasta = _acervo_emitente_unico(tmp_path)
    assert main([str(pasta), "--falhar-em-bloqueio"]) == 1
    assert main([str(pasta)]) == 0


def test_main_pasta_inexistente(tmp_path, capsys):
    assert main([str(tmp_path / "nao_existe")]) == 2
    assert "não encontrada" in capsys.readouterr().err


def test_main_caminho_e_arquivo_nao_pasta(tmp_path, capsys):
    arq = tmp_path / "a.xml"
    arq.write_text("<a/>", encoding="utf-8")
    assert main([str(arq)]) == 2
    assert "não é uma pasta" in capsys.readouterr().err


def test_acervo_multi_emitente_nao_mistura_skus_iguais(tmp_path):
    (tmp_path / "emitente_a.xml").write_text(
        _nota_crt3("SKU-X", documento="11111111000111"), encoding="utf-8"
    )
    (tmp_path / "emitente_b.xml").write_text(
        _nota_crt3("SKU-X", documento="22222222000122"), encoding="utf-8"
    )

    resumo = analisar(tmp_path)

    assert resumo.tem_multiplos_emitentes
    assert resumo.documentos_emitentes == ("11111111000111", "22222222000122")
    assert len(resumo.grupos) == 2


def test_relatorio_de_texto_diz_de_qual_emitente_e_cada_sku(tmp_path):
    """Separar os grupos por emitente não serve de nada se as linhas saem iguais."""
    for documento in ("11111111000111", "22222222000122"):
        (tmp_path / f"{documento}.xml").write_text(
            _nota_crt3("SKU-X", documento=documento), encoding="utf-8"
        )

    saida = formatar_texto(analisar(tmp_path))

    assert "[emitente 11111111000111]" in saida
    assert "[emitente 22222222000122]" in saida


def test_relatorio_de_texto_nao_polui_acervo_de_um_emitente_so(tmp_path):
    saida = formatar_texto(analisar(_acervo_emitente_unico(tmp_path)))
    assert "[emitente" not in saida


def test_html_ganha_coluna_de_emitente_quando_ha_mais_de_um(tmp_path):
    for documento in ("11111111000111", "22222222000122"):
        (tmp_path / f"{documento}.xml").write_text(
            _nota_crt3("SKU-X", documento=documento), encoding="utf-8"
        )

    saida = formatar_html(analisar(tmp_path))

    assert "<th>Emitente</th>" in saida
    assert "22222222000122" in saida


def test_html_de_um_emitente_so_nao_ganha_coluna_repetida(tmp_path):
    saida = formatar_html(analisar(_acervo_emitente_unico(tmp_path)))
    assert "<th>Emitente</th>" not in saida


def test_cabecalho_nao_vira_parede_com_muitos_emitentes(tmp_path):
    for i in range(9):
        documento = f"1111111100{i:04d}"
        (tmp_path / f"{documento}.xml").write_text(
            _nota_crt3("SKU-X", documento=documento), encoding="utf-8"
        )

    resumo = analisar(tmp_path)
    rotulo = rotulo_dos_emitentes(resumo)

    assert rotulo.endswith("e mais 6")
    assert rotulo.count(",") == 2


def test_comparativo_multi_emitente_nao_colapsa_sku_igual(tmp_path):
    antes = tmp_path / "antes"
    depois = tmp_path / "depois"
    antes.mkdir()
    depois.mkdir()
    for documento in ("11111111000111", "22222222000122"):
        (antes / f"{documento}.xml").write_text(
            _nota_crt3("SKU-X", documento=documento), encoding="utf-8"
        )
    (depois / "emitente_a.xml").write_text(
        _nota_crt3("SKU-X", documento="11111111000111"), encoding="utf-8"
    )

    anterior = json.loads(formatar_json(analisar(antes)))
    resultado = comparar(analisar(depois), anterior, "antes.json")

    assert resultado.corrigidos == ["22222222000122::SKU-X"]
    assert resultado.persistentes == ["11111111000111::SKU-X"]
