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
    assert item.tem_ibscbs
    assert item.tem_grupo_rtc
    assert item.cst_ibscbs == "000"
    assert item.cclass_trib == "000001"
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


def test_erro_de_leitura_vira_xml_invalido(tmp_path):
    with pytest.raises(XmlInvalido, match="não foi possível ler"):
        ler_nota(tmp_path / "arquivo_removido.xml")


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
