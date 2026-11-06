"""Cadastro de pessoas (RF-REC-01). Cada pessoa tem uma conta "A receber" no Ledger."""

import uuid

from django.db import transaction

from apps.ledger import audit
from apps.ledger.errors import InvalidTransactionError
from apps.ledger.models import LedgerAccount

from .models import Person


@transaction.atomic
def get_or_create(name: str, notes: str = "") -> Person:
    name = " ".join((name or "").split())
    if not name:
        raise InvalidTransactionError("Informe o nome da pessoa.")
    existing = Person.objects.filter(name__iexact=name).first()
    if existing:
        return existing
    account = LedgerAccount.objects.create(
        code=f"asset:person:{uuid.uuid4().hex[:12]}",
        kind="asset",
        asset_class="receivable",
        name=f"A receber: {name}",
        owner_type="person",
    )
    person = Person.objects.create(name=name, notes=notes, ledger_account=account)
    LedgerAccount.objects.filter(pk=account.pk).update(owner_id=person.pk)
    audit.log("create", person, after={"name": name})
    return person


def active():
    return Person.objects.filter(archived_at__isnull=True).select_related("ledger_account")
