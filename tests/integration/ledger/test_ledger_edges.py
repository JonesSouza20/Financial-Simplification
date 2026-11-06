"""Casos de borda dos serviços e do verificador (cobertura ≥ 95%, testing-plan.md §4)."""

import pytest
from django.db import connection

from apps.ledger import db_triggers, services
from apps.ledger.errors import InvalidTransactionError
from apps.ledger.invariants import check_all
from apps.ledger.models import LedgerAccount, TransactionType
from apps.ledger.services import Leg
from apps.money import Money

from .helpers import day, simple

pytestmark = pytest.mark.usefixtures("on_20_11")


def test_data_que_nao_e_date_e_recusada(accounts):
    with pytest.raises(InvalidTransactionError, match="Datas"):
        services.record(
            type=TransactionType.EXPENSE_PAID,
            legs=[Leg(accounts.mercado, Money(1)), Leg(accounts.corrente, Money(-1))],
            operation_date="2026-11-03",
            description="x",
        )


def test_valor_que_nao_e_money_e_recusado(accounts):
    with pytest.raises(InvalidTransactionError, match="Money"):
        services.record(
            type=TransactionType.EXPENSE_PAID,
            legs=[Leg(accounts.mercado, 1), Leg(accounts.corrente, -1)],
            operation_date=day(3),
            description="x",
        )


def test_conta_nao_gravada_e_recusada(accounts):
    loose = LedgerAccount(code="x", kind="expense", name="Solta")
    with pytest.raises(InvalidTransactionError, match="não gravada"):
        services.record(
            type=TransactionType.EXPENSE_PAID,
            legs=[Leg(loose, Money(1)), Leg(accounts.corrente, Money(-1))],
            operation_date=day(3),
            description="x",
        )


def test_modo_de_estorno_invalido(accounts):
    txn = simple(accounts.mercado, accounts.corrente, 100)
    with pytest.raises(InvalidTransactionError, match="Tipo de estorno"):
        services.reverse(txn, reason="x", mode="outro")


def test_estorno_parcial_e_correcao_idempotentes(accounts):
    purchase = simple(
        accounts.eletronicos, accounts.cartao_a, 1000, type=TransactionType.CARD_PURCHASE
    )
    a = services.reverse_partially(purchase, amount=Money(100), reason="x", idempotency_key="P1")
    b = services.reverse_partially(purchase, amount=Money(100), reason="x", idempotency_key="P1")
    assert a.pk == b.pk
    expense = simple(accounts.mercado, accounts.corrente, 500)
    legs = [Leg(accounts.mercado, Money(400)), Leg(accounts.corrente, Money(-400))]
    c = services.correct(expense, legs=legs, reason="x", idempotency_key="C1")
    d = services.correct(expense, legs=legs, reason="x", idempotency_key="C1")
    assert c.pk == d.pk
    assert services.account_balance(accounts.corrente) == Money(-400)


def test_correcao_com_nova_data_usa_a_nova_competencia(accounts):
    expense = simple(accounts.mercado, accounts.corrente, 500, on=day(3))
    new = services.correct(
        expense,
        legs=[Leg(accounts.mercado, Money(500)), Leg(accounts.corrente, Money(-500))],
        reason="data errada",
        operation_date=day(5),
    )
    assert (new.operation_date, new.competence_date) == (day(5), day(5))


def _corrupt(sql, params=()):
    db_triggers.uninstall(connection)
    with connection.cursor() as cursor:
        cursor.execute(sql, params)
    db_triggers.install(connection)


def test_detecta_vinculo_de_estorno_incoerente(accounts):
    txn = simple(accounts.mercado, accounts.corrente, 100)
    services.reverse(txn, reason="x")
    _corrupt("UPDATE ledger_transaction SET status = 'confirmed' WHERE id = %s", [txn.pk])
    assert any("incoerente" in v.detail for v in check_all())


def test_detecta_estornos_parciais_excessivos(accounts):
    purchase = simple(
        accounts.eletronicos, accounts.cartao_a, 1000, type=TransactionType.CARD_PURCHASE
    )
    services.reverse_partially(purchase, amount=Money(100), reason="x")
    _corrupt(
        "UPDATE transaction_link SET amount_cents = 5000 WHERE to_transaction_id = %s",
        [purchase.pk],
    )
    assert any("excedem" in v.detail for v in check_all())
