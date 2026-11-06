"""Cartões, valores a receber e dívidas no MVP-1 (RN-075, RN-078, RN-080, RN-085, RN-100 a RN-107,
RN-117, RN-118, T11, T14, T15, T17, T19)."""

import datetime

import pytest

from apps.cards import services as cards
from apps.cards.models import CardPurchase
from apps.cards.services import PurchaseInput
from apps.categories.services import by_key
from apps.debts import services as debts
from apps.ledger import services as ledger
from apps.ledger.errors import InvalidTransactionError
from apps.ledger.invariants import check_all
from apps.ledger.models import LedgerPosting, TransactionType
from apps.ledger.services import account_balance
from apps.money import Money
from apps.receivables import services as receivables

pytestmark = pytest.mark.usefixtures("on_20_11")
D = datetime.date
NOV_10 = D(2026, 11, 10)
NOV_20 = D(2026, 11, 20)


def buy(card, cents, on=NOV_10, n=1, category=None, shares=()):
    return cards.record_purchase(
        PurchaseInput(
            card=card,
            total=Money(cents),
            on=on,
            installments=n,
            category=category,
            shares=tuple(shares),
        )
    )


def est(card, today=NOV_20):
    return {e.due_date: e.amount.cents for e in cards.estimate(card, today)}


def test_compra_parcelada_grava_parcelas_e_consume_limite(card_a, cats):
    txn = buy(card_a, 60000, n=6, category=cats.eletronicos)
    purchase = CardPurchase.objects.get(transaction=txn)
    assert (purchase.installments_count, purchase.installment_cents) == (6, 10000)
    assert cards.available_limit(card_a) == Money(440000)
    assert est(card_a)[D(2026, 12, 5)] == 10000
    assert len(est(card_a)) == 6


def test_resto_de_centavos_na_primeira_parcela(card_a, cats):
    buy(card_a, 10000, n=3, category=cats.eletronicos)
    assert list(est(card_a).values()) == [3334, 3333, 3333]


def test_pagamento_abate_fatura_mais_antiga(card_a, fin, cats):
    buy(card_a, 30000, n=3, category=cats.eletronicos)
    cards.pay(card=card_a, account=fin.corrente, amount=Money(15000), on=D(2026, 11, 20))
    assert est(card_a) == {D(2027, 1, 5): 5000, D(2027, 2, 5): 10000}
    assert account_balance(fin.corrente.ledger_account) == Money(-15000)
    assert not LedgerPosting.objects.filter(
        account__kind="expense", transaction__type="T11_invoice_payment"
    ).exists()


def test_pagamento_acima_vira_credito(card_b, fin, cats):
    buy(card_b, 30000, on=D(2026, 11, 15), category=cats.mercado)
    cards.pay(card=card_b, account=fin.corrente, amount=Money(35000), on=D(2026, 11, 20))
    assert cards.liability(card_b) == Money(-5000)
    assert cards.available_limit(card_b) == Money(305000)  # S07: limite + crédito
    assert sum(est(card_b).values()) == -5000


def test_estorno_parcial_credita_fatura_do_estorno(card_a, cats):
    txn = buy(card_a, 20000, on=D(2026, 11, 15), category=cats.eletronicos)
    ledger.reverse_partially(txn, amount=Money(5000), reason="troca")
    assert est(card_a) == {D(2026, 12, 5): 15000}


def test_estorno_tecnico_some_da_estimativa(card_a, cats):
    txn = buy(card_a, 20000, category=cats.eletronicos)
    ledger.reverse(txn, reason="lançamento errado")
    assert est(card_a) == {}
    assert cards.liability(card_a) == Money(0)


def test_estorno_de_compra_de_terceiro_reduz_a_receber(card_a, ana, cats):
    txn = buy(card_a, 25000, category=cats.get("Restaurantes"), shares=[(ana, Money(15000))])
    ledger.reverse_partially(txn, amount=Money(5000), reason="item devolvido")
    assert receivables.open_total(ana) == Money(12000)
    ledger.reverse(txn, reason="cancelada", mode="commercial")
    assert receivables.open_total(ana) == Money(0)
    assert check_all() == []


@pytest.mark.parametrize(
    ("shares", "category", "message"),
    [
        ([("Ana", 30000)], None, "passam do valor"),
        ([], None, "categoria"),
        ([("Ana", 0)], "mercado", "maior que zero"),
    ],
)
def test_compra_invalida(card_a, cats, ana, shares, category, message):
    people = [(ana, Money(c)) for _, c in shares]
    with pytest.raises(InvalidTransactionError, match=message):
        buy(card_a, 20000, category=getattr(cats, category) if category else None, shares=people)


def test_compra_inteira_de_terceiro_dispensa_categoria(card_a, ana):
    txn = buy(card_a, 8000, shares=[(ana, Money(8000))])
    assert txn.type == TransactionType.CARD_THIRD_PARTY
    assert txn.description == "Compra no cartão"


def test_emprestimo_e_recebimentos(fin, ana):
    receivables.lend(
        person=ana,
        account=fin.corrente,
        amount=Money(50000),
        on=D(2026, 11, 12),
        due_date=D(2026, 12, 10),
    )
    receivables.receive(person=ana, account=fin.digital, amount=Money(10000), on=D(2026, 11, 20))
    assert receivables.open_total(ana) == Money(40000)
    assert account_balance(fin.corrente.ledger_account) == Money(-50000)
    assert account_balance(fin.digital.ledger_account) == Money(10000)
    assert not LedgerPosting.objects.filter(account__kind__in=["income", "expense"]).exists()
    with pytest.raises(InvalidTransactionError, match="acima do devido"):
        receivables.receive(
            person=ana, account=fin.digital, amount=Money(40001), on=D(2026, 11, 20)
        )
    assert check_all() == []


def test_recebimento_estornado_reabre(fin, ana):
    receivables.lend(
        person=ana,
        account=fin.corrente,
        amount=Money(5000),
        on=D(2026, 11, 12),
        due_date=D(2026, 12, 10),
    )
    receipt = receivables.receive(
        person=ana, account=fin.corrente, amount=Money(5000), on=D(2026, 11, 20)
    )
    assert receivables.open_total(ana) == Money(0)
    ledger.reverse(receipt, reason="Pix devolvido")
    assert receivables.open_total(ana) == Money(5000)
    assert check_all() == []


def test_recebimento_abate_o_mais_antigo(fin, ana, card_a):
    buy(card_a, 8000, on=D(2026, 11, 12), shares=[(ana, Money(8000))])  # vence 05/12
    receivables.lend(
        person=ana,
        account=fin.corrente,
        amount=Money(5000),
        on=D(2026, 11, 12),
        due_date=D(2026, 11, 30),
    )
    receivables.receive(person=ana, account=fin.corrente, amount=Money(6000), on=D(2026, 11, 20))
    remaining = {inst.due_date: m.cents for inst, m in receivables.open_installments(ana)}
    assert remaining == {D(2026, 12, 5): 7000}


def test_divida_parcela_com_principal_e_juros(fin):
    loan = debts.create_loan(
        creditor="Banco",
        description="Empréstimo",
        balance=Money(1000000),
        due_day=15,
        monthly_rate_percent="2,00",
        remaining_installments=12,
    )
    txn = debts.pay_loan(
        debt=loan,
        account=fin.corrente,
        principal=Money(74560),
        interest=Money(20000),
        on=D(2026, 11, 16),
    )
    assert txn.type == TransactionType.DEBT_INSTALLMENT
    assert debts.balance(loan) == Money(925440)
    assert account_balance(by_key("debt_interest").ledger_account) == Money(20000)
    assert account_balance(fin.corrente.ledger_account) == Money(-94560)
    with pytest.raises(InvalidTransactionError, match="saldo devedor"):
        debts.pay_loan(
            debt=loan,
            account=fin.corrente,
            principal=Money(925441),
            interest=Money(0),
            on=D(2026, 11, 16),
        )
    assert check_all() == []


def test_taxa_invalida(db):
    with pytest.raises(InvalidTransactionError):
        debts.create_loan(
            creditor="X", description="", balance=Money(100), due_day=5, monthly_rate_percent="45"
        )


def test_consorcio_e_despesa_da_categoria(fin):
    cons = debts.create_consortium(
        description="Consórcio", installment=Money(65000), due_day=20, remaining_installments=40
    )
    debts.pay_consortium(debt=cons, account=fin.corrente, amount=Money(65000), on=D(2026, 11, 20))
    assert account_balance(by_key("consortium").ledger_account) == Money(65000)
    assert debts.history(cons).count() == 1
    assert debts.balance(cons) == Money(0)
    with pytest.raises(InvalidTransactionError):
        debts.pay_loan(
            debt=cons,
            account=fin.corrente,
            principal=Money(1),
            interest=Money(0),
            on=D(2026, 11, 20),
        )
