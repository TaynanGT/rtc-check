# Parceiros, ERPs e integrações

## Integração de menor risco

1. ERP exporta XMLs para pasta controlada.
2. RTC Check roda localmente ou no CI.
3. A fila CSV/plano de ação entra no cadastro ou sistema de chamados.
4. O ERP gera um XML novo em homologação.
5. O validador oficial confirma o resultado.

Não é necessário dar acesso ao banco do ERP, certificado ou transmissão.

## Artefatos preparados

- CSV estável por SKU e emitente;
- JSON completo para automação;
- pacote ZIP com manifesto, plano de ação e checksums;
- códigos de saída previsíveis para CI;
- white-label de relatório;
- catálogo de regras com fonte, campo, confiança e responsável sugerido.

Conectores para Domínio, Alterdata ou outros fornecedores devem começar como
importação/exportação autorizada. Marketplace, referral, API hospedada e
redistribuição dependem de contrato, revisão jurídica e parceiro real; não estão
ativos por padrão.

