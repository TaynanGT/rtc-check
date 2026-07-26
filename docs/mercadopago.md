# Receber pagamentos com Mercado Pago

O código do checkout está pronto neste repositório: `rtc_check/mercadopago.py`
fala com a API e `rtc_check/servidor_vendas.py` (comando `rtc-check-vendas`)
cria o checkout hospedado, valida o webhook assinado e emite a licença Ed25519
por e-mail depois do pagamento aprovado. O que falta é o que **somente o
titular da conta** pode fazer: criar e verificar a conta, gerar credenciais e
apontar o servidor. Este guia é esse passo a passo.

Uma nota sobre nomes: o **Mercado Pago** é quem processa pagamentos no
ecossistema do Mercado Livre. O dinheiro aprovado cai na sua conta Mercado
Pago e de lá você saca para a conta bancária. Vender o RTC Check dentro do
*marketplace* do Mercado Livre é outra coisa (anúncio de produto físico ou
digital) e não é necessária para receber: o checkout hospedado do Mercado Pago
basta e funciona com Pix, cartão e boleto.

## O roteiro sem terminal e sem custo (recomendado)

Nada aqui exige programar nem pagar hospedagem: o blueprint usa o plano
**gratuito** do Render. São cliques e copiar-e-colar de credenciais — sempre
de um painel para outro painel, nunca por e-mail ou chat.

1. **Conta.** Entre em [mercadopago.com.br](https://www.mercadopago.com.br) e
   complete a verificação de identidade (e de CNPJ, se vender como empresa).
2. **Aplicação.** Em [Suas integrações](https://www.mercadopago.com.br/developers/panel/app),
   use (ou crie) uma aplicação com o produto **CheckoutPro**.
3. **Hospedagem.** Crie uma conta no [Render](https://dashboard.render.com),
   clique em **New → Blueprint**, conecte seu GitHub e escolha este
   repositório. O `render.yaml` descreve o serviço inteiro no plano gratuito,
   com URL pública automática.
4. **Access token.** No painel do Mercado Pago, em **Credenciais de
   produção**, copie o **Access Token** (`APP_USR-...`) e cole no Render como
   valor de `PAYMENT_API_KEY`. Os demais campos pedidos podem ficar com um
   valor temporário (ex.: `trocar-depois`) ou em branco.
5. **Chave de emissão.** Após o primeiro boot, abra a aba **Logs** do serviço
   no Render: o servidor gerou a chave que assina as licenças e imprimiu o
   bloco `-----BEGIN PRIVATE KEY-----`...`-----END PRIVATE KEY-----` com
   instruções. Copie o bloco inteiro para a variável
   `RTC_CHECK_CHAVE_PRIVADA_PEM` (aba **Environment**). Sem isso, o plano
   gratuito perderia a chave num reinício e as licenças vendidas ficariam
   órfãs. O log é privado da sua conta.
6. **Webhook.** No painel do Mercado Pago, em **Webhooks → Modo produção**,
   configure a URL `https://SEU-SERVICO.onrender.com/webhook/mercadopago` com
   o evento **Pagamentos**, copie a **assinatura secreta** exibida e cole no
   Render em `PAYMENT_WEBHOOK_SECRET`.
7. **E-mail (muito recomendado no plano gratuito).** Preencha no Render:
   `SMTP_HOST=smtp.gmail.com`, `SMTP_USER=seu-gmail`, `SMTP_PASS=senha de
   aplicativo` (crie em [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords),
   requer verificação em duas etapas) e `SMTP_FROM=seu-gmail`. Cada venda
   envia a chave ao comprador **com cópia oculta para você** — sem disco
   persistente, esse e-mail é o seu registro durável de cada chave vendida.
8. **Pronto.** O servidor anuncia a chave pública em
   `https://SEU-SERVICO.onrender.com/chave-publica`. Copie esse valor para
   `CHAVE_PUBLICA_PADRAO` em `src/rtc_check/edicao.py` (ou informe a URL a
   quem cuida do código) para que as instalações dos clientes reconheçam as
   licenças vendidas.

Limitações honestas do plano gratuito: o serviço hiberna sem tráfego — a
página de compra pode levar até ~1 minuto para abrir na primeira visita (o
webhook não sofre: o Mercado Pago reenvia notificações que falham) — e não há
disco persistente, papel que os passos 5 e 7 cobrem. Quando as vendas
justificarem, trocar `plan: free` por `plan: starter` (e opcionalmente voltar
um disco) elimina as duas limitações.

As seções seguintes detalham o mesmo processo para quem prefere fazer à mão em
um VPS próprio.

## 1. Conta e credenciais (ação do titular)

1. Crie ou use sua conta em [mercadopago.com.br](https://www.mercadopago.com.br)
   e complete a verificação de identidade (e de CNPJ, se for vender como
   empresa).
2. Em **Suas integrações** ([painel do desenvolvedor](https://www.mercadopago.com.br/developers/panel/app)),
   crie uma aplicação com o produto **CheckoutPro**.
3. Em **Credenciais de produção**, copie o **Access Token** (`APP_USR-...`).
   Ele é o `PAYMENT_API_KEY`. Nunca o commite; ele só existe no ambiente do
   servidor de vendas.

## 2. Chave de emissão de licenças

A licença que o comprador recebe é assinada com uma chave privada Ed25519 que
não está — e não pode estar — neste repositório. **O servidor gera essa chave
sozinho no primeiro boot** quando `RTC_CHECK_CHAVE_PRIVADA` não está definida,
grava o PEM no diretório de dados (`RTC_CHECK_VENDAS_DIR`) e anuncia a chave
pública correspondente em `GET /chave-publica`.

Copie o valor de `/chave-publica` para `CHAVE_PUBLICA_PADRAO` em
`src/rtc_check/edicao.py`: é assim que as instalações dos clientes validam as
licenças vendidas. Quem preferir gerar o par por conta própria pode apontar
`RTC_CHECK_CHAVE_PRIVADA` para um PEM Ed25519 existente; o arquivo gerado
automaticamente fica no disco persistente — faça backup dele, pois perder a
chave privada significa não conseguir emitir licenças que os aplicativos já
distribuídos aceitem.

## 3. Subir o servidor de vendas

Qualquer máquina com Python 3.11+ e HTTPS público serve: um VPS com Caddy ou
nginx na frente, ou uma plataforma que dê TLS de graça. O processo é um só:

```bash
pip install "rtc-check @ git+https://github.com/TaynanGT/rtc-check.git"

export PAYMENT_API_KEY="APP_USR-..."          # passo 1
export PAYMENT_WEBHOOK_SECRET="..."           # passo 4
export RTC_CHECK_VENDAS_URL="https://vendas.seudominio.com.br"
export RTC_CHECK_VENDAS_DIR="/var/lib/rtc-check-vendas"
# opcional: RTC_CHECK_CHAVE_PRIVADA aponta para um PEM próprio; sem ela, o
# servidor gera a chave de emissão no primeiro boot dentro do diretório acima
export SMTP_HOST="smtp.seuprovedor.com"       # envio da chave ao comprador
export SMTP_PORT=465
export SMTP_USER="vendas@seudominio.com.br"
export SMTP_PASS="..."
export SMTP_FROM="RTC Check <vendas@seudominio.com.br>"
export PORT=8080

rtc-check-vendas
```

Rotas expostas:

| Rota | Função |
|---|---|
| `GET /` | página com os botões Mensal (R$ 149) e Anual (R$ 1.490) |
| `GET /comprar/mensal` e `/comprar/anual` | cria a preferência e redireciona ao checkout do Mercado Pago |
| `POST /webhook/mercadopago` | notificação assinada; emite e envia a licença |
| `GET /obrigado` | retorno pós-pagamento |
| `GET /saude` | verificação de disponibilidade |
| `GET /chave-publica` | chave pública do emissor, para `CHAVE_PUBLICA_PADRAO` |

Cada venda (e também recusas, cancelamentos e reembolsos) fica registrada em
`vendas.jsonl` no diretório de dados, incluindo a chave emitida — é por ali
que você reenvia uma licença se o e-mail falhar. Sem SMTP configurado o
servidor não quebra: ele registra a venda e avisa no log para enviar a chave
manualmente.

## 4. Configurar o webhook (ação do titular)

No painel da aplicação, em **Webhooks → Modo produção**:

1. URL: `https://vendas.seudominio.com.br/webhook/mercadopago`
2. Evento: **Pagamentos** (`payment`).
3. Copie a **assinatura secreta** exibida — é o `PAYMENT_WEBHOOK_SECRET`.

O servidor valida o HMAC `x-signature` de cada notificação, reconsulta o
pagamento direto na API (nunca confia no corpo do webhook), confere valor,
moeda e status e é idempotente por id de pagamento. Notificação com
assinatura errada recebe 401; falha temporária de API recebe 500, o que faz o
Mercado Pago reenviar mais tarde.

## 5. Apontar o aplicativo e o site

Com o servidor no ar, o botão **Comprar licença** do desktop deixa de abrir a
compra assistida no GitHub. Defina no ambiente onde o app roda (ou no build):

```bash
RTC_CHECK_PAYMENT_PROVIDER="Mercado Pago"
RTC_CHECK_CHECKOUT_URL="https://vendas.seudominio.com.br"
```

No site (`site/index.html`), troque o link de compra assistida pela mesma URL
quando quiser divulgar o checkout direto.

## 6. Testar antes de divulgar

Use as **credenciais de teste** da mesma aplicação (outro Access Token) e os
[cartões de teste](https://www.mercadopago.com.br/developers/pt/docs/checkout-pro/additional-content/your-integrations/test/cards)
do Mercado Pago num servidor de homologação; o fluxo é idêntico. Confira:

1. `GET /comprar/mensal` redireciona ao checkout;
2. pagamento aprovado gera linha `licenca_emitida` em `vendas.jsonl`;
3. a chave chega por e-mail e ativa com `rtc-check --licenca ...`;
4. reenviar o mesmo webhook devolve `pagamento_duplicado` (nenhuma segunda
   emissão).

## Renovação, reembolso e cancelamento

- A licença mensal vale 33 dias e a anual 368: dois dias de folga para o
  comprador renovar comprando de novo pelo mesmo link. Cobrança recorrente
  automática (Assinaturas do Mercado Pago) pode ser adicionada depois, sem
  mudar o contrato do app.
- Reembolso e chargeback chegam pelo mesmo webhook e são gravados em
  `vendas.jsonl` como `reembolso_confirmado`/`pagamento_cancelado` para o seu
  acompanhamento. A chave já emitida não é revogável à distância — ela apenas
  expira no vencimento, o que é coerente com a política de gating honesto do
  projeto.

## O dinheiro

Pagamentos aprovados ficam disponíveis na sua conta Mercado Pago conforme o
prazo de liberação do meio de pagamento (Pix é imediato; cartão segue o prazo
configurado na conta, que também define a taxa). De lá, transfira para sua
conta bancária pelo app ou site do Mercado Pago. Emissão de nota fiscal de
serviço para cada venda continua sendo obrigação sua, fora do escopo desta
ferramenta.
