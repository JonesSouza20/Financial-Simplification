"""S00 — Abertura por itens em 01/11/2026 (reference-scenarios.md; RN-089, T23–T26).

Partes verificáveis no MVP-1. H, comprometido e disponível: MVP-2. Faturas reais: MVP-3
(aqui conferidas como estimativa, RN-075).
"""

import datetime

import pytest

from apps.accounts import services as accounts
from apps.accounts.models import FinancialAccount
from apps.cards import services as cards
from apps.cards.models import Card
from apps.debts import services as debts
from apps.debts.models import Debt
from apps.ledger.invariants import check_all
from apps.ledger.models import LedgerAccount, LedgerPosting
from apps.ledger.services import account_balance
from apps.money import Money
from apps.opening import services as opening

pytestmark = pytest.mark.usefixtures("on_20_11")
D = datetime.date

S00_DRAFT = {
    "accounts": [
        {"name": "Corrente", "account_type": "checking", "asset_class": "free", "balance": 250000},
        {"name": "Digital", "account_type": "digital", "asset_class": "free", "balance": 80000},
        {"name": "Espécie", "account_type": "cash", "asset_class": "free", "balance": 15000},
        {"name": "Reserva", "account_type": "reserve", "asset_class": "reserve", "balance": 0},
        {"name": "VR/VA", "account_type": "benefit", "asset_class": "benefit", "balance": 42000},
    ],
    "cards": [{"name": "Cartão A", "limit": 500000, "closing_day": 25, "due_day": 5}],
    "items": [
        {
            "card": 0,
            "kind": "closed_invoice",
            "description": "A1 fatura fechada",
            "amount": 123000,
            "due_date": "2026-11-05",
        },
        {
            "card": 0,
            "kind": "open_invoice",
            "description": "A2 compras da fatura aberta",
            "amount": 34000,
            "due_date": "2026-12-05",
        },
        {
            "card": 0,
            "kind": "remaining_installments",
            "description": "A3 TV",
            "purchase_date": "2026-06-15",
            "total": 240000,
            "installments": 10,
            "billed": 5,
            "due_date": "2026-12-05",
        },
    ],
    "debts": [
        {
            "kind": "loan",
            "creditor": "Banco",
            "description": "Empréstimo",
            "balance": 1000000,
            "rate": "2",
            "remaining": 12,
            "installment": 94560,
            "due_day": 15,
        },
        {
            "kind": "consortium",
            "creditor": "Administradora",
            "description": "Consórcio",
            "installment": 65000,
            "remaining": 40,
            "due_day": 20,
        },
    ],
    "receivables": [],
}


@pytest.fixture
def s00(db):
    opening.commit(S00_DRAFT)


def acc(name):
    return FinancialAccount.objects.get(name=name)


def test_s00_saldos(s00):
    free = sum(accounts.balance(acc(n)).cents for n in ("Corrente", "Digital", "Espécie"))
    assert free + accounts.balance(acc("Reserva")).cents == 345000  # saldo bancário
    assert accounts.balance(acc("VR/VA")) == Money(42000)


def test_s00_cartao(s00):
    card = Card.objects.get(name="Cartão A")
    assert cards.liability(card) == Money(277000)
    assert cards.available_limit(card) == Money(223000)


def test_s00_faturas_estimadas(s00):
    card = Card.objects.get(name="Cartão A")
    estimate = {e.due_date: e.amount.cents for e in cards.estimate(card, D(2026, 11, 1))}
    assert estimate == {
        D(2026, 11, 5): 123000,
        D(2026, 12, 5): 58000,
        D(2027, 1, 5): 24000,
        D(2027, 2, 5): 24000,
        D(2027, 3, 5): 24000,
        D(2027, 4, 5): 24000,
    }
    assert sum(estimate.values()) == 277000  # I-07 (estimativa)


def test_s00_patrimonio_e_dividas(s00):
    equity = LedgerAccount.objects.get(code="equity:opening")
    assert account_balance(equity) == Money(890000)  # patrimônio líquido de abertura −8.900,00
    loan = Debt.objects.get(kind="loan")
    assert debts.balance(loan) == Money(1000000)
    assert loan.monthly_rate == "0.02"
    consortium = Debt.objects.get(kind="consortium")
    assert consortium.ledger_account is None  # sem passivo (ADR-008)


def test_s00_nenhuma_despesa(s00):
    expenses = LedgerPosting.objects.filter(account__kind="expense")
    assert not expenses.exists()
    assert check_all() == []


def test_s00_abertura_so_uma_vez(s00):
    from apps.ledger.errors import InvalidStateError

    with pytest.raises(InvalidStateError):
        opening.commit(S00_DRAFT)


def test_s00_resumo_do_assistente_bate_com_o_gravado():
    summary = opening.summary(S00_DRAFT)
    assert summary["bank"] == Money(345000)
    assert summary["benefit"] == Money(42000)
    assert summary["cards_total"] == Money(277000)
    assert summary["debts_total"] == Money(1000000)
    assert summary["equity"] == Money(-890000)


def test_s00_falha_no_meio_nao_grava_nada(db):
    from apps.ledger.errors import InvalidTransactionError
    from apps.ledger.models import LedgerTransaction

    broken = {**S00_DRAFT, "debts": [{**S00_DRAFT["debts"][0], "rate": "abc"}]}
    with pytest.raises(InvalidTransactionError):
        opening.commit(broken)
    assert not FinancialAccount.objects.exists()
    assert not LedgerTransaction.objects.exists()
