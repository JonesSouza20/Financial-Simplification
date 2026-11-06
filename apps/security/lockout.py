"""Bloqueio progressivo de login (security-plan.md §3.3).

5 falhas → 15 min. Cada novo bloqueio nas últimas 24 h dobra o tempo, até 24 h.
"""

import datetime

from django.shortcuts import render
from django.utils import timezone

from apps.ledger.models import AuditLog

BASE = datetime.timedelta(minutes=15)
CAP = datetime.timedelta(hours=24)


def recent_lockouts() -> int:
    since = timezone.now() - datetime.timedelta(hours=24)
    return AuditLog.objects.filter(action="lockout", at__gte=since).count()


def cooloff(request=None, *args, **kwargs) -> datetime.timedelta:
    count = max(1, recent_lockouts())
    return min(BASE * (2 ** (count - 1)), CAP)


def lockout_response(request, *args, **kwargs):
    minutes = int(cooloff(request).total_seconds() // 60)
    return render(request, "security/locked.html", {"minutes": minutes}, status=403)
