"""Tarefas agendadas e execução com recuperação (ADR-018; architecture.md §11).

Cada tarefa tem um "horário devido" calculado. Ao rodar, o agendador executa a tarefa se o
horário devido mais recente ainda não tem execução registrada. Assim, se o PC estava
desligado às 03:00, o backup roda assim que o sistema voltar. A restrição única
(job_name, scheduled_for) garante uma execução por horário, mesmo com dois processos.
"""

from __future__ import annotations

import datetime
import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

from django.conf import settings
from django.db import IntegrityError, close_old_connections, transaction
from django.utils import timezone

from .models import JobRun

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Job:
    name: str
    label: str
    due: Callable[[datetime.datetime], datetime.datetime]  # horário devido mais recente ≤ now
    run: Callable[[], str]


def _at(now: datetime.datetime, hour: int, minute: int = 0) -> datetime.datetime:
    return now.replace(hour=hour, minute=minute, second=0, microsecond=0)


def daily_due(now: datetime.datetime) -> datetime.datetime:
    slot = _at(now, settings.FINANCAS_BACKUP_HOUR)
    return slot if slot <= now else slot - datetime.timedelta(days=1)


def monthly_due(now: datetime.datetime) -> datetime.datetime:
    """Dia 1º, uma hora depois do backup diário."""
    slot = _at(now.replace(day=1), settings.FINANCAS_BACKUP_HOUR + 1)
    if slot <= now:
        return slot
    prev = (now.replace(day=1) - datetime.timedelta(days=1)).replace(day=1)
    return _at(prev, settings.FINANCAS_BACKUP_HOUR + 1)


def _daily_backup() -> str:
    from apps.backup.core import create_backup

    record = create_backup("daily")
    return f"{record.file_name} ({record.size_bytes} bytes)"


def _monthly_restore_test() -> str:
    from apps.backup.core import monthly_restore_test

    test = monthly_restore_test()
    return f"teste de restauração de {test.file_name}: ok"


JOBS = [
    Job("daily_backup", "Backup diário", daily_due, _daily_backup),
    Job("monthly_restore_test", "Teste mensal de restauração", monthly_due, _monthly_restore_test),
]


def run_due(now: datetime.datetime | None = None, jobs: list[Job] | None = None) -> list[JobRun]:
    """Executa as tarefas cujo horário devido ainda não rodou. Devolve as execuções feitas."""
    now = now or timezone.localtime()
    done = []
    for job in jobs or JOBS:
        slot = job.due(now)
        try:
            with transaction.atomic():
                run = JobRun.objects.create(job_name=job.name, scheduled_for=slot)
        except IntegrityError:
            continue  # já executada (ou em execução) para este horário
        try:
            message = job.run()
            run.status, run.message = "ok", (message or "")[:300]
        except Exception as exc:  # noqa: BLE001 - toda falha fica registrada e visível
            log.exception("Tarefa %s falhou", job.name)
            run.status, run.message = "failed", str(exc)[:300]
        run.finished_at = timezone.now()
        run.save(update_fields=["status", "message", "finished_at"])
        done.append(run)
    return done


def last_runs() -> list[tuple[Job, JobRun | None]]:
    return [(job, JobRun.objects.filter(job_name=job.name).first()) for job in JOBS]


_thread: threading.Thread | None = None


def start(interval_seconds: int = 60) -> None:
    """Inicia o agendador numa thread do serviço (uma vez por processo)."""
    global _thread
    if _thread is not None:
        return

    def loop():
        while True:
            try:
                close_old_connections()
                run_due()
            except Exception:  # noqa: BLE001 - o agendador nunca derruba o serviço
                log.exception("Falha no agendador")
            finally:
                close_old_connections()
            time.sleep(interval_seconds)

    _thread = threading.Thread(target=loop, name="financas-agendador", daemon=True)
    _thread.start()
