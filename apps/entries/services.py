"""Lançamentos do usuário em linguagem comum, traduzidos em pernas do Ledger.

Gasto, recebimento e transferência (T01 a T07), lista de movimentações, Corrigir,
Estornar e Desfazer (RF-LAN-01 a 06, RF-CON-04; F-010 a F-014, F-021).
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field

from django.db.models import Exists, OuterRef, Q
from django.utils import timezone

from apps.accounts.models import FinancialAccount
from apps.categories.models import Category, CategoryKind
from apps.ledger import services as ledger
from apps.ledger.errors import InvalidStateError, InvalidTransactionError
from apps.ledger.models import (
    LedgerPosting,
    LedgerTransaction,
    LinkKind,
    TransactionLink,
    TransactionStatus,
    TransactionType,
)
from apps.ledger.services import Leg
from apps.money import Money

EXPENSE, INCOME, TRANSFER, CARD = "expense", "income", "transfer", "card"

EXPENSE_TYPES = {TransactionType.EXPENSE_PAID, TransactionType.EXPENSE_BENEFIT}
INCOME_TYPES = {TransactionType.INCOME_RECEIVED, TransactionType.BENEFIT_CREDIT}
TRANSFER_TYPES = {
    TransactionType.TRANSFER,
    TransactionType.RESERVE_DEPOSIT,
    TransactionType.RESERVE_WITHDRAWAL,
}
EDITABLE_TYPES = EXPENSE_TYPES | INCOME_TYPES | TRANSFER_TYPES
CARD_TYPES = {
    TransactionType.CARD_PURCHASE,
    TransactionType.CARD_THIRD_PARTY,
    TransactionType.CARD_MIXED,
    TransactionType.OPENING_CARD_ITEM,
    TransactionType.OPENING_CARD_THIRD_PARTY,
}
UNDO_WINDOW = datetime.timedelta(minutes=2)


@dataclass(frozen=True)
class EntryInput:
    kind: str
    amount: Money
    account: FinancialAccount
    on: datetime.date
    description: str = ""
    category: Category | None = None
    destination: FinancialAccount | None = None
    competence: datetime.date | None = None


def build(entry: EntryInput) -> tuple[str, list[Leg], str]:
    """Valida e devolve (tipo, pernas, descrição)."""
    if not entry.amount.is_positive:
        raise InvalidTransactionError("Informe um valor maior que zero.")
    if entry.account.archived_at:
        raise InvalidTransactionError("Esta conta está arquivada.")
    acc = entry.account.ledger_account
    if entry.kind == TRANSFER:
        dest = entry.destination
        if dest is None or dest.pk == entry.account.pk:
            raise InvalidTransactionError("Escolha contas de origem e destino diferentes.")
        if "benefit" in (entry.account.asset_class, dest.asset_class):
            raise InvalidTransactionError("Benefícios (VR/VA) não podem ser transferidos.")
        if dest.archived_at:
            raise InvalidTransactionError("A conta de destino está arquivada.")
        classes = (entry.account.asset_class, dest.asset_class)
        txn_type = {
            ("free", "reserve"): TransactionType.RESERVE_DEPOSIT,
            ("reserve", "free"): TransactionType.RESERVE_WITHDRAWAL,
        }.get(classes, TransactionType.TRANSFER)
        legs = [Leg(dest.ledger_account, entry.amount), Leg(acc, -entry.amount)]
        default = f"Transferência: {entry.account.name} → {dest.name}"
        return txn_type, legs, entry.description.strip() or default

    category = entry.category
    if category is None or category.archived_at:
        raise InvalidTransactionError("Escolha uma categoria ativa.")
    benefit = entry.account.asset_class == "benefit"
    if entry.kind == EXPENSE:
        if category.kind != CategoryKind.EXPENSE:
            raise InvalidTransactionError("Escolha uma categoria de despesa.")
        if benefit and not category.accepts_benefit:
            raise InvalidTransactionError(
                f"A categoria {category} não aceita pagamento com benefício."
            )
        txn_type = TransactionType.EXPENSE_BENEFIT if benefit else TransactionType.EXPENSE_PAID
        legs = [Leg(category.ledger_account, entry.amount), Leg(acc, -entry.amount)]
    elif entry.kind == INCOME:
        if category.kind != CategoryKind.INCOME:
            raise InvalidTransactionError("Escolha uma categoria de receita.")
        if benefit and category.system_key != "benefit_income":
            raise InvalidTransactionError("Crédito de VR/VA usa a categoria Benefícios.")
        txn_type = TransactionType.BENEFIT_CREDIT if benefit else TransactionType.INCOME_RECEIVED
        legs = [Leg(acc, entry.amount), Leg(category.ledger_account, -entry.amount)]
    else:
        raise InvalidTransactionError("Tipo de lançamento inválido.")
    return txn_type, legs, entry.description.strip() or str(category)


def record(entry, *, idempotency_key: str | None = None) -> LedgerTransaction:
    """Grava gasto, recebimento, transferência (EntryInput) ou compra no cartão."""
    from apps.cards.services import PurchaseInput, record_purchase

    if isinstance(entry, PurchaseInput):
        return record_purchase(entry, idempotency_key=idempotency_key)
    txn_type, legs, description = build(entry)
    return ledger.record(
        type=txn_type,
        legs=legs,
        operation_date=entry.on,
        competence_date=entry.competence,
        description=description,
        idempotency_key=idempotency_key,
    )


def possible_duplicate(entry) -> LedgerTransaction | None:
    """Mesma conta (ou cartão), mesmo valor e data, nas últimas 24 horas (RN-171). Só avisa."""
    since = timezone.now() - datetime.timedelta(hours=24)
    account = entry.card.ledger_account if hasattr(entry, "card") else entry.account.ledger_account
    amount = entry.total if hasattr(entry, "card") else entry.amount
    return (
        LedgerTransaction.objects.filter(
            status=TransactionStatus.CONFIRMED,
            operation_date=entry.on,
            created_at__gte=since,
            postings__account=account,
            postings__amount_cents__in=[amount.cents, -amount.cents],
        )
        .order_by("-id")
        .first()
    )


def correct(
    txn: LedgerTransaction, entry: EntryInput, *, reason: str, idempotency_key: str | None = None
) -> LedgerTransaction:
    if txn.type not in EDITABLE_TYPES:
        raise InvalidStateError("Este lançamento não pode ser corrigido por esta tela.")
    txn_type, legs, description = build(entry)
    return ledger.correct(
        txn,
        legs=legs,
        reason=reason,
        description=description,
        operation_date=entry.on,
        competence_date=entry.competence or entry.on,
        type=txn_type,
        idempotency_key=idempotency_key,
    )


def undo(txn: LedgerTransaction) -> LedgerTransaction:
    """Desfazer logo após salvar = estorno técnico (RN-122). Nada é apagado."""
    if timezone.now() - txn.created_at > UNDO_WINDOW:
        raise InvalidStateError("O prazo para desfazer passou. Use Estornar ou Corrigir.")
    return ledger.reverse(txn, reason="Desfeito logo após o lançamento")


# Leitura ------------------------------------------------------------------------------


@dataclass
class EntryView:
    txn: LedgerTransaction
    kind: str
    label: str
    amount: Money
    signed: Money
    account: str = ""
    destination: str = ""
    category: str = ""
    editable: bool = False
    legs: list[dict] = field(default_factory=list)


def _owners(postings):
    fin_ids = [p.account.owner_id for p in postings if p.account.owner_type == "financial_account"]
    cat_ids = [p.account.owner_id for p in postings if p.account.owner_type == "category"]
    fins = {a.pk: a for a in FinancialAccount.objects.filter(pk__in=fin_ids)}
    cats = {c.pk: c for c in Category.objects.filter(pk__in=cat_ids).select_related("parent")}
    return fins, cats


def describe(txn: LedgerTransaction) -> EntryView:
    postings = list(txn.postings.select_related("account").order_by("id"))
    fins, cats = _owners(postings)
    fin_legs = [
        (p, fins.get(p.account.owner_id))
        for p in postings
        if p.account.owner_type == "financial_account"
    ]
    cat_legs = [
        (p, cats.get(p.account.owner_id)) for p in postings if p.account.owner_type == "category"
    ]
    gross = Money(sum(p.amount_cents for p in postings if p.amount_cents > 0))
    view = EntryView(
        txn=txn,
        kind="other",
        label=txn.get_type_display(),
        amount=gross,
        signed=gross,
        editable=txn.type in EDITABLE_TYPES and txn.status == TransactionStatus.CONFIRMED,
    )
    view.legs = [
        {
            "name": p.account.name,
            "amount": Money(abs(p.amount_cents)),
            "direction": "entrada" if p.amount_cents > 0 else "saída",
        }
        for p in postings
    ]
    if txn.type in EXPENSE_TYPES:
        view.kind, view.label = EXPENSE, "Gasto"
        view.signed = -gross
    elif txn.type in INCOME_TYPES:
        view.kind, view.label = INCOME, "Recebimento"
    elif txn.type in TRANSFER_TYPES:
        view.kind, view.label = TRANSFER, "Transferência"
        view.signed = Money(0)
        for p, acc in fin_legs:
            if acc and p.amount_cents < 0:
                view.account = acc.name
            elif acc:
                view.destination = acc.name
    elif txn.type in CARD_TYPES:
        view.kind = CARD
        view.label = (
            "Compra no cartão"
            if txn.type
            in (
                TransactionType.CARD_PURCHASE,
                TransactionType.CARD_THIRD_PARTY,
                TransactionType.CARD_MIXED,
            )
            else "Item de abertura do cartão"
        )
        view.signed = Money(0)  # não mexe em conta financeira: vai para o cartão
        view.account = ", ".join(p.account.name for p in postings if p.account.owner_type == "card")
        people = [
            p.account.name.replace("A receber: ", "")
            for p in postings
            if p.account.owner_type == "person"
        ]
        if people:
            view.destination = "parte de " + ", ".join(people)
    elif fin_legs:
        net = sum(p.amount_cents for p, _ in fin_legs)
        view.signed = Money(net)
    if fin_legs and not view.account:
        view.account = ", ".join(a.name for _, a in fin_legs if a)
    if cat_legs:
        view.category = ", ".join(str(c) for _, c in cat_legs if c)
    return view


def movements(
    *,
    start: datetime.date | None = None,
    end: datetime.date | None = None,
    account: FinancialAccount | None = None,
    category: Category | None = None,
    status: str | None = None,
    text: str = "",
    by_competence: bool = False,
    show_all: bool = False,
):
    """Movimentações com filtros (RF-LAN-06). Por padrão oculta cancelados e pares estornados."""
    date_field = "competence_date" if by_competence else "operation_date"
    qs = LedgerTransaction.objects.exclude(status=TransactionStatus.DRAFT)
    if not show_all:
        is_reversal = TransactionLink.objects.filter(
            from_transaction=OuterRef("pk"),
            kind__in=[LinkKind.REVERSES, LinkKind.PARTIALLY_REVERSES],
        )
        qs = qs.exclude(status__in=[TransactionStatus.CANCELLED, TransactionStatus.REVERSED])
        qs = qs.exclude(Exists(is_reversal))
    if start:
        qs = qs.filter(**{f"{date_field}__gte": start})
    if end:
        qs = qs.filter(**{f"{date_field}__lte": end})
    if account:
        qs = qs.filter(postings__account=account.ledger_account)
    if category:
        qs = qs.filter(postings__account=category.ledger_account)
    if status:
        qs = qs.filter(status=status)
    if text.strip():
        qs = qs.filter(Q(description__icontains=text.strip()))
    return qs.distinct().order_by(f"-{date_field}", "-id")


def account_history(account: FinancialAccount):
    return (
        LedgerPosting.objects.filter(
            account=account.ledger_account,
            transaction__status__in=[TransactionStatus.CONFIRMED, TransactionStatus.REVERSED],
        )
        .select_related("transaction")
        .order_by("-transaction__operation_date", "-transaction_id")
    )
