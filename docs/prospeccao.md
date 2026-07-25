# Prospecção: RTC Check

**Nada foi enviado.** Este arquivo é a lista qualificada e as mensagens prontas.
O envio é seu: eu não disparo mensagem comercial em nome de ninguém.

Nenhum e-mail abaixo foi inventado. Onde não consegui confirmar o endereço numa
fonte pública, o campo está marcado `(confirmar no site)`. Confira antes de mandar.
Endereço errado queima domínio e vira spam.

---

## Antes de qualquer envio

Cold e-mail para empresa é o canal **mais fraco** dessa lista, e é o mais caro em
reputação. Com 9 dias até o corte e orçamento zero, a ordem que rende mais é:

1. **Comunidade onde a dor já está sendo discutida** (grátis, mais rápido, gera prova)
2. **Contabilidades** (alavancagem: cada escritório tem dezenas de CNPJ)
3. **Parceria com quem já vende fiscal** (mais lento, maior alcance)

Faça o 1 primeiro. Chegar no 3 dizendo "300 escritórios já rodaram" muda a conversa
inteira. Hoje você chegaria dizendo "fiz uma ferramenta", que é o que todo mundo diz.

---

## Nível 1: comunidade (comece por aqui, hoje)

Não é prospecção, é distribuição. Zero custo, sem risco de spam, e é onde as pessoas
com o problema já estão perguntando.

| Onde | Formato | Observação |
|---|---|---|
| Grupos de contabilidade e fiscal no LinkedIn | post com o print da saída do CLI | busque por "reforma tributária NF-e" e entre nos ativos |
| Comunidades de dev BR (`r/brdev`, Discord de dev) | post técnico: parsing de NF-e, decisões de projeto | público que integra ERP |
| Fóruns de ERP (Bling, Tiny, Omie, Protheus) | responder quem está perguntando sobre agosto | responda a dúvida primeiro, link depois |
| Hacker News / Show HN | em inglês, ângulo "regulatory deadline tooling" | alcance pequeno no BR, mas gera backlink |

**Regra:** responda a dúvida da pessoa de forma útil mesmo que ela nunca instale nada.
Post que só divulga é ignorado; resposta que resolve é compartilhada.

---

## Nível 2: contabilidades e escritórios (maior alavancagem)

Um escritório médio atende de 50 a 300 CNPJ. Se ele adota, você não ganhou um
usuário, ganhou um canal, e a assinatura Escritório existe exatamente para isso.

**Como montar a lista** (não inventei nomes; monte com fonte pública):

- CRC do seu estado publica registro de escritórios ativos
- Sindicato das empresas de serviços contábeis (SESCON) tem lista de associados
- Busca no LinkedIn: `"escritório contábil" + sua cidade`, filtrando por porte

**Critério de qualificação**, só vale o contato se:

- atende cliente em Lucro Real ou Presumido (CRT=3, que é quem cai no corte)
- tem cliente com volume relevante de NF-e (indústria, distribuidora, atacado)
- é escritório que já usa alguma automação (senão a barreira não é o produto, é o hábito)

**Canal:** e-mail comercial público do site, ou LinkedIn do sócio responsável pela área
fiscal. Nunca WhatsApp pessoal sem contato prévio.

---

## Nível 3: parceiros de distribuição (empresas reais, verificadas)

Todas abaixo vendem infraestrutura fiscal para ERPs. O encaixe é **complementar, não
concorrente**: elas emitem a nota; o RTC Check diz de antemão quais cadastros vão
derrubar a emissão. Menos rejeição na API delas é menos ticket de suporte.

| Empresa | Site | Por que encaixa | Canal |
|---|---|---|---|
| TecnoSpeed | [tecnospeed.com.br](https://tecnospeed.com.br/plugdfe/nfe/) | Vende componente de NF-e para ERPs; faz suporte "de dev para dev". A base de clientes dela é exatamente quem precisa auditar acervo antes de agosto. | Formulário comercial do site *(confirmar no site)* |
| Focus NFe | [focusnfe.com.br](https://focusnfe.com.br/) | API REST de emissão. Posicionamento é "economizar tempo de dev do cliente". Auditoria prévia é a mesma promessa, um passo antes. | Contato do site *(confirmar no site)* |
| NFE.io | [nfe.io](https://nfe.io/) | Plataforma de emissão com forte presença em dev. Público técnico, que instala CLI sem atrito. | Contato do site *(confirmar no site)* |
| Fiscal.io | [fiscal.io](https://conteudo.fiscal.io/notas-fiscais-de-saida-integracao-com-erp/) | Já faz captura de XML e detecção de erro em nota. Sobreposição parcial: pode ser parceiro **ou** comprador estratégico. | Contato do site *(confirmar no site)* |
| Brasil NFe | [brasilnfe.com.br](https://www.brasilnfe.com.br/) | API REST de emissão, sincroniza tributação com SEFAZ. | Contato do site *(confirmar no site)* |
| Software Express | [softwareexpress.com.br](https://www.softwareexpress.com.br/pt/blog/TEF-e-integracao-fiscal-para-reforma-tributaria/) | Publicou material sobre preparar ISVs para a Reforma. Já está falando com o público certo sobre o problema certo. | Contato do site *(confirmar no site)* |

**Não** aborde nenhuma delas como aquisição agora. Você tem duas semanas de código e
zero usuário. Proposta de compra nesse estágio queima a relação. A conversa correta
hoje é: "fiz isso, é aberto, resolve um pedaço do problema dos seus clientes, faz
sentido eu indicar vocês pra emissão e vocês indicarem isso pra auditoria prévia?"

---

## Registro de contatos

Preencha conforme enviar. Está vazio de propósito: não há nada enviado.

| Data | Empresa | Segmento | Contato | Canal | Mensagem | Resposta | Próximo passo | Status |
|---|---|---|---|---|---|---|---|---|
| | | | | | | | | |

---

## Sequência correta

Não pule etapa. Cada linha só faz sentido depois da anterior:

1. Validar o problema: 5 conversas com quem emite NF-e em CRT=3
2. Usuários-piloto: 10 rodando no acervo real deles
3. Prova de valor: "achou 214 SKUs que eu não sabia" dito por outra pessoa
4. Clientes pagantes
5. Patrocínio e parceria
6. Métricas de adoção
7. Só então, comprador estratégico
