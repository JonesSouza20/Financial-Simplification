"""Retenção de backups e agendador com recuperação (security-plan.md §7.1; ADR-018)."""

import datetime
import json
from zoneinfo import ZoneInfo

import pytest
import time_machine
from django.utils import timezone

from apps.backup import core
from apps.scheduler import jobs
from apps.scheduler.models import JobRun

SP = ZoneInfo("America/Sao_Paulo")


def fake_backup(directory, when, trigger="daily"):
    name = f"financas-{when:%Y%m%d-%H%M%S}-{trigger}"
    (directory / f"{name}.db.age").write_bytes(b"x")
    manifest = {"file": f"{name}.db.age", "created_at": when.isoformat(), "trigger": trigger}
    (directory / f"{name}.json").write_text(json.dumps(manifest))
    return name


def test_retencao_apos_400_dias(tmp_path, settings):
    now = datetime.datetime(2026, 11, 20, 3, 0, tzinfo=SP)
    for days in range(400):
        fake_backup(tmp_path, now - datetime.timedelta(days=days))
    fake_backup(tmp_path, now - datetime.timedelta(days=10), "pre_update")
    old_update = fake_backup(tmp_path, now - datetime.timedelta(days=120), "pre_update")
    core.apply_retention(tmp_path, now)
    kept = core.entries(tmp_path)
    regular = [e.created for e in kept if e.manifest["trigger"] == "daily"]
    assert {(now - d).days for d in regular if (now - d).days < 7} == set(range(7))
    weeks = {d.isocalendar()[:2] for d in regular}
    months = {(d.year, d.month) for d in regular}
    assert len(months) == 12 and len(weeks) >= 4
    older = [d for d in regular if (now - d).days > 40]
    assert older and all(d.day == 1 for d in older)  # mensais são do dia 1º
    assert sum(1 for d in regular if d.weekday() == 6) >= 4  # semanais de domingo
    assert len(regular) <= 7 + 4 + 12
    triggers = [e.manifest["trigger"] for e in kept]
    assert triggers.count("pre_update") == 1
    assert old_update not in {e.name for e in kept}
    assert not (tmp_path / f"{old_update}.json").exists()


def test_horarios_devidos():
    at = datetime.datetime(2026, 11, 20, 2, 59, tzinfo=SP)
    assert jobs.daily_due(at) == datetime.datetime(2026, 11, 19, 3, 0, tzinfo=SP)
    assert jobs.daily_due(at.replace(hour=3, minute=0)).day == 20
    assert jobs.monthly_due(datetime.datetime(2026, 11, 1, 3, 30, tzinfo=SP)) == datetime.datetime(
        2026, 10, 1, 4, 0, tzinfo=SP
    )
    assert jobs.monthly_due(datetime.datetime(2026, 11, 20, 9, 0, tzinfo=SP)) == datetime.datetime(
        2026, 11, 1, 4, 0, tzinfo=SP
    )


@pytest.mark.django_db
def test_recupera_tarefa_atrasada_uma_unica_vez():
    calls = []
    job = jobs.Job("teste", "Teste", jobs.daily_due, lambda: calls.append(1) or "feito")
    # PC desligado de 18/11 a 20/11 às 10:00: roda uma vez, para o horário mais recente.
    with time_machine.travel(datetime.datetime(2026, 11, 20, 10, 0, tzinfo=SP), tick=False):
        runs = jobs.run_due(timezone.localtime(), [job])
        again = jobs.run_due(timezone.localtime(), [job])
    assert len(calls) == 1 and again == []
    assert runs[0].status == "ok" and runs[0].scheduled_for.day == 20
    with time_machine.travel(datetime.datetime(2026, 11, 21, 3, 1, tzinfo=SP), tick=False):
        jobs.run_due(timezone.localtime(), [job])
    assert len(calls) == 2


@pytest.mark.django_db
def test_falha_da_tarefa_fica_registrada():
    def boom():
        raise RuntimeError("disco cheio")

    job = jobs.Job("quebra", "Quebra", jobs.daily_due, boom)
    jobs.run_due(timezone.localtime(), [job])
    run = JobRun.objects.get(job_name="quebra")
    assert run.status == "failed" and "disco cheio" in run.message and run.finished_at


@pytest.mark.django_db
def test_tarefas_reais_registradas(monkeypatch):
    calls = []
    fake = [
        jobs.Job(
            "daily_backup", "Backup diário", jobs.daily_due, lambda: calls.append("b") or "ok"
        ),
        jobs.Job(
            "monthly_restore_test",
            "Teste mensal",
            jobs.monthly_due,
            lambda: calls.append("t") or "ok",
        ),
    ]
    assert [j.name for j in jobs.JOBS] == [j.name for j in fake]
    monkeypatch.setattr(jobs, "JOBS", fake)
    jobs.run_due()
    assert calls == ["b", "t"]
    assert [run.status for _, run in jobs.last_runs()] == ["ok", "ok"]
