# Planos, licença e teste grátis

Como o RTC Check decide o que está liberado numa execução, e como ativar o que você
comprou. Se você só quer identificar se o padrão atual tem risco de rejeição em
agosto, nada disso é necessário: `rtc-check ./xmls` responde de graça e para sempre.

## As quatro edições

| Edição | Como se chega nela |
|---|---|
| **Comunidade** | padrão, sem configurar nada |
| **Teste grátis** | `rtc-check --iniciar-teste`, 14 dias, uma vez por máquina |
| **Escritório** | chave de licença |
| **Plataforma** | chave de licença, acrescenta o direito de redistribuir |

Teste grátis e Escritório liberam exatamente os mesmos recursos técnicos. O que a
Plataforma acrescenta é contratual, não é código.

## O que cada plano libera

Rode `rtc-check --plano` para ver a lista na sua instalação. Em resumo:

| Recurso | Comunidade | Pagos |
|---|---|---|
| Varredura local ilimitada | sim | sim |
| Relatório de texto, contagens completas | sim | sim |
| Regras `RTC001` a `RTC005` | sim | sim |
| Lista detalhada de SKUs | 5 primeiros | completa |
| Regras `NCM001` e `GTIN001` | não | sim |
| `--formato json`, `csv`, `html` | não | sim |
| `--saida` | não | sim |
| `--falhar-em-bloqueio` | não | sim |
| `--por-cnpj` | não | sim |
| `--comparar` | não | sim |

Pedir um recurso fora do plano não quebra a varredura: o comando sai com código **3** e
mostra como liberar. O que está fora do plano nunca é executado pela metade nem gravado
em arquivo parcial.

## Ativar o teste grátis

```bash
rtc-check --iniciar-teste
```

Grava `teste.json` no diretório de configuração com a data de início e a de vencimento.
Não há cadastro, e-mail, cartão nem chamada de rede: o teste é uma decisão local.

Uma vez por máquina. Depois de vencer, a instalação volta para o plano Comunidade com um
aviso, e um novo `--iniciar-teste` é recusado.

## Ativar uma chave

```bash
rtc-check --licenca RTC1-XXXXXXXX-YYYYYYYY
```

Confere a assinatura e o vencimento e guarda a chave no diretório de configuração. As
próximas execuções não precisam mais do argumento.

Para usar a chave só numa execução, passe junto do comando:

```bash
rtc-check ./xmls --licenca RTC1-... --formato csv --saida skus.csv
```

Em CI, prefira a variável de ambiente e um secret do runner:

```yaml
- run: rtc-check ./xmls --falhar-em-bloqueio
  env:
    RTC_CHECK_LICENCA: ${{ secrets.RTC_CHECK_LICENCA }}
```

Chave inválida, adulterada ou vencida **não derruba a execução**. O comando avisa no
stderr e segue no plano Comunidade, porque uma varredura de prontidão a nove dias do
corte vale mais do que a cobrança.

## Onde ficam os arquivos

| Sistema | Diretório |
|---|---|
| Linux e macOS | `$XDG_CONFIG_HOME/rtc-check`, ou `~/.config/rtc-check` |
| Windows | `%APPDATA%\rtc-check` |

Dois arquivos, ambos em texto: `licenca.txt` e `teste.json`. Apagar o diretório devolve a
instalação ao plano Comunidade.

## Variáveis de ambiente

| Variável | Para que serve |
|---|---|
| `RTC_CHECK_LICENCA` | chave de licença, útil em CI e contêiner |
| `RTC_CHECK_HOME` | força o diretório de configuração (testes, imagens efêmeras) |
| `RTC_CHECK_CHAVE_VERIFICACAO` | segredo usado para assinar e conferir as chaves |

## Emitir chaves (para quem vende)

```python
from datetime import date
from rtc_check.edicao import Plano, gerar_chave

print(gerar_chave(Plano.ESCRITORIO, date(2027, 7, 31), "Loja do Zé Ltda"))
```

A chave carrega plano, vencimento e titular em base32, assinados com HMAC-SHA256. O
segredo padrão é público, porque o repositório é público: quem distribui build oficial
define `RTC_CHECK_CHAVE_VERIFICACAO` no ambiente de build, e aí chaves forjadas com o
segredo público não abrem a instalação oficial.

## Por que o gating é honesto sobre si mesmo

O RTC Check é AGPL. O código do `edicao.py` está no repositório e qualquer pessoa
consegue remover a verificação em dez minutos. Isso é conhecido e não vai mudar.

A trava existe para deixar o limite do plano explícito e evitar compartilhamento casual
de chave, não para ser DRM. O que a assinatura entrega é a regra atualizada no dia em que
a NT sai, suporte com prazo e o direito de redistribuir — nada disso um patch local
resolve. Fechar o código para proteger a cobrança custaria a única coisa que faz alguém
confiar uma pasta de notas fiscais a este programa: dá para ler o que ele faz.
