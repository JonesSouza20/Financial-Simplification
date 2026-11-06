"""Produção: serviço no PC do usuário, acessado via Tailscale Serve com HTTPS.

A leitura da chave pelo cofre do Windows (keyring) entra na Fase 1D (ADR-020).
Até lá, a chave vem da variável de ambiente e a ausência impede a inicialização.
"""

import os

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403

DEBUG = False

SECRET_KEY = os.environ.get("FINANCAS_SECRET_KEY", "")
if len(SECRET_KEY) < 50:
    raise ImproperlyConfigured("FINANCAS_SECRET_KEY ausente ou curta demais.")

# Nome MagicDNS da máquina na tailnet, ex.: "pc.nome-da-tailnet.ts.net" (ADR-012).
TAILNET_HOST = os.environ.get("FINANCAS_TAILNET_HOST", "")
if TAILNET_HOST:
    ALLOWED_HOSTS = [*ALLOWED_HOSTS, TAILNET_HOST]  # noqa: F405
    CSRF_TRUSTED_ORIGINS = [f"https://{TAILNET_HOST}"]

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
