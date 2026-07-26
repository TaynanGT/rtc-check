# Changelog

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/).
Versionamento semântico.

## [0.4.0] / 2026-07-26

Da resposta ao recebimento: esta versão liga o checkout de verdade. Assinar o
plano Escritório agora é um clique, com Pix, cartão ou boleto pelo Mercado
Pago, e a licença chega por e-mail minutos após a aprovação.

### Adicionado
- Integração de pagamentos com Mercado Pago: cliente mínimo da API
  (`rtc_check/mercadopago.py`) e servidor de vendas `rtc-check-vendas`
  (`rtc_check/servidor_vendas.py`), que cria o Checkout Pro dos planos mensal e
  anual, valida a assinatura HMAC do webhook, reconsulta o pagamento na API,
  confere valor/moeda/status com idempotência por pagamento, emite a licença
  Ed25519 e envia a chave por e-mail. Vendas, recusas, cancelamentos e
  reembolsos ficam auditáveis em `vendas.jsonl`.
- Guia de ativação para o titular da conta em `docs/mercadopago.md`; variáveis
  correspondentes em `.env.example`.
- Deploy de um clique do servidor de vendas via blueprint `render.yaml` (plano
  gratuito): URL pública detectada automaticamente (`RENDER_EXTERNAL_URL`),
  chave de emissão Ed25519 gerada sozinha no primeiro boot (ou fornecida por
  `RTC_CHECK_CHAVE_PRIVADA_PEM`) e anunciada em `GET /chave-publica`, com
  roteiro sem terminal na documentação.
- Checkout oficial ativado: o aplicativo e o site apontam por padrão para
  https://rtc-check-vendas.onrender.com, e `CHAVE_PUBLICA_PADRAO` passa a ser a
  chave pública do emissor desse servidor.
- Endurecimento do servidor de vendas: pagamento de ambiente de teste
  (`live_mode` falso) é recusado, limite de criação de checkout por IP,
  cabeçalhos de segurança (CSP, X-Frame-Options) nas respostas, suporte a
  HEAD para monitores e log auditável por webhook sem dados pessoais.
- E-mail da chave informa a validade da licença e o id do pagamento para
  reconciliação; página de retorno diferencia pagamento aprovado de boleto
  aguardando compensação.

### Corrigido
- Reembolso, cancelamento ou chargeback notificado depois da emissão da
  licença era descartado como duplicado e não ficava registrado; a
  idempotência agora é por (pagamento, evento).

## [0.3.1] / 2026-07-26

### Alterado
- A ação principal e a demonstração aparecem já na abertura.
- O indicador de etapas acompanha seleção, processamento e resultado.
- A seleção mostra quantidade, tamanho, nomes e arquivos ignorados, com opção de limpar.
- Trial e licença refazem automaticamente a análise selecionada para liberar o resultado.
- A fila e cada ação podem ser copiadas diretamente para Excel, e-mail ou chamado do ERP.
- O diagnóstico oferece uma nova análise sem recarregar o aplicativo.
- O estado do plano explica quando os recursos estão efetivamente liberados.

## [0.3.0] / 2026-07-26

### Adicionado
- RTC Check Desktop: interface visual local com upload de XML/ZIP, demonstração,
  dashboard de prontidão, filtros e orientação acionável por achado.
- Relatórios white-label com marca, cor e botão para impressão/PDF.
- Ativação de teste e licença dentro da interface.
- Servidor restrito a `127.0.0.1`, token aleatório por sessão, CSP, limites de
  upload/ZIP e remoção dos temporários após cada análise.
- Build portátil para Windows com PyInstaller, checksum SHA-256 e publicação
  automática na release.
- Registro da evidência comercial e `.env.example` sem segredos para checkout modular.

### Alterado
- Plano Escritório reposicionado para R$ 149/mês ou R$ 1.490/ano, com volume
  local ilimitado.
- Versão elevada para 0.3.0 e novo comando `rtc-check --app`.

## [0.2.2] / 2026-07-25

### Corrigido
- XMLs com DTD ou entidades externas agora são rejeitados pelo parser seguro,
  evitando leitura indevida de arquivos locais e expansão de entidades.

### Adicionado
- Dependabot semanal para dependências Python e GitHub Actions.
- CodeQL para Python e workflows, com proteção obrigatória do check agregado do CI.

### Alterado
- Adicionada a dependência `defusedxml` e seus tipos de desenvolvimento.
- `cryptography` atualizado para a série 49 (mínimo seguro 48.0.1), corrigindo
  o alerta alto `GHSA-537c-gmf6-5ccf` identificado pelo Dependabot.
- Actions de terceiros fixadas por hash de commit para reduzir risco de
  alteração maliciosa ou acidental de tags.

## [0.2.1] / 2026-07-25

### Corrigido
- Licenças agora usam assinatura Ed25519: o pacote contém apenas a chave pública;
  a chave privada de emissão fica fora do repositório e da distribuição.
- `RTC006` valida o `cClassTrib` vigente para NF-e contra a fotografia oficial
  do IT 2025.002 v1.60, em vez de aceitar qualquer código não vazio.
- O teste grátis é descrito corretamente como único por diretório de configuração;
  sem conta ou rede não existe como garantir unicidade por máquina.

### Alterado
- Adicionada a dependência `cryptography` para verificar assinaturas Ed25519.

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
- O emitente aparece na lista de SKUs do relatório de texto e como coluna do HTML
  quando o acervo tem mais de uma empresa. Separar os grupos por emitente não
  resolvia nada enquanto as duas linhas saíam idênticas na tela.
- O cabeçalho resume a lista de emitentes em três documentos e um contador, em
  vez de despejar todos os CNPJs numa linha só.
- A tabela de CST do IBS/CBS ganhou teste com a lista literal dos 18 códigos
  oficiais. Os testes parametrizados liam a mesma constante que a regra consulta,
  então um código digitado errado passava com a suíte verde, e errar essa tabela
  gera bloqueio, não alerta.

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
