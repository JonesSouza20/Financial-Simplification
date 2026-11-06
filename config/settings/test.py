"""Testes automatizados.

O banco de teste é um arquivo (não memória) para que o modo WAL e o comportamento
real do SQLite sejam exercitados.
"""

from .base import *  # noqa: F403

SECRET_KEY = "teste-somente-0000000000000000000000000000000000000000000000"  # noqa: S105

DATABASES["default"]["TEST"] = {"NAME": str(DATA_DIR / "test_financeiro.db")}  # noqa: F405
