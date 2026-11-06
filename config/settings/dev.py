"""Desenvolvimento local. Nunca usar com dados reais."""

import os

from .base import *  # noqa: F403

DEBUG = True

SECRET_KEY = os.environ.get(
    "FINANCAS_SECRET_KEY",
    "dev-inseguro-nao-usar-com-dados-reais-0000000000000000000000",
)

# Estáticos direto das pastas de origem, sem collectstatic.
WHITENOISE_USE_FINDERS = True
