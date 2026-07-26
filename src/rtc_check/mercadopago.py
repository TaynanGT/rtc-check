"""Cliente mínimo da API do Mercado Pago para o backend de vendas.

Este módulo roda no servidor privado do vendedor (``servidor_vendas.py``),
nunca no aplicativo do cliente: o desktop continua recebendo somente a URL
HTTPS de checkout, conforme docs/checkout.md. Usa apenas a biblioteca padrão.

O Mercado Pago é o braço de pagamentos do ecossistema Mercado Livre: o valor
aprovado cai na conta Mercado Pago do titular, que saca para a conta bancária.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

API_MERCADO_PAGO = "https://api.mercadopago.com"
MOEDA = "BRL"


class ErroMercadoPago(Exception):
    """Falha de comunicação ou resposta inesperada da API do Mercado Pago."""


@dataclass(frozen=True)
class PlanoDeVenda:
    codigo: str
    titulo: str
    preco: float
    dias_de_licenca: int


# Preços públicos do plano Escritório (README e site). A licença cobre o
# período pago com folga de dois dias para renovar sem lacuna.
PLANOS_DE_VENDA: dict[str, PlanoDeVenda] = {
    "mensal": PlanoDeVenda("mensal", "RTC Check Escritório — 1 mês", 149.0, 33),
    "anual": PlanoDeVenda("anual", "RTC Check Escritório — 1 ano", 1490.0, 368),
}


def token_de_acesso() -> str:
    token = os.environ.get("PAYMENT_API_KEY", "").strip()
    if not token:
        raise ErroMercadoPago(
            "defina PAYMENT_API_KEY com o access token de produção do Mercado Pago"
        )
    return token


def _requisitar(metodo: str, caminho: str, corpo: dict[str, Any] | None = None) -> dict[str, Any]:
    dados = json.dumps(corpo).encode() if corpo is not None else None
    requisicao = urllib.request.Request(
        API_MERCADO_PAGO + caminho,
        data=dados,
        method=metodo,
        headers={
            "Authorization": f"Bearer {token_de_acesso()}",
            "Content-Type": "application/json",
            "X-Idempotency-Key": secrets.token_hex(16),
        },
    )
    try:
        with urllib.request.urlopen(requisicao, timeout=30) as resposta:  # noqa: S310
            carga = json.loads(resposta.read().decode())
    except urllib.error.HTTPError as erro:
        raise ErroMercadoPago(
            f"API do Mercado Pago devolveu HTTP {erro.code} em {caminho}"
        ) from erro
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as erro:
        raise ErroMercadoPago(f"falha ao falar com a API do Mercado Pago em {caminho}") from erro
    if not isinstance(carga, dict):
        raise ErroMercadoPago(f"resposta inesperada da API em {caminho}")
    return carga


def corpo_da_preferencia(plano: PlanoDeVenda, url_publica: str) -> dict[str, Any]:
    """Monta a preferência do Checkout Pro para um plano do RTC Check."""
    base = url_publica.rstrip("/")
    return {
        "items": [
            {
                "id": f"rtc-check-escritorio-{plano.codigo}",
                "title": plano.titulo,
                "quantity": 1,
                "unit_price": plano.preco,
                "currency_id": MOEDA,
            }
        ],
        "external_reference": plano.codigo,
        "metadata": {"rtc_check_plano": plano.codigo},
        "statement_descriptor": "RTCCHECK",
        "back_urls": {
            "success": f"{base}/obrigado",
            "pending": f"{base}/obrigado",
            "failure": f"{base}/",
        },
        "auto_return": "approved",
        "notification_url": f"{base}/webhook/mercadopago",
    }


def criar_preferencia(plano: PlanoDeVenda, url_publica: str) -> str:
    """Cria a preferência do Checkout Pro e devolve a URL hospedada de pagamento."""
    resposta = _requisitar(
        "POST", "/checkout/preferences", corpo_da_preferencia(plano, url_publica)
    )
    url = str(resposta.get("init_point", ""))
    if not url.startswith("https://"):
        raise ErroMercadoPago("preferência criada sem init_point utilizável")
    return url


def obter_pagamento(id_pagamento: str) -> dict[str, Any]:
    """Consulta o pagamento direto na API; o corpo do webhook nunca é confiável."""
    if not id_pagamento.isdigit():
        raise ErroMercadoPago("id de pagamento inválido")
    return _requisitar("GET", f"/v1/payments/{id_pagamento}")


def validar_assinatura_webhook(
    cabecalho_x_signature: str,
    id_do_dado: str,
    id_da_requisicao: str,
    segredo: str,
) -> bool:
    """Confere o HMAC-SHA256 do webhook conforme o manual do Mercado Pago.

    O manifesto assinado é ``id:{data.id};request-id:{x-request-id};ts:{ts};``,
    com o id em minúsculas e partes ausentes omitidas. Replay de notificação é
    inofensivo porque o pagamento é reconsultado na API e a emissão é
    idempotente por id de pagamento.
    """
    if not segredo or not id_do_dado:
        return False
    partes: dict[str, str] = {}
    for trecho in cabecalho_x_signature.split(","):
        chave, separador, valor = trecho.partition("=")
        if separador:
            partes[chave.strip()] = valor.strip()
    ts, v1 = partes.get("ts", ""), partes.get("v1", "")
    if not ts or not v1:
        return False
    manifesto = f"id:{id_do_dado.lower()};"
    if id_da_requisicao:
        manifesto += f"request-id:{id_da_requisicao};"
    manifesto += f"ts:{ts};"
    esperado = hmac.new(segredo.encode(), manifesto.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(esperado, v1)
