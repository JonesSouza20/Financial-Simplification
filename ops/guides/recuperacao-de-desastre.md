# Recuperação de desastre e testes de restauração

Referências: ADR-021, `docs/security-plan.md` §7.3 a §7.5 e §10.

**Pré-requisito:** a senha de backup guardada fora do sistema (papel ou cofre de senhas). Sem ela, os backups não abrem. Não há como contornar.

## 1. PC perdido, furtado ou disco perdido

Em outro computador com Windows 11:

1. Instale o Git e o Google Drive (ou OneDrive) e espere a pasta de backups sincronizar.
2. Copie o código a partir da cópia guardada na nuvem (§6):

```powershell
git clone "G:\Meu Drive\Backups Finanças\financas-codigo.bundle" "$env:USERPROFILE\Financas"
```
3. Escolha o backup `.db.age` mais recente da pasta da nuvem. O arquivo `.json` de mesmo nome precisa estar ao lado.
4. Rode o instalador apontando o backup (troque o caminho pelo seu):

```powershell
powershell -ExecutionPolicy Bypass -File ops\install.ps1 -Mode logon -RestoreFrom "G:\Meu Drive\Backups Finanças\financas-20270115-030000-daily.db.age"
```

5. O instalador cria uma chave nova da aplicação e pergunta a senha de backup (grave a mesma).
6. A restauração mostra o resumo (data, transações, saldos) e pede a palavra RESTAURAR.
7. Configure o Tailscale neste computador (`tailscale-https.md`) e remova o PC antigo no painel do Tailscale.
8. Entre com a senha de login que estava no backup. Revogue todos os aparelhos confiáveis e ative o celular de novo.
9. Se o PC antigo foi furtado: troque a senha de login e a senha de backup, e revogue o token do Telegram (`docs/security-plan.md` §10.6).

## 2. Abrir um backup sem o sistema

O arquivo é um banco SQLite comprimido com gzip e criptografado no formato `age` (senha). Com a ferramenta `age` (projeto `FiloSottile/age`):

```powershell
age --decrypt -o financas.db.gz "financas-20270115-030000-daily.db.age"
```

Ela pede a senha de backup. Depois, descompacte o `financas.db.gz` (o 7-Zip abre `.gz`). O resultado `financas.db` abre em qualquer visualizador de SQLite.

Isso serve para o teste anual (security-plan.md §7.4): abrir um backup **da nuvem** em outro computador, ou numa pasta separada, e conferir que o banco abre.

## 3. Teste trimestral (janeiro, abril, julho, outubro)

Checklist de `docs/security-plan.md` §7.5:

1. Tela **Saúde**: último backup diário OK, último teste automático OK, cópia na nuvem recente.
2. Pelo navegador, fora do PC, abra a pasta da nuvem e confirme que o arquivo de ontem está lá.
3. Tela **Backup**: em um backup que veio da nuvem, digite a senha de backup **guardada fora do sistema** e clique em "Testar restauração". O teste usa a senha digitada, não a do cofre.
4. Confira o resultado: número de transações e contas. Para ver os saldos, use "Ver resumo para restaurar" e **cancele** na tela de confirmação.
5. Compare o saldo da Corrente com o do sistema atual.
6. O teste fica registrado no histórico da tela Backup (teste manual).

Pelo terminal, o mesmo teste:

```powershell
powershell -ExecutionPolicy Bypass -File ops\restore.ps1 -Test
```

## 4. Senha de login esquecida

```powershell
powershell -ExecutionPolicy Bypass -File ops\reset-password.ps1
```

Pede a senha de backup como prova. Revoga todos os aparelhos e sessões.

## 5. Senha de backup perdida

Os backups antigos ficam ilegíveis. Com o sistema funcionando: tela **Backup → Senha de backup** (pede a senha de login), defina uma nova e clique em "Fazer backup agora". A partir daí os backups usam a senha nova.

## 6. Cópia do código na nuvem

O backup leva só os dados. O código fica neste PC. Depois de cada atualização, guarde uma cópia do código na pasta da nuvem (troque o caminho pelo seu):

```powershell
git -C "$env:USERPROFILE\Documents\Programa Financeiro" bundle create "G:\Meu Drive\Backups Finanças\financas-codigo.bundle" --all
```

O arquivo `.bundle` não tem dados financeiros nem segredos (eles nunca vão para o Git).
