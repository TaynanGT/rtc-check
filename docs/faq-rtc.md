# FAQ operacional da RTC

## O RTC Check garante conformidade?

Não. Ele faz triagem técnica dentro da cobertura declarada, registra a versão
normativa usada e encaminha para a confirmação oficial.

## O que é a RTC001 / rejeição 1115?

É a verificação de ausência do grupo IBS/CBS em item no escopo monitorado pela
UB12-10. A regra pode ter exceções; leia a mensagem completa e a fonte exibida.

## Quais documentos entram?

NF-e modelo 55 é a cobertura principal. NFS-e, CT-e, eventos e cálculo tributário
integral estão fora do escopo da versão 0.3.1.

## Meus XMLs vão para a Internet?

Não. O Desktop escuta em `127.0.0.1`, usa token por sessão e apaga temporários ao
terminar. Relatórios exportados podem conter dados fiscais e devem ser protegidos.

## Posso usar no CI de um ERP?

Sim. Use `--falhar-em-bloqueio` depois de ativar o teste ou uma licença compatível.
Fixe a versão do RTC Check e do snapshot normativo para manter o build reproduzível.
