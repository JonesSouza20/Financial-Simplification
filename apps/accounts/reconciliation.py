"""Conciliação de saldo (F-022; RN-130 a RN-133; T27)."""

from __future__ import annotations

import datetime

from django.db import transaction

from apps.ledger import services as ledger
from apps.ledger.errors import InvalidTransactionError
from apps.ledger.models import LedgerTransaction, TransactionType
from apps.ledger.services import Leg
from apps.money import Money

from .models import BalanceReconciliation, FinancialAccount


def calculated(account: FinancialAccount, on: datetime.date) -> Money:
    """Saldo calculado até o fim do dia `on` (RN-130)."""
    return ledger.account_balance(account.ledger_account, as_of=on)


@transaction.atomic
def reconcile(
    *,
    account: FinancialAccount,
    on: datetime.date,
    informed: Money,
    adjust: bool = False,
    notes: str = "",
) -> BalanceReconciliation:
    """Grava o marco. Com diferença, só ajusta se o usuário pedir, com descrição (RN-131)."""
    calc = calculated(account, on)
    diff = informed - calc
    adjustment = None
    if not diff.is_zero:
        if not adjust:
            raise InvalidTransactionError(
                f"Diferença de {diff}. Procure lançamentos esquecidos ou confirme o ajuste."
            )
        if not notes.strip():
            raise InvalidTransactionError("Descreva o motivo do ajuste.")
        equity = ledger.system_account("equity:adjustments")
        adjustment = ledger.record(
            type=TransactionType.RECONCILIATION_ADJUSTMENT,
            legs=[Leg(account.ledger_account, diff), Leg(equity, -diff)],
            operation_date=on,
            description=f"Ajuste de conciliação: {account.name}",
        )
    return BalanceReconciliation.objects.create(
        account=account,
        reconciliation_date=on,
        informed_cents=informed.cents,
        calculated_cents=calc.cents,
        difference_cents=diff.cents,
        adjustment_transaction=adjustment,
        notes=notes.strip()[:200],
    )


def latest(account: FinancialAccount) -> BalanceReconciliation | None:
    return account.reconciliations.first()


def reconciled_after(account: FinancialAccount, on: datetime.date):
    """Marcos conciliados com data igual ou posterior a `on` (para o aviso da RN-133)."""
    return account.reconciliations.filter(status="reconciled", reconciliation_date__gte=on)


def mark_stale(txn: LedgerTransaction) -> None:
    """Lançamento ou estorno com data em período conciliado: marco passa a 'a reconciliar'."""
    if txn.status != "confirmed":  # previsto e pendente nunca afetam saldo real (RN-012)
        return
    fin_ids = [
        p.account.owner_id
        for p in txn.postings.select_related("account")
        if p.account.owner_type == "financial_account"
    ]
    # O próprio ajuste da conciliação é gravado antes do marco e não o invalida.
    BalanceReconciliation.objects.filter(
        account_id__in=fin_ids,
        status="reconciled",
        reconciliation_date__gte=txn.operation_date,
        created_at__lte=txn.created_at,
    ).exclude(adjustment_transaction=txn).update(status="to_reconcile")
