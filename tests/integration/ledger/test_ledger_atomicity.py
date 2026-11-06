"""Atomicidade: falha no meio não deixa nada gravado (RN-173; testing-plan.md §7.2)."""

import pytest

from apps.ledger import services
from apps.ledger.models import (
    AuditLog,
    IdempotencyRecord,
    LedgerPosting,
    LedgerTransaction,
    TransactionStatus,
)
from apps.ledger.services import Leg
from apps.money import Money

from .helpers import day, simple

pytestmark = pytest.mark.usefixtures("on_20_11")


class Boom(Exception):
    pass


def fail_at(point):
    def hook(name):
        if name == point:
            raise Boom(name)

    return hook


def counts():
    return (
        LedgerTransaction.objects.count(),
        LedgerPosting.objects.count(),
        AuditLog.objects.count(),
        IdempotencyRecord.objects.count(),
    )


@pytest.mark.parametrize("point", ["after_first_posting", "before_finalize"])
def test_falha_durante_gravacao_nao_deixa_rastro(accounts, monkeypatch, point):
    before = counts()
    monkeypatch.setattr(services, "_fault_point", fail_at(point))
    with pytest.raises(Boom):
        services.record(
            type="T05_transfer",
            legs=[Leg(accounts.digital, Money(40000)), Leg(accounts.corrente, Money(-40000))],
            operation_date=day(12),
            description="Transferência",
            idempotency_key="K-falha",
        )
    assert counts() == before


def test_falha_no_meio_do_corrigir(accounts, monkeypatch):
    original = simple(accounts.mercado, accounts.corrente, 8500)
    before = counts()
    monkeypatch.setattr(services, "_fault_point", fail_at("correct_between"))
    with pytest.raises(Boom):
        services.correct(
            original,
            legs=[Leg(accounts.mercado, Money(5800)), Leg(accounts.corrente, Money(-5800))],
            reason="valor",
        )
    original.refresh_from_db()
    assert original.status == TransactionStatus.CONFIRMED
    assert counts() == before
