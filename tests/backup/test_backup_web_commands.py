"""Telas de backup e saúde, e comandos de terminal (F-100; security-plan.md §7, §10.4)."""

import datetime
import io

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.backup import core, health, secrets
from apps.backup.models import BackupRecord
from apps.entries import services as entries
from apps.entries.services import EXPENSE, EntryInput
from apps.ledger.models import LedgerTransaction
from apps.money import Money
from apps.security.models import TrustedDevice
from tests.conftest import PASSWORD

from .conftest import PASSPHRASE

pytestmark = pytest.mark.usefixtures("on_20_11")


def answers(monkeypatch, *values):
    queue = list(values)
    monkeypatch.setattr("getpass.getpass", lambda prompt="": queue.pop(0))


# Telas -----------------------------------------------------------------------------------


def test_paginas_de_backup_e_saude(web, vault, dirs):
    assert web.get("/backup/").status_code == 200
    body = web.get("/backup/saude/").content.decode()
    assert "Senha de backup não configurada" in body


def test_definir_senha_de_backup_exige_senha_de_login(web, vault):
    data = {"password": "errada", "passphrase": PASSPHRASE, "confirm": PASSPHRASE, "saved": "on"}
    web.post("/backup/senha/", data)
    assert not secrets.has(secrets.BACKUP_PASSPHRASE)
    web.post("/backup/senha/", {**data, "password": PASSWORD})
    assert secrets.get(secrets.BACKUP_PASSPHRASE) == PASSPHRASE


def test_senha_de_backup_curta_ou_sem_confirmacao(web, vault):
    page = web.post(
        "/backup/senha/",
        {"password": PASSWORD, "passphrase": "curta", "confirm": "curta", "saved": "on"},
        follow=True,
    )
    assert "16 caracteres" in page.content.decode()
    page = web.post(
        "/backup/senha/",
        {"password": PASSWORD, "passphrase": PASSPHRASE, "confirm": PASSPHRASE},
        follow=True,
    )
    assert "Confira os campos" in page.content.decode()


def test_pasta_da_nuvem_pela_tela(web, vault, tmp_path):
    page = web.post("/backup/nuvem/", {"path": str(tmp_path / "x")}, follow=True)
    assert "não encontrada" in page.content.decode()
    web.post("/backup/nuvem/", {"path": str(tmp_path)})
    assert core.cloud_dir() == tmp_path


@pytest.mark.usefixtures("committed_db")
def test_backup_teste_e_restauracao_pela_tela(web, with_passphrase, dirs, fin, cats):
    entries.record(
        EntryInput(
            kind=EXPENSE,
            amount=Money(1000),
            account=fin.corrente,
            on=datetime.date(2026, 11, 10),
            category=cats.mercado,
        )
    )
    page = web.post("/backup/agora/", follow=True).content.decode()
    assert "gravado e verificado" in page
    name = BackupRecord.objects.get().file_name
    page = web.post(
        "/backup/testar/", {"name": name, "passphrase": PASSPHRASE}, follow=True
    ).content.decode()
    assert "Restauração em teste OK" in page
    entries.record(
        EntryInput(
            kind=EXPENSE,
            amount=Money(2000),
            account=fin.corrente,
            on=datetime.date(2026, 11, 11),
            category=cats.mercado,
        )
    )
    skipped = web.post(
        "/backup/restaurar/",
        {"name": name, "password": PASSWORD, "passphrase": PASSPHRASE, "confirm": "on"},
    )
    assert skipped["Location"] == "/backup/"  # sem ver o resumo antes, nada acontece
    wrong = web.post(
        "/backup/restaurar/", {"name": name, "password": "errada", "passphrase": PASSPHRASE}
    )
    assert wrong["Location"] == "/backup/"
    preview = web.post(
        "/backup/restaurar/", {"name": name, "password": PASSWORD, "passphrase": PASSPHRASE}
    )
    body = preview.content.decode()
    assert preview.status_code == 200 and "Resumo do backup" in body
    assert "R$ -10,00" in body or "-R$ 10,00" in body or "10,00" in body
    assert "10/11/2026" in body
    assert LedgerTransaction.objects.count() == 2  # o resumo não substitui nada
    done = web.post(
        "/backup/restaurar/",
        {"name": name, "password": PASSWORD, "passphrase": PASSPHRASE, "confirm": "on"},
    )
    assert done["Location"] == "/acesso/entrar/"
    assert LedgerTransaction.objects.count() == 1


def test_backup_falho_pela_tela(web, vault, dirs):
    page = web.post("/backup/agora/", follow=True).content.decode()
    assert "Backup falhou" in page


# Saúde -----------------------------------------------------------------------------------


def test_relatorio_de_saude(db, with_passphrase, dirs):
    data = health.report()
    assert any("Nenhum backup bom" in i for i in data["issues"])
    assert any(
        "nuvem não configurada" in i.lower() or "Pasta da nuvem" in i for i in data["issues"]
    )
    assert health.level(data["issues"]) == "bad"
    assert health.level([]) == "ok"
    assert health.level(["Pasta da nuvem não configurada: o backup fica só neste PC."]) == "warn"


@pytest.mark.usefixtures("committed_db")
def test_alerta_de_nuvem_desatualizada(with_passphrase, dirs, fin):
    from apps.ui import models as prefs

    prefs.put("backup_cloud_dir", str(dirs[1]))
    core.create_backup()
    assert not any("72 horas" in i for i in health.report()["issues"])
    BackupRecord.objects.update(created_at=datetime.datetime(2026, 11, 16, tzinfo=datetime.UTC))
    assert any("72 horas" in i for i in health.report()["issues"])


def test_funnel_ligado_e_grave(db, with_passphrase, dirs, monkeypatch):
    monkeypatch.setattr(health, "funnel", lambda: "ligado")
    issues = health.report()["issues"]
    assert any("Funnel" in i for i in issues) and health.level(issues) == "bad"


def test_leitura_do_funnel(monkeypatch, _no_powershell):
    import subprocess

    outputs = iter(
        [
            (0, '{"AllowFunnel": {"pc.ts.net:443": true}}'),
            (0, "{}"),
            (0, "não é json"),
            (1, ""),
            (0, '["lista"]'),
        ]
    )

    def run(*a, **k):
        code, out = next(outputs)
        return subprocess.CompletedProcess(a, code, stdout=out, stderr="")

    monkeypatch.setattr(health.shutil, "which", lambda name: "tailscale")
    monkeypatch.setattr(health.subprocess, "run", run)
    results = []
    for _ in range(5):
        health._funnel_cache.clear()
        results.append(_no_powershell["funnel"]())
    health._funnel_cache.clear()
    assert results == ["ligado", "desligado"] + ["não verificado"] * 3


def test_criptografia_do_disco_responde(_no_powershell):
    health._encryption_cache.clear()
    assert _no_powershell["disk_encryption"]() in {
        "ativa",
        "desligada",
        "não disponível neste PC",
        "não verificado (fora do Windows)",
    }


# Comandos --------------------------------------------------------------------------------


@pytest.mark.usefixtures("committed_db")
def test_comandos_de_backup(with_passphrase, dirs, monkeypatch, fin):
    out = io.StringIO()
    call_command("backup_now", "--trigger", "pre_update", stdout=out)
    assert "local ok" in out.getvalue()
    name = core.available()[0].name
    out = io.StringIO()
    call_command("list_backups", stdout=out)
    assert name in out.getvalue()
    answers(monkeypatch, PASSPHRASE)
    out = io.StringIO()
    call_command("restore_backup", name, "--test", stdout=out)
    assert "Teste OK" in out.getvalue() and "Corrente" in out.getvalue()
    answers(monkeypatch, PASSPHRASE)
    monkeypatch.setattr("builtins.input", lambda prompt="": "não")
    with pytest.raises(CommandError, match="cancelada"):
        call_command("restore_backup", name)
    answers(monkeypatch, PASSPHRASE)
    monkeypatch.setattr("builtins.input", lambda prompt="": "RESTAURAR")
    out = io.StringIO()
    full_path = str(core.find(name).path)  # recuperação de desastre: caminho do arquivo
    call_command("restore_backup", full_path, stdout=out)
    assert "Restaurado" in out.getvalue()
    with pytest.raises(CommandError, match="não encontrado"):
        call_command("restore_backup", full_path.replace(".db.age", ".x.db.age"))


def test_backup_now_sem_senha(vault, dirs, db):
    with pytest.raises(CommandError, match="não configurada"):
        call_command("backup_now")


def test_check_invariants(db):
    out = io.StringIO()
    call_command("check_invariants", stdout=out)
    assert "Integridade OK" in out.getvalue()


def test_init_secrets(vault, monkeypatch):
    call_command("init_secrets", stdout=io.StringIO())
    key = secrets.get(secrets.SECRET_KEY)
    assert len(key) >= 64
    call_command("init_secrets", stdout=io.StringIO())
    assert secrets.get(secrets.SECRET_KEY) == key  # não troca a chave existente
    answers(monkeypatch, PASSPHRASE, "outra")
    with pytest.raises(CommandError, match="não são iguais"):
        call_command("init_secrets", "--backup-passphrase", stdout=io.StringIO())
    answers(monkeypatch, "curta", "curta")
    with pytest.raises(CommandError, match="16"):
        call_command("init_secrets", "--backup-passphrase", stdout=io.StringIO())
    answers(monkeypatch, PASSPHRASE, PASSPHRASE)
    call_command("init_secrets", "--backup-passphrase", stdout=io.StringIO())
    assert secrets.get(secrets.BACKUP_PASSPHRASE) == PASSPHRASE


def test_reset_password(user, with_passphrase, monkeypatch):
    TrustedDevice.objects.create(
        user=user,
        name="Celular",
        token_hash="x" * 64,
        pin_hash="x",
        expires_at=datetime.datetime(2027, 1, 1, tzinfo=datetime.UTC),
    )
    answers(monkeypatch, "errada")
    with pytest.raises(CommandError, match="incorreta"):
        call_command("reset_password")
    new = "nova frase de acesso bem longa"
    answers(monkeypatch, PASSPHRASE, new, new)
    call_command("reset_password", stdout=io.StringIO())
    user.refresh_from_db()
    assert user.check_password(new)
    assert TrustedDevice.objects.filter(revoked_at__isnull=True).count() == 0


def test_reset_password_sem_senha_de_backup(user, vault):
    with pytest.raises(CommandError, match="bloqueada"):
        call_command("reset_password")


# Bloqueio de manutenção -------------------------------------------------------------------


def test_bloqueio_de_manutencao(web, monkeypatch):
    from apps.backup import maintenance
    from apps.scheduler import jobs

    calls = []
    job = jobs.Job("teste", "Teste", jobs.daily_due, lambda: calls.append(1) or "ok")
    with maintenance.gate():
        page = web.get("/")
        assert page.status_code == 503 and page["Retry-After"] == "30"
        assert jobs.run_due(jobs=[job]) == [] and calls == []
        with pytest.raises(core.BackupError, match="em andamento"), maintenance.gate():
            pass
    assert web.get("/").status_code == 200
    jobs.run_due(jobs=[job])
    assert calls == [1]


@pytest.mark.usefixtures("committed_db")
def test_restauracao_ativa_o_bloqueio(with_passphrase, dirs, fin, monkeypatch):
    from apps.backup import maintenance

    record = core.create_backup()
    seen = []
    real = core.restore_into
    monkeypatch.setattr(
        core, "restore_into", lambda *a: seen.append(maintenance.active()) or real(*a)
    )
    core.restore_live(core.find(record.file_name), passphrase=PASSPHRASE)
    assert seen == [True] and not maintenance.active()
