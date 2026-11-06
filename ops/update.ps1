<#
.SYNOPSIS
    Atualiza o sistema com backup antes e volta atrás se algo falhar (security-plan.md §9).

.DESCRIPTION
    Ordem:
       1. recusa se houver mudanças locais no código (git);
       2. guarda a versão atual;
       3. para o sistema;
       4. backup "pre_update";
       5. git pull e uv sync;
       6. pip-audit e testes automáticos;
       7. arquivos estáticos;
       8. backup "pre_migration" (se houver migrações);
       9. migrate e verificação das invariantes;
      10. inicia.
    Falha antes das migrações: volta o código e inicia.
    Falha depois das migrações: volta o código PRIMEIRO e depois restaura o backup
    "pre_migration" (pede a senha de backup e a palavra RESTAURAR), e inicia.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File ops\update.ps1
#>
. (Join-Path $PSScriptRoot "common.ps1")
Assert-Config
Assert-Uv
Set-AppEnvironment
Set-Location $Root

Write-Step "Conferindo o código local"
if (git status --porcelain) {
    throw "Há mudanças locais no código (git status). Nada foi feito."
}
$previous = (git rev-parse HEAD).Trim()
Write-Ok "versão atual $previous"

function Undo-Code {
    Write-Step "Voltando o código para $previous"
    Invoke-Native "git" @("reset", "--hard", $previous)
    Invoke-Native "uv" @("sync", "--frozen")
    Invoke-Manage @("collectstatic", "--noinput", "--clear", "-v", "0")
}

function Invoke-Tests {
    # Os testes usam as próprias configurações e um banco de teste, nunca o banco real.
    $saved = @{
        ds  = $env:DJANGO_SETTINGS_MODULE
        dir = $env:FINANCAS_DATA_DIR
    }
    Remove-Item Env:DJANGO_SETTINGS_MODULE, Env:FINANCAS_DATA_DIR -ErrorAction SilentlyContinue
    try { Invoke-Native "uv" @("run", "pytest", "-q", "-m", "not e2e", "-p", "no:cacheprovider") }
    finally {
        $env:DJANGO_SETTINGS_MODULE = $saved.ds
        if ($saved.dir) { $env:FINANCAS_DATA_DIR = $saved.dir }
    }
}

Stop-App
$migrated = $false
$preMigration = $null
try {
    Write-Step "Backup antes da atualização"
    New-Backup "pre_update" | Out-Null

    Write-Step "Baixando a nova versão"
    Invoke-Native "git" @("pull", "--ff-only")
    $current = (git rev-parse HEAD).Trim()
    if ($current -eq $previous) { Write-Ok "já estava na versão mais recente" }
    Invoke-Native "uv" @("sync", "--frozen")

    Write-Step "Vulnerabilidades conhecidas nas dependências (pip-audit)"
    & uv run pip-audit
    if ($LASTEXITCODE -ne 0) {
        Write-Warn "o pip-audit encontrou problemas (ou não conseguiu consultar a internet)."
        if (-not (Confirm-Step "Continuar a atualização mesmo assim?")) { throw "Interrompido no pip-audit." }
    }

    Write-Step "Testes automáticos"
    Invoke-Tests

    Write-Step "Arquivos estáticos"
    Invoke-Manage @("collectstatic", "--noinput", "--clear", "-v", "0")

    Write-Step "Migrações do banco"
    & uv run python manage.py migrate --check | Out-Null
    if ($LASTEXITCODE -ne 0) {
        $preMigration = New-Backup "pre_migration"
        $migrated = $true
        Invoke-Manage @("migrate", "--noinput")
    }
    else { Write-Ok "nenhuma migração pendente" }

    Write-Step "Invariantes do Ledger"
    Invoke-Manage @("check_invariants")
}
catch {
    Write-Warn "a atualização falhou: $_"
    Undo-Code
    if ($migrated) {
        Write-Step "Restaurando o banco de antes das migrações ($preMigration)"
        Invoke-Manage @("restore_backup", $preMigration)
    }
    Start-App
    throw "Atualização desfeita. O sistema voltou para a versão $previous."
}
Start-App
Write-Step "Atualizado para $((git rev-parse --short HEAD).Trim())"
