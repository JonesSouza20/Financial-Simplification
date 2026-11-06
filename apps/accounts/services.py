"""Cadastro de contas financeiras e saldo de abertura (RF-CON-01 a 03, RF-CON-06; T23)."""

from __future__ import annotations

import datetime
import uuid

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.ledger import audit
from apps.ledger import services as ledger
from apps.ledger.errors import InvalidStateError, InvalidTransactionError
from apps.ledger.models import LedgerAccount, LedgerTransaction, TransactionStatus, TransactionType
from apps.ledger.services import Leg
from apps.money import Money

from .models import FinancialAccount


def opening_equity() -> LedgerAccount:
    return ledger.system_account("equity:opening")


@transaction.atomic
def create_account(
    *,
    name: str,
    account_type: str,
    asset_class: str,
    opening_balance: Money,
    opening_date: datetime.date | None = None,
    institution: str = "",
) -> FinancialAccount:
    name = name.strip()
    if not name:
        raise InvalidTransactionError("Informe o nome da conta.")
    opening_date = opening_date or max(settings.FINANCAS_START_DATE, timezone.localdate())
    if opening_date < settings.FINANCAS_START_DATE:
        raise InvalidTransactionError("A data de abertura não pode ser anterior a 01/11/2026.")
    ledger_account = LedgerAccount.objects.create(
        code=f"asset:fin:{uuid.uuid4().hex[:12]}",
        kind="asset",
        asset_class=asset_class,
        name=name,
        owner_type="financial_account",
    )
    account = FinancialAccount.objects.create(
        name=name,
        account_type=account_type,
        asset_class=asset_class,
        institution=institution.strip(),
        ledger_account=ledger_account,
        opening_date=opening_date,
    )
    LedgerAccount.objects.filter(pk=ledger_account.pk).update(owner_id=account.pk)
    ledger_account.refresh_from_db()
    if not opening_balance.is_zero:
        ledger.record(
            type=TransactionType.OPENING_BALANCE,
            legs=[
                Leg(ledger_account, opening_balance),
                Leg(opening_equity(), -opening_balance),
            ],
            operation_date=opening_date,
            description=f"Saldo de abertura: {name}",
        )
    audit.log("create", account, after={"name": name, "opening_cents": opening_balance.cents})
    return account


def balance(account: FinancialAccount) -> Money:
    return ledger.account_balance(account.ledger_account)


@transaction.atomic
def archive(account: FinancialAccount) -> None:
    """Arquiva sem excluir; só sem lançamentos futuros em aberto (RN-185)."""
    open_future = LedgerTransaction.objects.filter(
        postings__account=account.ledger_account,
        status__in=[TransactionStatus.FORECAST, TransactionStatus.PENDING],
    ).exists()
    if open_future:
        raise InvalidStateError("Esta conta tem lançamentos previstos ou pendentes.")
    now = timezone.now()
    FinancialAccount.objects.filter(pk=account.pk).update(archived_at=now)
    LedgerAccount.objects.filter(pk=account.ledger_account_id).update(archived_at=now)
    audit.log("archive", account)


def active_accounts():
    return FinancialAccount.objects.filter(archived_at__isnull=True).select_related(
        "ledger_account"
    )
