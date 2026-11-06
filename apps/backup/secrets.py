"""Segredos no Cofre de Credenciais do Windows via `keyring` (ADR-020; security-plan.md §6).

Nada aqui é gravado no banco, em logs ou em backups.
"""

from __future__ import annotations

import keyring

SERVICE = "financas"
SECRET_KEY = "secret_key"  # chave da aplicação (cookies)
BACKUP_PASSPHRASE = "backup_passphrase"  # senha de backup (também guardada fora do sistema)
TELEGRAM_TOKEN = "telegram_token"  # MVP-2

MIN_PASSPHRASE = 16


def get(name: str) -> str | None:
    try:
        return keyring.get_password(SERVICE, name)
    except keyring.errors.KeyringError:
        return None


def put(name: str, value: str) -> None:
    keyring.set_password(SERVICE, name, value)


def has(name: str) -> bool:
    return bool(get(name))


def validate_passphrase(value: str) -> None:
    from apps.ledger.errors import InvalidTransactionError

    if len(value or "") < MIN_PASSPHRASE:
        raise InvalidTransactionError(
            f"A senha de backup precisa de pelo menos {MIN_PASSPHRASE} caracteres."
        )
