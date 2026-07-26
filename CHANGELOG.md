# Changelog

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/).
Versionamento semântico.

## [Não publicado]

### Corrigido
- Arquivos com extensão em caixa alta (`NFe123.XML`, como o portal do SEFAZ
  entrega) eram ignorados na varredura no Linux, sem erro nenhum. Um acervo
  lido pela metade produzia um "nenhum bloqueio encontrado" mentiroso. A
  extensão agora é comparada sem diferenciar maiúsculas.
- O limiar do layout 4.00 comparava a versão como texto, e `"10.00" >= "4.00"`
  é falso: um layout futuro faria a ferramenta parar de cobrar o literal
  `SEM GTIN` em silêncio. `"4.0"` tinha o mesmo destino. A comparação passou a
  ser numérica, por componente.
- Um arquivo sem permissão de leitura ou apagado no meio da varredura derrubava
  a análise inteira com traceback: só `ParseError` era capturado. Agora vira
  linha no relatório de ilegíveis, como o XML malformado já virava.

### Segurança
- O CSV neutraliza fórmula de planilha. `cProd` e `xProd` vêm de XML emitido
  por terceiro, e o CSV existe justamente para ser aberto no Excel pelo time de
  cadastro: uma descrição começando com `=` era entregue como fórmula
  executável. A saída HTML já escapava; a CSV não.

## [0.1.1] / 2026-07-25

### Corrigido
- `GTIN001` não acusa mais `cEAN` vazio em notas de layout anterior ao 4.00.
  O literal `SEM GTIN` só existe a partir do 4.00 (NT 2016.002); antes disso,
  campo vazio era a forma correta de declarar produto sem código de barras.
  Falso positivo encontrado rodando contra NF-e públicas em layouts 2.00, 3.00
  e 3.10, que geravam nove alertas indevidos em onze arquivos.

### Adicionado
- A versão do layout da nota agora é lida e exposta em `NotaFiscal.versao`.

## [0.1.0] / 2026-07-25

Primeira versão pública, publicada 9 dias antes do corte de 03/08/2026.

### Adicionado
- Varredura recursiva de acervo de XML de NF-e/NFC-e (layout 4.00).
- Regra `RTC001`: item sem o grupo `gIBSCBS` em emitente CRT=3.
- Regra `RTC002`: `gIBSCBS` presente sem `cClassTrib`.
- Regra `NCM001`: NCM ausente ou fora do formato de 8 dígitos.
- Regra `GTIN001`: dígito verificador GS1 inválido, ausente ou malformado.
- Agregação por SKU. O relatório conta itens de trabalho, não ocorrências.
- Saída em texto, JSON, CSV e HTML.
- `--falhar-em-bloqueio` para uso em pipeline.
- Emitentes do Simples Nacional (CRT=1 e 2) ficam fora do corte de agosto.
