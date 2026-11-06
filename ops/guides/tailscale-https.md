# Acesso pelo celular: Tailscale Serve com HTTPS

Referências: ADR-012, `docs/security-plan.md` §4.

O sistema escuta só em `127.0.0.1`. O Tailscale Serve publica essa porta com HTTPS **só para os aparelhos da sua tailnet** (sua rede privada do Tailscale). Nada fica aberto na internet.

Confira os comandos na versão do Tailscale que você instalar (a sintaxe do `serve` mudou em versões antigas).

## 1. Preparar a tailnet

1. Instale o Tailscale no PC e no celular e entre com a mesma conta.
2. No painel de administração do Tailscale (no navegador):
   - em **DNS**, ligue o **MagicDNS** e **HTTPS Certificates**;
   - em **Machines**, renomeie o PC com um nome neutro (ex.: `pc-casa`), sem seu nome;
   - se puder escolher o nome da tailnet, use um nome neutro também;
   - deixe a **expiração de chave** ligada no celular.
3. A tailnet deve ter só o seu PC e o seu celular.

## 2. Publicar o sistema

O `install.ps1` oferece fazer isto. Para fazer à mão, no PowerShell:

```powershell
tailscale serve --bg 8000
```

```powershell
tailscale serve status
```

O `status` mostra o endereço `https://<nome-do-pc>.<sua-tailnet>.ts.net/` apontando para `http://127.0.0.1:8000`.

Esse mesmo nome precisa estar em `ops\config.ps1` (`TailnetHost`), sem `https://` e sem barra. O `install.ps1` preenche sozinho quando o Tailscale está instalado. Sem ele, o sistema recusa o acesso pelo celular (proteção do `ALLOWED_HOSTS`).

## 3. Funnel: nunca

O **Funnel** publica na internet aberta. Ele deve ficar sempre desligado.

```powershell
tailscale funnel status
```

A resposta não deve listar nenhum endereço. A tela **Saúde** do sistema também lê a configuração do Serve e mostra "Funnel: desligado". Se mostrar "ligado", desligue na hora:

```powershell
tailscale funnel reset
```

Se mostrar "não verificado", confira à mão com o comando acima.

## 4. Conferir no celular

1. Com o Tailscale ligado no celular, abra `https://<nome-do-pc>.<sua-tailnet>.ts.net/`.
2. O navegador deve mostrar o cadeado, sem alerta de certificado.
3. Entre com a senha, ative o aparelho confiável com PIN e instale como app ("Adicionar à tela inicial").
4. Desligue o Tailscale no celular e tente de novo: o endereço não deve abrir.
5. Mantenha o bloqueio de tela do celular ligado.

## 5. Celular perdido

1. Na tela **Segurança** do sistema, revogue o aparelho.
2. No painel do Tailscale, remova o celular da tailnet.
3. Siga `docs/security-plan.md` §10.1.
