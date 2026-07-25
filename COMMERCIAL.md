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
| **Preço** | R$ 0, para sempre | R$ 390/mês | sob consulta |
| Varredura local, ilimitada | sim | sim | sim |
| Regras do corte (`RTC001` a `RTC006`) | sim | sim | sim |
| Contagem de bloqueios, alertas e SKUs | sim | sim | sim |
| Lista detalhada de SKUs | 5 primeiros | completa | completa |
| Regras de cadastro (`NCM001`, `GTIN001`) | não | sim | sim |
| Saída em JSON, CSV e HTML | não | sim | sim |
| Gravar relatório em arquivo | não | sim | sim |
| `--falhar-em-bloqueio` (CI) | não | sim | sim |
| Detalhamento por CNPJ | não | sim | sim |
| Comparativo entre execuções | não | sim | sim |
| Atualização de regras | via GitHub | pacote assinado, no dia da NT | idem |
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

Uma única nota travada num embarque costuma pagar o ano do plano Escritório. Mas o
número que importa é o seu, e ele sai da primeira varredura, que é gratuita.

## Uma palavra sobre a trava

O código é aberto, então o gating dos recursos pagos está no repositório e pode ser
removido. Isso é conhecido e não vai mudar: fechar o código custaria a auditabilidade,
que é justamente o motivo pelo qual alguém aponta uma pasta de notas fiscais para este
programa. A assinatura não vende acesso ao binário, vende regra atualizada, suporte com
prazo e direito de redistribuir.

## Contato

Abra o [formulário do plano Escritório ou licença comercial](https://github.com/TaynanGT/rtc-check/issues/new?template=comercial.md).
Ele é público: não inclua XML, CNPJ, chave de NF-e nem outros dados confidenciais. Para uma
conversa privada, use o e-mail exibido no perfil do mantenedor.
