"""Verificação de uma cópia do banco com SQL puro (sem o Django), usada antes de gravar um
backup e ao restaurar (ADR-021; architecture.md §10.1). Cobre a integridade do SQLite e as
invariantes estruturais do Ledger (I-01, I-02, I-03, I-08, I-09)."""

from __future__ import annotations

import sqlite3

from django.conf import settings

OPENING_TYPES = (
    "T23_opening_balance",
    "T24_opening_card_item",
    "T25_opening_card_third_party",
    "T26_opening_debt",
)


def _scalar(conn: sqlite3.Connection, sql: str, params=()):
    return conn.execute(sql, params).fetchone()[0]


def problems(path) -> list[str]:
    """Lista de problemas encontrados; vazia quando a cópia está íntegra."""
    found: list[str] = []
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        integrity = _scalar(conn, "PRAGMA integrity_check")
        if integrity != "ok":
            found.append(f"integrity_check: {integrity}")
        fk = conn.execute("PRAGMA foreign_key_check").fetchall()
        if fk:
            found.append(f"foreign_key_check: {len(fk)} referência(s) quebrada(s)")
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "ledger_transaction" not in tables:
            return [*found, "tabelas do Ledger ausentes"]
        unbalanced = _scalar(
            conn,
            """
            SELECT COUNT(*) FROM (SELECT t.id FROM ledger_transaction t
              LEFT JOIN ledger_posting p ON p.transaction_id = t.id
              WHERE t.status <> 'draft' GROUP BY t.id
              HAVING COALESCE(SUM(p.amount_cents), 0) <> 0)""",
        )
        if unbalanced:
            found.append(f"I-01: {unbalanced} transação(ões) não somam zero")
        drafts = _scalar(conn, "SELECT COUNT(*) FROM ledger_transaction WHERE status = 'draft'")
        if drafts:
            found.append(f"I-01: {drafts} transação(ões) em rascunho")
        thin = _scalar(
            conn,
            """
            SELECT COUNT(*) FROM (SELECT t.id FROM ledger_transaction t
              LEFT JOIN ledger_posting p ON p.transaction_id = t.id AND p.amount_cents <> 0
              WHERE t.status IN ('confirmed', 'reversed') GROUP BY t.id HAVING COUNT(p.id) < 2)""",
        )
        if thin:
            found.append(f"I-02: {thin} transação(ões) com menos de duas pernas")
        orphan = _scalar(
            conn,
            """
            SELECT COUNT(*) FROM ledger_transaction t WHERE t.status = 'reversed' AND NOT EXISTS (
              SELECT 1 FROM transaction_link l
              WHERE l.to_transaction_id = t.id AND l.kind = 'reverses')""",
        )
        if orphan:
            found.append(f"I-03: {orphan} estorno(s) sem vínculo")
        total = _scalar(
            conn,
            """
            SELECT COALESCE(SUM(p.amount_cents), 0) FROM ledger_posting p
            JOIN ledger_transaction t ON t.id = p.transaction_id
            WHERE t.status IN ('confirmed', 'reversed')""",
        )
        if total:
            found.append(f"I-08: soma global das pernas = {total}")
        marks = ",".join("?" * len(OPENING_TYPES))
        early = _scalar(
            conn,
            f"SELECT COUNT(*) FROM ledger_transaction WHERE status <> 'draft' "  # noqa: S608
            f"AND operation_date < ? AND type NOT IN ({marks})",
            (settings.FINANCAS_START_DATE.isoformat(), *OPENING_TYPES),
        )
        if early:
            found.append(f"I-09: {early} transação(ões) antes de 01/11/2026")
    finally:
        conn.close()
    return found


def counts(path) -> dict:
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        return {
            table: _scalar(conn, f"SELECT COUNT(*) FROM {table}")  # noqa: S608
            for table in (
                "ledger_transaction",
                "ledger_posting",
                "ledger_account",
                "financial_account",
                "audit_log",
            )
        }
    finally:
        conn.close()


def schema(path) -> str:
    """Última migração aplicada, para conferir compatibilidade na restauração."""
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        row = conn.execute("SELECT COUNT(*), MAX(applied) FROM django_migrations").fetchone()
        return f"{row[0]} migrações"
    finally:
        conn.close()


def summary(path) -> dict:
    """Resumo mostrado antes de restaurar (security-plan.md §7.2, passo 5): saldo de cada
    conta, data e descrição do último lançamento. Só para exibição; nunca vai ao manifesto."""
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        accounts = conn.execute(
            """
            SELECT f.name, COALESCE(SUM(CASE WHEN t.status IN ('confirmed', 'reversed')
                                        THEN p.amount_cents END), 0)
            FROM financial_account f
            LEFT JOIN ledger_posting p ON p.account_id = f.ledger_account_id
            LEFT JOIN ledger_transaction t ON t.id = p.transaction_id
            WHERE f.archived_at IS NULL GROUP BY f.id ORDER BY f.name"""
        ).fetchall()
        last = conn.execute(
            "SELECT operation_date, description FROM ledger_transaction "
            "WHERE status IN ('confirmed', 'reversed') ORDER BY operation_date DESC, id DESC "
            "LIMIT 1"
        ).fetchone()
    finally:
        conn.close()
    return {
        "accounts": [{"name": n, "cents": c} for n, c in accounts],
        "last": {"date": last[0], "description": last[1]} if last else None,
    }
