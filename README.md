# RTC Check

[![CI](https://github.com/TaynanGT/rtc-check/actions/workflows/ci.yml/badge.svg)](https://github.com/TaynanGT/rtc-check/actions/workflows/ci.yml)
[![Licença: AGPL v3](https://img.shields.io/badge/licen%C3%A7a-AGPL--3.0-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%20a%203.14-blue.svg)](pyproject.toml)

**[Página do projeto](https://taynangt.github.io/rtc-check/)**

**Descubra hoje quais dos seus produtos o SEFAZ vai rejeitar em 3 de agosto.**

A partir de **03/08/2026**, a NF-e emitida por empresa no Regime Normal (CRT=3) sem os
campos de IBS e CBS passa a ser rejeitada. Nota rejeitada é mercadoria parada na doca.

O problema prático não é entender a regra. É saber **quais dos seus milhares de produtos
estão fora**. O RTC Check varre o acervo de XML que você já tem no disco e devolve a lista
de SKUs que precisam de ação, agrupada por produto e ordenada por impacto.

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

Nenhum XML sai do seu computador. Sem upload, sem conta, sem servidor, sem telemetria.
Zero dependências além da biblioteca padrão do Python. Dá para auditar o que ele faz em
uma tarde, e é por isso que o código é aberto.

## Instalação

```bash
pip install rtc-check
```

Ou, sem instalar nada de forma permanente:

```bash
uvx rtc-check ./xmls
```

Requer Python 3.11 ou superior. Testado em Windows, Linux e macOS.

## Uso

```bash
rtc-check ./pasta-com-xmls
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

| Opção | O que faz |
|---|---|
| `-f, --formato` | `texto` (padrão), `json`, `csv`, `html` |
| `-o, --saida` | grava em arquivo em vez da tela |
| `--sem-recursao` | não entra em subpastas |
| `--falhar-em-bloqueio` | sai com código 1 se houver bloqueios |

## O que ele verifica

| Código | Severidade | Verificação |
|---|---|---|
| `RTC001` | bloqueio | Emitente CRT=3 com item sem o grupo `gIBSCBS` |
| `RTC002` | bloqueio | Grupo `gIBSCBS` presente, mas sem `cClassTrib` |
| `NCM001` | bloqueio | NCM ausente ou fora do formato de 8 dígitos |
| `GTIN001` | alerta | GTIN com dígito verificador inválido, ausente ou malformado |

Notas de emitentes no Simples Nacional (CRT=1 e 2) não geram bloqueio de RTC. A transição
delas segue regra própria e não cai no corte de agosto.

## O que ele *não* é

Não é um validador de schema. O RTC Check confere **presença e formato** de campos usando
tags do layout 4.00, estáveis e públicas desde 2018. Ele não substitui o
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
[COMMERCIAL.md](COMMERCIAL.md).
