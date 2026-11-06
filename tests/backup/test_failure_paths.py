"""Caminhos de falha da verificação, dos comandos e do agendador (testing-plan.md §4, §10)."""

import datetime
import io
import sqlite3

import keyring
import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.backup import secrets, verify
from apps.backup.models import BackupRecord, RestoreTest
from apps.ledger import invariants
from apps.scheduler import jobs
from apps.scheduler.models import JobRun

from .conftest import PASSPHRASE


def answers(monkeypatch, *values):
    queue = list(values)
    monkeypatch.setattr("getpass.getpass", lambda prompt="": queue.pop(0))


# Verificação da cópia (SQL puro) ---------------------------------------------------------


def tiny_ledger(path):
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE ledger_transaction (id INTEGER PRIMARY KEY, status TEXT,
            operation_date TEXT, type TEXT);
        CREATE TABLE ledger_posting (id INTEGER PRIMARY KEY, transaction_id INTEGER,
            amount_cents INTEGER);
        CREATE TABLE transaction_link (id INTEGER PRIMARY KEY, to_transaction_id INTEGER,
            kind TEXT);
        INSERT INTO ledger_transaction VALUES (1, 'draft', '2026-11-10', 'T01');
        INSERT INTO ledger_transaction VALUES (2, 'confirmed', '2026-11-10', 'T01');
        INSERT INTO ledger_posting VALUES (1, 2, 500);
        INSERT INTO ledger_transaction VALUES (3, 'reversed', '2026-10-01', 'T01');
        INSERT INTO ledger_posting VALUES (2, 3, 100);
        INSERT INTO ledger_posting VALUES (3, 3, -100);
        """
    )
    conn.commit()
    conn.close()


def test_verificacao_aponta_cada_invariante(tmp_path):
    path = tmp_path / "ruim.db"
    tiny_ledger(path)
    found = " | ".join(verify.problems(path))
    for code in (
        "I-01: 1 transação(ões) não somam zero",
        "rascunho",
        "I-02",
        "I-03",
        "I-08",
        "I-09",
    ):
        assert code in found


def test_verificacao_sem_tabelas_do_ledger(tmp_path):
    path = tmp_path / "vazio.db"
    sqlite3.connect(path).close()
    assert verify.problems(path) == ["tabelas do Ledger ausentes"]


# Comandos --------------------------------------------------------------------------------


def test_check_invariants_com_problema(db, monkeypatch):
    monkeypatch.setattr(
        "apps.backup.management.commands.check_invariants.check_all",
        lambda: [invariants.Violation("I-01", "transação 7 não soma zero")],
    )
    out = io.StringIO()
    with pytest.raises(CommandError, match="1 problema"):
        call_command("check_invariants", stdout=out)
    assert "I-01: transação 7" in out.getvalue()


def test_list_backups_vazio(db, dirs):
    out = io.StringIO()
    call_command("list_backups", stdout=out)
    assert "Nenhum backup" in out.getvalue()


def test_reset_password_falhas(db, with_passphrase, monkeypatch, user):
    answers(monkeypatch, PASSPHRASE, "uma senha", "outra senha")
    with pytest.raises(CommandError, match="não são iguais"):
        call_command("reset_password")
    answers(monkeypatch, PASSPHRASE, "123", "123")
    with pytest.raises(CommandError):
        call_command("reset_password")
    assert not user.check_password("123")


def test_reset_password_sem_usuario(db, with_passphrase, monkeypatch):
    answers(monkeypatch, PASSPHRASE)
    with pytest.raises(CommandError, match="Nenhum usuário"):
        call_command("reset_password")


def test_cofre_indisponivel_vira_ausente(monkeypatch):
    def broken(*args):
        raise keyring.errors.KeyringError("cofre fechado")

    monkeypatch.setattr(keyring, "get_password", broken)
    assert secrets.get(secrets.BACKUP_PASSPHRASE) is None


def test_run_jobs(db, monkeypatch):
    fake = [jobs.Job("teste", "Teste", jobs.daily_due, lambda: "feito")]
    monkeypatch.setattr(jobs, "JOBS", fake)
    out = io.StringIO()
    call_command("run_jobs", stdout=out)
    assert "teste: ok feito" in out.getvalue()
    out = io.StringIO()
    call_command("run_jobs", stdout=out)
    assert "Nada devido" in out.getvalue()


def test_textos_dos_registros(db):
    when = datetime.datetime(2026, 11, 20, 3, 0, tzinfo=datetime.UTC)
    assert str(BackupRecord(file_name="", created_at=when)).startswith("backup 20/11/2026")
    assert str(RestoreTest(kind="auto", file_name="x.db.age")) == "auto x.db.age"
    assert "teste" in str(JobRun(job_name="teste", scheduled_for=when, status="ok"))


# Agendador -------------------------------------------------------------------------------


@pytest.mark.usefixtures("committed_db", "on_20_11")
def test_tarefas_reais_de_backup_e_teste(with_passphrase, dirs, fin):
    assert "bytes" in jobs._daily_backup()
    assert "ok" in jobs._monthly_restore_test()


class StopLoop(BaseException):
    pass


def test_laco_do_agendador_sobrevive_a_falhas(monkeypatch):
    calls = []

    def run_due():
        calls.append(1)
        raise RuntimeError("banco ocupado")

    def sleep(seconds):
        raise StopLoop

    class InlineThread:
        def __init__(self, target, name, daemon):
            self.target = target

        def start(self):
            with pytest.raises(StopLoop):
                self.target()

    monkeypatch.setattr(jobs, "_thread", None)
    monkeypatch.setattr(jobs, "run_due", run_due)
    monkeypatch.setattr(jobs, "close_old_connections", lambda: None)
    monkeypatch.setattr(jobs.time, "sleep", sleep)
    monkeypatch.setattr(jobs.threading, "Thread", InlineThread)
    jobs.start()
    jobs.start()  # segunda chamada não cria outra thread
    assert calls == [1]
