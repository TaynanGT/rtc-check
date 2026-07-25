# Política de segurança

## Superfície de ataque

O RTC Check lê arquivos XML de entrada e escreve relatórios. Ele **não** faz
requisição de rede, **não** abre porta, **não** executa código do XML e **não**
tem dependência de terceiros em tempo de execução, só a biblioteca padrão.

O parser usa `xml.etree.ElementTree`, que **não** resolve entidades externas
nem DTD remoto, o que fecha as classes XXE e billion-laughs por resolução
externa. Ainda assim: só rode a ferramenta em XML de origem que você conhece.

A saída HTML escapa todo conteúdo vindo do XML (`html.escape`), incluindo
código de produto e descrição. Há teste automatizado cobrindo isso.

## Dados

Nada sai da máquina. Sem telemetria, sem análise de uso, sem chamada externa.
O `.gitignore` do projeto bloqueia `*.html`, `xmls/` e `acervo/` justamente
para evitar que um relatório ou XML de cliente vá parar num commit.

## Relatando uma vulnerabilidade

Abra um advisory privado pelo GitHub em vez de uma issue pública.
Resposta em até 5 dias úteis.

## Versões suportadas

| Versão | Suporte |
|---|---|
| 0.1.x | sim |
