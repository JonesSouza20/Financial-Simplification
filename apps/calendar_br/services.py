"""Dias úteis e vencimentos (business-rules.md §17, RN-090 a RN-094)."""

from __future__ import annotations

import calendar
import datetime

from django.db import transaction

from apps.ledger import audit
from apps.ledger.errors import InvalidStateError, InvalidTransactionError

from . import defaults
from .models import Holiday, HolidayScope
from .signals import holidays_changed

SEED_YEARS = range(2026, 2041)  # cobre a janela de 13 meses; depois disso, erro explícito
ONE_DAY = datetime.timedelta(days=1)
BANKING, SALARY = "affects_banking", "affects_salary"


class CalendarMissingError(InvalidStateError):
    """Ano sem feriados carregados: melhor recusar do que calcular data errada."""


def seed(years=SEED_YEARS) -> int:
    """Carrega os anos ainda sem nenhum feriado. Não toca em ano já carregado (RN-092)."""
    created = 0
    for year in years:
        if Holiday.objects.filter(date__year=year).exists():
            continue
        Holiday.objects.bulk_create(
            Holiday(date=when, name=name, scope=scope)
            for when, name, scope in defaults.for_year(year)
        )
        created += 1
    return created


def _closed_dates(year: int, field: str) -> set[datetime.date]:
    rows = list(Holiday.objects.filter(date__year=year).values_list("date", field))
    if not rows:
        raise CalendarMissingError(f"O calendário de {year} não está carregado.")
    return {when for when, affects in rows if affects}


def is_business_day(day: datetime.date, *, field: str = BANKING) -> bool:
    """Segunda a sexta, exceto feriados da tabela e Carnaval (RN-090)."""
    closed = _closed_dates(day.year, field)  # confere o ano mesmo em fim de semana
    return day.weekday() < 5 and day not in closed


def nth_business_day(year: int, month: int, nth: int) -> datetime.date:
    """N-ésimo dia útil do mês, contado do dia 1º. Salário usa nth = 5 (RN-091)."""
    if nth < 1:
        raise InvalidTransactionError("O dia útil deve ser 1 ou maior.")
    closed = _closed_dates(year, SALARY)
    last = calendar.monthrange(year, month)[1]
    count = 0
    for number in range(1, last + 1):
        day = datetime.date(year, month, number)
        if day.weekday() < 5 and day not in closed:
            count += 1
            if count == nth:
                return day
    raise InvalidTransactionError(f"{month:02d}/{year} não tem {nth} dias úteis.")


def effective_due(due: datetime.date, *, anticipate: bool = False) -> datetime.date:
    """Vencimento efetivo: próximo dia útil, ou o anterior nas contas que antecipam (RN-093)."""
    step = -ONE_DAY if anticipate else ONE_DAY
    day = due
    while not is_business_day(day):
        day += step
    return day


def clamp_day(year: int, month: int, day: int) -> datetime.date:
    """Dia inexistente no mês vai para o último dia (RN-055)."""
    return datetime.date(year, month, min(day, calendar.monthrange(year, month)[1]))


def add_months(start: datetime.date, months: int, *, day: int | None = None) -> datetime.date:
    index = start.year * 12 + start.month - 1 + months
    year, month = divmod(index, 12)
    return clamp_day(year, month + 1, day if day is not None else start.day)


def needs_yearly_review(today: datetime.date) -> bool:
    """Em dezembro, lembrar de revisar os feriados do ano seguinte (RN-094)."""
    return today.month == 12


@transaction.atomic
def add_holiday(
    day: datetime.date, name: str, *, affects_salary: bool = True, affects_banking: bool = True
) -> Holiday:
    name = (name or "").strip()
    if not name:
        raise InvalidTransactionError("Informe o nome do feriado.")
    if Holiday.objects.filter(date=day).exists():
        raise InvalidStateError("Já existe um feriado nesta data.")
    holiday = Holiday.objects.create(
        date=day,
        name=name,
        scope=HolidayScope.CUSTOM,
        affects_salary=affects_salary,
        affects_banking=affects_banking,
    )
    audit.record_event("holiday_add", "holiday", 0, after={"date": day.isoformat(), "name": name})
    holidays_changed.send(sender=Holiday)
    return holiday


@transaction.atomic
def remove_holiday(day: datetime.date) -> None:
    holiday = Holiday.objects.filter(date=day).first()
    if holiday is None:
        raise InvalidStateError("Feriado não encontrado.")
    if Holiday.objects.filter(date__year=day.year).count() == 1:
        raise InvalidStateError("O ano precisa manter ao menos um feriado na tabela.")
    name = holiday.name
    holiday.delete()
    audit.record_event(
        "holiday_remove", "holiday", 0, after={"date": day.isoformat(), "name": name}
    )
    holidays_changed.send(sender=Holiday)
