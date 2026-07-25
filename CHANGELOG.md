# Changelog

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/).
Versionamento semântico.

## [0.2.0] / 2026-07-25

Edições. A varredura e o relatório de texto continuam gratuitos e sem cadastro
para qualquer pessoa; exportação e automação passam a fazer parte dos planos
pagos, com 14 dias de teste grátis liberados por um comando local.

### Adicionado
- Módulo `edicao`: planos Comunidade, Teste grátis, Escritório e Plataforma,
  chave de licença assinada (HMAC-SHA256) e catálogo de recursos por plano.
- `--iniciar-teste`: libera 14 dias de todos os recursos, sem cadastro nem rede.
- `--licenca CHAVE`: ativa e guarda a licença em `~/.config/rtc-check/`.
- `--plano`: mostra a edição em uso e o que está liberado.
- `--por-cnpj`: quebra o resultado por emitente, em texto, JSON e HTML.
- `--comparar relatorio.json`: diferença entre duas varreduras, com SKUs novos,
  corrigidos e pendentes.
- Variáveis `RTC_CHECK_LICENCA`, `RTC_CHECK_HOME` e `RTC_CHECK_CHAVE_VERIFICACAO`.
- Código de saída 3 quando o recurso pedido está fora do plano em uso.
- README em inglês (`README.en.md`) e `docs/planos.md`.
- Referências versionadas nos relatórios: Nota Técnica 2025.002-RTC v1.50
  e tabela CST/cClassTrib do Informe Técnico 2025.002 v1.60.
- Formulário público para plano Escritório e licença comercial, sem solicitar
  dados fiscais.

### Alterado
- Regras `NCM001` e `GTIN001` passam a fazer parte dos planos pagos. `RTC001` a
  `RTC005`, que tratam o corte de agosto, seguem no plano gratuito.
- O relatório de texto gratuito detalha os 5 primeiros SKUs bloqueados; a
  contagem total continua completa e correta.
- Chave inválida ou vencida não derruba a execução: cai para o plano Comunidade
  com aviso, porque a varredura importa mais do que a cobrança.

### Corrigido
- A agregação passa a incluir o documento do emitente, evitando colisão de SKU
  entre empresas.
- `RTC001` agora valida o grupo pai `IBSCBS` pela UB12-10 e respeita as exceções
  de NF-e referenciada anterior a 2026 e combustíveis monofásicos.
- Novas regras CST-aware: CST inexistente, `gIBSCBS` obrigatório e `gIBSCBS`
  proibido, conforme UB13-10, UB13-20 e UB13-30.
- Caminhos relativos preservam a identidade de XMLs homônimos em subpastas.
- Erros de leitura e permissão viram arquivos ilegíveis sem interromper a varredura.

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
