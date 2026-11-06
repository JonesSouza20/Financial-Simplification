"""Gatilhos de integridade do SQLite (database-design.md §11).

Segunda barreira, além dos serviços: mesmo SQL direto não consegue alterar ou apagar
o que o Ledger já registrou.
"""

TRIGGERS: dict[str, str] = {
    "posting_no_update": """
        CREATE TRIGGER IF NOT EXISTS posting_no_update
        BEFORE UPDATE ON ledger_posting
        BEGIN SELECT RAISE(ABORT, 'ledger: pernas são imutáveis'); END;
    """,
    "posting_no_delete": """
        CREATE TRIGGER IF NOT EXISTS posting_no_delete
        BEFORE DELETE ON ledger_posting
        BEGIN SELECT RAISE(ABORT, 'ledger: pernas não podem ser excluídas'); END;
    """,
    "posting_insert_only_draft": """
        CREATE TRIGGER IF NOT EXISTS posting_insert_only_draft
        BEFORE INSERT ON ledger_posting
        WHEN (SELECT status FROM ledger_transaction WHERE id = NEW.transaction_id) <> 'draft'
        BEGIN SELECT RAISE(ABORT, 'ledger: pernas só entram em transação em rascunho'); END;
    """,
    "txn_no_delete": """
        CREATE TRIGGER IF NOT EXISTS txn_no_delete
        BEFORE DELETE ON ledger_transaction
        BEGIN SELECT RAISE(ABORT, 'ledger: transações não podem ser excluídas'); END;
    """,
    "txn_insert_draft_only": """
        CREATE TRIGGER IF NOT EXISTS txn_insert_draft_only
        BEFORE INSERT ON ledger_transaction
        WHEN NEW.status <> 'draft'
        BEGIN SELECT RAISE(ABORT, 'ledger: transação deve nascer em rascunho'); END;
    """,
    "txn_immutable_closed": """
        CREATE TRIGGER IF NOT EXISTS txn_immutable_closed
        BEFORE UPDATE ON ledger_transaction
        WHEN OLD.status IN ('confirmed', 'reversed', 'cancelled')
         AND (NEW.type <> OLD.type
              OR NEW.operation_date <> OLD.operation_date
              OR NEW.competence_date <> OLD.competence_date
              OR NEW.description <> OLD.description
              OR NEW.uuid <> OLD.uuid)
        BEGIN SELECT RAISE(ABORT, 'ledger: transação encerrada é imutável'); END;
    """,
    "txn_valid_transition": """
        CREATE TRIGGER IF NOT EXISTS txn_valid_transition
        BEFORE UPDATE OF status ON ledger_transaction
        WHEN NEW.status <> OLD.status AND NOT (
               (OLD.status = 'draft' AND NEW.status IN ('forecast', 'pending', 'confirmed'))
            OR (OLD.status = 'forecast' AND NEW.status IN ('pending', 'cancelled'))
            OR (OLD.status = 'pending' AND NEW.status = 'cancelled')
            OR (OLD.status = 'confirmed' AND NEW.status = 'reversed'))
        BEGIN SELECT RAISE(ABORT, 'ledger: transição de estado inválida'); END;
    """,
    "txn_balanced_on_finalize": """
        CREATE TRIGGER IF NOT EXISTS txn_balanced_on_finalize
        BEFORE UPDATE OF status ON ledger_transaction
        WHEN OLD.status = 'draft' AND NEW.status <> 'draft' AND (
              (SELECT COALESCE(SUM(amount_cents), 0) FROM ledger_posting
                WHERE transaction_id = NEW.id) <> 0
           OR (SELECT COUNT(*) FROM ledger_posting WHERE transaction_id = NEW.id) < 2)
        BEGIN SELECT RAISE(ABORT, 'ledger: pernas não somam zero ou são menos de duas'); END;
    """,
    "reversal_requires_link": """
        CREATE TRIGGER IF NOT EXISTS reversal_requires_link
        BEFORE UPDATE OF status ON ledger_transaction
        WHEN OLD.status = 'confirmed' AND NEW.status = 'reversed' AND NOT EXISTS (
            SELECT 1 FROM transaction_link
             WHERE to_transaction_id = NEW.id AND kind = 'reverses')
        BEGIN SELECT RAISE(ABORT, 'ledger: estorno sem vínculo com a original'); END;
    """,
    "link_no_update": """
        CREATE TRIGGER IF NOT EXISTS link_no_update
        BEFORE UPDATE ON transaction_link
        BEGIN SELECT RAISE(ABORT, 'ledger: vínculos são imutáveis'); END;
    """,
    "link_no_delete": """
        CREATE TRIGGER IF NOT EXISTS link_no_delete
        BEFORE DELETE ON transaction_link
        BEGIN SELECT RAISE(ABORT, 'ledger: vínculos não podem ser excluídos'); END;
    """,
    "note_no_update": """
        CREATE TRIGGER IF NOT EXISTS note_no_update
        BEFORE UPDATE ON transaction_note
        BEGIN SELECT RAISE(ABORT, 'ledger: notas só podem ser acrescentadas'); END;
    """,
    "note_no_delete": """
        CREATE TRIGGER IF NOT EXISTS note_no_delete
        BEFORE DELETE ON transaction_note
        BEGIN SELECT RAISE(ABORT, 'ledger: notas só podem ser acrescentadas'); END;
    """,
    "audit_no_update": """
        CREATE TRIGGER IF NOT EXISTS audit_no_update
        BEFORE UPDATE ON audit_log
        BEGIN SELECT RAISE(ABORT, 'auditoria: só inserção'); END;
    """,
    "audit_no_delete": """
        CREATE TRIGGER IF NOT EXISTS audit_no_delete
        BEFORE DELETE ON audit_log
        BEGIN SELECT RAISE(ABORT, 'auditoria: só inserção'); END;
    """,
}

# Gatilhos que bloqueiam DELETE. Só os testes que gravam de verdade os removem,
# e apenas para limpar o banco de teste (database-design.md §15).
DELETE_BLOCKERS = (
    "posting_no_delete",
    "txn_no_delete",
    "link_no_delete",
    "note_no_delete",
    "audit_no_delete",
)


def install_sql() -> list[str]:
    return [sql.strip() for sql in TRIGGERS.values()]


def uninstall_sql(names=None) -> list[str]:
    return [f"DROP TRIGGER IF EXISTS {name};" for name in (names or TRIGGERS)]


def install(connection) -> None:
    with connection.cursor() as cursor:
        for sql in install_sql():
            cursor.execute(sql)


def uninstall(connection, names=None) -> None:
    with connection.cursor() as cursor:
        for sql in uninstall_sql(names):
            cursor.execute(sql)
