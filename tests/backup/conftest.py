"""Cofre de segredos em memória e pastas temporárias para os testes de backup."""

import pytest

PASSPHRASE = "frase de backup bem longa 2026"  # noqa: S105 - só em testes


@pytest.fixture
def vault(_memory_keyring):
    """O cofre em memória (já ligado para todos os testes em tests/conftest.py)."""
    return _memory_keyring


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
