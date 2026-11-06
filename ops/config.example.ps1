# Configuração local do sistema de finanças.
# O install.ps1 copia este arquivo para ops\config.ps1 (fora do Git) e preenche os valores.
# Todos os scripts (install, update, restore, reset-password) leem ops\config.ps1, e o
# serviço recebe os mesmos valores. Depois de mudar algo aqui, rode o install.ps1 de novo.

$Financas = @{
    # Porta local. O servidor escuta só em 127.0.0.1 (security-plan.md §4).
    Port        = 8000
    # Nome MagicDNS do PC na tailnet, ex.: "pc.nome-da-tailnet.ts.net". Vazio = só acesso local.
    TailnetHost = ""
    # Pasta dos dados (banco, backups, logs). Vazio = pasta var\ do projeto.
    DataDir     = ""
    # "service" (serviço do Windows via WinSW) ou "logon" (Agendador de Tarefas, plano B).
    Mode        = ""
}
