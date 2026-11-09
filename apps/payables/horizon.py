"""Horizonte H (RN-140; ADR-036). Única definição: o saldo disponível (Fase 2B) reutiliza."""

from __future__ import annotations

import datetime
from dataclasses import dataclass

from apps.calendar_br.services import add_months
from apps.categories.services import by_key
from apps.ledger import services as ledger
from apps.ui import models as prefs

from .models import Commitment, Direction
from .services import PLANNED, is_open

NEXT_SALARY, MONTH_END = "next_salary", "month_end"


@dataclass(frozen=True)
class Horizon:
    date: datetime.date  # exclusivo: entram vencimentos originais < date
    salary_late: bool = False


def _first_of_next_month(today: datetime.date) -> datetime.date:
    return add_months(today, 1, day=1)


def oldest_open_salary() -> Commitment | None:
    """Salário previsto mais antigo ainda não recebido."""
    salary = by_key("salary").ledger_account
    candidates = (
        Commitment.objects.filter(
            direction=Direction.IN,
            transaction__status__in=PLANNED,
            transaction__postings__account=salary,
            closed_at__isnull=True,
        )
        .select_related("transaction")
        .order_by("due_date", "id")
    )
    return next((c for c in candidates if is_open(c)), None)


def horizon(today: datetime.date | None = None) -> Horizon:
    """Só avança para o salário seguinte quando este é confirmado. Atrasado: H = amanhã."""
    today = today or ledger.today()
    if prefs.get("horizon_mode", NEXT_SALARY) == MONTH_END:
        return Horizon(_first_of_next_month(today))
    salary = oldest_open_salary()
    if salary is None:
        return Horizon(_first_of_next_month(today))
    if salary.due_date < today:
        return Horizon(today + datetime.timedelta(days=1), salary_late=True)
    return Horizon(salary.due_date)
