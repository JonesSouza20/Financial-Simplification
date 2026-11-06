"""S13 — Conciliação de saldo (parte MVP-1; RN-130 a RN-133, T27)."""

import datetime

import pytest

from apps.accounts import reconciliation
from apps.entries import services as entries
from apps.entries.services import EXPENSE, EntryInput
from apps.ledger.errors import InvalidTransactionError
from apps.ledger.invariants import check_all
from apps.ledger.models import LedgerPosting, TransactionType
from apps.ledger.services import account_balance
from apps.money import Money

pytestmark = pytest.mark.usefixtures("on_20_11")
D20 = datetime.date(2026, 11, 20)


@pytest.fixture
def corrente(fin):
    return fin.make("Corrente S13", "checking", "free", 123456)


def test_s13_sem_ajuste_e_recusado(corrente):
    with pytest.raises(InvalidTransactionError, match="Diferença de −R\\$ 5,00"):
        reconciliation.reconcile(account=corrente, on=D20, informed=Money(122956))


def test_s13_ajuste_registrado(corrente):
    rec = reconciliation.reconcile(
        account=corrente,
        on=D20,
        informed=Money(122956),
        adjust=True,
        notes="tarifa não identificada",
    )
    assert rec.difference_cents == -500
    assert rec.adjustment_transaction.type == TransactionType.RECONCILIATION_ADJUSTMENT
    legs = {
        p.account.code: p.amount_cents
        for p in rec.adjustment_transaction.postings.select_related("account")
    }
    assert legs[corrente.ledger_account.code] == -500
    assert legs["equity:adjustments"] == 500
    assert account_balance(corrente.ledger_account) == Money(122956)
    assert not LedgerPosting.objects.filter(account__kind__in=["income", "expense"]).exists()
    assert check_all() == []


def test_s13_ajuste_exige_motivo(corrente):
    with pytest.raises(InvalidTransactionError, match="motivo"):
        reconciliation.reconcile(account=corrente, on=D20, informed=Money(122956), adjust=True)


def test_s13_saldo_igual_sem_ajuste(corrente):
    rec = reconciliation.reconcile(account=corrente, on=D20, informed=Money(123456))
    assert rec.difference_cents == 0 and rec.adjustment_transaction is None


def test_s13_lancamento_retroativo_deixa_a_reconciliar(corrente, cats):
    rec = reconciliation.reconcile(account=corrente, on=D20, informed=Money(123456))
    assert list(reconciliation.reconciled_after(corrente, datetime.date(2026, 11, 18))) == [rec]
    entries.record(
        EntryInput(
            kind=EXPENSE,
            amount=Money(1000),
            account=corrente,
            on=datetime.date(2026, 11, 18),
            category=cats.mercado,
        )
    )
    rec.refresh_from_db()
    assert rec.status == "to_reconcile"
