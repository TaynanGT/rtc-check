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

O backend privado do vendedor, fora deste repositório público, deve:

1. criar checkout para o plano mensal ou anual;
2. receber webhook assinado pelo provedor;
3. validar valor, moeda, status e idempotência;
4. emitir a licença Ed25519 somente após pagamento confirmado;
5. enviar recibo e chave sem registrar dados fiscais do comprador;
6. tratar cancelamento, reembolso, renovação e expiração;
7. nunca devolver `PAYMENT_API_KEY`, `PAYMENT_WEBHOOK_SECRET` ou chave privada.

Estados mínimos: `checkout_iniciado`, `pagamento_confirmado`,
`licenca_emitida`, `pagamento_cancelado` e `reembolso_confirmado`.

O checkout automático não está ativo enquanto o titular não escolher o provedor,
verificar a conta e aceitar seus termos. Essa é uma ação externa e irreversível
que não deve ser simulada no código.
