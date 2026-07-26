# Captação comercial privada

A landing aceita um endpoint HTTPS configurável em `site/lead-config.js`. Ele recebe
somente `email`, `empresa`, `perfil`, `plano` e o consentimento opcional
`novidades` por `POST` JSON. O endpoint é público;
segredos, chaves de API e dados de pagamento pertencem exclusivamente ao backend.

## Antes de ativar

1. Escolha um provedor ou backend que trate dados sob sua política de privacidade.
2. Configure CORS apenas para `https://taynangt.github.io` e `https://taynangt.github.io/rtc-check/`.
3. Valide o corpo com `docs/lead.schema.json`, rejeite propriedades adicionais,
   aplique honeypot, limite de requisições e atraso progressivo.
4. Registre apenas o necessário, redija logs e defina retenção curta.
5. Envie confirmação por e-mail sem incluir XML, CNPJ, chaves de NF-e ou dados de pagamento.
6. Troque o valor vazio de `RTC_CHECK_LEADS_ENDPOINT` pela URL HTTPS do endpoint.

Sem endpoint configurado, o formulário não copia nem transmite os dados: ele encaminha
para o download e teste local.
