"""Produção: serviço no PC do usuário, acessado via Tailscale Serve com HTTPS (ADR-011, ADR-012).

A chave da aplicação vem do Cofre de Credenciais do Windows (ADR-020). A variável de ambiente
FINANCAS_SECRET_KEY só é aceita como plano B documentado.
"""

import os

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403

DEBUG = False


def _secret_key() -> str:
    value = os.environ.get("FINANCAS_SECRET_KEY", "")
    if not value:
        from apps.backup import secrets

        value = secrets.get(secrets.SECRET_KEY) or ""
    if len(value) < 50:
        raise ImproperlyConfigured(
            "Chave da aplicação ausente. Rode: uv run python manage.py init_secrets"
        )
    return value


SECRET_KEY = _secret_key()

# Nome MagicDNS da máquina na tailnet, ex.: "pc.nome-da-tailnet.ts.net" (ADR-012).
TAILNET_HOST = os.environ.get("FINANCAS_TAILNET_HOST", "")
if TAILNET_HOST:
    ALLOWED_HOSTS = [*ALLOWED_HOSTS, TAILNET_HOST]  # noqa: F405
    CSRF_TRUSTED_ORIGINS = [f"https://{TAILNET_HOST}"]

# Nomes próprios: o sistema em uso e o de desenvolvimento rodam no mesmo PC (ADR-038) e o
# navegador separa cookies por endereço, não por porta.
SESSION_COOKIE_NAME = "financas_sessao"
CSRF_COOKIE_NAME = "financas_csrf"
FINANCAS_DEVICE_COOKIE = "financas_aparelho"
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Logs locais com rotação diária e 90 dias de histórico (security-plan.md §11).
LOG_DIR = DATA_DIR / "logs"  # noqa: F405
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"plain": {"format": "%(asctime)s %(levelname)s %(name)s: %(message)s"}},
    "handlers": {
        "file": {
            "class": "logging.handlers.TimedRotatingFileHandler",
            "filename": str(LOG_DIR / "financas.log"),
            "when": "midnight",
            "backupCount": 90,
            "encoding": "utf-8",
            "formatter": "plain",
        },
    },
    "root": {"handlers": ["file"], "level": "INFO"},
    "loggers": {"django.request": {"handlers": ["file"], "level": "WARNING", "propagate": False}},
}
