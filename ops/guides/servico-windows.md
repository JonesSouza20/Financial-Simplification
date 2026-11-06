# Instalação, serviço do Windows e atualização

Referências: `docs/architecture.md` §11, `docs/security-plan.md` §9 e §12, ADR-038.

Os comandos de ferramentas externas (WinSW, Tailscale) foram escritos pela documentação delas. Confira cada um na versão que você instalar. Se algo for diferente, anote e me avise.

## 1. Onde instalar: um clone separado

O sistema em uso roda de uma **cópia separada** desta pasta de desenvolvimento (ADR-038). Assim:

- o que muda no desenvolvimento só chega ao sistema quando você roda o `update.ps1`;
- o `update.ps1` consegue voltar à versão anterior se algo falhar;
- o banco real fica longe dos testes.

Abra o PowerShell e rode:

```powershell
git clone "$env:USERPROFILE\Documents\Programa Financeiro" "$env:USERPROFILE\Financas"
```

```powershell
cd $env:USERPROFILE\Financas
```

Os dados (banco, backups locais, logs) ficam em `%USERPROFILE%\Financas\var\`, fora do Git.

## 2. Escolha do modo de início automático

| Modo | Quando usar | Exige |
|---|---|---|
| `service` (recomendado) | O sistema sobe junto com o Windows, mesmo sem login | PowerShell como administrador; a **senha** da sua conta do Windows |
| `logon` (plano B) | Sua conta entra só com PIN/Windows Hello e não tem senha utilizável, ou você não quer dar a senha ao serviço | Nada especial; o sistema roda enquanto sua sessão estiver aberta (pode ficar com a tela bloqueada) |

No modo `logon`, ou com o Google Drive/OneDrive fechados, a cópia para a nuvem só sobe com a sessão aberta. A tela **Saúde** mostra a data da última cópia.

## 3. Modo `service`: baixar o WinSW

1. Abra a página oficial de versões do WinSW no GitHub (projeto `winsw/winsw`) e baixe o arquivo **`WinSW-x64.exe` da versão 2.12.0**.
2. Na mesma página, anote o SHA-256 publicado para esse arquivo.
3. O instalador mostra o SHA-256 do arquivo baixado e pergunta se confere. Se não conferir, responda N e baixe de novo.

## 4. Instalar

Modo `service`, no PowerShell **como administrador**:

```powershell
powershell -ExecutionPolicy Bypass -File ops\install.ps1 -Mode service -WinSWPath "$env:USERPROFILE\Downloads\WinSW-x64.exe"
```

Modo `logon`, no PowerShell comum:

```powershell
powershell -ExecutionPolicy Bypass -File ops\install.ps1 -Mode logon
```

O instalador:

1. confere o `uv` (e oferece o instalador oficial, se faltar);
2. grava `ops\config.ps1` com porta, nome do PC na tailnet, pasta de dados e modo;
3. cria a chave da aplicação no Cofre de Credenciais do Windows e pergunta a senha de backup;
4. cria o banco, gera os arquivos estáticos e roda as invariantes;
5. confere a criptografia do disco;
6. registra o serviço (o WinSW pede usuário e senha da conta; responda `y` para "logon como serviço") ou a tarefa do Agendador;
7. inicia e confere que a porta escuta só em `127.0.0.1`;
8. oferece configurar o Tailscale Serve (veja `tailscale-https.md`).

Depois, abra `http://127.0.0.1:8000/`, crie a senha de login e siga o assistente de abertura. A entrada por `http://127.0.0.1` com cookies seguros foi conferida no Chromium (mesmo motor do Edge e do Chrome); em outro navegador, se o login não funcionar, use o endereço `https://...ts.net/`.

Para trocar algo (porta, modo, nome na tailnet), edite `ops\config.ps1` ou passe o parâmetro, e rode o `install.ps1` de novo. Ele atualiza o serviço ou a tarefa.

## 5. Atualizar

```powershell
powershell -ExecutionPolicy Bypass -File ops\update.ps1
```

No modo `service`, use o PowerShell como administrador (é preciso parar o serviço).

O script recusa se houver mudanças locais no código. Depois: para o sistema, faz backup `pre_update`, baixa a nova versão, roda `pip-audit` e os testes, gera os estáticos, faz backup `pre_migration` (se houver migrações), migra, roda as invariantes e inicia.

Se algo falhar, ele volta o código e, se já tinha migrado, restaura o backup `pre_migration` (pede a senha de backup e a palavra RESTAURAR).

## 6. Restaurar e redefinir a senha

```powershell
powershell -ExecutionPolicy Bypass -File ops\restore.ps1
```

```powershell
powershell -ExecutionPolicy Bypass -File ops\restore.ps1 -Test
```

```powershell
powershell -ExecutionPolicy Bypass -File ops\reset-password.ps1
```

`-Test` só restaura num arquivo temporário e verifica, sem parar o sistema. A restauração também pode ser feita pela tela **Backup**.

## 7. Conferências depois de instalar

- `services.msc` (modo `service`) mostra "Finanças pessoais" como Automático (atraso na inicialização) e Em execução; ou o Agendador de Tarefas mostra a tarefa "Financas" (modo `logon`).
- Reinicie o PC e confirme que `http://127.0.0.1:8000/` abre sem você iniciar nada.
- No celular **fora** da tailnet (Wi-Fi da casa com o Tailscale desligado), o endereço do PC na rede local não abre.
- Logs: `var\logs\financas.log` (aplicação), `var\logs\financas.out.log`/`.err.log` (WinSW) ou `var\logs\serve.log` (plano B).
