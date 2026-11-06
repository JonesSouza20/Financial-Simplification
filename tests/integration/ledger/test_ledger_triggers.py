"""Gatilhos do banco recusam alterações proibidas mesmo com SQL direto (testing-plan.md §7.3)."""

import pytest
from django.db import DatabaseError, connection, transaction

from apps.ledger.models import AuditLog, TransactionStatus, TransactionType

from .helpers import simple

pytestmark = pytest.mark.usefixtures("on_20_11")


def raw(sql, params=()):
    with transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(sql, params)


def assert_blocked(sql, params=(), message=""):
    with pytest.raises(DatabaseError, match=message):
        raw(sql, params)


@pytest.fixture
def txn(accounts):
    return simple(accounts.mercado, accounts.corrente, 8500)


def test_pernas_nao_mudam_nem_somem(txn):
    posting = txn.postings.first()
    assert_blocked(
        "UPDATE ledger_posting SET amount_cents = 1 WHERE id = %s", [posting.pk], "imutáveis"
    )
    assert_blocked("DELETE FROM ledger_posting WHERE id = %s", [posting.pk], "excluídas")


def test_transacao_nao_e_excluida(txn):
    assert_blocked("DELETE FROM ledger_transaction WHERE id = %s", [txn.pk], "excluídas")


def test_transacao_confirmada_imutavel(txn):
    assert_blocked(
        "UPDATE ledger_transaction SET description = 'outra' WHERE id = %s", [txn.pk], "imutável"
    )
    assert_blocked(
        "UPDATE ledger_transaction SET operation_date = '2026-11-04' WHERE id = %s",
        [txn.pk],
        "imutável",
    )


def test_transicao_invalida(txn):
    assert_blocked(
        "UPDATE ledger_transaction SET status = 'pending' WHERE id = %s", [txn.pk], "transição"
    )
    assert_blocked(
        "UPDATE ledger_transaction SET status = 'cancelled', cancel_reason = 'x' WHERE id = %s",
        [txn.pk],
        "transição",
    )


def test_estorno_sem_vinculo(txn):
    assert_blocked(
        "UPDATE ledger_transaction SET status = 'reversed' WHERE id = %s", [txn.pk], "vínculo"
    )


def test_perna_so_em_rascunho(txn, accounts):
    assert_blocked(
        "INSERT INTO ledger_posting (transaction_id, account_id, amount_cents, memo) "
        "VALUES (%s, %s, 1, '')",
        [txn.pk, accounts.mercado.pk],
        "rascunho",
    )


def test_transacao_nasce_em_rascunho(db):
    assert_blocked(
        "INSERT INTO ledger_transaction (uuid, type, status, operation_date, competence_date, "
        "description, origin, version, created_at, updated_at) VALUES "
        "('00000000000000000000000000000001', %s, 'confirmed', '2026-11-03', '2026-11-03', "
        "'x', 'manual', 1, '2026-11-03', '2026-11-03')",
        [TransactionType.EXPENSE_PAID],
        "rascunho",
    )


def test_finalizacao_desequilibrada(accounts):
    with (
        pytest.raises(DatabaseError, match="somam zero"),
        transaction.atomic(),
        connection.cursor() as cursor,
    ):
        cursor.execute(
            "INSERT INTO ledger_transaction (uuid, type, status, operation_date, "
            "competence_date, description, origin, version, created_at, updated_at) VALUES "
            "('00000000000000000000000000000002', %s, 'draft', '2026-11-03', '2026-11-03', "
            "'x', 'manual', 1, '2026-11-03', '2026-11-03')",
            [TransactionType.EXPENSE_PAID],
        )
        txn_id = cursor.lastrowid
        cursor.execute(
            "INSERT INTO ledger_posting (transaction_id, account_id, amount_cents, memo) "
            "VALUES (%s, %s, 100, '')",
            [txn_id, accounts.mercado.pk],
        )
        cursor.execute(
            "UPDATE ledger_transaction SET status = %s WHERE id = %s",
            [TransactionStatus.CONFIRMED, txn_id],
        )


def test_auditoria_so_insercao(txn):
    log = AuditLog.objects.filter(entity_id=txn.pk).first()
    assert_blocked("UPDATE audit_log SET action = 'x' WHERE id = %s", [log.pk], "só inserção")
    assert_blocked("DELETE FROM audit_log WHERE id = %s", [log.pk], "só inserção")
