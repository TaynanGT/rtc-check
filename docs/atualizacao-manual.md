# Atualização manual e integridade

1. Baixe o ZIP exclusivamente na página de releases do projeto.
2. Compare o SHA-256 do arquivo com `SHA256SUMS.txt` publicado junto da release:

```powershell
Get-FileHash .\RTC-Check-Windows-*.zip -Algorithm SHA256
```

3. Extraia em uma nova pasta e abra a versão nova. A versão aparece no rodapé.
4. Mantenha a pasta anterior até confirmar uma análise de demonstração.

O executável ainda não é assinado com Authenticode porque isso depende de um
certificado de editor. SHA-256 confere integridade do arquivo baixado, mas não
substitui uma assinatura de identidade do editor.
