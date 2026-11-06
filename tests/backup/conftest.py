"""Cofre de segredos em memória e pastas temporárias para os testes de backup."""

import keyring
import pytest
from keyring.backend import KeyringBackend

PASSPHRASE = "frase de backup bem longa 2026"  # noqa: S105 - só em testes


class MemoryKeyring(KeyringBackend):
    priority = 1

    def __init__(self):
        super().__init__()
        self.data = {}

    def get_password(self, service, username):
        return self.data.get((service, username))

    def set_password(self, service, username, password):
        self.data[(service, username)] = password

    def delete_password(self, service, username):
        self.data.pop((service, username), None)


@pytest.fixture
def vault():
    previous = keyring.get_keyring()
    memory = MemoryKeyring()
    keyring.set_keyring(memory)
    yield memory
    keyring.set_keyring(previous)


@pytest.fixture
def with_passphrase(vault):
    from apps.backup import secrets

    secrets.put(secrets.BACKUP_PASSPHRASE, PASSPHRASE)
    return PASSPHRASE


@pytest.fixture
def dirs(settings, tmp_path):
    settings.FINANCAS_BACKUP_DIR = tmp_path / "local"
    cloud = tmp_path / "nuvem"
    cloud.mkdir()
    return tmp_path / "local", cloud


@pytest.fixture(autouse=True)
def _no_powershell(monkeypatch):
    """Sem PowerShell nem Tailscale nos testes; as funções reais ficam no retorno para os
    testes que as exercitam."""
    from apps.backup import health

    real = {"disk_encryption": health.disk_encryption, "funnel": health.funnel}
    monkeypatch.setattr(health, "disk_encryption", lambda: "ativa")
    monkeypatch.setattr(health, "funnel", lambda: "desligado")
    return real
