"""Idempotência e concorrência (RN-170, RN-173; testing-plan.md §7.4)."""

import threading

import pytest
from django.db import connection

from apps.ledger import services
from apps.ledger.errors import IdempotencyConflictError
from apps.ledger.models import LedgerTransaction, TransactionType

from .helpers import balance, simple

pytestmark = pytest.mark.usefixtures("on_20_11")


def test_mesma_chave_devolve_a_mesma_transacao(accounts):
    first = simple(accounts.mercado, accounts.corrente, 4590, idempotency_key="K1")
    second = simple(accounts.mercado, accounts.corrente, 4590, idempotency_key="K1")
    assert first.pk == second.pk
    assert LedgerTransaction.objects.count() == 1
    assert balance(accounts.corrente) == -4590


def test_chave_reusada_em_outra_operacao(accounts):
    txn = simple(accounts.mercado, accounts.corrente, 100, idempotency_key="K2")
    with pytest.raises(IdempotencyConflictError):
        services.reverse(txn, reason="x", idempotency_key="K2")


def test_estorno_idempotente(accounts):
    txn = simple(accounts.mercado, accounts.corrente, 100)
    a = services.reverse(txn, reason="x", idempotency_key="R1")
    b = services.reverse(txn, reason="x", idempotency_key="R1")
    assert a.pk == b.pk


@pytest.mark.usefixtures("committed_db")
def test_envios_simultaneos_com_a_mesma_chave(accounts):
    """Duas threads, duas conexões, mesma chave: uma única transação."""
    barrier = threading.Barrier(2)
    results, errors = [], []

    def submit():
        try:
            barrier.wait()
            txn = simple(
                accounts.mercado,
                accounts.corrente,
                4590,
                idempotency_key="K-par",
                type=TransactionType.EXPENSE_PAID,
            )
            results.append(txn.pk)
        except Exception as exc:  # noqa: BLE001 - registrado e verificado abaixo
            errors.append(exc)
        finally:
            connection.close()

    threads = [threading.Thread(target=submit) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert errors == []
    assert len(results) == 2 and results[0] == results[1]
    assert LedgerTransaction.objects.count() == 1
