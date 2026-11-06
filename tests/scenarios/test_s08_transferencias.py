"""S08 — Transferências e reserva (reference-scenarios.md; T05–T07, RN-060, RN-061, RN-173)."""

import datetime

import pytest

from apps.accounts import services as accounts
from apps.entries import services as entries
from apps.entries.services import TRANSFER, EntryInput
from apps.ledger import services as ledger
from apps.ledger.invariants import check_all
from apps.ledger.models import LedgerTransaction
from apps.ledger.services import account_balance
from apps.money import Money

pytestmark = pytest.mark.usefixtures("on_20_11")
D = datetime.date(2026, 11, 12)


@pytest.fixture
def s08(fin):
    corrente = fin.make("Corrente S08", "checking", "free", 200000)
    digital = fin.make("Digital S08", "digital", "free", 50000)
    reserva = fin.make("Reserva S08", "reserve", "reserve", 0)
    return corrente, digital, reserva


def balances(*accs):
    return [accounts.balance(a).cents for a in accs]


def bank_and_free(corrente, digital, reserva):
    free = accounts.balance(corrente) + accounts.balance(digital)
    return (free + accounts.balance(reserva)).cents, free.cents


def move(origin, dest, cents):
    return entries.record(
        EntryInput(kind=TRANSFER, amount=Money(cents), account=origin, on=D, destination=dest)
    )


def test_s08_sequencia(s08):
    corrente, digital, reserva = s08
    assert balances(*s08) == [200000, 50000, 0] and bank_and_free(*s08) == (250000, 250000)
    move(corrente, digital, 40000)
    assert balances(*s08) == [160000, 90000, 0] and bank_and_free(*s08) == (250000, 250000)
    move(corrente, reserva, 100000)
    assert balances(*s08) == [60000, 90000, 100000] and bank_and_free(*s08) == (250000, 150000)
    move(reserva, digital, 30000)
    assert balances(*s08) == [60000, 120000, 70000] and bank_and_free(*s08) == (250000, 180000)
    assert check_all() == []


def test_s08_sem_receita_nem_despesa(s08):
    corrente, digital, reserva = s08
    move(corrente, digital, 40000)
    move(corrente, reserva, 100000)
    for txn in LedgerTransaction.objects.filter(type__startswith="T0"):
        kinds = {p.account.kind for p in txn.postings.select_related("account")}
        assert kinds == {"asset"}, txn.type


def test_s08_falha_entre_pernas_nao_grava_nada(s08, monkeypatch):
    corrente, digital, _ = s08
    before = LedgerTransaction.objects.count()

    def boom(name):
        if name == "after_first_posting":
            raise RuntimeError("falha simulada")

    monkeypatch.setattr(ledger, "_fault_point", boom)
    with pytest.raises(RuntimeError):
        move(corrente, digital, 40000)
    assert LedgerTransaction.objects.count() == before
    assert account_balance(corrente.ledger_account) == Money(200000)
