"""Configuração pública e substituível do checkout.

O cliente desktop recebe somente uma URL HTTPS. Chaves de API e segredos de
webhook pertencem ao backend do provedor e nunca entram no aplicativo.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlparse

URL_COMPRA_ASSISTIDA = (
    "https://github.com/TaynanGT/rtc-check/issues/new?template=comercial.md"
)
# Checkout oficial: o servidor de vendas do projeto, com pagamento pelo
# Mercado Pago. O ambiente continua podendo apontar para outra URL HTTPS.
URL_CHECKOUT_PADRAO = "https://rtc-check-vendas.onrender.com"
PROVEDOR_PADRAO = "Mercado Pago"
PRECO_MENSAL_BR = "R$ 149/mês"
PRECO_ANUAL_BR = "R$ 1.490/ano"


@dataclass(frozen=True)
class Checkout:
    provedor: str
    url: str
    automatico: bool


def carregar() -> Checkout:
    provedor = os.environ.get("RTC_CHECK_PAYMENT_PROVIDER", "").strip()[:40]
    url = os.environ.get("RTC_CHECK_CHECKOUT_URL", "").strip()
    parsed = urlparse(url)
    if parsed.scheme == "https" and parsed.netloc:
        return Checkout(
            provedor=provedor or "checkout externo",
            url=url,
            automatico=True,
        )
    return Checkout(
        provedor=provedor or PROVEDOR_PADRAO,
        url=URL_CHECKOUT_PADRAO,
        automatico=True,
    )
