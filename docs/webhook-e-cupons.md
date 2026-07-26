# Contratos externos: webhook e cupons

Este documento deixa prontos os artefatos que dependem do provedor escolhido.
O aplicativo local não faz chamadas de pagamento nem envia XMLs.

## Webhook

O backend privado pode receber eventos do checkout em `POST /v1/rtc-check/events`
com `Content-Type: application/json`, `X-RTC-Timestamp` e
`X-RTC-Signature: sha256=<hex>`. A assinatura é HMAC-SHA256 do texto
`<timestamp>.<corpo-UTF8>` e o servidor deve rejeitar timestamps fora de cinco
minutos e `event_id` já processado.

Eventos mínimos:

- `checkout_iniciado`
- `pagamento_confirmado`
- `licenca_emitida`
- `pagamento_cancelado`
- `reembolso_confirmado`

O formato do corpo está em [webhook-event.schema.json](webhook-event.schema.json).
O receptor deve responder `204` somente depois de persistir o evento de forma
idempotente; falhas temporárias devem retornar `5xx` para permitir retry. Nunca
aceite XML, chave privada, API key ou dados de cartão nesse contrato.

## Cupons

Cupons são uma regra do checkout, não uma permissão embutida na licença. Antes de
ativar um código real, o responsável financeiro precisa definir: validade,
quantidade, planos elegíveis, moeda, percentual ou valor fixo, cumulatividade,
cancelamento e tratamento tributário. O backend deve registrar apenas o código
normalizado e o resultado da validação, nunca dados de cartão.

Casos mínimos para o sandbox do provedor:

1. código válido no plano elegível;
2. código expirado;
3. código esgotado;
4. plano não elegível;
5. código inválido sem revelar se outro código existe;
6. reembolso e renovação sem reaplicar desconto indevido.

Até existir provedor, conta e regra comercial aprovados, a interface permanece
na compra assistida e não exibe cupom fictício.
