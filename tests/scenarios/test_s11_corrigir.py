"""S11 — Correção de lançamento confirmado (reference-scenarios.md; RN-082, RN-120, RN-122)."""

import datetime

import pytest
from django.db import DatabaseError, connection, transaction

from apps.ledger import services
from apps.ledger.errors import AlreadyReversedError
from apps.ledger.invariants import check_all
from apps.ledger.models import AuditLog, LinkKind, TransactionStatus, TransactionType
from apps.ledger.services import Leg
from apps.money import Money
from tests.conftest import travel_to

D03 = datetime.date(2026, 11, 3)
D04 = datetime.date(2026, 11, 4)


@pytest.fixture
def scenario(accounts):
    with travel_to(D03):
        t1 = services.record(
            type=TransactionType.EXPENSE_PAID,
            legs=[Leg(accounts.mercado, Money(8500)), Leg(accounts.corrente, Money(-8500))],
            operation_date=D03,
            description="Mercado",
        )
    with travel_to(D04):
        t3 = services.correct(
            t1,
            legs=[Leg(accounts.mercado, Money(5800)), Leg(accounts.corrente, Money(-5800))],
            reason="valor digitado errado",
        )
    t1.refresh_from_db()
    t2 = t1.links_in.get(kind=LinkKind.REVERSES).from_transaction
    return t1, t2, t3


def test_s11_estados_e_datas(scenario):
    t1, t2, t3 = scenario
    assert t1.status == TransactionStatus.REVERSED
    assert t2.status == TransactionStatus.CONFIRMED
    assert t2.type == TransactionType.TECHNICAL_REVERSAL
    assert (t2.operation_date, t2.competence_date) == (D04, D03)
    assert t3.status == TransactionStatus.CONFIRMED
    assert (t3.operation_date, t3.competence_date) == (D03, D03)
    assert t3.links_out.get(kind=LinkKind.CORRECTS).to_transaction == t1


def test_s11_efeito_liquido(scenario, accounts):
    assert services.account_balance(accounts.corrente) == Money(-5800)
    assert services.account_balance(accounts.mercado) == Money(5800)
    assert check_all() == []


def test_s11_pernas_de_cada_transacao(scenario, accounts):
    t1, t2, t3 = scenario

    def legs(txn):
        return {p.account.code: p.amount_cents for p in txn.postings.select_related("account")}

    assert legs(t1) == {accounts.mercado.code: 8500, accounts.corrente.code: -8500}
    assert legs(t2) == {accounts.mercado.code: -8500, accounts.corrente.code: 8500}
    assert legs(t3) == {accounts.mercado.code: 5800, accounts.corrente.code: -5800}


def test_s11_auditoria_ligada(scenario):
    t1, t2, t3 = scenario
    actions = set(
        AuditLog.objects.filter(entity_type="ledger_transaction", entity_id=t1.pk).values_list(
            "action", flat=True
        )
    )
    assert {"create", "reverse", "correct"} <= actions


def test_s11_nao_estorna_de_novo_nem_altera(scenario):
    t1, _, t3 = scenario
    with travel_to(D04), pytest.raises(AlreadyReversedError):
        services.reverse(t1, reason="de novo")
    with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("UPDATE ledger_transaction SET description = 'x' WHERE id = %s", [t3.pk])
