from pathlib import Path

import pytest

from rtc_check.parser import XmlInvalido, ler_nota, varrer_pasta

FIXTURES = Path(__file__).parent / "fixtures"

# Contado da pasta, nao chumbado: fixture nova nao deve quebrar teste alheio.
TOTAL_FIXTURES = len(list(FIXTURES.glob("*.xml")))


def test_le_nota_legado():
    nota = ler_nota(FIXTURES / "legado_crt3.xml")
    assert nota.chave == "35240712345678000199550010000000011000000017"
    assert nota.emitente_nome == "METALURGICA HORIZONTE LTDA"
    assert nota.crt == "3"
    assert nota.em_escopo_agosto
    assert len(nota.itens) == 2
    assert all(not item.tem_grupo_rtc for item in nota.itens)


def test_detecta_grupo_rtc_em_nota_conforme():
    nota = ler_nota(FIXTURES / "conforme_crt3.xml")
    item = nota.itens[0]
    assert item.tem_grupo_rtc
    assert item.tem_class_trib


def test_simples_nacional_fora_de_escopo():
    nota = ler_nota(FIXTURES / "simples_crt1.xml")
    assert nota.crt == "1"
    assert not nota.em_escopo_agosto


def test_campos_do_item():
    nota = ler_nota(FIXTURES / "legado_crt3.xml")
    item = nota.itens[0]
    assert item.codigo == "SKU-1001"
    assert item.ncm == "72104900"
    assert item.cfop == "5102"
    assert item.cean == "7891234567895"
    assert item.descricao == "CHAPA DE ACO GALVANIZADO 2MM"


def test_cean_vazio_vira_none():
    nota = ler_nota(FIXTURES / "cadastro_sujo_crt3.xml")
    assert nota.itens[1].cean is None


def test_xml_malformado_levanta():
    with pytest.raises(XmlInvalido, match="malformado"):
        ler_nota(FIXTURES / "malformado.xml")


def test_xml_que_nao_e_nfe_levanta():
    with pytest.raises(XmlInvalido, match="infNFe"):
        ler_nota(FIXTURES / "nao_e_nfe.xml")


def test_varredura_e_ordenada_e_deterministica():
    encontrados = varrer_pasta(FIXTURES)
    assert len(encontrados) == TOTAL_FIXTURES
    assert encontrados == sorted(encontrados)
    assert varrer_pasta(FIXTURES) == encontrados


def test_varredura_sem_recursao(tmp_path):
    (tmp_path / "raiz.xml").write_text("<a/>", encoding="utf-8")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "filho.xml").write_text("<a/>", encoding="utf-8")

    assert len(varrer_pasta(tmp_path, recursivo=False)) == 1
    assert len(varrer_pasta(tmp_path, recursivo=True)) == 2


@pytest.mark.parametrize("nome", ["a.xml", "b.XML", "c.Xml", "d.xML"])
def test_varredura_ignora_caixa_da_extensao(tmp_path, nome):
    """O portal do SEFAZ entrega ``NFe123.XML``, em caixa alta.

    Filtrando por ``*.xml``, esses arquivos sumiam da varredura no Linux sem
    erro nenhum — e um acervo lido pela metade produz um "nenhum bloqueio
    encontrado" que é pior do que um traceback.
    """
    (tmp_path / nome).write_text("<a/>", encoding="utf-8")
    assert [p.name for p in varrer_pasta(tmp_path)] == [nome]


def test_varredura_nao_duplica_em_sistema_de_arquivos_insensivel(tmp_path):
    """No Windows e no macOS o glob já é insensível: não pode contar duas vezes."""
    (tmp_path / "nota.xml").write_text("<a/>", encoding="utf-8")
    encontrados = varrer_pasta(tmp_path)
    assert len(encontrados) == len(set(encontrados)) == 1


def test_varredura_ignora_quem_nao_e_xml(tmp_path):
    for nome in ("nota.xml", "planilha.csv", "leiame.txt", "sem_extensao"):
        (tmp_path / nome).write_text("x", encoding="utf-8")
    assert [p.name for p in varrer_pasta(tmp_path)] == ["nota.xml"]


def test_arquivo_ilegivel_vira_xml_invalido_e_nao_derruba_a_varredura(tmp_path):
    """Só ``ParseError`` era capturado: qualquer ``OSError`` vazava e matava o run."""
    with pytest.raises(XmlInvalido, match="não foi possível ler"):
        ler_nota(tmp_path / "nao_existe.xml")

    with pytest.raises(XmlInvalido, match="não foi possível ler"):
        ler_nota(tmp_path)  # diretório no lugar de arquivo


def test_le_nfce_modelo_65_com_cpf_e_dEmi():
    """Três caminhos de fallback que a cobertura de linha dava como exercitados.

    ``CNPJ or CPF`` e ``dhEmi or dEmi`` cabem numa linha só, então o lado direito
    nunca rodava e mesmo assim contava como coberto.
    """
    nota = ler_nota(FIXTURES / "nfce_mod65_cpf.xml")
    assert nota.modelo == "65"
    assert nota.emitente_cnpj == "12345678909"  # veio do CPF
    assert nota.emissao == "2015-03-18"  # veio do dEmi
    assert not nota.em_escopo_agosto  # CRT=1


def test_acentuacao_sobrevive_a_encoding_iso_8859_1():
    """A maior parte do acervo real vem em ISO-8859-1, não em UTF-8.

    Funciona porque o ElementTree respeita a declaração do XML. Um refactor para
    ``Path.read_text()`` quebraria toda descrição acentuada em silêncio.
    """
    nota = ler_nota(FIXTURES / "nfce_mod65_cpf.xml")
    assert nota.emitente_nome == "ARMAZÉM SÃO JOÃO - COMÉRCIO DE ALIMENTAÇÃO"
    assert nota.itens[0].descricao == "PÃO FRANCÊS A GRANEL"


def test_det_sem_prod_e_ignorado(tmp_path):
    arq = tmp_path / "n.xml"
    arq.write_text(
        '<?xml version="1.0"?><NFe xmlns="http://www.portalfiscal.inf.br/nfe">'
        '<infNFe Id="NFe1" versao="4.00"><ide><mod>55</mod></ide>'
        "<emit><CRT>3</CRT></emit>"
        '<det nItem="1"><imposto/></det></infNFe></NFe>',
        encoding="utf-8",
    )
    assert ler_nota(arq).itens == []


def test_falta_emit_ou_ide_levanta(tmp_path):
    arq = tmp_path / "n.xml"
    arq.write_text(
        '<?xml version="1.0"?><NFe xmlns="http://www.portalfiscal.inf.br/nfe">'
        '<infNFe Id="NFe1" versao="4.00"><ide><mod>55</mod></ide></infNFe></NFe>',
        encoding="utf-8",
    )
    with pytest.raises(XmlInvalido, match="emit/ide"):
        ler_nota(arq)


def test_entidade_externa_nao_e_resolvida(tmp_path):
    """XXE: o acervo vem de terceiros, então isto precisa de trava explícita."""
    arq = tmp_path / "xxe.xml"
    arq.write_text(
        '<?xml version="1.0"?><!DOCTYPE r [<!ENTITY x SYSTEM "file:///etc/passwd">]>'
        '<NFe xmlns="http://www.portalfiscal.inf.br/nfe">'
        '<infNFe Id="NFe1" versao="4.00"><ide><mod>55</mod></ide>'
        "<emit><CRT>3</CRT><xNome>&x;</xNome></emit></infNFe></NFe>",
        encoding="utf-8",
    )
    with pytest.raises(XmlInvalido):
        ler_nota(arq)
