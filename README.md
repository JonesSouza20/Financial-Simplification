# Finanças — sistema de gestão financeira pessoal

Projeto completo em [`docs/`](docs/README.md). Roadmap em [`docs/implementation-roadmap.md`](docs/implementation-roadmap.md).

Estado: **Fase 1D — Operação: serviço, agendador e backup** concluída. Próxima: porta de validação do MVP-1 (uso real por algumas semanas).

## Requisitos

- Windows 11
- [uv](https://docs.astral.sh/uv/). Ele instala o Python 3.13 e as dependências travadas em `uv.lock`.

## Comandos

```bash
uv sync
```

```bash
uv run pytest
```

```bash
uv run ruff check .
```

```bash
uv run python manage.py runserver 127.0.0.1:8001
```

O banco e os arquivos de dados ficam em `var/`, que está fora do Git. A pasta pode ser trocada pela variável de ambiente `FINANCAS_DATA_DIR`.

Testes de propriedade com 1.000 exemplos (porta de validação):

```bash
HYPOTHESIS_PROFILE=thorough uv run pytest
```

Testes de ponta a ponta (Chromium do Playwright, instalado com `uv run playwright install chromium`):

```bash
uv run pytest -m e2e
```

Gerar o CSS depois de mudar templates ou `tailwind/input.css` (o arquivo gerado fica no Git):

```bash
TAILWINDCSS_VERSION=v4.1.7 uv run tailwindcss -i tailwind/input.css -o static/css/app.css --minify
```

Primeiro acesso (desenvolvimento): abra `http://127.0.0.1:8001/` e crie a senha. A porta 8000 fica para o sistema em uso. As categorias padrão são carregadas pelo `migrate`. Depois use o assistente de abertura (`/abertura/contas/`).

## Instalação no PC (uso real)

O sistema em uso roda de um clone separado desta pasta (ADR-038). Passo a passo em [`ops/guides/servico-windows.md`](ops/guides/servico-windows.md):

```powershell
git clone "$env:USERPROFILE\Documents\Programa Financeiro" "$env:USERPROFILE\Financas"
```

```powershell
powershell -ExecutionPolicy Bypass -File ops\install.ps1 -Mode logon
```

Outros scripts: `ops\update.ps1` (atualizar com backup e volta atrás), `ops\restore.ps1` (restaurar ou `-Test`), `ops\reset-password.ps1` (senha esquecida).

Guias: [Tailscale Serve e HTTPS](ops/guides/tailscale-https.md), [criptografia do disco](ops/guides/criptografia-do-disco.md), [recuperação de desastre](ops/guides/recuperacao-de-desastre.md).

Comandos de terminal (com `DJANGO_SETTINGS_MODULE=config.settings.prod`, que os scripts já definem): `backup_now`, `list_backups`, `restore_backup <nome> [--test]`, `check_invariants`, `init_secrets [--backup-passphrase]`, `reset_password`, `run_jobs`.

