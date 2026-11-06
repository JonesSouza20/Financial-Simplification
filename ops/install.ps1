<#
.SYNOPSIS
    Instala (ou reinstala) o sistema de finanças neste PC.

.DESCRIPTION
    Passo a passo guiado (architecture.md §11; security-plan.md §12):
      1. confere o uv (instala o Python e as dependências travadas);
      2. grava ops\config.ps1 (porta, nome na tailnet, pasta de dados, modo);
      3. cria a chave da aplicação e a senha de backup no Cofre de Credenciais do Windows;
      4. cria/atualiza o banco e os arquivos estáticos;
      5. (opcional) restaura um backup, para recuperação de desastre (security-plan.md §7.3);
      6. confere a criptografia do disco;
      7. registra o início automático: serviço do Windows (WinSW) ou, no plano B,
         tarefa "ao fazer logon" no Agendador de Tarefas;
      8. inicia e confere que a porta escuta só em 127.0.0.1;
      9. (opcional) publica na tailnet com o Tailscale Serve (HTTPS, nunca Funnel).

    Comandos de ferramentas externas (WinSW, Tailscale) devem ser conferidos na versão
    instalada; veja ops\guides\.

.PARAMETER Mode
    "service" (recomendado; exige PowerShell como administrador e a senha da conta do Windows)
    ou "logon" (plano B, sem administrador; o sistema roda com a sua sessão aberta).

.PARAMETER WinSWPath
    Caminho do WinSW-x64.exe baixado da página oficial de versões do WinSW (v2.12.0).
    Só no modo "service" e só na primeira vez.

.PARAMETER RestoreFrom
    Caminho completo de um backup .db.age (com o .json ao lado) para restaurar na instalação.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File ops\install.ps1 -Mode logon
#>
param(
    [ValidateSet("service", "logon")][string]$Mode,
    [string]$WinSWPath,
    [string]$RestoreFrom,
    [int]$Port = 0,
    [string]$DataDir
)

. (Join-Path $PSScriptRoot "common.ps1")

Write-Host "Instalação do sistema de finanças em $Root" -ForegroundColor Cyan
if (-not (git -C $Root remote)) {
    Write-Warn "esta pasta não tem origem Git. O recomendado é instalar num clone separado da pasta"
    Write-Warn "de desenvolvimento, para o update.ps1 funcionar (veja ops\guides\servico-windows.md)."
    if (-not (Confirm-Step "Instalar aqui mesmo assim?")) { return }
}

# 1. uv -------------------------------------------------------------------------------------
Write-Step "Conferindo o uv"
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Warn "o uv não está instalado."
    Write-Host "    O instalador oficial é: powershell -ExecutionPolicy ByPass -c `"irm https://astral.sh/uv/install.ps1 | iex`""
    if (Confirm-Step "Baixar e rodar o instalador oficial do uv agora?") {
        powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
        $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
    }
    Assert-Uv
}
Write-Ok (uv --version)

# 2. Configuração ---------------------------------------------------------------------------
Write-Step "Configuração (ops\config.ps1)"
if (-not $Financas) {
    . (Join-Path $PSScriptRoot "config.example.ps1")
}
if ($Port -gt 0) { $Financas.Port = $Port }
if ($PSBoundParameters.ContainsKey("DataDir")) { $Financas.DataDir = $DataDir }
if ($Mode) { $Financas.Mode = $Mode }
while ($Financas.Mode -notin @("service", "logon")) {
    Write-Host "    service = serviço do Windows (inicia sem login; pede a senha da conta do Windows)"
    Write-Host "    logon   = Agendador de Tarefas ao entrar no Windows (plano B, sem administrador)"
    $Financas.Mode = Read-Host "    Modo (service/logon)"
}
if ($Financas.Mode -eq "service" -and -not (Test-Admin)) {
    throw "O modo service precisa do PowerShell aberto como administrador."
}

$tailscale = Get-Command tailscale -ErrorAction SilentlyContinue
if (-not $tailscale -and (Test-Path "C:\Program Files\Tailscale\tailscale.exe")) {
    $tailscale = Get-Command "C:\Program Files\Tailscale\tailscale.exe"
}
if (-not $Financas.TailnetHost -and $tailscale) {
    try {
        $status = & $tailscale.Source status --json | ConvertFrom-Json
        $Financas.TailnetHost = ([string]$status.Self.DNSName).TrimEnd(".")
    }
    catch { Write-Warn "não consegui ler o nome na tailnet ($_)." }
}
if (-not $Financas.TailnetHost) {
    Write-Warn "nome na tailnet desconhecido; o celular não vai acessar até ele ser preenchido."
    $typed = Read-Host "    Nome MagicDNS do PC (ex.: pc.nome-da-tailnet.ts.net) ou Enter para pular"
    $Financas.TailnetHost = $typed.Trim()
}
Save-Config
Write-Ok "porta $($Financas.Port), modo $($Financas.Mode), tailnet '$($Financas.TailnetHost)'"

# 3. Dependências e segredos ----------------------------------------------------------------
Write-Step "Instalando as dependências travadas (uv sync)"
Push-Location $Root
try { Invoke-Native "uv" @("sync", "--frozen") } finally { Pop-Location }

Write-Step "Segredos no Cofre de Credenciais do Windows"
if ($Financas.DataDir) { $env:FINANCAS_DATA_DIR = $Financas.DataDir }
# A configuração de produção exige a chave; ela é criada antes com a configuração de desenvolvimento.
$env:DJANGO_SETTINGS_MODULE = "config.settings.dev"
Invoke-Manage @("init_secrets")
if (Confirm-Step "Definir (ou trocar) agora a senha de backup? Recomendado na primeira instalação") {
    Write-Host "    Use 16 caracteres ou mais e guarde-a FORA do sistema (papel ou cofre de senhas)."
    Invoke-Manage @("init_secrets", "--backup-passphrase")
}

# 4. Banco e arquivos estáticos -------------------------------------------------------------
Set-AppEnvironment
Write-Step "Banco de dados e arquivos estáticos"
if ((Test-Port)) { Stop-App }
Invoke-Manage @("migrate", "--noinput")
Invoke-Manage @("collectstatic", "--noinput", "--clear", "-v", "0")
Invoke-Manage @("check_invariants")

# 5. Restauração (recuperação de desastre) --------------------------------------------------
if ($RestoreFrom) {
    Write-Step "Restaurando $RestoreFrom"
    Invoke-Manage @("restore_backup", $RestoreFrom)
    Invoke-Manage @("migrate", "--noinput")  # o backup pode ser de uma versão anterior
    Invoke-Manage @("check_invariants")
}

# 6. Criptografia do disco ------------------------------------------------------------------
Write-Step "Criptografia do disco (ADR-022)"
$drive = (Split-Path -Qualifier $Root)
$code = (New-Object -ComObject Shell.Application).NameSpace("$drive\").Self.ExtendedProperty("System.Volume.BitLockerProtection")
if ($code -in @(1, 3, 5, 6)) { Write-Ok "criptografia ativa em $drive" }
else {
    Write-Warn "criptografia do dispositivo não está ativa em $drive (código '$code'). Veja ops\guides\criptografia-do-disco.md."
}

# 7. Início automático ----------------------------------------------------------------------
$python = Join-Path $Root ".venv\Scripts\python.exe"
$pythonw = Join-Path $Root ".venv\Scripts\pythonw.exe"
$serve = Join-Path $Root "ops\serve.py"
$serveArgs = "`"$serve`" --port $($Financas.Port) --tailnet-host `"$($Financas.TailnetHost)`""
if ($Financas.DataDir) { $serveArgs += " --data-dir `"$($Financas.DataDir)`"" }

if ($Financas.Mode -eq "service") {
    Write-Step "Serviço do Windows (WinSW)"
    if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Ok "tarefa do plano B removida"
    }
    if ($WinSWPath) {
        $hash = (Get-FileHash -Algorithm SHA256 $WinSWPath).Hash
        Write-Host "    SHA-256 do arquivo: $hash"
        Write-Host "    Compare com o SHA-256 publicado na página oficial de versões do WinSW."
        if (-not (Confirm-Step "O SHA-256 confere?")) { throw "WinSW não confirmado. Nada foi registrado." }
        Copy-Item $WinSWPath $WinSWExe -Force
    }
    if (-not (Test-Path $WinSWExe)) {
        throw "Falta o WinSW. Baixe o WinSW-x64.exe (v2.12.0) e rode de novo com -WinSWPath <caminho>. Veja ops\guides\servico-windows.md."
    }
    $template = Get-Content -Raw -Encoding UTF8 (Join-Path $PSScriptRoot "service\financas.template.xml")
    $logs = if ($Financas.DataDir) { Join-Path $Financas.DataDir "logs" } else { Join-Path $Root "var\logs" }
    $xml = $template.Replace("@PYTHON@", [Security.SecurityElement]::Escape($python))
    $xml = $xml.Replace("@ARGUMENTS@", [Security.SecurityElement]::Escape($serveArgs))
    $xml = $xml.Replace("@ROOT@", [Security.SecurityElement]::Escape($Root))
    $xml = $xml.Replace("@LOGDIR@", [Security.SecurityElement]::Escape($logs))
    $utf8Bom = New-Object System.Text.UTF8Encoding($true)
    [System.IO.File]::WriteAllText((Join-Path $PSScriptRoot "service\financas.xml"), $xml, $utf8Bom)
    if (Get-Service -Name $ServiceName -ErrorAction SilentlyContinue) {
        Invoke-Native $WinSWExe @("refresh")
        Write-Ok "serviço atualizado"
    }
    else {
        Write-Host "    O WinSW vai pedir usuário e senha da sua conta do Windows (ex.: .\$env:USERNAME)."
        Write-Host "    Responda 'y' para permitir 'logon como serviço'. Conta só com PIN/Windows Hello"
        Write-Host "    pode não ter senha utilizável; nesse caso use -Mode logon (plano B)."
        Invoke-Native $WinSWExe @("install", "/p")
        Write-Ok "serviço registrado com início automático"
    }
}
else {
    Write-Step "Tarefa 'ao fazer logon' no Agendador de Tarefas (plano B)"
    $user = "$env:USERDOMAIN\$env:USERNAME"
    $action = New-ScheduledTaskAction -Execute $pythonw -Argument $serveArgs -WorkingDirectory $Root
    $trigger = New-ScheduledTaskTrigger -AtLogOn -User $user
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
        -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) `
        -StartWhenAvailable -MultipleInstances IgnoreNew
    $principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings `
        -Principal $principal -Description "Sistema de finanças pessoais (127.0.0.1)" -Force | Out-Null
    Write-Ok "tarefa registrada para $user"
}

# 8. Início ---------------------------------------------------------------------------------
Start-App

# 9. Tailscale Serve ------------------------------------------------------------------------
Write-Step "Acesso pelo celular (Tailscale Serve)"
if ($tailscale) {
    Write-Host "    O Tailscale Serve publica http://127.0.0.1:$($Financas.Port) com HTTPS só na sua tailnet."
    Write-Host "    Comando: tailscale serve --bg $($Financas.Port)   (nunca use 'tailscale funnel')"
    if (Confirm-Step "Configurar o Tailscale Serve agora?") {
        Invoke-Native $tailscale.Source @("serve", "--bg", [string]$Financas.Port)
    }
    & $tailscale.Source serve status
    Write-Host "    Funnel (deve estar vazio/desligado):"
    & $tailscale.Source funnel status
}
else {
    Write-Warn "Tailscale não encontrado. Veja ops\guides\tailscale-https.md."
}

Write-Step "Pronto"
Write-Host "    Abra http://127.0.0.1:$($Financas.Port)/ neste PC."
if ($Financas.TailnetHost) { Write-Host "    No celular (na tailnet): https://$($Financas.TailnetHost)/" }
Write-Host "    Falta (checklist em docs\security-plan.md §12): pasta da nuvem, primeiro backup,"
Write-Host "    teste de restauração e aparelho confiável. A tela Configurações > Saúde mostra o estado."
