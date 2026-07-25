# Referência normativa da RTC

Cada relatório do RTC Check registra a referência normativa usada na análise.
Isso permite explicar, meses depois, **qual fotografia regulatória** gerou cada
fila de trabalho.

## Referência da versão 0.2.0

| Campo | Valor |
|---|---|
| Documento de regras | Nota Técnica 2025.002-RTC |
| Versão | 1.50 |
| Publicação | junho de 2026 |
| Corte monitorado | 03/08/2026 para emitentes CRT=3 |
| Fonte | [NT oficial](https://www.nfe.fazenda.gov.br/portal/exibirArquivo.aspx?conteudo=pD4YrecPV6s%3D) |
| Tabela CST/cClassTrib | Informe Técnico 2025.002 v1.60, publicado em 23/06/2026 |
| Fonte da tabela | [IT oficial](https://www.nfe.fazenda.gov.br/portal/exibirArquivo.aspx?conteudo=jxTMMQeEVM8%3D) |

As regras `RTC001` a `RTC005` implementam a UB12-10, a cardinalidade de
`CST`/`cClassTrib` no layout e as UB13-10, UB13-20 e UB13-30. A UB12-10 considera
as exceções de devolução/complementar que referencia NF-e anterior a 2026 e de
`cProdANP` presente na tabela oficial de combustíveis monofásicos.

## Como a regra é atualizada

1. Compare a nova publicação do portal oficial com as regras implementadas.
2. Atualize a referência em `src/rtc_check/normativa.py`.
3. Adicione fixtures que cubram o comportamento novo e o comportamento que não
   deve mudar.
4. Atualize `CHANGELOG.md` e publique uma versão nova.

O RTC Check é uma triagem do acervo: confere regras selecionadas para priorizar
produtos. Um achado em XML histórico significa risco caso o mesmo padrão de
emissão continue após o corte; não é rejeição retroativa. A validação completa
de schema e a autorização da NF-e continuam
sendo responsabilidade do validador oficial da SEFAZ.
