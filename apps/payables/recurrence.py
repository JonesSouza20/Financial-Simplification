"""Recorrências (business-rules.md §7, RN-050 a RN-055; RN-022; RN-173)."""

from __future__ import annotations

import datetime
import itertools

from django.conf import settings
from django.db import transaction
from django.db.models import F

from apps.accounts.models import FinancialAccount
from apps.calendar_br import services as calendar
from apps.categories.models import Category
from apps.categories.services import by_key
from apps.debts.models import Debt, DebtKind
from apps.ledger import audit
from apps.ledger import services as ledger
from apps.ledger.errors import ConcurrentEditError, InvalidTransactionError, LedgerError
from apps.ledger.models import TransactionStatus
from apps.money import Money

from . import services
from .horizon import horizon
from .models import (
    Commitment,
    CommitmentKind,
    DayRule,
    Direction,
    Frequency,
    RecurrenceRule,
    ValueType,
)

WINDOW_MONTHS = 13  # RN-051
ENDED = "recorrência encerrada"
CHANGED = "recorrência alterada"
ALLOWED_KINDS = (CommitmentKind.BILL, CommitmentKind.INCOME, CommitmentKind.CONSORTIUM)
EDITABLE = {
    "name",
    "amount_cents",
    "value_type",
    "frequency",
    "interval",
    "day_rule",
    "day_value",
    "category",
    "financial_account",
    "payment_method",
    "anticipates",
    "end_date",
    "remaining_count",
}


def window_end(today: datetime.date) -> datetime.date:
    return calendar.add_months(today, WINDOW_MONTHS)


def _validate(rule: RecurrenceRule) -> None:
    if rule.kind not in ALLOWED_KINDS:
        raise InvalidTransactionError("Este tipo de recorrência ainda não está disponível.")
    if not (rule.name or "").strip():
        raise InvalidTransactionError("Informe o nome da recorrência.")
    if rule.amount_cents <= 0:
        raise InvalidTransactionError("Informe um valor maior que zero.")
    if rule.value_type not in ValueType.values:
        raise InvalidTransactionError("Tipo de valor inválido.")
    if rule.frequency not in Frequency.values or rule.interval < 1:
        raise InvalidTransactionError("Periodicidade inválida.")
    if rule.financial_account is None:
        raise InvalidTransactionError("Escolha a conta prevista.")
    if rule.kind != CommitmentKind.CONSORTIUM and rule.category is None:
        raise InvalidTransactionError("Escolha a categoria.")
    if rule.end_date and rule.end_date < rule.start_date:
        raise InvalidTransactionError("O fim não pode ser antes do início.")
    if rule.remaining_count == 0:
        raise InvalidTransactionError("O número de ocorrências deve ser maior que zero.")
    if rule.frequency == Frequency.WEEKLY:
        return
    if rule.day_rule == DayRule.FIXED_DAY and not 1 <= (rule.day_value or 0) <= 31:
        raise InvalidTransactionError("Dia do mês inválido.")
    if rule.day_rule == DayRule.NTH_BUSINESS_DAY and not 1 <= (rule.day_value or 0) <= 23:
        raise InvalidTransactionError("Dia útil inválido.")
    if rule.day_rule not in DayRule.values:
        raise InvalidTransactionError("Regra de dia inválida.")


def _month_step(rule: RecurrenceRule) -> int:
    if rule.frequency == Frequency.MONTHLY:
        return 1
    if rule.frequency == Frequency.YEARLY:
        return 12 * rule.interval
    return rule.interval


def _date_in_month(rule: RecurrenceRule, year: int, month: int) -> datetime.date:
    if rule.day_rule == DayRule.NTH_BUSINESS_DAY:
        return calendar.nth_business_day(year, month, rule.day_value)
    if rule.day_rule == DayRule.LAST_DAY:
        return calendar.clamp_day(year, month, 31)
    return calendar.clamp_day(year, month, rule.day_value)  # RN-055


def _raw_dates(rule: RecurrenceRule):
    """Datas da regra em ordem, sem limite."""
    start = rule.start_date
    if rule.frequency == Frequency.WEEKLY:
        step = datetime.timedelta(weeks=rule.interval)
        for k in itertools.count():
            yield start + k * step
        return
    step = _month_step(rule)
    for k in itertools.count():
        first = calendar.add_months(start, k * step, day=1)
        yield _date_in_month(rule, first.year, first.month)


def occurrence_dates(rule: RecurrenceRule, until: datetime.date) -> list[datetime.date]:
    """Datas até `until`, respeitando início, fim e número de ocorrências."""
    dates = []
    count = 0
    for day in _raw_dates(rule):
        if day > until or (rule.end_date and day > rule.end_date):
            break
        if day < rule.start_date:
            continue
        if rule.remaining_count is not None and count >= rule.remaining_count:
            break
        count += 1
        dates.append(day)
    return dates


def preview(rule: RecurrenceRule, count: int = 12) -> list[datetime.date]:
    """Próximas datas antes de salvar: mostra o efeito de feriados e fins de semana (F-033)."""
    _validate(rule)
    dates = []
    for day in _raw_dates(rule):
        if len(dates) >= count or (rule.end_date and day > rule.end_date):
            break
        if day >= rule.start_date:
            dates.append(day)
    if rule.remaining_count is not None:
        dates = dates[: rule.remaining_count]
    return dates


def _has_live_occurrence(rule: RecurrenceRule, day: datetime.date) -> bool:
    return rule.commitments.filter(due_date=day, transaction__status__in=services.PLANNED).exists()


def _materialize(rule: RecurrenceRule, until: datetime.date) -> int:
    """Cria o que falta até `until`, sempre como previsto (RN-051)."""
    if not rule.active:
        return 0
    start = max(
        settings.FINANCAS_START_DATE,
        rule.start_date,
        (rule.generated_until + datetime.timedelta(days=1))
        if rule.generated_until
        else rule.start_date,
    )
    created = 0
    for day in occurrence_dates(rule, until):
        if day < start or _has_live_occurrence(rule, day):
            continue
        services._create(
            kind=rule.kind,
            description=rule.name,
            category=rule.category,
            account=rule.financial_account,
            amount=Money(rule.amount_cents),
            due_date=day,
            txn_status=TransactionStatus.FORECAST,
            value_type=rule.value_type,
            payment_method=rule.payment_method,
            anticipates=rule.anticipates,
            recurrence=rule,
            debt=rule.debt,
        )
        created += 1
    RecurrenceRule.objects.filter(pk=rule.pk).update(generated_until=until)
    rule.generated_until = until
    return created


def promote_due(today: datetime.date | None = None) -> int:
    """Saída fixa que entra em H vira pendente (RN-052). Variável espera o valor real."""
    today = today or ledger.today()
    limit = horizon(today).date
    candidates = Commitment.objects.filter(
        direction=Direction.OUT,
        value_type=ValueType.FIXED,
        transaction__status=TransactionStatus.FORECAST,
        closed_at__isnull=True,
        due_date__lt=limit,
    ).select_related("transaction")
    promoted = 0
    for commitment in candidates:
        if services.is_open(commitment):
            ledger.promote(commitment.transaction)
            promoted += 1
    return promoted


def create_rule(
    *,
    name: str,
    kind: str,
    amount: Money,
    frequency: str,
    day_rule: str,
    start_date: datetime.date,
    account: FinancialAccount,
    category: Category | None = None,
    day_value: int | None = None,
    interval: int = 1,
    value_type: str = ValueType.FIXED,
    end_date: datetime.date | None = None,
    remaining_count: int | None = None,
    payment_method: str | None = None,
    anticipates: bool = False,
    debt: Debt | None = None,
    today: datetime.date | None = None,
) -> RecurrenceRule:
    today = today or ledger.today()
    if kind == CommitmentKind.CONSORTIUM:
        if debt is None or debt.kind != DebtKind.CONSORTIUM:
            raise InvalidTransactionError("Escolha o consórcio desta recorrência.")
        category = by_key("consortium")
        value_type = ValueType.FIXED
    rule = RecurrenceRule(
        name=(name or "").strip(),
        kind=kind,
        frequency=frequency,
        interval=interval,
        day_rule=day_rule,
        day_value=day_value,
        amount_cents=amount.cents,
        value_type=value_type,
        category=category,
        financial_account=account,
        debt=debt,
        payment_method=payment_method,
        anticipates=anticipates,
        start_date=start_date,
        end_date=end_date,
        remaining_count=remaining_count,
    )
    _validate(rule)
    with transaction.atomic():
        rule.save()
        _materialize(rule, window_end(today))
        promote_due(today)
        audit.log("create", rule, after={"name": rule.name, "amount_cents": rule.amount_cents})
    return rule


def create_salary(
    *,
    account: FinancialAccount,
    amount: Money,
    start_date: datetime.date,
    name: str = "Salário",
    nth: int = 5,
    today: datetime.date | None = None,
) -> RecurrenceRule:
    """Salário no 5º dia útil (RN-022, RN-091)."""
    return create_rule(
        name=name,
        kind=CommitmentKind.INCOME,
        amount=amount,
        frequency=Frequency.MONTHLY,
        day_rule=DayRule.NTH_BUSINESS_DAY,
        day_value=nth,
        start_date=start_date,
        account=account,
        category=by_key("salary"),
        today=today,
    )


def create_consortium(
    *,
    debt: Debt,
    account: FinancialAccount,
    amount: Money,
    start_date: datetime.date,
    remaining_count: int,
    today: datetime.date | None = None,
) -> RecurrenceRule:
    """Consórcio como recorrência fixa com fim definido (ADR-008)."""
    return create_rule(
        name=f"Consórcio: {debt.description}",
        kind=CommitmentKind.CONSORTIUM,
        amount=amount,
        frequency=Frequency.MONTHLY,
        day_rule=DayRule.FIXED_DAY,
        day_value=debt.due_day,
        start_date=start_date,
        account=account,
        debt=debt,
        remaining_count=remaining_count,
        today=today,
    )


def _cancel_future(rule: RecurrenceRule, start: datetime.date, reason: str) -> int:
    """Cancela ocorrências a partir de `start` sem liquidação (RN-053, RN-054)."""
    cancelled = 0
    candidates = rule.commitments.filter(
        due_date__gte=start, transaction__status__in=services.PLANNED, closed_at__isnull=True
    ).select_related("transaction")
    for commitment in candidates:
        if not services.settled_cents(commitment):
            services.cancel(commitment, reason=reason)
            cancelled += 1
    return cancelled


def _fresh(rule: RecurrenceRule, expected_version: int | None) -> RecurrenceRule:
    current = RecurrenceRule.objects.get(pk=rule.pk)
    if expected_version is not None and current.version != expected_version:
        raise ConcurrentEditError(
            "Esta recorrência foi alterada em outro aparelho. Os dados foram recarregados."
        )
    return current


def update_rule(
    rule: RecurrenceRule,
    *,
    from_date: datetime.date | None = None,
    today: datetime.date | None = None,
    expected_version: int | None = None,
    **changes,
) -> RecurrenceRule:
    """Altera só o futuro sem liquidação (RN-053). O passado nunca muda."""
    today = today or ledger.today()
    start = from_date or today
    if start < today:
        raise InvalidTransactionError("A alteração só vale de hoje em diante.")
    unknown = set(changes) - EDITABLE
    if unknown:
        raise InvalidTransactionError(f"Campo não editável: {sorted(unknown)[0]}.")
    with transaction.atomic():
        current = _fresh(rule, expected_version)
        if not current.active:
            raise InvalidTransactionError("Esta recorrência está encerrada.")
        before = {key: str(getattr(current, key)) for key in changes}
        for key, value in changes.items():
            setattr(current, key, value)
        _validate(current)
        current.generated_until = start - datetime.timedelta(days=1)
        current.version = F("version") + 1
        current.save()
        current.refresh_from_db()
        _cancel_future(current, start, CHANGED)
        _materialize(current, window_end(today))
        promote_due(today)
        audit.log(
            "update",
            current,
            before=before,
            after={key: str(getattr(current, key)) for key in changes},
        )
    return current


def end_rule(
    rule: RecurrenceRule,
    *,
    today: datetime.date | None = None,
    reason: str = ENDED,
    expected_version: int | None = None,
) -> RecurrenceRule:
    """Encerra e cancela as ocorrências futuras sem liquidação (RN-054)."""
    today = today or ledger.today()
    with transaction.atomic():
        current = _fresh(rule, expected_version)
        _cancel_future(current, today, reason)
        current.active = False
        current.end_date = today
        current.version = F("version") + 1
        current.save()
        current.refresh_from_db()
        audit.log("end", current, reason=reason)
    return current


def renew(today: datetime.date | None = None) -> str:
    """Tarefa diária: janela móvel de 13 meses e previsto → pendente em H (RN-051, RN-052)."""
    today = today or ledger.today()
    created = 0
    problems = []
    for rule in RecurrenceRule.objects.filter(active=True):
        try:
            with transaction.atomic():
                created += _materialize(rule, window_end(today))
        except LedgerError as exc:
            problems.append(f"{rule.name}: {exc}")
    promoted = promote_due(today)
    if problems:
        # A tarefa fica como falha e aparece na tela de saúde; as outras regras seguiram.
        raise InvalidTransactionError("Recorrências com problema: " + "; ".join(problems))
    return f"{created} ocorrências criadas, {promoted} passaram a pendente"
