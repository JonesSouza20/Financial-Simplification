"""Categorias: criação, renomeação e arquivamento (RF-CAT-01 a 03)."""

from __future__ import annotations

import uuid

from django.db import transaction
from django.utils import timezone

from apps.ledger import audit
from apps.ledger.errors import InvalidStateError, InvalidTransactionError
from apps.ledger.models import LedgerAccount

from . import defaults
from .models import Category, CategoryKind


def _ledger_account(kind: str, name: str) -> LedgerAccount:
    return LedgerAccount.objects.create(
        code=f"{kind}:cat:{uuid.uuid4().hex[:12]}", kind=kind, name=name, owner_type="category"
    )


@transaction.atomic
def create(
    *,
    name: str,
    kind: str,
    parent: Category | None = None,
    accepts_benefit: bool = False,
    is_system: bool = False,
    system_key: str | None = None,
    sort_order: int = 0,
) -> Category:
    name = name.strip()
    if not name:
        raise InvalidTransactionError("Informe o nome da categoria.")
    if parent is not None and (parent.kind != kind or parent.parent_id):
        raise InvalidTransactionError("Subcategoria precisa ter o mesmo tipo e um único nível.")
    account = _ledger_account(kind, name)
    category = Category.objects.create(
        name=name,
        kind=kind,
        parent=parent,
        accepts_benefit=accepts_benefit,
        is_system=is_system,
        system_key=system_key,
        sort_order=sort_order,
        ledger_account=account,
    )
    LedgerAccount.objects.filter(pk=account.pk).update(owner_id=category.pk)
    return category


@transaction.atomic
def rename(category: Category, name: str) -> Category:
    name = name.strip()
    if not name:
        raise InvalidTransactionError("Informe o nome da categoria.")
    if category.is_system:
        raise InvalidStateError("Categorias de sistema não podem ser renomeadas.")
    before = {"name": category.name}
    Category.objects.filter(pk=category.pk).update(name=name)
    LedgerAccount.objects.filter(pk=category.ledger_account_id).update(name=name)
    category.refresh_from_db()
    audit.log("rename", category, before=before, after={"name": name})
    return category


@transaction.atomic
def archive(category: Category) -> None:
    if category.is_system:
        raise InvalidStateError("Categorias de sistema não podem ser arquivadas.")
    from apps.payables.services import open_on_account

    now = timezone.now()
    ids = [category.pk, *category.children.values_list("pk", flat=True)]
    related = list(Category.objects.filter(pk__in=ids).select_related("ledger_account"))
    if any(open_on_account(cat.ledger_account) for cat in related):  # I-10
        raise InvalidStateError("Esta categoria tem contas previstas ou pendentes.")
    for cat in related:
        Category.objects.filter(pk=cat.pk).update(archived_at=now)
        LedgerAccount.objects.filter(pk=cat.ledger_account_id).update(archived_at=now)
    audit.log("archive", category)


def by_key(key: str) -> Category:
    return Category.objects.get(system_key=key)


def selectable(kind: str, *, benefit: bool = False):
    """Categorias que aceitam lançamento: ativas, folhas (sem filhas ativas) e não de sistema."""
    parents_with_children = Category.objects.filter(
        parent__isnull=False, archived_at__isnull=True
    ).values("parent_id")
    qs = Category.objects.filter(kind=kind, archived_at__isnull=True, is_system=False).exclude(
        pk__in=parents_with_children
    )
    if benefit:
        qs = qs.filter(accepts_benefit=True)
    return qs.select_related("parent", "ledger_account").order_by(
        "parent__sort_order", "sort_order", "name"
    )


def seed_defaults() -> None:
    """Carga inicial idempotente (chamada pela migração)."""
    if Category.objects.exists():
        return
    for order, (name, subs, benefit, key) in enumerate(defaults.EXPENSES):
        parent = create(
            name=name,
            kind=CategoryKind.EXPENSE,
            accepts_benefit=benefit,
            system_key=key,
            sort_order=order,
        )
        for sub_order, sub in enumerate(subs):
            create(
                name=sub,
                kind=CategoryKind.EXPENSE,
                parent=parent,
                sort_order=sub_order,
                accepts_benefit=sub in defaults.BENEFIT_SUBCATEGORIES,
            )
    for order, (name, key) in enumerate(defaults.SYSTEM_EXPENSES, start=100):
        create(
            name=name, kind=CategoryKind.EXPENSE, is_system=True, system_key=key, sort_order=order
        )
    for order, (name, key) in enumerate(defaults.INCOMES):
        create(
            name=name,
            kind=CategoryKind.INCOME,
            system_key=key,
            sort_order=order,
            is_system=key in defaults.SYSTEM_INCOME_KEYS,
        )
