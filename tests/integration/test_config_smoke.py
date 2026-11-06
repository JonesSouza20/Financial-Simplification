"""Fumaça da configuração (Fase 0): fuso, idioma, SQLite e hash de senha."""

import pytest
from django.conf import settings
from django.db import connection


def test_localizacao_pt_br():
    assert settings.LANGUAGE_CODE == "pt-br"
    assert settings.TIME_ZONE == "America/Sao_Paulo"
    assert settings.USE_TZ is True


def test_argon2_e_o_hash_principal():
    assert settings.PASSWORD_HASHERS[0].endswith("Argon2PasswordHasher")


def test_sqlite_em_modo_immediate():
    assert settings.DATABASES["default"]["OPTIONS"]["transaction_mode"] == "IMMEDIATE"


@pytest.mark.django_db
def test_sqlite_chaves_estrangeiras_ligadas():
    with connection.cursor() as cur:
        cur.execute("PRAGMA foreign_keys")
        assert cur.fetchone()[0] == 1


@pytest.mark.django_db
def test_sqlite_em_modo_wal():
    with connection.cursor() as cur:
        cur.execute("PRAGMA journal_mode")
        assert cur.fetchone()[0].lower() == "wal"


def test_servidor_so_aceita_hosts_locais_por_padrao():
    # O pytest-django acrescenta "testserver" durante os testes.
    assert set(settings.ALLOWED_HOSTS) - {"testserver"} == {"127.0.0.1", "localhost"}
