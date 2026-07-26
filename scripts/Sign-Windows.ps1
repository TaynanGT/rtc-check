[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Executable,
    [string]$CertificateThumbprint = $env:RTC_CHECK_SIGNING_CERT_THUMBPRINT
)

$ErrorActionPreference = "Stop"
$resolved = (Resolve-Path -LiteralPath $Executable).Path
if (-not $CertificateThumbprint) {
    throw "Nenhum certificado Authenticode foi configurado. Defina RTC_CHECK_SIGNING_CERT_THUMBPRINT ou passe -CertificateThumbprint."
}

$cert = Get-ChildItem "Cert:\CurrentUser\My\$CertificateThumbprint" -ErrorAction SilentlyContinue
if (-not $cert) {
    $cert = Get-ChildItem "Cert:\LocalMachine\My\$CertificateThumbprint" -ErrorAction SilentlyContinue
}
if (-not $cert -or $cert.HasPrivateKey -ne $true) {
    throw "Certificado não encontrado ou sem chave privada: $CertificateThumbprint"
}

$assinatura = Set-AuthenticodeSignature -FilePath $resolved -Certificate $cert
if ($assinatura.Status -ne "Valid") {
    throw "A assinatura Authenticode não ficou válida: $($assinatura.Status) $($assinatura.StatusMessage)"
}

Write-Host "Assinatura Authenticode válida: $resolved"
