<#
.SYNOPSIS
    Define nova senha de login quando ela foi esquecida (security-plan.md §10.4).

.DESCRIPTION
    Funciona só neste PC, com a sua sessão do Windows aberta. Pede a senha de backup como
    prova adicional. Revoga todos os aparelhos confiáveis e sessões; ative o PIN de novo
    no celular depois.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File ops\reset-password.ps1
#>
. (Join-Path $PSScriptRoot "common.ps1")
Assert-Config
Assert-Uv
Set-AppEnvironment

Write-Step "Redefinir a senha de login"
Invoke-Manage @("reset_password")
Write-Ok "senha redefinida; aparelhos confiáveis revogados"
