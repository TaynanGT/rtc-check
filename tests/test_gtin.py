import pytest

from rtc_check import gtin


@pytest.mark.parametrize(
    "valor",
    [
        "7891234567895",  # GTIN-13 válido
        "SEM GTIN",
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
        ("sem gtin", "caixa errada"),
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
