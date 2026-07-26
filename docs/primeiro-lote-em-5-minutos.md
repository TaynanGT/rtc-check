# Primeiro lote em cinco minutos

1. Baixe a release para Windows ou instale com `uvx` conforme o README.
2. Abra `RTC-Check.exe` (ou execute `rtc-check --app`). A página abre em
   `127.0.0.1`; não envie XMLs por e-mail para receber suporte.
3. Clique em **Ver demonstração** para reconhecer a fila sem usar documento real.
4. Selecione um pequeno lote de cópias de XMLs (ou um ZIP de até 64 MB) e clique em
   **Analisar agora**. A ferramenta apaga os temporários ao concluir.
5. Comece pelo primeiro SKU, corrija-o no ERP e valide uma nova NF-e no
   [validador RTC da SVRS](https://dfe-portal.svrs.rs.gov.br/Cff/ValidadorRtcNfe).
6. Com o teste do plano Escritório ativo, baixe o **Pacote ZIP** e entregue o CSV
   ao responsável pelo cadastro. O ZIP não leva os XMLs originais.

Se algo falhar, copie somente `rtc-check --diagnostico` e a mensagem de erro.
Esse diagnóstico não inclui caminhos, CNPJ, XMLs ou chaves de NF-e.
