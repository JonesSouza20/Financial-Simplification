"""Saldo comprometido, disponível e "Pode gastar" (RN-143, RN-145, RN-154; ADR-041).

Nada aqui é gravado: tudo deriva do Ledger, dos compromissos e da estimativa das faturas.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass

from apps.accounts import services as accounts
from apps.cards import services as cards
from apps.ledger import services as ledger
from apps.ledger.models import TransactionStatus
from apps.money import Money
from apps.payables import horizon as horizons
from apps.payables import services as payables
from apps.payables.models import Commitment, Direction
from apps.ui import models as prefs

MINIMUM_KEY = "safety_minimum_cents"
OK, AT_LIMIT, BELOW_MINIMUM, UNCOVERED = "ok", "at_limit", "below_minimum", "uncovered"


@dataclass(frozen=True)
class Line:
    """Uma linha da explicação do cálculo."""

    label: str
    amount: Money
    estimated: bool = False
    due_date: datetime.date | None = None
    commitment: Commitment | None = None
    card: object | None = None


@dataclass(frozen=True)
class Position:
    today: datetime.date
    horizon: datetime.date
    salary_late: bool
    free: Money
    reserve: Money
    benefit: Money
    invoices: tuple[Line, ...]
    pending: tuple[Line, ...]
    estimates: tuple[Line, ...]
    committed: Money
    available: Money
    minimum: Money
    can_spend: Money
    state: str
    shortfall: Money  # quanto falta, nos estados abaixo do mínimo ou sem cobertura

    @property
    def estimated_total(self) -> Money:
        return Money.sum([line.amount for line in self.estimates])

    @property
    def days_to_horizon(self) -> int:
        return (self.horizon - self.today).days


def get_minimum() -> Money:
    return Money(int(prefs.get(MINIMUM_KEY, 0) or 0))


def set_minimum(amount: Money) -> None:
    if amount.is_negative:
        from apps.ledger.errors import InvalidTransactionError

        raise InvalidTransactionError("O mínimo de segurança não pode ser negativo.")
    prefs.put(MINIMUM_KEY, amount.cents)


def _class_totals() -> dict[str, Money]:
    rows = [(a.asset_class, accounts.balance(a)) for a in accounts.active_accounts()]
    return {k: Money.sum([b for c, b in rows if c == k]) for k in ("free", "reserve", "benefit")}


def _invoice_lines(limit: datetime.date, today: datetime.date) -> list[Line]:
    lines = []
    for card in cards.active_cards():
        for invoice in cards.estimate(card, today):
            if invoice.due_date < limit and invoice.amount.is_positive:
                lines.append(
                    Line(
                        label=f"Fatura {card.name}",
                        amount=invoice.amount,
                        estimated=True,
                        due_date=invoice.due_date,
                        card=card,
                    )
                )
    return sorted(lines, key=lambda line: line.due_date)


def _commitment_lines(limit: datetime.date, status: str) -> list[Line]:
    """Compromissos de saída em aberto com vencimento original antes do horizonte."""
    candidates = Commitment.objects.filter(
        direction=Direction.OUT,
        transaction__status=status,
        closed_at__isnull=True,
        due_date__lt=limit,
    ).select_related("transaction")
    lines = []
    for commitment in candidates:
        remaining = payables.open_amount(commitment)
        if remaining.is_positive:
            lines.append(
                Line(
                    label=commitment.transaction.description,
                    amount=remaining,
                    estimated=status == TransactionStatus.FORECAST,
                    due_date=commitment.due_date,
                    commitment=commitment,
                )
            )
    return sorted(lines, key=lambda line: line.due_date)


def position(today: datetime.date | None = None) -> Position:
    """Fotografia dos saldos no dia. Disponível fica igual à RN-145; o resto é derivado."""
    today = today or ledger.today()
    h = horizons.horizon(today)
    totals = _class_totals()
    invoices = _invoice_lines(h.date, today)
    pending = _commitment_lines(h.date, TransactionStatus.PENDING)
    estimates = _commitment_lines(h.date, TransactionStatus.FORECAST)
    committed = Money.sum([line.amount for line in [*invoices, *pending]])
    available = totals["free"] - committed
    minimum = get_minimum()
    after_estimates = available - Money.sum([line.amount for line in estimates])
    can_spend = after_estimates - minimum
    if after_estimates.is_negative:
        state, shortfall = UNCOVERED, -after_estimates
    elif can_spend.is_negative:
        state, shortfall = BELOW_MINIMUM, -can_spend
    elif can_spend.is_zero:
        state, shortfall = AT_LIMIT, Money(0)
    else:
        state, shortfall = OK, Money(0)
    return Position(
        today=today,
        horizon=h.date,
        salary_late=h.salary_late,
        free=totals["free"],
        reserve=totals["reserve"],
        benefit=totals["benefit"],
        invoices=tuple(invoices),
        pending=tuple(pending),
        estimates=tuple(estimates),
        committed=committed,
        available=available,
        minimum=minimum,
        can_spend=can_spend,
        state=state,
        shortfall=shortfall,
    )
