"""Validação de GTIN (código de barras) pelo dígito verificador GS1.

A NF-e aceita GTIN-8, 12, 13 e 14 no campo ``cEAN``/``cEANTrib``. O literal
``SEM GTIN`` é válido e significa que o produto não possui código de barras.
"""

from __future__ import annotations

SEM_GTIN = "SEM GTIN"
TAMANHOS_VALIDOS = (8, 12, 13, 14)


def digito_verificador(digitos: str) -> int:
    """Calcula o dígito verificador GS1 (mod 10) para o corpo do GTIN.

    Pesos 3 e 1 alternados, da direita para a esquerda, sem incluir o DV.
    """
    total = 0
    for posicao, caractere in enumerate(reversed(digitos)):
        peso = 3 if posicao % 2 == 0 else 1
        total += int(caractere) * peso
    return (10 - total % 10) % 10


def esta_vazio(valor: str | None) -> bool:
    """cEAN ausente ou em branco. Legítimo antes do layout 4.00."""
    return valor is None or not valor.strip()


def validar(valor: str | None) -> tuple[bool, str]:
    """Retorna ``(valido, motivo)``. Motivo fica vazio quando válido.

    Não decide sobre cEAN vazio: isso depende da versão do layout e é tratado
    em :mod:`rtc_check.rules`.
    """
    # A checagem explicita de None fica aqui, e nao delegada a esta_vazio(),
    # porque o mypy nao estreita o tipo atraves de outra funcao.
    if valor is None or not valor.strip():
        return False, "cEAN ausente (informe o GTIN ou o literal 'SEM GTIN')"

    valor = valor.strip().upper()
    if valor == SEM_GTIN:
        return True, ""

    if not valor.isdigit():
        return False, f"GTIN '{valor}' contém caracteres não numéricos"

    if len(valor) not in TAMANHOS_VALIDOS:
        return False, (
            f"GTIN '{valor}' tem {len(valor)} dígitos; "
            f"esperado {', '.join(map(str, TAMANHOS_VALIDOS))}"
        )

    esperado = digito_verificador(valor[:-1])
    if int(valor[-1]) != esperado:
        return False, (
            f"GTIN '{valor}' com dígito verificador inválido "
            f"(informado {valor[-1]}, esperado {esperado})"
        )

    return True, ""
