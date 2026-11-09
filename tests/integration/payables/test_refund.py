"""Reembolso T20 (RF-LAN-05; RN-024, RN-121; I-03)."""

import datetime as dt

import pytest

from apps.accounts.models import FinancialAccount
from apps.accounts.services import balance
from apps.entries import services as entries
from apps.entries.services import EXPENSE, INCOME, EntryInput
from apps.ledger import services as ledger
from apps.ledger.errors import InvalidStateError, InvalidTransactionError, ReversalLimitError
from apps.ledger.invariants import check_all
from apps.ledger.models import LinkKind, TransactionStatus, TransactionType
from apps.money import Money
from apps.payables import services as payables

pytestmark = pytest.mark.usefixtures("on_20_11")

TODAY = dt.date(2026, 11, 20)


@pytest.fixture
def conta(fin):
    fin.make("Base", "checking", "free", 1_000_000)
    return FinancialAccount.objects.get(name="Base")


@pytest.fixture
def gasto(conta, cats):
    return entries.record(
        EntryInput(
            kind=EXPENSE,
            amount=Money(10000),
            account=conta,
            on=dt.date(2026, 11, 10),
            category=cats.mercado,
        )
    )


def test_T20_reduz_despesa_e_volta_dinheiro(conta, cats, gasto):
    txn = entries.refund(gasto, amount=Money(3000), account=conta, on=TODAY)
    assert txn.type == TransactionType.REFUND
    assert txn.competence_date == TODAY
    assert balance(conta) == Money(993_000)
    assert ledger.account_balance(cats.mercado.ledger_account) == Money(7000)
    assert txn.links_out.get().kind == LinkKind.REFUNDS
    assert check_all() == []


def test_RN_024_reembolso_nunca_e_receita(conta, cats, gasto):
    entries.refund(gasto, amount=Money(3000), account=conta, on=TODAY)
    assert ledger.account_balance(cats.salario.ledger_account) == Money(0)


def test_RN_121_soma_nao_passa_do_original(conta, gasto):
    entries.refund(gasto, amount=Money(6000), account=conta, on=TODAY)
    with pytest.raises(ReversalLimitError, match="ultrapassa"):
        entries.refund(gasto, amount=Money(4001), account=conta, on=TODAY)
    entries.refund(gasto, amount=Money(4000), account=conta, on=TODAY)
    assert balance(conta) == Money(1_000_000)
    assert check_all() == []


def test_reembolso_estornado_libera_o_limite(conta, gasto):
    txn = entries.refund(gasto, amount=Money(10000), account=conta, on=TODAY)
    ledger.reverse(txn, reason="não veio")
    entries.refund(gasto, amount=Money(10000), account=conta, on=TODAY)
    assert balance(conta) == Money(1_000_000)
    assert check_all() == []


def test_RN_121_estorno_total_depois_de_reembolso_e_so_o_restante(conta, cats, gasto):
    entries.refund(gasto, amount=Money(3000), account=conta, on=TODAY)
    ledger.reverse(gasto, reason="era engano")
    assert balance(conta) == Money(1_000_000)
    assert ledger.account_balance(cats.mercado.ledger_account) == Money(0)
    assert check_all() == []


def test_totalmente_reembolsado_nao_estorna(conta, gasto):
    entries.refund(gasto, amount=Money(10000), account=conta, on=TODAY)
    with pytest.raises(ReversalLimitError, match="totalmente"):
        ledger.reverse(gasto, reason="x")


def test_corrigir_com_reembolso_e_bloqueado(conta, cats, gasto):
    entries.refund(gasto, amount=Money(1), account=conta, on=TODAY)
    with pytest.raises(InvalidStateError, match="reembolso"):
        entries.correct(
            gasto,
            EntryInput(
                kind=EXPENSE, amount=Money(5), account=conta, on=TODAY, category=cats.mercado
            ),
            reason="x",
        )
    assert not entries.describe(gasto).editable


def test_I03_detecta_reembolso_acima_do_original(conta, cats, gasto):
    from django.db import connection

    other = entries.refund(gasto, amount=Money(100), account=conta, on=TODAY)
    with connection.cursor() as cursor:
        cursor.execute("DROP TRIGGER link_no_update")
        cursor.execute(
            "UPDATE transaction_link SET amount_cents = 99999 WHERE from_transaction_id = %s",
            [other.pk],
        )
    assert any(v.code == "I-03" and "excedem" in v.detail for v in check_all())


def test_reembolso_invalido(conta, cats, fin, gasto):
    with pytest.raises(InvalidTransactionError, match="maior que zero"):
        entries.refund(gasto, amount=Money(0), account=conta, on=TODAY)
    with pytest.raises(InvalidTransactionError, match="benefício"):
        entries.refund(gasto, amount=Money(1), account=fin.vr, on=TODAY)
    receita = entries.record(
        EntryInput(kind=INCOME, amount=Money(1), account=conta, on=TODAY, category=cats.salario)
    )
    with pytest.raises(InvalidStateError, match="despesas pagas"):
        entries.refund(receita, amount=Money(1), account=conta, on=TODAY)
    ledger.reverse(gasto, reason="x")
    with pytest.raises(InvalidStateError, match="confirmadas"):
        entries.refund(gasto, amount=Money(1), account=conta, on=TODAY)


def test_ledger_recusa_reembolso_de_tipo_errado(conta, cats):
    receita = entries.record(
        EntryInput(kind=INCOME, amount=Money(1), account=conta, on=TODAY, category=cats.salario)
    )
    with pytest.raises(InvalidStateError, match="despesas pagas"):
        ledger.refund(
            receita,
            legs=[],
            amount=Money(1),
            operation_date=TODAY,
            description="x",
        )


def test_ledger_limite_total(conta, cats, gasto):
    legs = [
        ledger.Leg(conta.ledger_account, Money(10001)),
        ledger.Leg(cats.mercado.ledger_account, Money(-10001)),
    ]
    with pytest.raises(ReversalLimitError, match="ultrapassa"):
        ledger.refund(gasto, legs=legs, amount=Money(10001), operation_date=TODAY, description="x")


def test_idempotente(conta, gasto):
    first = entries.refund(gasto, amount=Money(1), account=conta, on=TODAY, idempotency_key="k")
    second = entries.refund(gasto, amount=Money(1), account=conta, on=TODAY, idempotency_key="k")
    assert first.pk == second.pk
    assert balance(conta) == Money(990_001)


def test_reembolso_de_conta_paga_nao_reabre(conta, cats):
    bill = payables.create_bill(
        description="Luz",
        category=cats.aluguel,
        account=conta,
        amount=Money(10000),
        due_date=dt.date(2026, 11, 25),
    )
    settlement = payables.pay(bill, amount=Money(10000))
    entries.refund(settlement.transaction, amount=Money(2000), account=conta, on=TODAY)
    assert payables.open_amount(bill) == Money(0)
    assert settlement.transaction.status == TransactionStatus.CONFIRMED
