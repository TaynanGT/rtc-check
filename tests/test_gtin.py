import pytest

from rtc_check import gtin


@pytest.mark.parametrize(
    "valor",
    [
        "7891234567895",  # GTIN-13 válido
        "SEM GTIN",
        "sem gtin",  # normalizado para maiúsculas
        "  SEM GTIN  ",
    ],
)
def test_aceita_validos(valor):
    valido, motivo = gtin.validar(valor)
    assert valido, motivo


@pytest.mark.parametrize(
    ("valor", "trecho_do_motivo"),
    [
        ("7891234567890", "dígito verificador"),
        ("789123456789X", "não numéricos"),
        ("12345", "dígitos"),
        ("", "ausente"),
        (None, "ausente"),
    ],
)
def test_rejeita_invalidos(valor, trecho_do_motivo):
    valido, motivo = gtin.validar(valor)
    assert not valido
    assert trecho_do_motivo in motivo


def test_digito_verificador_conhecido():
    # Corpo de um GTIN-13 cujo DV publicado pela GS1 é 5.
    assert gtin.digito_verificador("789123456789") == 5


def test_digito_verificador_gtin8():
    corpo = "9638507"
    dv = gtin.digito_verificador(corpo)
    assert gtin.validar(corpo + str(dv))[0]


@pytest.mark.parametrize("tamanho", gtin.TAMANHOS_VALIDOS)
def test_todos_os_tamanhos_aceitos_fazem_ida_e_volta(tamanho):
    """``TAMANHOS_VALIDOS`` tem quatro entradas; só 8 e 13 eram exercitadas."""
    corpo = "".join(str((i * 7 + 3) % 10) for i in range(tamanho - 1))
    valido, motivo = gtin.validar(corpo + str(gtin.digito_verificador(corpo)))
    assert valido, motivo


@pytest.mark.parametrize("tamanho", gtin.TAMANHOS_VALIDOS)
def test_dv_errado_e_recusado_em_todos_os_tamanhos(tamanho):
    corpo = "".join(str((i * 7 + 3) % 10) for i in range(tamanho - 1))
    dv_errado = (gtin.digito_verificador(corpo) + 1) % 10
    valido, motivo = gtin.validar(corpo + str(dv_errado))
    assert not valido
    assert "dígito verificador" in motivo


@pytest.mark.parametrize("tamanho", [7, 9, 11, 15])
def test_tamanhos_fora_da_tabela_sao_recusados(tamanho):
    valido, motivo = gtin.validar("1" * tamanho)
    assert not valido
    assert "dígitos" in motivo


@pytest.mark.parametrize(
    ("valor", "vazio"),
    [(None, True), ("", True), ("   ", True), ("\t", True), ("0", False)],
)
def test_esta_vazio(valor, vazio):
    assert gtin.esta_vazio(valor) is vazio
