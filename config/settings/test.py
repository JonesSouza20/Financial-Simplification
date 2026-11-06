"""Testes automatizados.

O banco de teste é um arquivo (não memória) para que o modo WAL e o comportamento
real do SQLite sejam exercitados.
"""

from .base import *  # noqa: F403

SECRET_KEY = "teste-somente-0000000000000000000000000000000000000000000000"  # noqa: S105

DATABASES["default"]["TEST"] = {"NAME": str(DATA_DIR / "test_financeiro.db")}  # noqa: F405

# Estáticos direto das pastas de origem, sem collectstatic (o teste de produção desliga).
WHITENOISE_USE_FINDERS = True
STATIC_ROOT.mkdir(parents=True, exist_ok=True)  # noqa: F405 - evita aviso do WhiteNoise
# Backups dos testes nunca na pasta de backups real.
FINANCAS_BACKUP_DIR = DATA_DIR / "test-backups"  # noqa: F405
