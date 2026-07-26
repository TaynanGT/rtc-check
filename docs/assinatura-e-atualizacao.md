# Assinatura e atualização verificável

Cada release publica `SHA256SUMS.txt`. No Windows:

```powershell
Get-FileHash .\RTC-Check-Windows-0.3.1.zip -Algorithm SHA256
```

Compare o valor com o arquivo da mesma release. Fixe uma tag em automações e leia o
changelog antes de atualizar. O pacote de entrega gerado pelo aplicativo também
inclui checksums de seus relatórios.

Authenticode exige um certificado de assinatura de código emitido para o titular.
Enquanto ele não existir, o build não deve ser apresentado como assinado e o
SmartScreen pode mostrar aviso. A ativação futura deve ocorrer no workflow de release,
com certificado em secret manager e verificação de assinatura após o build.
