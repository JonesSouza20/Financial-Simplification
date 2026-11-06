<#
.SYNOPSIS
    Restaura um backup pelo terminal (security-plan.md §7.2). Também dá para restaurar pela
    tela Configurações > Backup.

.DESCRIPTION
    Lista os backups (pasta local e da nuvem), restaura o escolhido num arquivo temporário,
    verifica, mostra o resumo e só substitui depois que você digitar RESTAURAR. Antes de
    substituir, faz backup do estado atual ("pre_restore").

.PARAMETER Name
    Nome do backup (financas-...db.age) ou caminho completo de um arquivo .db.age.

.PARAMETER Test
    Só testa (restaura em arquivo temporário e verifica), sem parar o sistema nem substituir.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File ops\restore.ps1
.EXAMPLE
    powershell -ExecutionPolicy Bypass -File ops\restore.ps1 -Test
#>
param(
    [string]$Name,
    [switch]$Test
)

. (Join-Path $PSScriptRoot "common.ps1")
Assert-Config
Assert-Uv
Set-AppEnvironment

Write-Step "Backups disponíveis"
Invoke-Manage @("list_backups")
if (-not $Name) { $Name = (Read-Host "    Nome do backup (copie da lista)").Trim() }
if (-not $Name) { throw "Nenhum backup escolhido." }

if ($Test) {
    Invoke-Manage @("restore_backup", $Name, "--test")
    return
}

Stop-App
try {
    Invoke-Manage @("restore_backup", $Name)
    Invoke-Manage @("migrate", "--noinput")  # o backup pode ser de uma versão anterior
    Invoke-Manage @("check_invariants")
}
finally {
    Start-App
}
Write-Host "    Entre de novo com a senha de login que estava no backup."
