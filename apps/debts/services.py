"""Dívida e consórcio provisórios (RF-DIV-00; RN-117, RN-118; ADR-008).

Empréstimo: passivo com saldo de abertura (T26); a parcela é lançada com principal, juros e
encargos informados pelo extrato (T17). A tabela Price chega no MVP-5.
Consórcio: sem passivo; cada parcela é despesa da categoria Consórcio (T19).
"""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.db import transaction

from apps.accounts.models import FinancialAccount
from apps.categories.services import by_key
from apps.ledger import audit
from apps.ledger import services as ledger
from apps.ledger.errors import InvalidTransactionError
from apps.ledger.models import (
    EFFECTIVE_STATUSES,
    LedgerAccount,
    LedgerTransaction,
    TransactionType,
)
from apps.ledger.services import Leg
from apps.money import Money

from .models import Debt, DebtKind


def _rate(text: str | None) -> str | None:
    if text in (None, ""):
        return None
    try:
        value = Decimal(str(text).replace(",", "."))
    except InvalidOperation as exc:
        raise InvalidTransactionError(
            "Taxa inválida. Use, por exemplo, 2,00 para 2% ao mês."
        ) from exc
    if not Decimal("0") <= value <= Decimal("30"):
        raise InvalidTransactionError("Taxa fora do intervalo de 0% a 30% ao mês (RN-183).")
    return str(value / 100)


@transaction.atomic
def create_loan(
    *,
    creditor: str,
    description: str,
    balance: Money,
    due_day: int,
    monthly_rate_percent: str | None = None,
    remaining_installments: int | None = None,
    contract_installment: Money | None = None,
    on: datetime.date | None = None,
) -> Debt:
    if not balance.is_positive:
        raise InvalidTransactionError("Informe o saldo devedor atual.")
    if not 1 <= due_day <= 31:
        raise InvalidTransactionError("Dia de vencimento de 1 a 31.")
    account = LedgerAccount.objects.create(
        code=f"liability:debt:{uuid.uuid4().hex[:12]}",
        kind="liability",
        name=f"Dívida: {creditor.strip()}",
        owner_type="debt",
    )
    debt = Debt.objects.create(
        kind=DebtKind.LOAN,
        creditor=creditor.strip(),
        description=description.strip() or creditor,
        monthly_rate=_rate(monthly_rate_percent),
        amortization_system="price",
        remaining_installments=remaining_installments,
        contract_installment_cents=contract_installment.cents if contract_installment else None,
        due_day=due_day,
        ledger_account=account,
    )
    LedgerAccount.objects.filter(pk=account.pk).update(owner_id=debt.pk)
    equity = ledger.system_account("equity:opening")
    ledger.record(
        type=TransactionType.OPENING_DEBT,
        legs=[Leg(equity, balance), Leg(account, -balance)],
        operation_date=on or settings.FINANCAS_START_DATE,
        description=f"Abertura da dívida: {debt}",
    )
    audit.log("create", debt, after={"balance_cents": balance.cents})
    return debt


@transaction.atomic
def create_consortium(
    *,
    description: str,
    installment: Money,
    due_day: int,
    remaining_installments: int,
    creditor: str = "Consórcio",
) -> Debt:
    if not installment.is_positive or remaining_installments < 1:
        raise InvalidTransactionError("Informe o valor da parcela e as parcelas restantes.")
    debt = Debt.objects.create(
        kind=DebtKind.CONSORTIUM,
        creditor=creditor.strip() or "Consórcio",
        description=description.strip() or "Consórcio",
        contract_installment_cents=installment.cents,
        remaining_installments=remaining_installments,
        due_day=due_day,
    )
    audit.log("create", debt, after={"installment_cents": installment.cents})
    return debt


def balance(debt: Debt) -> Money:
    if debt.ledger_account_id is None:
        return Money(0)
    return ledger.display_balance(debt.ledger_account)


def pay_loan(
    *,
    debt: Debt,
    account: FinancialAccount,
    principal: Money,
    interest: Money,
    charges: Money | None = None,
    on: datetime.date,
    idempotency_key: str | None = None,
) -> LedgerTransaction:
    """Parcela do empréstimo (T17), com valores do extrato (RN-112, RN-117)."""
    if debt.kind != DebtKind.LOAN:
        raise InvalidTransactionError("Use o pagamento de consórcio para esta dívida.")
    charges = charges or Money(0)
    if principal.is_negative or interest.is_negative or charges.is_negative:
        raise InvalidTransactionError("Valores não podem ser negativos.")
    total = principal + interest + charges
    if not total.is_positive:
        raise InvalidTransactionError("Informe o valor pago.")
    if principal > balance(debt):
        raise InvalidTransactionError(f"O principal passa do saldo devedor ({balance(debt)}).")
    legs = []
    if principal.is_positive:
        legs.append(Leg(debt.ledger_account, principal, "principal"))
    if interest.is_positive:
        legs.append(Leg(by_key("debt_interest").ledger_account, interest, "juros"))
    if charges.is_positive:
        legs.append(Leg(by_key("debt_charges").ledger_account, charges, "encargos"))
    legs.append(Leg(account.ledger_account, -total))
    return ledger.record(
        type=TransactionType.DEBT_INSTALLMENT,
        legs=legs,
        operation_date=on,
        description=f"Parcela: {debt}",
        idempotency_key=idempotency_key,
    )


def consortium_legs(debt: Debt, account: FinancialAccount, amount: Money) -> list[Leg]:
    """Pernas da parcela (T19). Planejado e pago usam as mesmas, com o vínculo no memo."""
    return [
        Leg(by_key("consortium").ledger_account, amount, f"consórcio #{debt.pk}"),
        Leg(account.ledger_account, -amount),
    ]


def pay_consortium(
    *,
    debt: Debt,
    account: FinancialAccount,
    amount: Money,
    on: datetime.date,
    idempotency_key: str | None = None,
) -> LedgerTransaction:
    """Parcela do consórcio (T19): despesa da categoria Consórcio (ADR-008)."""
    if debt.kind != DebtKind.CONSORTIUM:
        raise InvalidTransactionError("Esta dívida não é um consórcio.")
    if not amount.is_positive:
        raise InvalidTransactionError("Informe o valor pago.")
    return ledger.record(
        type=TransactionType.CONSORTIUM_INSTALLMENT,
        legs=consortium_legs(debt, account, amount),
        operation_date=on,
        description=f"Parcela: {debt.description}",
        idempotency_key=idempotency_key,
    )


def history(debt: Debt):
    if debt.ledger_account_id is None:
        consortium = by_key("consortium").ledger_account
        return LedgerTransaction.objects.filter(
            status__in=EFFECTIVE_STATUSES,
            type=TransactionType.CONSORTIUM_INSTALLMENT,
            postings__account=consortium,
            postings__memo=f"consórcio #{debt.pk}",
        ).order_by("-operation_date", "-id")
    return LedgerTransaction.objects.filter(
        status__in=EFFECTIVE_STATUSES, postings__account=debt.ledger_account
    ).order_by("-operation_date", "-id")


def active():
    return Debt.objects.filter(archived_at__isnull=True)
