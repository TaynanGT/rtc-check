# Licença comercial e planos

Duas coisas diferentes moram neste arquivo, e vale separar antes:

- **A licença do código** é AGPL-3.0-or-later. Rodar internamente na sua empresa,
  inclusive para fins comerciais, está liberado e não custa nada.
- **Os planos** decidem quais recursos da ferramenta estão liberados na sua instalação.
  A varredura e o relatório de texto são gratuitos para sempre; exportação e automação
  são pagas, com 14 dias de teste grátis.

Você precisa de **licença comercial** (plano Plataforma) em dois casos:

- quer embarcar o RTC Check num produto seu de código fechado;
- quer oferecê-lo como serviço a terceiros sem publicar suas modificações.

## Planos

| | Comunidade | Escritório | Plataforma |
|---|---|---|---|
| **Preço** | R$ 0, para sempre | R$ 149/mês ou R$ 1.490/ano | sob consulta |
| Interface local para Windows | sim | sim | sim |
| Varredura local, ilimitada | sim | sim | sim |
| Regras do corte (`RTC001` a `RTC007`) | sim | sim | sim |
| Contagem de bloqueios, alertas e SKUs | sim | sim | sim |
| Lista detalhada de SKUs | 5 primeiros | completa | completa |
| Regras de cadastro (`NCM001`, `GTIN001`) | não | sim | sim |
| Saída em JSON, CSV e HTML | não | sim | sim |
| Gravar relatório em arquivo | não | sim | sim |
| `--falhar-em-bloqueio` (CI) | não | sim | sim |
| Detalhamento por CNPJ | não | sim | sim |
| Comparativo entre execuções | não | sim | sim |
| Atualização de regras | via GitHub | atualização prioritária e versionada | idem |
| Suporte | issues públicas | e-mail, 1 dia útil | contrato |
| Licença para redistribuir | não | não | sim |

Teste tudo por 14 dias, sem cadastro e sem cartão:

```bash
rtc-check --iniciar-teste
```

Ativação, variáveis de ambiente e emissão de chaves: [docs/planos.md](docs/planos.md).

## O que exatamente se paga

O plano gratuito responde à pergunta com prazo: *meu padrão atual tem risco de
rejeição em agosto, e em quantos produtos?* Isso vale para todo mundo, do MEI com
trinta notas ao grupo com quatro mil.

O que se paga é o trabalho que vem depois da resposta:

- **Entregar para quem corrige.** CSV para o time de cadastro, HTML para a diretoria,
  JSON para o ERP. É a diferença entre saber do problema e distribuir o problema.
- **Não depender de ninguém lembrar.** `--falhar-em-bloqueio` no pipeline transforma a
  conferência em regra, não em rotina de alguém.
- **Acompanhar a fila andar.** `--comparar` mostra o que foi corrigido, o que apareceu e
  o que continua parado entre duas varreduras.
- **Tempo.** A NT 2025.002 já teve mais de trinta revisões. Cada uma pode mudar campo,
  regra de validação ou prazo. Uma varredura é foto; a obrigação é filme.

## Cálculo de retorno

Preencha com os seus números, porque não invento os seus:

```
notas rejeitadas por dia × horas para reprocessar cada uma × custo/hora
+ valor do faturamento parado esperando autorização
```

Não há promessa de retorno. Compare o valor do plano com o custo observado de
reprocessamento, faturamento parado e horas de cadastro. O número que importa é o
seu, e a primeira varredura gratuita ajuda a estimá-lo.

## Uma palavra sobre a trava

O código é aberto, então o gating dos recursos pagos está no repositório e pode ser
removido. Isso é conhecido e não vai mudar: fechar o código custaria a auditabilidade,
que é justamente o motivo pelo qual alguém aponta uma pasta de notas fiscais para este
programa. A assinatura não vende acesso ao binário: vende priorização de atualizações
após revisão técnica, suporte com prazo e direito de redistribuir.

## Contato

Use a [captação comercial privada](https://taynangt.github.io/rtc-check/#contato) para informar
somente e-mail corporativo, perfil e interesse. Nunca envie XML, CNPJ, chave de NF-e,
credenciais ou dados de pagamento.

O checkout com Mercado Pago está implementado e no ar
([docs/mercadopago.md](docs/mercadopago.md)): o servidor `rtc-check-vendas`, em
<https://rtc-check-vendas.onrender.com>, cria o checkout hospedado (Pix, cartão ou
boleto), valida o webhook assinado e emite a licença após o pagamento confirmado.
Essa é a URL padrão da instalação; `RTC_CHECK_CHECKOUT_URL` (com
`RTC_CHECK_CHECKOUT_ALLOWED_HOSTS`) pode apontar para outro checkout HTTPS.
Nenhuma credencial fica no repositório, e o pacote local nunca precisa de
credenciais de pagamento para ativar o teste.
