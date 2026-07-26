[CmdletBinding()]
param(
    [string]$OutputDirectory = "dist\windows"
)

$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $true
$repoRoot = Split-Path -Parent $PSScriptRoot
$resolvedRepo = [System.IO.Path]::GetFullPath($repoRoot)
$resolvedOutput = [System.IO.Path]::GetFullPath((Join-Path $repoRoot $OutputDirectory))

if (-not $resolvedOutput.StartsWith($resolvedRepo, [StringComparison]::OrdinalIgnoreCase)) {
    throw "O diretório de saída precisa ficar dentro do repositório."
}

Push-Location $repoRoot
try {
    uv sync --all-extras
    uv run ruff check .
    uv run mypy
    uv run pytest -q

    New-Item -ItemType Directory -Force -Path $resolvedOutput | Out-Null

    uv run pyinstaller `
        --noconfirm `
        --clean `
        --onefile `
        --windowed `
        --name "RTC-Check" `
        --collect-data "rtc_check" `
        --distpath $resolvedOutput `
        --workpath (Join-Path $repoRoot "build\pyinstaller") `
        --specpath (Join-Path $repoRoot "build") `
        (Join-Path $repoRoot "scripts\desktop_entry.py")

    $exe = Join-Path $resolvedOutput "RTC-Check.exe"
    if (-not (Test-Path -LiteralPath $exe)) {
        throw "O executável não foi gerado."
    }

    $versao = uv run python -c "import rtc_check; print(rtc_check.__version__)"

    # Smoke test do artefato real, sem abrir o navegador. O endpoint usa o
    # mesmo token aleatório exigido pela interface.
    $portProbe = [System.Net.Sockets.TcpListener]::new(
        [System.Net.IPAddress]::Loopback,
        0
    )
    $portProbe.Start()
    $smokePort = ([System.Net.IPEndPoint]$portProbe.LocalEndpoint).Port
    $portProbe.Stop()
    $env:RTC_CHECK_SEM_NAVEGADOR = "1"
    $env:RTC_CHECK_PORTA = [string]$smokePort
    $processo = Start-Process -FilePath $exe -PassThru -WindowStyle Hidden
    try {
        $pagina = $null
        for ($tentativa = 0; $tentativa -lt 40; $tentativa++) {
            try {
                $pagina = Invoke-WebRequest -UseBasicParsing `
                    -Uri "http://127.0.0.1:$smokePort/" -TimeoutSec 1
                break
            }
            catch {
                Start-Sleep -Milliseconds 250
            }
        }
        if ($null -eq $pagina -or $pagina.StatusCode -ne 200) {
            throw "O executável iniciou, mas a interface local não respondeu."
        }
        $tokenMatch = [regex]::Match(
            $pagina.Content,
            '<meta name="rtc-token" content="([^"]+)">'
        )
        if (-not $tokenMatch.Success) {
            throw "A interface não publicou o token de sessão esperado."
        }
        $headers = @{ "X-RTC-Token" = $tokenMatch.Groups[1].Value }
        $status = Invoke-RestMethod -Uri "http://127.0.0.1:$smokePort/api/status" `
            -Headers $headers
        if ($status.versao -ne $versao) {
            throw "Versão do executável ($($status.versao)) difere do pacote ($versao)."
        }
        Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:$smokePort/api/encerrar" `
            -Headers $headers -ContentType "application/json" -Body "{}" | Out-Null
        $processo.WaitForExit(5000) | Out-Null
        Write-Host "Smoke test do executável: aprovado"
    }
    finally {
        Remove-Item Env:\RTC_CHECK_SEM_NAVEGADOR -ErrorAction SilentlyContinue
        Remove-Item Env:\RTC_CHECK_PORTA -ErrorAction SilentlyContinue
        if (-not $processo.HasExited) {
            Stop-Process -Id $processo.Id -Force
        }
    }

    $readme = Join-Path $resolvedOutput "LEIA-ME.txt"
    @"
RTC Check Desktop $versao

1. Abra RTC-Check.exe.
2. O navegador abrirá automaticamente no endereço local.
3. Arraste arquivos XML ou ZIP.
4. Use "Encerrar" na parte superior quando terminar.

Privacidade: o servidor escuta somente em 127.0.0.1, não envia telemetria e
apaga os arquivos temporários ao terminar cada análise.

Windows pode exibir o SmartScreen porque este executável ainda não possui uma
assinatura Authenticode de editor verificado. Confira o SHA-256 publicado na
release do GitHub antes de executar.
"@ | Set-Content -LiteralPath $readme -Encoding UTF8

    $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $exe).Hash.ToLowerInvariant()
    "$hash  RTC-Check.exe" | Set-Content `
        -LiteralPath (Join-Path $resolvedOutput "SHA256SUMS.txt") -Encoding ASCII

    $zip = Join-Path (Split-Path $resolvedOutput -Parent) "RTC-Check-Windows-$versao.zip"
    Compress-Archive -Force -Path @($exe, $readme, (Join-Path $resolvedOutput "SHA256SUMS.txt")) `
        -DestinationPath $zip

    Write-Host "Executável: $exe"
    Write-Host "Pacote:     $zip"
    Write-Host "SHA-256:    $hash"
}
finally {
    Pop-Location
}
