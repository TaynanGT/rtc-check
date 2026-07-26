# Checkout e emissão de licença

O aplicativo nunca recebe chave de API de pagamento. Ele abre somente uma URL
HTTPS configurável:

```text
RTC_CHECK_PAYMENT_PROVIDER=
RTC_CHECK_CHECKOUT_URL=
```

Sem configuração, o botão **Comprar licença** abre o formulário comercial do
GitHub e informa que a compra é assistida. Com uma URL HTTPS, a interface mostra
o nome do provedor e abre seu checkout hospedado.

## Contrato do provedor

O contrato abaixo está implementado para o Mercado Pago em
`rtc_check/servidor_vendas.py` (comando `rtc-check-vendas`), com o cliente da
API em `rtc_check/mercadopago.py`. O código é aberto; os segredos (access
token, segredo do webhook, chave privada Ed25519, SMTP) vivem só no ambiente
do servidor do vendedor. O passo a passo de ativação está em
[mercadopago.md](mercadopago.md).

O backend do vendedor deve:

1. criar checkout para o plano mensal ou anual;
2. receber webhook assinado pelo provedor;
3. validar valor, moeda, status e idempotência;
4. emitir a licença Ed25519 somente após pagamento confirmado;
5. enviar recibo e chave sem registrar dados fiscais do comprador;
6. tratar cancelamento, reembolso, renovação e expiração;
7. nunca devolver `PAYMENT_API_KEY`, `PAYMENT_WEBHOOK_SECRET` ou chave privada.

Estados mínimos: `checkout_iniciado`, `pagamento_confirmado`,
`licenca_emitida`, `pagamento_cancelado` e `reembolso_confirmado`.

O checkout automático oficial está no ar em
<https://rtc-check-vendas.onrender.com>, que é a URL padrão embutida no
aplicativo quando o ambiente não define outra. A compra assistida pelo
formulário continua existindo como alternativa.
