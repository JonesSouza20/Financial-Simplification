"""Validações e caminhos de borda da Fase 1C (cobertura ≥ 95%, testing-plan.md §4)."""

import datetime

import pytest
from django.utils import timezone

from apps.cards import services as cards
from apps.cards.services import PurchaseInput
from apps.debts import services as debts
from apps.ledger.errors import InvalidTransactionError
from apps.ledger.invariants import check_all
from apps.ledger.models import LedgerTransaction, TransactionType
from apps.money import Money
from apps.opening.forms import CardDraftForm, DebtDraftForm, ItemDraftForm
from apps.persons import services as persons
from apps.receivables import services as receivables

pytestmark = pytest.mark.usefixtures("on_20_11")
D = datetime.date
NOV_15 = D(2026, 11, 15)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"name": " "}, "nome do cartão"),
        ({"credit_limit": Money(0)}, "limite"),
        ({"closing_day": 5, "due_day": 5}, "diferentes"),
        ({"closing_day": 32}, "1 a 31"),
    ],
)
def test_cadastro_de_cartao_invalido(db, kwargs, message):
    base = {"name": "X", "credit_limit": Money(100), "closing_day": 25, "due_day": 5}
    with pytest.raises(InvalidTransactionError, match=message):
        cards.create_card(**{**base, **kwargs})


@pytest.mark.parametrize(
    ("change", "message"),
    [({"total": Money(0)}, "maior que zero"), ({"installments": 49}, "1 a 48")],
)
def test_compra_invalida_por_valor_ou_parcelas(card_a, cats, change, message):
    data = {"card": card_a, "total": Money(1000), "on": NOV_15, "category": cats.mercado}
    with pytest.raises(InvalidTransactionError, match=message):
        cards.record_purchase(PurchaseInput(**{**data, **change}))


def test_cartao_arquivado_recusa_compra(card_a, cats):
    card_a.archived_at = timezone.now()
    with pytest.raises(InvalidTransactionError, match="arquivado"):
        cards.build_purchase(
            PurchaseInput(card=card_a, total=Money(1), on=NOV_15, category=cats.mercado)
        )


def test_reenvio_idempotente_de_compra(card_a, cats):
    inp = PurchaseInput(card=card_a, total=Money(1000), on=NOV_15, category=cats.mercado)
    a = cards.record_purchase(inp, idempotency_key="KC")
    b = cards.record_purchase(inp, idempotency_key="KC")
    assert a.pk == b.pk
    assert card_a.purchases.count() == 1


def test_pagamento_invalido(card_a, fin):
    with pytest.raises(InvalidTransactionError, match="maior que zero"):
        cards.pay(card=card_a, account=fin.corrente, amount=Money(0), on=NOV_15)
    with pytest.raises(InvalidTransactionError, match="VR/VA"):
        cards.pay(card=card_a, account=fin.vr, amount=Money(100), on=NOV_15)


def test_item_de_abertura_de_terceiro(card_a, ana):
    txn = cards.record_opening_item(
        card=card_a,
        kind="open_invoice",
        description="Tênis da Ana",
        amount=Money(30000),
        person=ana,
    )
    assert txn.type == TransactionType.OPENING_CARD_THIRD_PARTY
    assert receivables.open_total(ana) == Money(30000)
    assert cards.due_until(card_a, D(2026, 12, 6)) == Money(30000)  # vence 05/12 (próximo)
    assert cards.due_until(card_a, D(2026, 12, 5)) == Money(0)
    assert check_all() == []


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"kind": "remaining_installments", "total": None}, "total e o número"),
        (
            {
                "kind": "remaining_installments",
                "total": Money(1000),
                "installments": 3,
                "billed": 3,
            },
            "menos que o total",
        ),
        ({"kind": "closed_invoice", "amount": None}, "valor do item"),
        ({"kind": "outro", "amount": Money(1)}, "inválido"),
    ],
)
def test_item_de_abertura_invalido(card_a, kwargs, message):
    with pytest.raises(InvalidTransactionError, match=message):
        cards.record_opening_item(card=card_a, description="x", **kwargs)


def test_emprestimo_e_recebimento_invalidos(fin, ana):
    with pytest.raises(InvalidTransactionError, match="maior que zero"):
        receivables.lend(
            person=ana, account=fin.corrente, amount=Money(0), on=NOV_15, due_date=NOV_15
        )
    with pytest.raises(InvalidTransactionError, match="VR/VA"):
        receivables.lend(person=ana, account=fin.vr, amount=Money(1), on=NOV_15, due_date=NOV_15)
    with pytest.raises(InvalidTransactionError, match="maior que zero"):
        receivables.receive(person=ana, account=fin.corrente, amount=Money(0), on=NOV_15)
    with pytest.raises(InvalidTransactionError, match="VR/VA"):
        receivables.receive(person=ana, account=fin.vr, amount=Money(1), on=NOV_15)


def test_recebimento_idempotente(fin, ana):
    receivables.lend(
        person=ana, account=fin.corrente, amount=Money(5000), on=NOV_15, due_date=NOV_15
    )
    a = receivables.receive(
        person=ana, account=fin.corrente, amount=Money(1000), on=NOV_15, idempotency_key="KR"
    )
    b = receivables.receive(
        person=ana, account=fin.corrente, amount=Money(1000), on=NOV_15, idempotency_key="KR"
    )
    assert a.pk == b.pk
    assert receivables.open_total(ana) == Money(4000)


def test_verificacao_detecta_divergencia_no_a_receber(fin, ana):
    from apps.receivables.models import ReceivableInstallment

    receivables.lend(
        person=ana, account=fin.corrente, amount=Money(5000), on=NOV_15, due_date=NOV_15
    )
    ReceivableInstallment.objects.update(amount_cents=4000)
    assert any(v.code == "I-06" for v in check_all())


def test_pessoa(db):
    with pytest.raises(InvalidTransactionError):
        persons.get_or_create("  ")
    assert persons.get_or_create("Ana") == persons.get_or_create("  ana ")


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [({"balance": Money(0)}, "saldo devedor"), ({"due_day": 40}, "1 a 31")],
)
def test_divida_invalida(db, kwargs, message):
    base = {"creditor": "Banco", "description": "", "balance": Money(100), "due_day": 5}
    with pytest.raises(InvalidTransactionError, match=message):
        debts.create_loan(**{**base, **kwargs})


def test_parcelas_invalidas(fin):
    loan = debts.create_loan(creditor="Banco", description="", balance=Money(100000), due_day=5)
    cons = debts.create_consortium(
        description="C", installment=Money(100), due_day=5, remaining_installments=2
    )
    with pytest.raises(InvalidTransactionError):
        debts.create_consortium(
            description="C", installment=Money(0), due_day=5, remaining_installments=2
        )
    with pytest.raises(InvalidTransactionError, match="negativos"):
        debts.pay_loan(
            debt=loan, account=fin.corrente, principal=Money(-1), interest=Money(0), on=NOV_15
        )
    with pytest.raises(InvalidTransactionError, match="valor pago"):
        debts.pay_loan(
            debt=loan, account=fin.corrente, principal=Money(0), interest=Money(0), on=NOV_15
        )
    with pytest.raises(InvalidTransactionError, match="não é um consórcio"):
        debts.pay_consortium(debt=loan, account=fin.corrente, amount=Money(1), on=NOV_15)
    with pytest.raises(InvalidTransactionError, match="valor pago"):
        debts.pay_consortium(debt=cons, account=fin.corrente, amount=Money(0), on=NOV_15)
    txn = debts.pay_loan(
        debt=loan,
        account=fin.corrente,
        principal=Money(1000),
        interest=Money(200),
        charges=Money(50),
        on=NOV_15,
    )
    assert txn.postings.count() == 4
    assert LedgerTransaction.objects.filter(type=TransactionType.DEBT_INSTALLMENT).count() == 1


def test_formularios_do_assistente():
    assert not CardDraftForm(
        {"name": "X", "credit_limit": "0,00", "closing_day": 1, "due_day": 2}
    ).is_valid()
    item = ItemDraftForm({"card": "0", "kind": "remaining_installments"}, cards=[{"name": "A"}])
    assert not item.is_valid() and "total" in str(item.errors)
    item = ItemDraftForm(
        {
            "card": "0",
            "kind": "remaining_installments",
            "total": "100,00",
            "installments": "3",
            "billed": "3",
        },
        cards=[{"name": "A"}],
    )
    assert not item.is_valid() and "menos que o total" in str(item.errors)
    item = ItemDraftForm({"card": "0", "kind": "closed_invoice"}, cards=[{"name": "A"}])
    assert not item.is_valid() and "valor da fatura" in str(item.errors)
    loan = DebtDraftForm({"kind": "loan", "due_day": "5"})
    assert not loan.is_valid() and "credor" in str(loan.errors)
    cons = DebtDraftForm({"kind": "consortium", "due_day": "5"})
    assert not cons.is_valid() and "parcela" in str(cons.errors)
    ok = DebtDraftForm(
        {"kind": "consortium", "due_day": "20", "installment": "650,00", "remaining": "40"}
    )
    assert ok.is_valid() and ok.item()["installment"] == 65000
