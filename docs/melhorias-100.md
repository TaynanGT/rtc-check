# RTC Check — 100 melhorias por área

Este catálogo transforma o pedido de evolução em um backlog verificável. Os
itens marcados como **feito nesta rodada** foram implementados e validados no
branch atual; os marcados como **já presente** foram conferidos na base; os
marcados como **preparado** têm contrato, script ou critérios de aceitação
prontos, mas aguardam uma autoridade externa. O item **substituído** recebeu
uma solução mais durável. Nada abaixo é apresentado como integração ativa sem
evidência.

## 1. Produto e experiência principal

1. **feito nesta rodada** — Entregar HTML, CSV, JSON e manifesto em um pacote ZIP.
2. **feito nesta rodada** — Copiar um resumo executivo pronto para e-mail ou chamado.
3. **feito nesta rodada** — Ordenar a fila por prioridade, ocorrências, SKU ou emitente.
4. **feito nesta rodada** — Persistir a preferência de ordenação no navegador.
5. **já presente** — Fluxo guiado em três etapas: selecionar, analisar e corrigir.
6. **já presente** — Demonstração com XMLs sintéticos para ativação imediata.
7. **já presente** — Arrastar arquivos, selecionar múltiplos arquivos e escolher uma pasta.
8. **já presente** — Preservar o resultado ao limpar uma seleção para evitar perda acidental.
9. **já presente** — Cancelar lote longo com feedback de estado.
10. **feito nesta rodada** — Criar histórico local opcional de métricas com exclusão explícita.

## 2. Privacidade e segurança

11. **já presente** — Escutar somente em 127.0.0.1.
12. **já presente** — Token aleatório por sessão para as rotas da API.
13. **já presente** — Rejeitar hosts diferentes do loopback.
14. **já presente** — Limitar upload total a 64 MB.
15. **já presente** — Limitar cada XML a 25 MB.
16. **já presente** — Limitar ZIP descompactado a 500 MB.
17. **já presente** — Limitar quantidade a 20.000 XMLs.
18. **já presente** — Apagar temporários ao fim da análise e manter resultados somente em memória.
19. **já presente** — CSP, nosniff, frame deny, no-store e referrer policy restritiva.
20. **feito nesta rodada** — Exibir painel técnico copiável com limites, versão e privacidade.

## 3. Motor fiscal e qualidade do diagnóstico

21. **já presente** — Agregar achados por SKU em vez de repetir a mesma correção por nota.
22. **já presente** — Separar bloqueios, alertas e informações por severidade.
23. **já presente** — Ordenar códigos por prioridade operacional.
24. **já presente** — Preservar emitente e SKU na identidade do grupo.
25. **já presente** — Mostrar notas afetadas e ocorrências por item.
26. **já presente** — Exibir ação recomendada para cada código conhecido.
27. **já presente** — Informar arquivos inválidos sem misturá-los às métricas válidas.
28. **feito nesta rodada** — Adicionar explicação detalhada por regra com campo, impacto, responsável e fonte.
29. **feito nesta rodada** — Permitir selecionar quais regras entram na auditoria.
30. **feito nesta rodada** — Criar comparação local entre análises consecutivas com validação de versão normativa.

## 4. Exportação e integração

31. **feito nesta rodada** — Gerar manifesto com versão, normativa, contagens e aviso de privacidade.
32. **feito nesta rodada** — Não incluir XMLs originais no pacote de entrega.
33. **feito nesta rodada** — Aplicar marca e cor configuradas ao HTML do pacote.
34. **já presente** — Exportar relatório HTML imprimível para PDF.
35. **já presente** — Exportar fila CSV compatível com Excel.
36. **já presente** — Exportar JSON com emitentes e itens completos.
37. **feito nesta rodada** — Usar nomes de arquivo estáveis e amigáveis no pacote.
38. **já presente** — Copiar a fila em formato tabular para ERP, planilha ou chamado.
39. **feito nesta rodada** — Copiar a primeira ação e o resumo executivo.
40. **preparado** — Contrato HMAC, esquema JSON, idempotência, replay protection e casos de retry estão em `docs/webhook-e-cupons.md`; o envio real aguarda o receptor privado.

## 5. Interface, acessibilidade e teclado

41. **feito nesta rodada** — Adicionar ajuda rápida acessível pela barra superior.
42. **feito nesta rodada** — Documentar atalhos Ctrl/Cmd+Enter, / e Esc na própria interface.
43. **feito nesta rodada** — Permitir fechar diálogos com Esc.
44. **feito nesta rodada** — Foco rápido na busca com a tecla /.
45. **feito nesta rodada** — Indicar aria-busy durante análises.
46. **já presente** — Skip link para pular ao conteúdo.
47. **já presente** — Estados de foco visíveis e navegação por teclado.
48. **já presente** — Respeitar prefers-reduced-motion.
49. **já presente** — Layout responsivo com tabela em cartões no celular.
50. **feito nesta rodada** — Adicionar smoke automatizado Chromium para o fluxo visual e controles principais.

## 6. Conversão e monetização

51. **já presente** — Teste gratuito ativado localmente sem cartão.
52. **já presente** — Plano Escritório com preço mensal e anual visíveis.
53. **já presente** — Checkout modular por variável de ambiente.
54. **já presente** — Captação assistida como fallback quando checkout automático não está configurado.
55. **feito nesta rodada** — Reforçar a entrega concreta do pacote como argumento de compra.
56. **feito nesta rodada** — Explicar na ajuda o caminho demonstração → correção → validador oficial.
57. **feito nesta rodada** — Manter tabela pública de comparação Comunidade, Escritório e Plataforma.
58. **feito nesta rodada** — Registrar somente eventos operacionais agregados no navegador, sem dados fiscais.
59. **feito nesta rodada** — Formulário privado com consentimento explícito e interesse comercial, sem aceitar XML ou dados fiscais.
60. **preparado** — Ciclo de vida, casos de sandbox e limites de responsabilidade estão documentados; o cupom real continua no provedor financeiro.

## 7. Onboarding, confiança e documentação

61. **já presente** — README com instalação, uso local, limites e segurança.
62. **já presente** — Evidência comercial separando fato, hipótese e risco.
63. **já presente** — Documento de captação privada sem pedir XML ou dados fiscais.
64. **já presente** — Links para normativa e validador oficial.
65. **já presente** — Aviso de que a triagem não substitui validação profissional.
66. **feito nesta rodada** — Ajuda rápida embutida no primeiro contato.
67. **feito nesta rodada** — Manifesto do pacote explicando o que foi e não foi incluído.
68. **feito nesta rodada** — Criar guias de primeiro lote em cinco minutos.
69. **feito nesta rodada** — Adicionar FAQ operacional de rejeição 1115, CRT 3 e limites.
70. **substituído** — Demonstração interativa local e smoke Chromium exercitam o fluxo real; não foi incluído GIF decorativo desatualizável.

## 8. Testes, observabilidade e confiabilidade

71. **já presente** — Suíte HTTP cobrindo status, demo, upload, cancelamento e licença.
72. **já presente** — Testes de limites e ZIP inválido/bomba de descompressão.
73. **já presente** — Ruff limpo no código e nos testes.
74. **já presente** — mypy estrito limpo no pacote Python.
75. **feito nesta rodada** — Testar conteúdo e manifesto do pacote ZIP.
76. **já presente** — Retornar mensagens de erro legíveis em JSON.
77. **já presente** — Tratar resultado expirado e conflito de mudança de plano.
78. **feito nesta rodada** — Rodar smoke test Playwright em Chromium no CI.
79. **já presente** — Cobertura mínima de 90% já é exigida no pipeline.
80. **já presente** — Instalação limpa do wheel já é testada em Windows e Ubuntu.

## 9. Performance, distribuição e operação

81. **já presente** — Análise assíncrona para lotes reais.
82. **já presente** — Progresso por XML analisado.
83. **já presente** — Limites de memória e descarte de temporários.
84. **já presente** — Dependências de runtime pequenas e explícitas.
85. **já presente** — Entrada de console e interface Desktop no mesmo pacote.
86. **preparado** — `scripts/Sign-Windows.ps1` assina e valida quando um certificado de editor estiver instalado; sem certificado, o release mantém SHA-256 e instruções de verificação.
87. **feito nesta rodada** — Adicionar `rtc-check --diagnostico` sem revelar dados sensíveis.
88. **já presente** — Empacotamento Windows reproduzível com PyInstaller já está no script de release.
89. **já presente** — Teste de volume mede tempo e pico de memória para 2.000 XMLs/10.000 itens, com teto de regressão no CI.
90. **já presente** — Documentação de atualização manual, SHA-256 e verificação de integridade já está disponível.

## 10. Crescimento, suporte e evolução do negócio

91. **feito nesta rodada** — Registrar uma hipótese comercial explícita no scorecard.
92. **feito nesta rodada** — Manter aquisição por demonstração, captação privada e validador oficial.
93. **já presente** — Identificar escritórios contábeis e equipes fiscais como compradores iniciais.
94. **já presente** — Posicionar privacidade local como diferenciação verificável.
95. **feito nesta rodada** — Preparar roteiro de demonstração comercial de 15 minutos.
96. **feito nesta rodada** — Criar calculadora local de esforço manual por ocorrências.
97. **feito nesta rodada** — Adicionar pesquisa de satisfação local após a fila, sem telemetria.
98. **feito nesta rodada** — Criar diagnóstico redigido e copiável para suporte.
99. **feito nesta rodada** — Changelog registra impacto de pacote, diagnóstico, catálogo e privacidade por versão.
100. **feito nesta rodada** — Eventos de demonstração, teste, análise e exportação ficam agregados no navegador e podem ser apagados; não há telemetria remota.

## Critério de conclusão desta rodada

O pacote atual fecha o caminho principal: importar, analisar localmente,
entender a fila, comparar, copiar, entregar um ZIP profissional e pedir suporte
sem expor XMLs. Os três itens que precisam de identidade, contrato ou sistema
externo agora têm seu contrato, script ou critérios de aceitação preparados;
nenhum foi falsamente apresentado como ativo. O GIF foi substituído
deliberadamente por demonstração interativa e teste visual do fluxo verdadeiro.
