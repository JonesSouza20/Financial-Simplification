"""Trilha de auditoria (RN-190 a RN-192). Só inserção; nunca guarda segredos."""

from .models import AuditLog, LedgerTransaction


def snapshot_transaction(txn: LedgerTransaction) -> dict:
    return {
        "uuid": str(txn.uuid),
        "type": txn.type,
        "status": txn.status,
        "operation_date": txn.operation_date.isoformat(),
        "competence_date": txn.competence_date.isoformat(),
        "description": txn.description,
        "legs": [
            {"account": p.account.code, "amount_cents": p.amount_cents, "memo": p.memo}
            for p in txn.postings.select_related("account").order_by("id")
        ],
    }


def record_event(
    action: str, entity_type: str, entity_id: int, *, after=None, reason: str | None = None
) -> AuditLog:
    """Evento sem entidade carregada (ex.: login, bloqueio). Nunca recebe senha, PIN ou token."""
    return AuditLog.objects.create(
        action=action, entity_type=entity_type, entity_id=entity_id, after_json=after, reason=reason
    )


def log(action: str, entity, *, before=None, after=None, reason: str | None = None) -> AuditLog:
    return AuditLog.objects.create(
        action=action,
        entity_type=entity._meta.db_table,
        entity_id=entity.pk,
        before_json=before,
        after_json=after,
        reason=reason,
    )
