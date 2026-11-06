# Funções comuns aos scripts de operação. Não rode este arquivo direto.
# Compatível com o Windows PowerShell 5.1 (o que vem no Windows 11).

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$ConfigPath = Join-Path $PSScriptRoot "config.ps1"
$ServiceName = "financas"
$TaskName = "Financas"
$WinSWExe = Join-Path $PSScriptRoot "service\financas.exe"

if (Test-Path $ConfigPath) { . $ConfigPath }

function Write-Step([string]$Text) {
    Write-Host ""
    Write-Host "==> $Text" -ForegroundColor Cyan
}

function Write-Ok([string]$Text) { Write-Host "    OK: $Text" -ForegroundColor Green }

function Write-Warn([string]$Text) { Write-Host "    ATENÇÃO: $Text" -ForegroundColor Yellow }

function Confirm-Step([string]$Question) {
    $answer = Read-Host "$Question (S/N)"
    return ($answer -match '^[sS]')
}

function Test-Admin {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Assert-Config {
    if (-not $Financas -or -not $Financas.Mode) {
        throw "Falta ops\config.ps1 (ou o modo de execução). Rode ops\install.ps1 primeiro."
    }
}

function Save-Config {
    $text = @"
# Configuração local do sistema de finanças (gerada pelo install.ps1; fora do Git).
# Depois de mudar algo aqui, rode ops\install.ps1 de novo.
`$Financas = @{
    Port        = $($Financas.Port)
    TailnetHost = "$($Financas.TailnetHost)"
    DataDir     = "$($Financas.DataDir)"
    Mode        = "$($Financas.Mode)"
}
"@
    $utf8Bom = New-Object System.Text.UTF8Encoding($true)
    [System.IO.File]::WriteAllText($ConfigPath, $text, $utf8Bom)
}

function Set-AppEnvironment {
    # Os comandos rodam com as mesmas configurações e o mesmo banco do serviço.
    $env:DJANGO_SETTINGS_MODULE = "config.settings.prod"
    $env:FINANCAS_PORT = [string]$Financas.Port
    $env:FINANCAS_TAILNET_HOST = $Financas.TailnetHost
    if ($Financas.DataDir) { $env:FINANCAS_DATA_DIR = $Financas.DataDir }
    else { Remove-Item Env:FINANCAS_DATA_DIR -ErrorAction SilentlyContinue }
}

function Invoke-Native {
    # Roda um programa e para o script se ele falhar.
    param([string]$Program, [string[]]$Arguments)
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Falhou ($LASTEXITCODE): $Program $($Arguments -join ' ')"
    }
}

function Invoke-Manage {
    param([string[]]$Arguments)
    Push-Location $Root
    try { Invoke-Native "uv" (@("run", "python", "manage.py") + $Arguments) }
    finally { Pop-Location }
}

function Get-ManageOutput {
    # Igual ao Invoke-Manage, mas devolve o texto (para ler o nome do backup gerado).
    param([string[]]$Arguments)
    Push-Location $Root
    try {
        $out = & uv run python manage.py @Arguments
        if ($LASTEXITCODE -ne 0) { throw "Falhou: manage.py $($Arguments -join ' ')" }
        $out | ForEach-Object { Write-Host "    $_" }
        return ($out -join "`n")
    }
    finally { Pop-Location }
}

function New-Backup([string]$Trigger) {
    $text = Get-ManageOutput @("backup_now", "--trigger", $Trigger)
    if ($text -match 'Backup (\S+\.db\.age)') { return $Matches[1] }
    throw "Não encontrei o nome do backup na saída."
}

function Test-Port {
    $client = New-Object System.Net.Sockets.TcpClient
    try { $client.Connect("127.0.0.1", [int]$Financas.Port); return $true }
    catch { return $false }
    finally { $client.Close() }
}

function Wait-Port([bool]$Open, [int]$Seconds = 60) {
    for ($i = 0; $i -lt $Seconds; $i++) {
        if ((Test-Port) -eq $Open) { return $true }
        Start-Sleep -Seconds 1
    }
    return $false
}

function Stop-App {
    Assert-Config
    Write-Step "Parando o sistema"
    if ($Financas.Mode -eq "service") {
        if (-not (Test-Admin)) { throw "Abra o PowerShell como administrador para parar o serviço." }
        if (Get-Service -Name $ServiceName -ErrorAction SilentlyContinue) {
            Stop-Service -Name $ServiceName
        }
    }
    else {
        if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
            Stop-ScheduledTask -TaskName $TaskName
        }
    }
    if (-not (Wait-Port $false 30)) { throw "O sistema não parou (porta $($Financas.Port) ainda aberta)." }
    Write-Ok "parado"
}

function Start-App {
    Assert-Config
    Write-Step "Iniciando o sistema"
    if ($Financas.Mode -eq "service") { Start-Service -Name $ServiceName }
    else { Start-ScheduledTask -TaskName $TaskName }
    if (-not (Wait-Port $true 60)) {
        $logs = if ($Financas.DataDir) { $Financas.DataDir } else { Join-Path $Root "var" }
        throw "O sistema não respondeu em 60 s. Veja os logs em $logs\logs."
    }
    $listen = Get-NetTCPConnection -LocalPort ([int]$Financas.Port) -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty LocalAddress -Unique
    $public = @($listen | Where-Object { $_ -ne "127.0.0.1" })
    if ($public.Count -gt 0) {
        Write-Warn "a porta $($Financas.Port) também escuta em: $($public -join ', '). Deveria ser só 127.0.0.1."
    }
    Write-Ok "respondendo em http://127.0.0.1:$($Financas.Port)/"
}

function Assert-Uv {
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        throw "O uv não foi encontrado. Rode ops\install.ps1 (ele explica como instalar)."
    }
}
