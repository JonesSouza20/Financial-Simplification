# Finanças — sistema de gestão financeira pessoal

Projeto completo em [`docs/`](docs/README.md). Roadmap em [`docs/implementation-roadmap.md`](docs/implementation-roadmap.md).

Estado: **Fase 0 — Fundação técnica**.

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
