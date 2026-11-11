"""Cartões no MVP-1: registro provisório, itens de abertura, pagamento e estimativa de faturas.

Compras geram as pernas definitivas na data da compra (ADR-004). Faturas reais chegam no
MVP-3; até lá, o valor de cada fatura é estimado pelas regras de ciclo (RN-070 a RN-075).
"""

from __future__ import annotations

import datetime
import uuid
from collections import defaultdict
from dataclasses import dataclass, field

from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.accounts.models import FinancialAccount
from apps.categories.models import Category, CategoryKind
from apps.ledger import audit
from apps.ledger import services as ledger
from apps.ledger.errors import InvalidTransactionError
from apps.ledger.models import (
    LedgerAccount,
    LedgerTransaction,
    LinkKind,
    TransactionStatus,
    TransactionType,
)
from apps.ledger.services import Leg
from apps.money import Money, split_installments
from apps.persons.models import Person

from . import cycle
from .models import Card, CardPurchase, CardPurchaseShare, OpeningKind


@transaction.atomic
def _check_appearance(bank: str, color: str) -> None:
    from .brands import BANKS, COLORS

    if bank and bank not in BANKS:
        raise InvalidTransactionError("Banco desconhecido.")
    if color and color not in COLORS:
        raise InvalidTransactionError("Cor desconhecida.")


def set_appearance(card: Card, *, bank: str, color: str) -> Card:
    """Troca banco e cor do cartão desenhado. Não mexe em nenhum valor."""
    _check_appearance(bank, color)
    before = {"bank": card.bank, "color": card.color}
    Card.objects.filter(pk=card.pk).update(bank=bank, color=color, version=F("version") + 1)
    card.refresh_from_db()
    audit.log("appearance", card, before=before, after={"bank": bank, "color": color})
    return card


def create_card(
    *,
    name: str,
    credit_limit: Money,
    closing_day: int,
    due_day: int,
    issuer: str = "",
    brand: str = "",
    default_payment_account: FinancialAccount | None = None,
    closing_day_goes_next: bool = True,
    remainder_on: str = "first",
    bank: str = "",
    color: str = "",
) -> Card:
    name = name.strip()
    _check_appearance(bank, color)
    if not name:
        raise InvalidTransactionError("Informe o nome do cartão.")
    if not credit_limit.is_positive:
        raise InvalidTransactionError("O limite deve ser maior que zero.")
    if not (1 <= closing_day <= 31 and 1 <= due_day <= 31) or closing_day == due_day:
        raise InvalidTransactionError(
            "Dias de fechamento e vencimento devem ser de 1 a 31 e diferentes."
        )
    account = LedgerAccount.objects.create(
        code=f"liability:card:{uuid.uuid4().hex[:12]}",
        kind="liability",
        name=name,
        owner_type="card",
    )
    card = Card.objects.create(
        name=name,
        bank=bank,
        color=color,
        issuer=issuer.strip(),
        brand=brand.strip(),
        credit_limit_cents=credit_limit.cents,
        closing_day=closing_day,
        due_day=due_day,
        closing_day_goes_next=closing_day_goes_next,
        remainder_on=remainder_on,
        default_payment_account=default_payment_account,
        ledger_account=account,
    )
    LedgerAccount.objects.filter(pk=account.pk).update(owner_id=card.pk)
    audit.log("create", card, after={"name": name, "limit_cents": credit_limit.cents})
    return card


def active_cards():
    return Card.objects.filter(archived_at__isnull=True).select_related("ledger_account")


def liability(card: Card) -> Money:
    """Saldo devedor do cartão, inclusive parcelas futuras (RN-086)."""
    return ledger.display_balance(card.ledger_account)


def available_limit(card: Card) -> Money:
    return Money(card.credit_limit_cents) - liability(card)


# Compras ------------------------------------------------------------------------------


@dataclass(frozen=True)
class PurchaseInput:
    card: Card
    total: Money
    on: datetime.date
    installments: int = 1
    category: Category | None = None
    description: str = ""
    shares: tuple[tuple[Person, Money], ...] = field(default_factory=tuple)


def _split(card: Card, total: Money, count: int) -> list[Money]:
    if count == 1:
        return [total]
    return split_installments(total, count, card.remainder_on)


def build_purchase(inp: PurchaseInput) -> tuple[str, list[Leg], str, Money]:
    """Valida e devolve (tipo, pernas, descrição, parte própria). T08, T09 ou T10."""
    if inp.card.archived_at:
        raise InvalidTransactionError("Este cartão está arquivado.")
    if not inp.total.is_positive:
        raise InvalidTransactionError("Informe um valor maior que zero.")
    if not 1 <= inp.installments <= 48:
        raise InvalidTransactionError("Parcelas: de 1 a 48.")
    shared = Money.sum([m for _, m in inp.shares])
    if any(not m.is_positive for _, m in inp.shares):
        raise InvalidTransactionError("A parte de cada pessoa deve ser maior que zero.")
    own = inp.total - shared
    if own.is_negative:
        raise InvalidTransactionError("As partes de outras pessoas passam do valor da compra.")
    legs: list[Leg] = []
    if own.is_positive:
        cat = inp.category
        if cat is None or cat.kind != CategoryKind.EXPENSE or cat.archived_at:
            raise InvalidTransactionError("Escolha a categoria da sua parte da compra.")
        legs.append(Leg(cat.ledger_account, own, "parte própria"))
    for person, cents in inp.shares:
        legs.append(Leg(person.ledger_account, cents, f"parte de {person.name}"))
    legs.append(Leg(inp.card.ledger_account, -inp.total))
    if not inp.shares:
        txn_type = TransactionType.CARD_PURCHASE
    elif own.is_zero:
        txn_type = TransactionType.CARD_THIRD_PARTY
    else:
        txn_type = TransactionType.CARD_MIXED
    default = str(inp.category) if inp.category and own.is_positive else "Compra no cartão"
    return txn_type, legs, inp.description.strip() or default, own


@transaction.atomic
def record_purchase(inp: PurchaseInput, *, idempotency_key: str | None = None):
    txn_type, legs, description, _ = build_purchase(inp)
    txn = ledger.record(
        type=txn_type,
        legs=legs,
        operation_date=inp.on,
        description=description,
        idempotency_key=idempotency_key,
    )
    if CardPurchase.objects.filter(transaction=txn).exists():
        return txn  # reenvio idempotente
    purchase = CardPurchase.objects.create(
        transaction=txn,
        card=inp.card,
        purchase_date=inp.on,
        description=description,
        total_cents=inp.total.cents,
        installments_count=inp.installments,
        **_installment_fields(inp.total.cents, inp.installments),
    )
    _create_shares(
        purchase,
        inp.shares,
        cycle.first_due(
            inp.on, inp.card.closing_day, inp.card.due_day, inp.card.closing_day_goes_next
        ),
    )
    return txn


def _installment_fields(total_cents: int, count: int) -> dict:
    """Valor-base e primeira parcela gravados (primeira + base × (n − 1) = total).

    São informativos: as parcelas efetivas vêm sempre de `_split`, que respeita a regra
    de resto do cartão (RN-005).
    """
    base = total_cents // count
    return {"installment_cents": base, "first_installment_cents": total_cents - base * (count - 1)}


def _create_shares(purchase, shares, due: datetime.date) -> None:
    from apps.receivables import services as receivables

    for person, cents in shares:
        CardPurchaseShare.objects.create(
            card_purchase=purchase, person=person, amount_cents=cents.cents
        )
        receivables.create(
            person=person,
            origin_kind="card_share",
            origin_transaction=purchase.transaction,
            total=cents,
            due_date=due,
            description=f"{purchase.description} (cartão {purchase.card})",
        )


# Itens de abertura ---------------------------------------------------------------------


def next_due_from_start(card: Card) -> datetime.date:
    return cycle.first_due(
        settings.FINANCAS_START_DATE, card.closing_day, card.due_day, card.closing_day_goes_next
    )


@transaction.atomic
def record_opening_item(
    *,
    card: Card,
    kind: str,
    description: str,
    amount: Money | None = None,
    due_date: datetime.date | None = None,
    purchase_date: datetime.date | None = None,
    total: Money | None = None,
    installments: int = 1,
    billed: int = 0,
    person: Person | None = None,
) -> LedgerTransaction:
    """Item de abertura em 01/11/2026 (RN-089, T24/T25). Próprio vai contra o patrimônio."""
    start = settings.FINANCAS_START_DATE
    description = description.strip() or OpeningKind(kind).label
    if kind == OpeningKind.REMAINING:
        if total is None or not total.is_positive or not 2 <= installments <= 48:
            raise InvalidTransactionError("Informe o total e o número de parcelas (2 a 48).")
        if not 0 <= billed < installments:
            raise InvalidTransactionError("Parcelas já faturadas devem ser menos que o total.")
        parts = _split(card, total, installments)
        amount = Money.sum(parts[billed:])
        first_due = due_date or next_due_from_start(card)
        orig = purchase_date or start
    elif kind in (OpeningKind.CLOSED_INVOICE, OpeningKind.OPEN_INVOICE):
        if amount is None or not amount.is_positive:
            raise InvalidTransactionError("Informe o valor do item.")
        total, installments, billed, parts = amount, 1, 0, [amount]
        first_due = due_date or next_due_from_start(card)
        orig = purchase_date or start
    else:
        raise InvalidTransactionError("Tipo de item de abertura inválido.")
    if person is None:
        equity = ledger.system_account("equity:opening")
        legs = [Leg(equity, amount), Leg(card.ledger_account, -amount)]
        txn_type = TransactionType.OPENING_CARD_ITEM
    else:
        legs = [
            Leg(person.ledger_account, amount, f"parte de {person.name}"),
            Leg(card.ledger_account, -amount),
        ]
        txn_type = TransactionType.OPENING_CARD_THIRD_PARTY
    txn = ledger.record(
        type=txn_type,
        legs=legs,
        operation_date=start,
        description=f"Abertura {card.name}: {description}",
    )
    purchase = CardPurchase.objects.create(
        transaction=txn,
        card=card,
        purchase_date=orig,
        description=description,
        total_cents=total.cents,
        installments_count=installments,
        **_installment_fields(total.cents, installments),
        is_opening_item=True,
        opening_kind=kind,
        installments_already_billed=billed,
        opening_amount_cents=amount.cents,
        first_invoice_due_date=first_due,
    )
    if person is not None:
        from apps.receivables import services as receivables

        CardPurchaseShare.objects.create(
            card_purchase=purchase, person=person, amount_cents=amount.cents
        )
        receivables.create(
            person=person,
            origin_kind="opening",
            origin_transaction=txn,
            total=amount,
            due_date=first_due,
            description=description,
        )
    return txn


# Pagamento -----------------------------------------------------------------------------


def pay(
    *,
    card: Card,
    account: FinancialAccount,
    amount: Money,
    on: datetime.date,
    idempotency_key: str | None = None,
) -> LedgerTransaction:
    """Pagamento do cartão (T11): liquida passivo; não é despesa (RN-164)."""
    if not amount.is_positive:
        raise InvalidTransactionError("Informe um valor maior que zero.")
    if account.asset_class == "benefit":
        raise InvalidTransactionError("Cartão não pode ser pago com VR/VA.")
    return ledger.record(
        type=TransactionType.INVOICE_PAYMENT,
        legs=[Leg(card.ledger_account, amount), Leg(account.ledger_account, -amount)],
        operation_date=on,
        description=f"Pagamento {card.name}",
        idempotency_key=idempotency_key,
    )


# Estimativa de faturas (RN-075) ---------------------------------------------------------


@dataclass
class EstimatedInvoice:
    due_date: datetime.date
    amount: Money
    overdue: bool = False


def _parts_by_due(card: Card, purchase: CardPurchase) -> list[tuple[datetime.date, int]]:
    total = Money(purchase.total_cents)
    parts = _split(card, total, purchase.installments_count)
    if purchase.is_opening_item:
        remaining = [p.cents for p in parts[purchase.installments_already_billed :]]
        first = purchase.first_invoice_due_date
        return [(cycle.nth_due(first, i + 1, card.due_day), c) for i, c in enumerate(remaining)]
    first = cycle.first_due(
        purchase.purchase_date, card.closing_day, card.due_day, card.closing_day_goes_next
    )
    return [(cycle.nth_due(first, i + 1, card.due_day), p.cents) for i, p in enumerate(parts)]


def estimate(card: Card, today: datetime.date | None = None) -> list[EstimatedInvoice]:
    """Faturas estimadas com valor em aberto. A soma é sempre o saldo devedor do cartão.

    Parcelas pelas regras de ciclo; estornos parciais como crédito na fatura do estorno;
    pagamentos e qualquer diferença abatidos da fatura mais antiga (RN-078).
    """
    today = today or timezone.localdate()
    charges: dict[datetime.date, int] = defaultdict(int)
    purchases = card.purchases.filter(transaction__status=TransactionStatus.CONFIRMED)
    for purchase in purchases:
        for due, cents in _parts_by_due(card, purchase):
            charges[due] += cents
        for link in purchase.transaction.links_in.filter(
            kind=LinkKind.PARTIALLY_REVERSES, from_transaction__status=TransactionStatus.CONFIRMED
        ).select_related("from_transaction"):
            due = cycle.first_due(
                link.from_transaction.operation_date,
                card.closing_day,
                card.due_day,
                card.closing_day_goes_next,
            )
            charges[due] -= link.amount_cents
    owed = liability(card).cents
    settled = sum(charges.values()) - owed  # pagamentos e diferenças a abater
    dues = sorted(charges)
    for due in dues:
        if settled <= 0:
            break
        take = min(settled, max(charges[due], 0))
        charges[due] -= take
        settled -= take
    if settled != 0:  # crédito a favor (pagamento acima) ou cobrança fora das compras
        nxt = next((d for d in dues if d >= today), None) or cycle.first_due(
            today, card.closing_day, card.due_day, card.closing_day_goes_next
        )
        charges[nxt] -= settled
    return [
        EstimatedInvoice(due, Money(cents), overdue=due < today and cents > 0)
        for due, cents in sorted(charges.items())
        if cents
    ]


def due_until(card: Card, until: datetime.date, today: datetime.date | None = None) -> Money:
    """Parte estimada do cartão com vencimento original antes de `until` (RN-075, RN-143)."""
    return Money.sum([inv.amount for inv in estimate(card, today) if inv.due_date < until])


def recent_purchases(card: Card, limit: int = 30):
    return (
        card.purchases.select_related("transaction")
        .prefetch_related("shares__person")
        .order_by("-purchase_date", "-id")[:limit]
    )


def payments(card: Card):
    return LedgerTransaction.objects.filter(
        type=TransactionType.INVOICE_PAYMENT, postings__account=card.ledger_account
    ).order_by("-operation_date", "-id")
