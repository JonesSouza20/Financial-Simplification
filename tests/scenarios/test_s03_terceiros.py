"""S03 — Compras de terceiro: à vista, parcelada e mista (parte MVP-1; T09, T10, RN-100)."""

import datetime

import pytest

from apps.cards import services as cards
from apps.cards.services import PurchaseInput
from apps.ledger.invariants import check_all
from apps.ledger.models import LedgerPosting, TransactionType
from apps.ledger.services import account_balance
from apps.money import Money
from apps.receivables import services as receivables

pytestmark = pytest.mark.usefixtures("on_20_11")
D = datetime.date


@pytest.fixture
def s03(card_a, ana, cats):
    t1 = cards.record_purchase(
        PurchaseInput(
            card=card_a, total=Money(8000), on=D(2026, 11, 12), shares=((ana, Money(8000)),)
        )
    )
    t2 = cards.record_purchase(
        PurchaseInput(
            card=card_a,
            total=Money(12000),
            on=D(2026, 11, 13),
            installments=3,
            shares=((ana, Money(12000)),),
        )
    )
    restaurantes = cats.get("Restaurantes")
    t3 = cards.record_purchase(
        PurchaseInput(
            card=card_a,
            total=Money(25000),
            on=D(2026, 11, 14),
            category=restaurantes,
            description="Jantar",
            shares=((ana, Money(15000)),),
        )
    )
    return t1, t2, t3, restaurantes


def test_s03_tipos_e_pernas(s03, ana, card_a):
    t1, t2, t3, restaurantes = s03
    assert [t1.type, t2.type, t3.type] == [
        TransactionType.CARD_THIRD_PARTY,
        TransactionType.CARD_THIRD_PARTY,
        TransactionType.CARD_MIXED,
    ]
    legs = {p.account_id: p.amount_cents for p in t3.postings.all()}
    assert legs == {
        restaurantes.ledger_account_id: 10000,
        ana.ledger_account_id: 15000,
        card_a.ledger_account_id: -25000,
    }


def test_s03_resultados(s03, ana, card_a):
    assert receivables.open_total(ana) == Money(35000)
    assert account_balance(ana.ledger_account) == Money(35000)
    expenses = sum(p.amount_cents for p in LedgerPosting.objects.filter(account__kind="expense"))
    assert expenses == 10000  # só a parte própria do jantar
    assert not LedgerPosting.objects.filter(account__kind="income").exists()
    assert cards.liability(card_a) == Money(45000)
    assert check_all() == []


def test_s03_fatura_estimada_05_12(s03, card_a):
    estimate = {e.due_date: e.amount.cents for e in cards.estimate(card_a)}
    assert estimate[D(2026, 12, 5)] == 37000  # 80,00 + 40,00 + 250,00
    assert estimate[D(2027, 1, 5)] == 4000
    assert estimate[D(2027, 2, 5)] == 4000


def test_s03_a_receber_vence_na_fatura(s03, ana):
    dues = {inst.due_date for inst, _ in receivables.open_installments(ana)}
    assert dues == {D(2026, 12, 5)}  # MVP-1: uma parcela por compra, no vencimento da fatura
