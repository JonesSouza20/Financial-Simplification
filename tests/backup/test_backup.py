"""Backup e recuperação (testing-plan.md §10; security-plan.md §7; ADR-021)."""

import datetime
import gzip
import json
import sqlite3

import pyrage
import pytest
from django.db import connection

from apps.backup import core, verify
from apps.backup.models import BackupRecord, RestoreTest
from apps.entries import services as entries
from apps.entries.services import EXPENSE, EntryInput
from apps.ledger import db_triggers
from apps.ledger.models import LedgerTransaction
from apps.money import Money
from apps.ui import models as prefs

from .conftest import PASSPHRASE

pytestmark = pytest.mark.usefixtures("on_20_11", "committed_db")


@pytest.fixture
def data(fin, cats):
    for cents in (1000, 2000, 3000):
        entries.record(
            EntryInput(
                kind=EXPENSE,
                amount=Money(cents),
                account=fin.corrente,
                on=datetime.date(2026, 11, 10),
                category=cats.mercado,
            )
        )
    return LedgerTransaction.objects.count()


def test_sem_senha_de_backup_nada_e_feito(vault, dirs):
    with pytest.raises(core.BackupError, match="não configurada"):
        core.create_backup()
    record = BackupRecord.objects.get()
    assert not record.ok and "não configurada" in record.message
    assert not list(dirs[0].glob("*.age")) if dirs[0].exists() else True


def test_ida_e_volta(with_passphrase, dirs, data, tmp_path):
    local, cloud = dirs
    prefs.put("backup_cloud_dir", str(cloud))
    record = core.create_backup("daily")
    assert record.ok and record.local_ok and record.cloud_ok is True
    blob = (local / record.file_name).read_bytes()
    assert blob.startswith(b"age-encryption.org/v1")  # formato age padrão
    assert (cloud / record.file_name).read_bytes() == blob
    manifest = json.loads((local / record.file_name.replace(".db.age", ".json")).read_text())
    assert manifest["counts"]["ledger_transaction"] == data
    assert "amount" not in json.dumps(manifest)  # manifesto sem valores financeiros
    # Descriptografia independente do sistema (mesmo formato do programa age).
    plain = gzip.decompress(pyrage.passphrase.decrypt(blob, PASSPHRASE))
    restored = tmp_path / "independente.db"
    restored.write_bytes(plain)
    assert verify.problems(restored) == []
    assert verify.counts(restored)["ledger_transaction"] == data
    # Restauração em banco vazio pelo serviço.
    target = tmp_path / "vazio.db"
    sqlite3.connect(target).close()
    details = core.restore_into(target, core.find(record.file_name), PASSPHRASE)
    assert details["counts"] == manifest["counts"]


def test_backup_com_escrita_simultanea_fica_consistente(with_passphrase, dirs, data, fin, cats):
    record = core.create_backup()
    entries.record(
        EntryInput(
            kind=EXPENSE,
            amount=Money(500),
            account=fin.corrente,
            on=datetime.date(2026, 11, 11),
            category=cats.mercado,
        )
    )
    test = core.test_restore(core.find(record.file_name))
    assert test.passed and test.details_json["counts"]["ledger_transaction"] == data


def test_arquivo_corrompido_e_detectado(with_passphrase, dirs, data):
    record = core.create_backup()
    path = dirs[0] / record.file_name
    raw = bytearray(path.read_bytes())
    raw[-10] ^= 0xFF
    path.write_bytes(bytes(raw))
    with pytest.raises(core.BackupError, match="SHA-256"):
        core.test_restore(core.find(record.file_name))
    assert RestoreTest.objects.get(passed=False).details_json["error"]


def test_senha_de_backup_errada(with_passphrase, dirs, data):
    record = core.create_backup()
    with pytest.raises(core.BackupError, match="incorreta"):
        core.test_restore(core.find(record.file_name), passphrase="outra frase bem longa!")  # noqa: S106


def test_invariante_violada_impede_backup(with_passphrase, dirs, data):
    db_triggers.uninstall(connection)
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE ledger_posting SET amount_cents = amount_cents + 1 WHERE id = "
            "(SELECT MIN(id) FROM ledger_posting)"
        )
    db_triggers.install(connection)
    with pytest.raises(core.BackupError, match="I-01"):
        core.create_backup()
    assert not list(dirs[0].glob("*.age"))


def test_nuvem_indisponivel_mantem_backup_local(with_passphrase, dirs, data, tmp_path):
    prefs.put("backup_cloud_dir", str(tmp_path / "nao-existe" / "x"))
    record = core.create_backup()
    assert record.local_ok and record.cloud_ok is True  # pasta criada ao gravar
    prefs.put("backup_cloud_dir", str(tmp_path / "arquivo.txt"))
    (tmp_path / "arquivo.txt").write_text("não é pasta")
    record = core.create_backup()
    assert record.local_ok and record.cloud_ok is False and "nuvem falhou" in record.message


def test_pasta_da_nuvem_invalida(db, tmp_path):
    with pytest.raises(core.BackupError, match="não encontrada"):
        core.set_cloud_dir(str(tmp_path / "nada"))
    assert core.set_cloud_dir(str(tmp_path)) == tmp_path


def test_restauracao_sobre_o_banco_em_uso(with_passphrase, dirs, data, fin, cats):
    record = core.create_backup()
    entries.record(
        EntryInput(
            kind=EXPENSE,
            amount=Money(999),
            account=fin.corrente,
            on=datetime.date(2026, 11, 12),
            category=cats.mercado,
        )
    )
    assert LedgerTransaction.objects.count() == data + 1
    core.restore_live(core.find(record.file_name), passphrase=PASSPHRASE)
    assert LedgerTransaction.objects.count() == data
    assert BackupRecord.objects.filter(trigger="pre_restore").count() == 0  # veio do backup
    assert any(e.manifest["trigger"] == "pre_restore" for e in core.available())
    assert RestoreTest.objects.filter(kind="restore", passed=True).exists()


def test_restauracao_com_falha_nao_toca_nos_dados(with_passphrase, dirs, data):
    record = core.create_backup()
    with pytest.raises(core.BackupError):
        core.restore_live(
            core.find(record.file_name),
            passphrase="senha errada demais aqui",  # noqa: S106
        )
    assert LedgerTransaction.objects.count() == data


def test_teste_mensal(with_passphrase, dirs, data):
    with pytest.raises(core.BackupError, match="Nenhum backup"):
        core.monthly_restore_test()
    core.create_backup()
    assert core.monthly_restore_test().passed
