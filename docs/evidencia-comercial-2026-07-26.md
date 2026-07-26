# Evidência comercial — RTC Check Desktop

Registro compacto antes da implementação da interface local, em 26/07/2026.

| Campo | Evidência observada |
|---|---|
| Comprador prioritário | Equipes fiscais e de TI de indústrias, distribuidores, fabricantes de ERP e escritórios que não podem enviar XML fiscal para terceiros. |
| Fluxo doloroso | Descobrir, antes da emissão, quais cadastros de produto repetem padrões que podem causar rejeição de NF-e com IBS/CBS; distribuir a correção e comprovar progresso. |
| Alternativas atuais | Validador oficial da SVRS, ERPs, audita-rtc, Refistax, Radar360 e conferência manual de XML/planilhas. |
| Reclamações observadas | Mudanças frequentes de schema e cronograma, divergências entre documentação e ambientes e trabalho manual para baixar, revisar e corrigir XMLs em volume. |
| Referências de preço | audita-rtc: R$ 67/mês e R$ 147/mês; Refistax: R$ 399/mês; RTC Check anterior: R$ 390/mês. Valores observados nas páginas públicas em 26/07/2026. |
| Canal de aquisição | Conteúdo técnico sobre rejeições, comunidades de ERP/contabilidade, parceiros de implantação, demonstração local e GitHub. |
| Promessa do produto | Transformar um acervo fiscal sensível numa fila priorizada de produtos sem enviar nenhum documento para terceiros. |
| Hipótese de preço | R$ 149/mês ou R$ 1.490/ano por instalação local, sem franquia de XML/CNPJ; Plataforma sob consulta. |
| Evento de ativação | A pessoa executa a demonstração ou analisa o primeiro lote e encontra a contagem de SKUs a corrigir. |
| Evento de conversão | Ativa o trial, tenta exportar a fila completa ou inicia a compra assistida. |
| Sinal de retenção | Repete a análise após corrigir cadastros, compara a redução da fila ou integra o portão ao CI. |
| Razão para pagar agora | Prazo de rejeição próximo, necessidade de distribuir a correção e manter a regra atualizada sem expor XMLs. |
| Esforço estimado | 1–3 dias focados para a primeira interface local vendável, empacotamento Windows, onboarding, relatórios e checkout configurável. |
| Risco comercial principal | Um contador comum prefere uma interface web e PDF white-label; uma equipe técnica pode criar validações próprias. A diferenciação precisa ser privacidade local + volume ilimitado + automação. |

## Fontes consultadas

- [Validador oficial RTC NF-e/NFC-e da SVRS](https://dfe-portal.svrs.rs.gov.br/Cff/ValidadorRtcNfe)
- [Planos e recursos do audita-rtc](https://www.auditartc.com.br/)
- [Política de privacidade do audita-rtc](https://www.auditartc.com.br/privacidade)
- [Planos e recursos do Refistax](https://refistax.com.br/)
- [Discussão sobre preparação de XML e parametrização de ERP](https://www.reddit.com/r/ContabilidadeAtual/comments/1uab1ml/prepara%C3%A7%C3%A3o_xml_rt/)

## Decisão

Não competir como mais um SaaS de upload. O RTC Check Desktop será uma ferramenta
visual, local e auditável: arrastar XML/ZIP, obter uma fila priorizada por SKU,
exportar relatórios e acompanhar correções sem que o documento fiscal saia do PC.
