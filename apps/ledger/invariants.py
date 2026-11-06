"""Verificação das invariantes do Ledger (business-rules.md §21; architecture.md §6.6).

Na Fase 1A: I-01, I-02, I-03, I-04, I-08 e I-09. As demais entram com seus módulos.
Usada pelos testes, pelo backup (Fase 1D) e pela tela "Saúde dos dados".
"""

from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings
from django.db import connection

from .models import EFFECTIVE_STATUSES, OPENING_TYPES, LedgerAccount
from .services import account_balance


@dataclass(frozen=True)
class Violation:
    code: str
    detail: str


def _rows(sql: str, params=()) -> list[tuple]:
    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        return cursor.fetchall()


def check_all() -> list[Violation]:
    violations: list[Violation] = []
    effective = tuple(str(s) for s in EFFECTIVE_STATUSES)

    # I-01: toda transação soma zero; nenhum rascunho sobrevive ao commit.
    for (txn_id,) in _rows(
        """SELECT t.id FROM ledger_transaction t
           LEFT JOIN ledger_posting p ON p.transaction_id = t.id
           WHERE t.status <> 'draft'
           GROUP BY t.id HAVING COALESCE(SUM(p.amount_cents), 0) <> 0"""
    ):
        violations.append(Violation("I-01", f"transação {txn_id} não soma zero"))
    for (txn_id,) in _rows("SELECT id FROM ledger_transaction WHERE status = 'draft'"):
        violations.append(Violation("I-01", f"transação {txn_id} ficou em rascunho"))

    # I-02: confirmada ou estornada tem pelo menos duas pernas não nulas.
    for (txn_id,) in _rows(
        """SELECT t.id FROM ledger_transaction t
           LEFT JOIN ledger_posting p ON p.transaction_id = t.id AND p.amount_cents <> 0
           WHERE t.status IN (%s, %s)
           GROUP BY t.id HAVING COUNT(p.id) < 2""",
        effective,
    ):
        violations.append(Violation("I-02", f"transação {txn_id} tem menos de duas pernas"))

    # I-03: estornos coerentes.
    for link_id, to_status, from_status in _rows(
        """SELECT l.id, o.status, r.status FROM transaction_link l
           JOIN ledger_transaction o ON o.id = l.to_transaction_id
           JOIN ledger_transaction r ON r.id = l.from_transaction_id
           WHERE l.kind = 'reverses'"""
    ):
        if to_status != "reversed" or from_status != "confirmed":
            violations.append(Violation("I-03", f"vínculo de estorno {link_id} incoerente"))
    for (txn_id,) in _rows(
        """SELECT t.id FROM ledger_transaction t WHERE t.status = 'reversed' AND NOT EXISTS (
             SELECT 1 FROM transaction_link l
             WHERE l.to_transaction_id = t.id AND l.kind = 'reverses')"""
    ):
        violations.append(Violation("I-03", f"transação {txn_id} estornada sem vínculo"))
    # Original estornada + todos os seus estornos somam zero por conta.
    for txn_id, account_id, _total in _rows(
        """SELECT o.id, p.account_id, SUM(p.amount_cents) FROM ledger_transaction o
           JOIN ledger_posting p ON p.transaction_id = o.id
              OR p.transaction_id IN (
                   SELECT l.from_transaction_id FROM transaction_link l
                   WHERE l.to_transaction_id = o.id
                     AND l.kind IN ('reverses', 'partially_reverses'))
           WHERE o.status = 'reversed'
           GROUP BY o.id, p.account_id HAVING SUM(p.amount_cents) <> 0"""
    ):
        violations.append(
            Violation("I-03", f"estorno da transação {txn_id} não espelha a conta {account_id}")
        )
    # Estornos parciais nunca passam do valor original.
    for txn_id, partial, gross in _rows(
        """SELECT o.id,
                  (SELECT COALESCE(SUM(l.amount_cents), 0) FROM transaction_link l
                    WHERE l.to_transaction_id = o.id AND l.kind = 'partially_reverses'),
                  (SELECT COALESCE(SUM(p.amount_cents), 0) FROM ledger_posting p
                    WHERE p.transaction_id = o.id AND p.amount_cents > 0)
           FROM ledger_transaction o
           WHERE EXISTS (SELECT 1 FROM transaction_link l
                         WHERE l.to_transaction_id = o.id AND l.kind = 'partially_reverses')"""
    ):
        if partial > gross:
            violations.append(Violation("I-03", f"estornos parciais excedem a transação {txn_id}"))

    # I-04: saldo recalculado do zero (SQL direto) = saldo exibido (serviço).
    raw = dict(
        _rows(
            """SELECT p.account_id, SUM(p.amount_cents) FROM ledger_posting p
               JOIN ledger_transaction t ON t.id = p.transaction_id
               WHERE t.status IN (%s, %s) GROUP BY p.account_id""",
            effective,
        )
    )
    for account in LedgerAccount.objects.all():
        if account_balance(account).cents != raw.get(account.pk, 0):
            violations.append(Violation("I-04", f"saldo divergente na conta {account.code}"))

    # I-08: equação patrimonial ⇔ soma global das pernas efetivas = 0.
    (total,) = _rows(
        """SELECT COALESCE(SUM(p.amount_cents), 0) FROM ledger_posting p
           JOIN ledger_transaction t ON t.id = p.transaction_id
           WHERE t.status IN (%s, %s)""",
        effective,
    )[0]
    if total != 0:
        violations.append(Violation("I-08", f"equação patrimonial desequilibrada em {total}"))

    # I-09: nada antes do início, exceto abertura.
    opening = tuple(str(t) for t in OPENING_TYPES)
    marks = ", ".join(["%s"] * len(opening))
    for (txn_id,) in _rows(
        f"""SELECT id FROM ledger_transaction
            WHERE status <> 'draft' AND operation_date < %s AND type NOT IN ({marks})""",  # noqa: S608
        (settings.FINANCAS_START_DATE.isoformat(), *opening),
    ):
        violations.append(Violation("I-09", f"transação {txn_id} anterior ao início do uso"))

    return violations
