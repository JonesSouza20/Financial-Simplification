"""Valores a receber no MVP-1 (RF-REC-01, 02, 04): empréstimo simples, parte de terceiro no
cartão e recebimento. Nada aqui é receita (RN-104)."""

from __future__ import annotations

import datetime
from dataclasses import dataclass

from django.db import transaction
from django.db.models import Q, Sum

from apps.accounts.models import FinancialAccount
from apps.ledger import services as ledger
from apps.ledger.errors import InvalidTransactionError
from apps.ledger.models import LedgerTransaction, TransactionStatus, TransactionType
from apps.ledger.services import Leg
from apps.money import Money
from apps.persons.models import Person

from .models import Receivable, ReceivableAllocation, ReceivableInstallment

CONFIRMED = Q(allocations__transaction__status=TransactionStatus.CONFIRMED)


def create(
    *,
    person: Person,
    origin_kind: str,
    origin_transaction: LedgerTransaction,
    total: Money,
    due_date: datetime.date,
    description: str,
) -> Receivable:
    receivable = Receivable.objects.create(
        person=person,
        origin_kind=origin_kind,
        origin_transaction=origin_transaction,
        total_cents=total.cents,
        description=description[:200],
    )
    ReceivableInstallment.objects.create(
        receivable=receivable, number=1, due_date=due_date, amount_cents=total.cents
    )
    return receivable


@transaction.atomic
def lend(
    *,
    person: Person,
    account: FinancialAccount,
    amount: Money,
    on: datetime.date,
    due_date: datetime.date,
    description: str = "",
    idempotency_key: str | None = None,
) -> LedgerTransaction:
    """Empréstimo a terceiro (T14): sai da conta e vira valor a receber; não é despesa."""
    if not amount.is_positive:
        raise InvalidTransactionError("Informe um valor maior que zero.")
    if account.asset_class == "benefit":
        raise InvalidTransactionError("Benefícios (VR/VA) não podem ser emprestados.")
    description = description.strip() or f"Empréstimo para {person.name}"
    txn = ledger.record(
        type=TransactionType.LOAN_TO_PERSON,
        legs=[Leg(person.ledger_account, amount), Leg(account.ledger_account, -amount)],
        operation_date=on,
        description=description,
        idempotency_key=idempotency_key,
    )
    if not Receivable.objects.filter(origin_transaction=txn).exists():
        create(
            person=person,
            origin_kind="loan",
            origin_transaction=txn,
            total=amount,
            due_date=due_date,
            description=description,
        )
    return txn


def _allocated(installment: ReceivableInstallment) -> int:
    return (
        installment.allocations.filter(transaction__status=TransactionStatus.CONFIRMED).aggregate(
            total=Sum("amount_cents")
        )["total"]
        or 0
    )


def open_installments(person: Person):
    """Parcelas com valor em aberto, da mais antiga para a mais nova (RN-103)."""
    result = []
    for inst in (
        ReceivableInstallment.objects.filter(receivable__person=person)
        .select_related("receivable")
        .order_by("due_date", "id")
    ):
        remaining = inst.amount_cents - _allocated(inst)
        if remaining > 0:
            result.append((inst, Money(remaining)))
    return result


def open_total(person: Person) -> Money:
    return Money.sum([m for _, m in open_installments(person)])


@transaction.atomic
def receive(
    *,
    person: Person,
    account: FinancialAccount,
    amount: Money,
    on: datetime.date,
    idempotency_key: str | None = None,
) -> LedgerTransaction:
    """Recebimento (T15): volta para a conta e reduz o a receber; nunca é receita (RN-104)."""
    if not amount.is_positive:
        raise InvalidTransactionError("Informe um valor maior que zero.")
    if account.asset_class == "benefit":
        raise InvalidTransactionError("Escolha uma conta de dinheiro, não VR/VA.")
    pending = open_installments(person)
    owed = Money.sum([m for _, m in pending])
    existing = ledger._idempotent_result(idempotency_key, "record") if idempotency_key else None
    if existing is not None:
        return existing
    if amount > owed:
        raise InvalidTransactionError(
            f"{person.name} deve {owed}. Valor acima do devido não é aceito nesta versão."
        )
    txn = ledger.record(
        type=TransactionType.PERSON_RECEIPT,
        legs=[Leg(account.ledger_account, amount), Leg(person.ledger_account, -amount)],
        operation_date=on,
        description=f"Recebido de {person.name}",
        idempotency_key=idempotency_key,
    )
    left = amount.cents
    for inst, remaining in pending:
        if left <= 0:
            break
        take = min(left, remaining.cents)
        ReceivableAllocation.objects.create(
            installment=inst, transaction=txn, kind="receipt", amount_cents=take
        )
        left -= take
    return txn


def on_reversal(original: LedgerTransaction, reversal: LedgerTransaction) -> None:
    """Estorno de compra de terceiro ou de empréstimo reduz o a receber (RN-085).

    Recebimentos estornados deixam de contar sozinhos (alocação de transação não confirmada).
    """
    receivables = list(Receivable.objects.filter(origin_transaction=original))
    if not receivables:
        return
    by_account = {}
    for p in reversal.postings.select_related("account"):
        if p.account.owner_type == "person" and p.amount_cents < 0:
            by_account[p.account_id] = -p.amount_cents
    for receivable in receivables:
        left = by_account.get(receivable.person.ledger_account_id, 0)
        for inst in receivable.installments.order_by("-due_date", "-id"):
            if left <= 0:
                break
            remaining = inst.amount_cents - _allocated(inst)
            take = min(left, remaining)
            if take > 0:
                ReceivableAllocation.objects.create(
                    installment=inst,
                    transaction=reversal,
                    kind="purchase_reversal",
                    amount_cents=take,
                )
                left -= take
        by_account[receivable.person.ledger_account_id] = left


@dataclass
class PersonSummary:
    person: Person
    open: Money
    overdue: Money


def summaries(today: datetime.date) -> list[PersonSummary]:
    rows = []
    for person in Person.objects.filter(archived_at__isnull=True):
        pending = open_installments(person)
        rows.append(
            PersonSummary(
                person=person,
                open=Money.sum([m for _, m in pending]),
                overdue=Money.sum([m for inst, m in pending if inst.due_date < today]),
            )
        )
    return rows


def check() -> list:
    """I-06 (a receber): Σ parcelas em aberto de cada pessoa = saldo da conta A receber."""
    from apps.ledger.invariants import Violation

    violations = []
    for person in Person.objects.all():
        ledger_balance = ledger.account_balance(person.ledger_account)
        if ledger_balance != open_total(person):
            violations.append(
                Violation(
                    "I-06",
                    f"a receber de {person.name}: alocações {open_total(person)} × "
                    f"Ledger {ledger_balance}",
                )
            )
    return violations
