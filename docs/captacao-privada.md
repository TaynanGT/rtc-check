# Captação comercial privada

A landing aceita um endpoint HTTPS configurável em `site/lead-config.js`. Ele recebe
somente `email`, `empresa`, `perfil` e `plano` por `POST` JSON. O endpoint é público;
segredos, chaves de API e dados de pagamento pertencem exclusivamente ao backend.

## Antes de ativar

1. Escolha um provedor ou backend que trate dados sob sua política de privacidade.
2. Configure CORS apenas para `https://taynangt.github.io` e `https://taynangt.github.io/rtc-check/`.
3. Valide e limite todos os campos no servidor, registre apenas o necessário e defina retenção.
4. Envie confirmação por e-mail sem incluir XML, CNPJ, chaves de NF-e ou dados de pagamento.
5. Troque o valor vazio de `RTC_CHECK_LEADS_ENDPOINT` pela URL HTTPS do endpoint.

Sem endpoint configurado, o formulário continua útil: ele valida os campos e copia o
pedido para a área de transferência, mas não transmite dado algum.
