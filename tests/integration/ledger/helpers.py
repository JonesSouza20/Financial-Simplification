"""Atalhos para montar transações nos testes."""

import datetime

from apps.ledger import services
from apps.ledger.models import TransactionType
from apps.ledger.services import Leg
from apps.money import Money

NOV = datetime.date(2026, 11, 1)


def day(n: int) -> datetime.date:
    return NOV.replace(day=n)


def simple(debit, credit, cents, *, type=TransactionType.EXPENSE_PAID, on=None, **kwargs):
    """Transação de duas pernas: `debit` +cents, `credit` −cents."""
    return services.record(
        type=type,
        legs=[Leg(debit, Money(cents)), Leg(credit, Money(-cents))],
        operation_date=on or day(3),
        description=kwargs.pop("description", "Teste"),
        **kwargs,
    )


def balance(account) -> int:
    return services.account_balance(account).cents
