"""Avisos (F-080): o que avisar, quando, sem repetir e respeitando o silêncio noturno."""

from __future__ import annotations

import datetime
import logging

from django.db.models import Q
from django.utils import timezone

from apps.backup.models import BackupRecord
from apps.ledger import services as ledger
from apps.ledger.models import TransactionStatus
from apps.payables import services as payables
from apps.payables.models import Commitment, Direction
from apps.scheduler.models import JobRun
from apps.ui import models as prefs

from . import telegram
from .models import Notification, NotificationKind, NotificationStatus
from .telegram import TelegramError

log = logging.getLogger(__name__)

DAYS_KEY = "alert_days_before"
QUIET_START_KEY = "alert_quiet_start"
QUIET_END_KEY = "alert_quiet_end"
DEFAULT_DAYS, DEFAULT_QUIET_START, DEFAULT_QUIET_END = 3, 22, 7
RETRY = datetime.timedelta(minutes=15)
EXPIRES = datetime.timedelta(hours=24)
BACKUP_GAP = datetime.timedelta(hours=36)
WEEKDAYS = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]
BACKUP_JOBS = {
    "daily_backup": "Backup de hoje falhou",
    "monthly_restore_test": "Teste de restauração falhou",
}


def days_before() -> int:
    return int(prefs.get(DAYS_KEY, DEFAULT_DAYS))


def quiet_hours() -> tuple[int, int]:
    return (
        int(prefs.get(QUIET_START_KEY, DEFAULT_QUIET_START)),
        int(prefs.get(QUIET_END_KEY, DEFAULT_QUIET_END)),
    )


def is_quiet(hour: int, start: int, end: int) -> bool:
    if start == end:
        return False
    return start <= hour < end if start < end else hour >= start or hour < end


def enqueue(kind: str, summary: str, dedup_key: str) -> bool:
    """Põe o aviso na fila. Quem envia é o agendador; nunca a tela nem o login."""
    if not telegram.configured():
        return False
    _, created = Notification.objects.get_or_create(
        dedup_key=dedup_key[:120], defaults={"kind": kind, "summary": summary[:300]}
    )
    return created


def enqueue_safely(kind: str, summary: str, dedup_key: str) -> None:
    """Para login e aparelhos: um problema no aviso jamais atrapalha o acesso."""
    try:
        enqueue(kind, summary, dedup_key)
    except Exception:  # noqa: BLE001 - segurança do acesso vem antes do aviso
        log.warning("Não foi possível registrar o aviso de segurança.")


def _value(commitment: Commitment) -> str:
    amount = payables.open_amount(commitment)
    forecast = commitment.transaction.status == TransactionStatus.FORECAST
    return f"cerca de {amount}" if forecast and commitment.value_type == "variable" else str(amount)


def _due_alerts(today: datetime.date, days: int) -> int:
    limit = today + datetime.timedelta(days=days)
    created = 0
    candidates = Commitment.objects.filter(
        direction=Direction.OUT,
        transaction__status__in=payables.PLANNED,
        closed_at__isnull=True,
        due_date__lte=limit,
    ).select_related("transaction")
    for c in candidates:
        if not payables.is_open(c):
            continue
        name = c.transaction.description
        if payables.status(c, today) == payables.OVERDUE:
            text = f"Atrasado: {name} {_value(c)}, venceu em {c.effective_due_date:%d/%m}."
            created += enqueue(NotificationKind.OVERDUE, text, f"late:{c.pk}")
            continue
        if c.effective_due_date < today or c.scheduled_debit_date:
            continue
        moment = "today" if c.due_date <= today else "soon"
        weekday = WEEKDAYS[c.due_date.weekday()]
        text = f"{name} {_value(c)} vence em {c.due_date:%d/%m} ({weekday})."
        if c.effective_due_date != c.due_date:
            text += f" Pode pagar até {c.effective_due_date:%d/%m}."
        created += enqueue(NotificationKind.DUE, text, f"{moment}:{c.pk}:{c.due_date.isoformat()}")
    return created


def _backup_alerts(now: datetime.datetime) -> int:
    created = 0
    since = now - datetime.timedelta(days=2)
    for run in JobRun.objects.filter(
        job_name__in=BACKUP_JOBS, status="failed", started_at__gte=since
    ):
        text = f"{BACKUP_JOBS[run.job_name]}: {telegram.scrub(run.message)}"
        created += enqueue(NotificationKind.BACKUP, text, f"job:{run.pk}")
    last = BackupRecord.objects.filter(checks_passed=True, local_ok=True).first()
    if last is None or now - last.created_at > BACKUP_GAP:
        text = "Nenhum backup bom nas últimas 36 horas."
        created += enqueue(NotificationKind.BACKUP, text, f"nobackup:{now.date().isoformat()}")
    return created


def collect(now: datetime.datetime | None = None) -> str:
    """Tarefa diária das 08:00, ou assim que o PC voltar, se estava desligado."""
    if not telegram.configured():
        return "Telegram não configurado"
    now = now or timezone.localtime()
    created = _due_alerts(ledger.today(), days_before()) + _backup_alerts(now)
    return f"{created} avisos na fila"


def flush(now: datetime.datetime | None = None) -> int:
    """Envia o que está na fila. Na falha, para e tenta de novo em 15 minutos."""
    now = now or timezone.localtime()
    queue = Notification.objects.filter(status=NotificationStatus.PENDING).filter(
        Q(next_try_at__isnull=True) | Q(next_try_at__lte=now)
    )
    start, end = quiet_hours()
    quiet = is_quiet(timezone.localtime(now).hour, start, end)
    sent = 0
    for item in queue.order_by("created_at", "id"):
        if now - item.created_at > EXPIRES:
            item.status = NotificationStatus.FAILED
            item.last_error = item.last_error or "Expirou sem conseguir enviar."
            item.save(update_fields=["status", "last_error"])
            continue
        if quiet and item.kind != NotificationKind.SECURITY:
            continue
        try:
            telegram.send(item.summary)
        except TelegramError as exc:
            message = telegram.scrub(exc)[:200]
            item.last_error, item.next_try_at = message, now + RETRY
            item.save(update_fields=["last_error", "next_try_at"])
            log.warning("Aviso não enviado: %s", message)
            break
        item.status, item.sent_at, item.next_try_at = NotificationStatus.SENT, now, None
        item.save(update_fields=["status", "sent_at", "next_try_at"])
        sent += 1
    return sent
