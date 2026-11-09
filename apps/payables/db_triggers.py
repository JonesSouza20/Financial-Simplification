"""Gatilhos de compromissos e liquidações (database-design.md §11).

Ficam separados dos gatilhos do Ledger porque as tabelas nascem em migração posterior.
"""

TRIGGERS: dict[str, str] = {
    "settlement_requires_confirmed": """
        CREATE TRIGGER IF NOT EXISTS settlement_requires_confirmed
        BEFORE INSERT ON settlement
        WHEN (SELECT status FROM ledger_transaction WHERE id = NEW.transaction_id) <> 'confirmed'
        BEGIN SELECT RAISE(ABORT, 'ledger: liquidação exige transação confirmada'); END;
    """,
    "settlement_no_update": """
        CREATE TRIGGER IF NOT EXISTS settlement_no_update
        BEFORE UPDATE ON settlement
        BEGIN SELECT RAISE(ABORT, 'ledger: liquidações são imutáveis'); END;
    """,
    "settlement_no_delete": """
        CREATE TRIGGER IF NOT EXISTS settlement_no_delete
        BEFORE DELETE ON settlement
        BEGIN SELECT RAISE(ABORT, 'ledger: liquidações não podem ser excluídas'); END;
    """,
    "commitment_no_delete": """
        CREATE TRIGGER IF NOT EXISTS commitment_no_delete
        BEFORE DELETE ON commitment
        BEGIN SELECT RAISE(ABORT, 'ledger: compromissos não podem ser excluídos'); END;
    """,
}

DELETE_BLOCKERS = ("settlement_no_delete", "commitment_no_delete")


def install(connection) -> None:
    with connection.cursor() as cursor:
        for sql in TRIGGERS.values():
            cursor.execute(sql.strip())


def uninstall(connection, names=None) -> None:
    with connection.cursor() as cursor:
        for name in names or TRIGGERS:
            cursor.execute(f"DROP TRIGGER IF EXISTS {name};")
