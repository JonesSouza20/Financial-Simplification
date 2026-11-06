"""Configurações comuns a todos os ambientes.

Referências: architecture.md §3, §7, §9; database-design.md §1; security-plan.md §3, §8.
"""

import datetime
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Pasta de dados (banco, backups temporários, logs). Fica fora do Git.
DATA_DIR = Path(os.environ.get("FINANCAS_DATA_DIR", BASE_DIR / "var"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

DEBUG = False

# O servidor escuta só em 127.0.0.1; o nome *.ts.net é acrescentado em prod (ADR-012).
ALLOWED_HOSTS = ["127.0.0.1", "localhost"]

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "axes",
    "apps.ledger",
    "apps.security",
    "apps.accounts",
    "apps.categories",
    "apps.entries",
    "apps.persons",
    "apps.receivables",
    "apps.cards",
    "apps.debts",
    "apps.opening",
    "apps.backup",
    "apps.scheduler",
    "apps.ui",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # Arquivos estáticos em produção, antes do login obrigatório (ADR-037).
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "apps.backup.maintenance.MaintenanceMiddleware",
    "apps.ui.middleware.SecurityHeadersMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.security.middleware.SessionTimeoutMiddleware",
    "django.contrib.auth.middleware.LoginRequiredMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "axes.middleware.AxesMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.ui.context.ui",
            ],
        },
    },
]

# SQLite (ADR-014): WAL, chaves estrangeiras (o Django liga por padrão) e
# transações em modo IMMEDIATE, para evitar conflitos de escrita no meio da operação.
SQLITE_INIT_COMMAND = "PRAGMA journal_mode=WAL;PRAGMA synchronous=NORMAL;PRAGMA busy_timeout=20000;"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": DATA_DIR / "financeiro.db",
        "OPTIONS": {
            "transaction_mode": "IMMEDIATE",
            "timeout": 20,
            "init_command": SQLITE_INIT_COMMAND,
        },
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Senhas: Argon2id primeiro (ADR-019).
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]
LOGIN_URL = "security:login"
LOGIN_REDIRECT_URL = "ui:home"

# Bloqueio de tentativas (security-plan.md §3.3). Usuário único: o bloqueio é global.
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = "apps.security.lockout.cooloff"
AXES_LOCKOUT_PARAMETERS = ["username"]
AXES_RESET_ON_SUCCESS = True
AXES_LOCKOUT_CALLABLE = "apps.security.lockout.lockout_response"
AXES_VERBOSE = False
# axes.W006 alerta para troca de User-Agent/cookie contornar o bloqueio. Aqui o login usa
# sempre o mesmo nome de usuário, então o bloqueio por "username" já é global para todos.
SILENCED_SYSTEM_CHECKS = ["axes.W006"]

# Sessões e aparelhos confiáveis (security-plan.md §3.2, §3.4; ADR-019, ADR-035).
FINANCAS_SESSION_IDLE_SECONDS = 30 * 60
FINANCAS_SESSION_ABSOLUTE_SECONDS = 12 * 60 * 60
FINANCAS_DEVICE_TRUST_DAYS = 30
FINANCAS_PIN_MAX_FAILURES = 5

# Localização (RNF-03).
LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = DATA_DIR / "staticfiles"  # preenchido por collectstatic (install/update.ps1)

# Sessões e cookies (security-plan.md §3.2). Valores Secure são ligados em prod (HTTPS).
SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Strict"
SESSION_COOKIE_AGE = FINANCAS_SESSION_ABSOLUTE_SECONDS
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Strict"

# Cabeçalhos de segurança (security-plan.md §8). CSP em apps/ui/middleware.py.
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"

FINANCAS_VERSION = "0.1.0"

# Backup (ADR-021; security-plan.md §7). A pasta da nuvem é escolhida na tela de backup.
FINANCAS_BACKUP_DIR = DATA_DIR / "backups"
FINANCAS_BACKUP_HOUR = 3  # 03:00
FINANCAS_RETENTION = {"daily": 7, "weekly": 4, "monthly": 12, "pre_update_days": 90}

# Início do uso (ADR-031). Datas anteriores só para itens de abertura (RN-181, I-09).
FINANCAS_START_DATE = datetime.date(2026, 11, 1)
