# RTC Check

[![CI](https://github.com/TaynanGT/rtc-check/actions/workflows/ci.yml/badge.svg)](https://github.com/TaynanGT/rtc-check/actions/workflows/ci.yml)
[![Licença: AGPL v3](https://img.shields.io/badge/licen%C3%A7a-AGPL--3.0-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%20a%203.14-blue.svg)](pyproject.toml)

**[Página do projeto](https://taynangt.github.io/rtc-check/)** · **[Planos](#planos)** ·
**[English](README.en.md)**

**Descubra hoje quais produtos mantêm um padrão de XML com risco de rejeição
a partir de 3 de agosto — com uma interface visual e sem enviar a nota fiscal
para a nuvem.**

A partir de **03/08/2026**, a UB12-10 passa a rejeitar a NF-e de empresa no
Regime Normal (CRT=3) sem o grupo `IBSCBS`, quando a regra for aplicável.

O problema prático não é entender a regra. É saber **quais dos seus milhares de produtos
estão fora**. O RTC Check varre o acervo de XML que você já tem no disco e devolve a lista
de SKUs que precisam de ação, agrupada por produto e ordenada por impacto.

## Referência normativa da análise

Esta versão registra em todo relatório as referências usadas: **Nota Técnica
2025.002-RTC v1.50** para as regras e **Informe Técnico 2025.002 v1.60** para a
tabela CST/cClassTrib, com corte monitorado em 03/08/2026 para CRT=3. As fontes e
o processo de atualização estão em [docs/normativa-rtc.md](docs/normativa-rtc.md).

```
  RTC Check | prontidão para a Reforma Tributária
  ----------------------------------------------------
  Corte da obrigatoriedade (CRT=3): 03/08/2026  (9 dias)

  XMLs lidos ............... 4127
  Notas em escopo (CRT=3) .. 3980
  Itens analisados ......... 21544

  Bloqueios ................ 8102
  Alertas .................. 341
  SKUs a corrigir .......... 214
```

214 itens de trabalho, não 8.102. Você corrige o cadastro do produto uma vez.

## Roda na sua máquina. Ponto.

Nenhum XML sai do seu computador. Sem conta, servidor externo ou telemetria. A interface
visual usa um servidor temporário restrito a `127.0.0.1`; os uploads do navegador são
processados no próprio PC e apagados ao terminar a análise. O runtime usa `defusedxml`
para bloquear construções XML perigosas e `cryptography` para verificar licenças
Ed25519. O código é aberto para que esse fluxo seja auditável.

A varredura e o relatório acima são **gratuitos para sempre e sem cadastro**: qualquer
pessoa identifica padrões do acervo com risco de rejeição pela interface ou pelo terminal.
Exportar, automatizar e comparar execuções fazem parte dos planos pagos, com
[14 dias de teste grátis](#planos) liberados por um comando local.

## Instalação

### Windows, sem Python

Baixe `RTC-Check-Windows-*.zip` na
[release mais recente](https://github.com/TaynanGT/rtc-check/releases/latest),
extraia e abra `RTC-Check.exe`. O navegador abrirá a interface local. O pacote inclui
um SHA-256 para conferência; enquanto não houver assinatura Authenticode, o Windows
pode exibir o SmartScreen.

### Python, Windows, macOS ou Linux

Ainda não está no PyPI ([falta um passo que só o dono da conta faz](docs/publicar-no-pypi.md)).

```bash
pip install "rtc-check @ git+https://github.com/TaynanGT/rtc-check.git"
```

Ou rode sem instalar nada de forma permanente:

```bash
uvx --from git+https://github.com/TaynanGT/rtc-check.git rtc-check ./xmls
```

Em produção, prefira fixar uma versão a acompanhar a `main`: acrescente a tag da
release à URL, como em `...rtc-check.git@v0.3.0`. As tags disponíveis estão em
[releases](https://github.com/TaynanGT/rtc-check/releases).

Requer Python 3.11 ou superior. Testado em Windows, Linux e macOS, do 3.11 ao 3.14.

## Interface visual

```bash
rtc-check --app
```

Na interface, selecione XMLs ou um ZIP, veja a fila priorizada, filtre bloqueios,
ative o teste, personalize a marca e exporte CSV, JSON ou um relatório pronto para
impressão/PDF. O botão **Encerrar** finaliza o servidor e remove os resultados em memória.

## Uso

```bash
rtc-check ./pasta-com-xmls
```

É isso que o plano gratuito faz, e é o suficiente para saber onde você está. Os
comandos abaixo fazem parte dos planos pagos; para experimentar todos por 14 dias:

```bash
rtc-check --iniciar-teste
```

Relatório em HTML para mandar ao contador ou à diretoria:

```bash
rtc-check ./xmls --formato html --saida prontidao.html
```

Planilha para o time de cadastro trabalhar:

```bash
rtc-check ./xmls --formato csv --saida skus.csv
```

Dentro de um pipeline, falhando o build se houver bloqueio:

```bash
rtc-check ./xmls --falhar-em-bloqueio
```

Quantos bloqueios cada empresa do grupo tem:

```bash
rtc-check ./xmls --por-cnpj
```

E, depois que o time mexeu no cadastro, o que de fato andou:

```bash
rtc-check ./xmls --comparar prontidao-da-semana-passada.json
```

| Opção | O que faz | Plano |
|---|---|---|
| `-f, --formato` | `texto` (padrão), `json`, `csv`, `html` | pago, exceto `texto` |
| `-o, --saida` | grava em arquivo em vez da tela | pago |
| `--sem-recursao` | não entra em subpastas | gratuito |
| `--falhar-em-bloqueio` | sai com código 1 se houver bloqueios | pago |
| `--por-cnpj` | quebra o resultado por emitente | pago |
| `--comparar` | diferença para um relatório JSON anterior | pago |
| `--iniciar-teste` | libera 14 dias de teste nesta máquina | gratuito |
| `--licenca` | ativa uma chave | gratuito |
| `--plano` | mostra a edição em uso e o que está liberado | gratuito |

Códigos de saída: `0` tudo certo, `1` há bloqueio (com `--falhar-em-bloqueio`),
`2` erro de uso, `3` recurso fora do plano em uso.

## Planos

| | Comunidade | Escritório | Plataforma |
|---|---|---|---|
| **Preço** | R$ 0, para sempre | R$ 149/mês ou R$ 1.490/ano | sob consulta |
| Varredura local ilimitada | sim | sim | sim |
| Regras do corte (`RTC001` a `RTC006`) | sim | sim | sim |
| Contagem de bloqueios e SKUs | sim | sim | sim |
| Lista completa de SKUs | 5 primeiros | completa | completa |
| Regras de cadastro (`NCM001`, `GTIN001`) | não | sim | sim |
| Exportar JSON, CSV e HTML | não | sim | sim |
| Gravar em arquivo, portão de CI | não | sim | sim |
| Quebra por CNPJ, comparativo | não | sim | sim |
| Atualização de regras | via GitHub | atualização prioritária e versionada | idem |
| Suporte | issues públicas | e-mail, 1 dia útil | contrato |
| Licença para redistribuir | não | não | sim |

O teste grátis de 14 dias libera tudo da coluna Escritório, sem cadastro, sem cartão
e sem rede: `rtc-check --iniciar-teste` grava um arquivo local e pronto. Detalhes de
ativação, variáveis de ambiente e emissão de chaves em [docs/planos.md](docs/planos.md).

O plano gratuito não é isca. Ele responde inteira a pergunta que fez você chegar aqui,
que é *"meu padrão atual tem risco de rejeição em agosto?"*. O que se paga é o
trabalho depois da resposta: exportar para quem vai corrigir, travar o pipeline,
acompanhar a fila semana a semana e receber atualizações priorizadas depois da revisão
técnica de cada NT.

## Vários emitentes sem colisão de SKU

O agrupamento usa documento do emitente + SKU, então códigos iguais de empresas
diferentes nunca são consolidados. O detalhamento por CNPJ no relatório está
disponível no plano Escritório com `--por-cnpj`.

## O que ele verifica

| Código | Severidade | Verificação | Plano |
|---|---|---|---|
| `RTC001` | bloqueio | Grupo pai `IBSCBS` ausente quando exigido pela UB12-10 | gratuito |
| `RTC002` | bloqueio | `IBSCBS` presente, mas sem `cClassTrib` | gratuito |
| `RTC003` | bloqueio | CST do IBS/CBS ausente ou inexistente na tabela oficial | gratuito |
| `RTC004` | bloqueio | CST exige `gIBSCBS`, mas o grupo não foi informado | gratuito |
| `RTC005` | bloqueio | CST proíbe `gIBSCBS`, mas o grupo foi informado | gratuito |
| `RTC006` | bloqueio | `cClassTrib` inexistente ou não vigente para NF-e na tabela oficial | gratuito |
| `NCM001` | bloqueio | NCM ausente ou fora do formato de 8 dígitos | pago |
| `GTIN001` | alerta | GTIN com dígito verificador inválido ou malformado. `cEAN` vazio só alerta em layout 4.00 ou superior | pago |

As seis regras do corte de agosto são gratuitas, de propósito: elas respondem à
pergunta que tem prazo. `NCM001` e `GTIN001` são higiene de cadastro, valem o ano
inteiro e não têm data marcada.

Notas de emitentes no Simples Nacional (CRT=1 e 2) não geram bloqueio de RTC. A transição
delas segue regra própria e não cai no corte de agosto.

A `RTC001` respeita as exceções oficiais para devolução/complementar que referencia
NF-e anterior a 2026 e para `cProdANP` presente na tabela de combustíveis monofásicos.
Como a entrada é um acervo histórico, “bloqueio” significa que o padrão encontrado
causará rejeição se continuar numa emissão sujeita à regra após o corte.

O `cEAN` vazio é tratado conforme a versão do layout da nota. O literal `SEM GTIN` só
existe a partir do 4.00 (NT 2016.002): em notas antigas, no 2.00 ou 3.xx, campo vazio
era a forma correta de declarar produto sem código de barras, e cobrar o literal ali
seria falso positivo.

## O que ele *não* é

Não é um validador de schema. O RTC Check confere **regras selecionadas de
presença, formato e compatibilidade com o CST**. Ele não substitui o
[validador oficial do SEFAZ-RS](https://dfe-portal.svrs.rs.gov.br/Cff/ValidadorRtcNfe),
que é a fonte de verdade para conformidade estrutural, e valida uma nota por vez.

Os dois se complementam: use o RTC Check para descobrir *onde* está o problema no seu
acervo inteiro, e o validador oficial para confirmar a nota corrigida antes de emitir.

## Desenvolvimento

```bash
git clone https://github.com/TaynanGT/rtc-check && cd rtc-check
uv venv && uv pip install -e ".[dev]"
uv run pytest          # testes
uv run ruff check .    # lint
uv run mypy            # tipos
```

## Licença

AGPL-3.0-or-later. Uso interno na sua empresa, incluindo comercial, está liberado.

Se você quer embarcar o RTC Check num produto fechado ou oferecê-lo como serviço sem
publicar suas modificações, existe licença comercial. Veja
[COMMERCIAL.md](COMMERCIAL.md) ou abra o
[formulário comercial](https://github.com/TaynanGT/rtc-check/issues/new?template=comercial.md).

Uma observação honesta sobre os planos: o código é aberto, então o gating dos recursos
pagos está aqui no repositório e qualquer pessoa consegue removê-lo. Isso é conhecido e
não vai mudar. O que a assinatura entrega não é acesso ao binário: é priorização de
atualizações após revisão técnica, suporte com prazo e direito de redistribuir. Quem
precisa patchear para não pagar provavelmente não é o cliente deste produto, e não vale
transformar a ferramenta em algo que ninguém consegue auditar só por causa disso.
