# Finanças — sistema de gestão financeira pessoal

Projeto completo em [`docs/`](docs/README.md). Roadmap em [`docs/implementation-roadmap.md`](docs/implementation-roadmap.md).

Estado: **Fase 1B — Cadastros, lançamentos e segurança** concluída. Próxima: Fase 1C.

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
uv run python manage.py runserver 127.0.0.1:8000
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

Primeiro acesso: abra `http://127.0.0.1:8000/` e crie a senha. As categorias padrão são carregadas pelo `migrate`.

