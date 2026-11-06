"""O verificador de invariantes detecta dados corrompidos (I-01 a I-04, I-08, I-09).

Para simular corrupção, os gatilhos são removidos dentro da transação do teste,
que é desfeita ao final (DDL do SQLite é transacional).
"""

import pytest
from django.db import connection

from apps.ledger import db_triggers
from apps.ledger.invariants import check_all

from .helpers import simple

pytestmark = pytest.mark.usefixtures("on_20_11")


def corrupt(sql, params=()):
    db_triggers.uninstall(connection)
    with connection.cursor() as cursor:
        cursor.execute(sql, params)
    db_triggers.install(connection)


def codes():
    return {v.code for v in check_all()}


def test_banco_integro_sem_violacoes(accounts):
    simple(accounts.mercado, accounts.corrente, 100)
    assert check_all() == []


def test_detecta_perna_alterada(accounts):
    txn = simple(accounts.mercado, accounts.corrente, 100)
    corrupt(
        "UPDATE ledger_posting SET amount_cents = 99 WHERE transaction_id = %s "
        "AND amount_cents > 0",
        [txn.pk],
    )
    assert {"I-01", "I-08"} <= codes()


def test_detecta_rascunho_e_transacao_sem_pernas(accounts):
    txn = simple(accounts.mercado, accounts.corrente, 100)
    corrupt("DELETE FROM ledger_posting WHERE transaction_id = %s", [txn.pk])
    assert "I-02" in codes()
    corrupt("UPDATE ledger_transaction SET status = 'draft' WHERE id = %s", [txn.pk])
    assert "I-01" in codes()


def test_detecta_estorno_sem_vinculo(accounts):
    txn = simple(accounts.mercado, accounts.corrente, 100)
    corrupt("UPDATE ledger_transaction SET status = 'reversed' WHERE id = %s", [txn.pk])
    assert "I-03" in codes()


def test_detecta_data_anterior_ao_inicio(accounts):
    txn = simple(accounts.mercado, accounts.corrente, 100)
    corrupt("UPDATE ledger_transaction SET operation_date = '2026-10-15' WHERE id = %s", [txn.pk])
    assert "I-09" in codes()
