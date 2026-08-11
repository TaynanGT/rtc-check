# Instruções globais

Valem para todos os projetos e todos os modelos. Um `CLAUDE.md` de projeto
acrescenta a estas regras; ele não as substitui.

## Conversa

- Responda em português do Brasil.
- Diga o que falhou, o que ficou de fora e o que não foi verificado. Não relate
  como pronto o que você não viu funcionar.
- Ao corrigir algo que você mesmo afirmou antes, corrija e siga. Sem retratação
  longa.

## Antes de dizer que terminou

- Rode a verificação que o projeto já tem — teste, lint, tipo, build — e mostre a
  saída real, não um resumo dela.
- Sem forma de verificar, diga isso. É resposta melhor do que uma afirmação.
- Falha de CI que você não causou: diga por que acha que não causou, com
  evidência, em vez de calar ou de assumir culpa por reflexo.

## Contexto

- Delegue busca ampla a subagente: ele devolve `arquivo:linha` em vez de despejar
  arquivo no contexto principal.
- Leia o trecho que a tarefa pede, não o arquivo inteiro por precaução.

## Segredos

Nunca leia, nem copie para log, relatório, commit ou mensagem: `.env`,
`credentials/`, `*.pem`, `*.key`, `id_rsa*`, e qualquer diretório de dado de
cliente. Arquivo `.env.example` é público; os valores reais, não.

## Esforço e modelo

- Não suba o nível de esforço por reflexo. Nível alto amplia a cobertura ao custo
  de falso positivo — em trabalho que precisa de precisão, `medium` costuma
  render mais que `high`.
- Modelo resolve capacidade, esforço resolve minúcia. Problema ambíguo pede
  modelo mais forte; tarefa mecânica pede modelo mais barato.
- `max` é desaconselhado como padrão: retornos decrescentes e propenso a
  overthinking.
