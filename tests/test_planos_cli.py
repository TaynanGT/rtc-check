"""Gating na linha de comando: o que o plano gratuito faz e o que não faz."""

import json
from pathlib import Path

from rtc_check import edicao as ed
from rtc_check.cli import SAIDA_FORA_DO_PLANO, analisar, main

FIXTURES = Path(__file__).parent / "fixtures"


def _acervo(tmp_path, skus=("A", "B", "C", "D", "E", "F", "G")):
    tmp_path.mkdir(parents=True, exist_ok=True)
    for sku in skus:
        (tmp_path / f"{sku}.xml").write_text(
            f"""<?xml version="1.0" encoding="UTF-8"?>
<NFe xmlns="http://www.portalfiscal.inf.br/nfe"><infNFe Id="NFe1" versao="4.00">
<ide><mod>55</mod><nNF>1</nNF></ide>
<emit><CNPJ>1111</CNPJ><xNome>ACME</xNome><CRT>3</CRT></emit>
<det nItem="1"><prod><cProd>SKU-{sku}</cProd><cEAN>SEM GTIN</cEAN>
<xProd>PRODUTO {sku}</xProd><NCM>72104900</NCM><CFOP>5102</CFOP></prod></det>
</infNFe></NFe>""",
            encoding="utf-8",
        )
    return tmp_path


# --- plano gratuito ---------------------------------------------------------


def test_varredura_em_texto_funciona_sem_licenca(tmp_path, capsys):
    assert main([str(_acervo(tmp_path))]) == 0
    saida = capsys.readouterr().out
    assert "SKUs a corrigir" in saida
    assert "Bloqueios" in saida


def test_relatorio_gratuito_convida_para_o_teste(tmp_path, capsys):
    main([str(_acervo(tmp_path))])
    saida = capsys.readouterr().out
    assert "Plano Comunidade" in saida
    assert "--iniciar-teste" in saida


def test_relatorio_gratuito_corta_a_lista_de_skus(tmp_path, capsys):
    main([str(_acervo(tmp_path))])
    saida = capsys.readouterr().out
    assert saida.count("PRODUTO ") == ed.LIMITE_GRATUITO_DE_SKUS
    assert f"e mais {7 - ed.LIMITE_GRATUITO_DE_SKUS} SKU(s)" in saida


def test_formatos_de_exportacao_pedem_plano(tmp_path, capsys):
    pasta = str(_acervo(tmp_path))
    for formato in ("json", "csv", "html"):
        assert main([pasta, "-f", formato]) == SAIDA_FORA_DO_PLANO
        assert "faz parte do plano" in capsys.readouterr().err


def test_gravar_em_arquivo_pede_plano(tmp_path):
    destino = tmp_path / "r.txt"
    assert main([str(_acervo(tmp_path)), "-o", str(destino)]) == SAIDA_FORA_DO_PLANO
    assert not destino.exists()


def test_portao_de_ci_pede_plano(tmp_path):
    assert main([str(_acervo(tmp_path)), "--falhar-em-bloqueio"]) == SAIDA_FORA_DO_PLANO


def test_por_cnpj_e_comparar_pedem_plano(tmp_path):
    pasta = str(_acervo(tmp_path))
    assert main([pasta, "--por-cnpj"]) == SAIDA_FORA_DO_PLANO
    assert main([pasta, "--comparar", "x.json"]) == SAIDA_FORA_DO_PLANO


def test_regras_de_cadastro_ficam_fora_do_gratuito(tmp_path, capsys):
    """NCM inválido não aparece sem plano; RTC001 aparece para todo mundo."""
    (tmp_path / "n.xml").write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<NFe xmlns="http://www.portalfiscal.inf.br/nfe"><infNFe Id="NFe1" versao="4.00">
<ide><mod>55</mod><nNF>1</nNF></ide>
<emit><CNPJ>1</CNPJ><xNome>T</xNome><CRT>3</CRT></emit>
<det nItem="1"><prod><cProd>SKU-N</cProd><cEAN>SEM GTIN</cEAN>
<xProd>P</xProd><NCM>123</NCM><CFOP>5102</CFOP></prod></det>
</infNFe></NFe>""",
        encoding="utf-8",
    )
    main([str(tmp_path)])
    saida = capsys.readouterr().out
    assert "RTC001" in saida
    assert "NCM001" not in saida


# --- plano pago -------------------------------------------------------------


def test_licenca_libera_a_exportacao(tmp_path, licenciado, capsys):
    assert main([str(_acervo(tmp_path)), "-f", "json"]) == 0
    dados = json.loads(capsys.readouterr().out)
    assert dados["skus_a_corrigir"] == 7


def test_licenca_mostra_a_lista_inteira(tmp_path, licenciado, capsys):
    main([str(_acervo(tmp_path))])
    saida = capsys.readouterr().out
    assert saida.count("PRODUTO ") == 7
    assert "Plano Comunidade" not in saida


def test_por_cnpj_quebra_por_emitente(tmp_path, licenciado, capsys):
    assert main([str(_acervo(tmp_path)), "--por-cnpj"]) == 0
    saida = capsys.readouterr().out
    assert "Por emitente" in saida
    assert "ACME" in saida


def test_por_cnpj_no_json(tmp_path, licenciado, capsys):
    main([str(_acervo(tmp_path)), "-f", "json", "--por-cnpj"])
    emitentes = json.loads(capsys.readouterr().out)["emitentes"]
    assert emitentes[0]["cnpj"] == "1111"
    assert emitentes[0]["skus_a_corrigir"] == 7


def test_comparativo_aponta_o_que_foi_corrigido(tmp_path, licenciado, capsys):
    antes = _acervo(tmp_path / "antes")
    anterior = tmp_path / "anterior.json"
    main([str(antes), "-f", "json", "-o", str(anterior)])
    capsys.readouterr()

    depois = _acervo(tmp_path / "depois", skus=("A", "B", "Z"))
    assert main([str(depois), "--comparar", str(anterior)]) == 0
    saida = capsys.readouterr().out
    assert "Comparativo com anterior.json" in saida
    assert "SKUs corrigidos .. 5" in saida  # C, D, E, F, G sumiram
    assert "SKUs novos ....... 1" in saida  # SKU-Z apareceu


def test_comparativo_com_arquivo_que_nao_e_relatorio(tmp_path, licenciado, capsys):
    ruim = tmp_path / "ruim.json"
    ruim.write_text('{"qualquer": "coisa"}', encoding="utf-8")
    assert main([str(_acervo(tmp_path)), "--comparar", str(ruim)]) == 2
    assert "não parece um relatório do RTC Check" in capsys.readouterr().err


def test_analisar_sem_filtro_de_regras_roda_tudo():
    """A biblioteca continua completa: o gating é da CLI, não do motor."""
    resumo = analisar(FIXTURES)
    codigos = {c for g in resumo.grupos for c in g.codigos}
    assert "NCM001" in codigos


# --- comandos de plano ------------------------------------------------------


def test_plano_mostra_o_que_esta_liberado(capsys):
    assert main(["--plano"]) == 0
    saida = capsys.readouterr().out
    assert "plano Comunidade" in saida
    assert "Fora do plano:" in saida


def test_diagnostico_nao_expoe_caminhos_ou_documentos(capsys):
    assert main(["--diagnostico"]) == 0
    dados = json.loads(capsys.readouterr().out)
    assert dados["produto"] == "RTC Check"
    assert dados["privacidade"]["telemetria"] is False
    assert dados["limites"]["xmls_por_lote"] == 20_000
    assert "CNPJ" not in json.dumps(dados)


def test_iniciar_teste_libera_tudo(tmp_path, capsys):
    assert main(["--iniciar-teste"]) == 0
    assert "teste grátis liberado" in capsys.readouterr().out
    assert main([str(_acervo(tmp_path)), "-f", "csv"]) == 0


def test_iniciar_teste_duas_vezes_falha(capsys):
    assert main(["--iniciar-teste"]) == 0
    assert main(["--iniciar-teste"]) == 2
    assert "já está ativo" in capsys.readouterr().err


def test_ativar_licenca_guarda_a_chave(capsys):
    from datetime import date, timedelta

    chave = ed.gerar_chave(
        ed.Plano.ESCRITORIO, date.today() + timedelta(days=10), "Empresa X"
    )
    assert main(["--licenca", chave]) == 0
    assert "Escritório" in capsys.readouterr().out
    assert ed.resolver().plano is ed.Plano.ESCRITORIO


def test_ativar_licenca_invalida_falha(capsys):
    assert main(["--licenca", "RTC1-NADA-VER"]) == 2
    assert "recusada" in capsys.readouterr().err


def test_sem_pasta_e_erro_de_uso(capsys):
    assert main([]) == 2
    assert "informe a pasta" in capsys.readouterr().err


def test_csv_gravado_com_bom_para_o_excel(tmp_path, licenciado):
    destino = tmp_path / "fila.csv"
    assert main([str(_acervo(tmp_path)), "-f", "csv", "-o", str(destino)]) == 0
    assert destino.read_bytes().startswith(b"\xef\xbb\xbf")


def test_celula_de_formula_e_neutralizada():
    from rtc_check.report import _celula_segura

    assert _celula_segura('=HYPERLINK("http://x")').startswith("'")
    assert _celula_segura("+55 11").startswith("'")
    assert _celula_segura("CAFÉ TORRADO") == "CAFÉ TORRADO"


def test_portao_de_ci_sem_nenhum_xml_falha_com_codigo_2(tmp_path, licenciado, capsys):
    vazia = tmp_path / "sem-xmls"
    vazia.mkdir()
    assert main([str(vazia), "--falhar-em-bloqueio"]) == 2
    assert "nenhum XML analisado" in capsys.readouterr().err


def test_comparativo_com_arquivo_inexistente_falha_antes_da_varredura(
    tmp_path, licenciado, capsys
):
    assert main([str(_acervo(tmp_path)), "--comparar", str(tmp_path / "x.json")]) == 2
    assert "não consegui ler" in capsys.readouterr().err


def test_licenca_junto_da_varredura_fica_gravada(tmp_path, capsys):
    from datetime import date, timedelta

    chave = ed.gerar_chave(
        ed.Plano.ESCRITORIO, date.today() + timedelta(days=30), "Cliente CLI"
    )
    assert main([str(_acervo(tmp_path)), "--licenca", chave]) == 0
    assert "ativada e gravada" in capsys.readouterr().err
    # Sem argumento nenhum, a próxima execução já enxerga o plano pago.
    assert ed.resolver().plano is ed.Plano.ESCRITORIO
