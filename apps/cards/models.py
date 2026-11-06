"""Cartões, compras e itens de abertura (database-design.md §6; ADR-004, ADR-031)."""

from django.db import models
from django.db.models import F, Q

from apps.accounts.models import FinancialAccount
from apps.ledger.models import LedgerAccount, LedgerTransaction
from apps.persons.models import Person


class Card(models.Model):
    name = models.CharField(max_length=60)
    issuer = models.CharField(max_length=60, blank=True, default="")
    brand = models.CharField(max_length=30, blank=True, default="")
    credit_limit_cents = models.BigIntegerField()
    closing_day = models.PositiveSmallIntegerField()
    due_day = models.PositiveSmallIntegerField()
    closing_day_goes_next = models.BooleanField(default=True)
    remainder_on = models.CharField(max_length=5, default="first")
    consumes_full_limit = models.BooleanField(default=True)
    default_payment_account = models.ForeignKey(
        FinancialAccount, null=True, blank=True, on_delete=models.PROTECT
    )
    ledger_account = models.OneToOneField(LedgerAccount, on_delete=models.PROTECT)
    archived_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "card"
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(
                name="card_days_valid",
                condition=Q(
                    closing_day__gte=1, closing_day__lte=31, due_day__gte=1, due_day__lte=31
                )
                & ~Q(closing_day=F("due_day")),
            ),
            models.CheckConstraint(
                name="card_limit_positive", condition=Q(credit_limit_cents__gt=0)
            ),
        ]

    def __str__(self) -> str:
        return self.name


class OpeningKind(models.TextChoices):
    CLOSED_INVOICE = "closed_invoice", "Fatura fechada a vencer"
    OPEN_INVOICE = "open_invoice", "Compras da fatura aberta"
    REMAINING = "remaining_installments", "Parcelas restantes de compra antiga"


class CardPurchase(models.Model):
    transaction = models.OneToOneField(LedgerTransaction, on_delete=models.PROTECT)
    card = models.ForeignKey(Card, on_delete=models.PROTECT, related_name="purchases")
    purchase_date = models.DateField()
    description = models.CharField(max_length=200)
    total_cents = models.BigIntegerField()
    installments_count = models.PositiveSmallIntegerField(default=1)
    installment_cents = models.BigIntegerField()
    first_installment_cents = models.BigIntegerField()
    is_opening_item = models.BooleanField(default=False)
    opening_kind = models.CharField(
        max_length=24, choices=OpeningKind.choices, null=True, blank=True
    )
    installments_already_billed = models.PositiveSmallIntegerField(default=0)
    opening_amount_cents = models.BigIntegerField(null=True, blank=True)
    first_invoice_due_date = models.DateField(null=True, blank=True)

    class Meta:
        db_table = "card_purchase"
        constraints = [
            models.CheckConstraint(
                name="card_purchase_installments_sum",
                condition=Q(
                    total_cents=F("first_installment_cents")
                    + F("installment_cents") * (F("installments_count") - 1)
                ),
            ),
            models.CheckConstraint(
                name="card_purchase_installments_range",
                condition=Q(installments_count__gte=1, installments_count__lte=48),
            ),
        ]

    def __str__(self) -> str:
        return self.description


class CardPurchaseShare(models.Model):
    card_purchase = models.ForeignKey(CardPurchase, on_delete=models.PROTECT, related_name="shares")
    person = models.ForeignKey(Person, on_delete=models.PROTECT)
    amount_cents = models.BigIntegerField()

    class Meta:
        db_table = "card_purchase_share"
        constraints = [
            models.CheckConstraint(name="card_share_positive", condition=Q(amount_cents__gt=0))
        ]

    def __str__(self) -> str:
        return f"{self.person}: {self.amount_cents}"


class CardLimitEvent(models.Model):
    """Mudança de limite total e conciliação de limite (RN-087, RN-088). Sem perna no Ledger."""

    card = models.ForeignKey(Card, on_delete=models.PROTECT, related_name="limit_events")
    event_date = models.DateField()
    kind = models.CharField(max_length=16)  # limit_change, reconciliation
    new_limit_cents = models.BigIntegerField(null=True, blank=True)
    informed_available_cents = models.BigIntegerField(null=True, blank=True)
    calculated_available_cents = models.BigIntegerField(null=True, blank=True)
    difference_cents = models.BigIntegerField(null=True, blank=True)
    probable_cause = models.CharField(max_length=24, blank=True, default="")
    notes = models.CharField(max_length=200, blank=True, default="")

    class Meta:
        db_table = "card_limit_event"

    def __str__(self) -> str:
        return f"{self.card} {self.kind} {self.event_date}"
