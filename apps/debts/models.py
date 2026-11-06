"""Dívidas e consórcio (database-design.md §8). No MVP-1: registro provisório (RF-DIV-00)."""

from django.db import models

from apps.ledger.models import LedgerAccount


class DebtKind(models.TextChoices):
    LOAN = "loan", "Empréstimo ou financiamento"
    CONSORTIUM = "consortium", "Consórcio"


class Debt(models.Model):
    kind = models.CharField(max_length=12, choices=DebtKind.choices)
    creditor = models.CharField(max_length=60)
    description = models.CharField(max_length=120)
    original_amount_cents = models.BigIntegerField(null=True, blank=True)
    monthly_rate = models.CharField(max_length=20, null=True, blank=True)  # decimal em texto
    amortization_system = models.CharField(max_length=8, null=True, blank=True)
    contract_installment_cents = models.BigIntegerField(null=True, blank=True)
    remaining_installments = models.PositiveSmallIntegerField(null=True, blank=True)
    due_day = models.PositiveSmallIntegerField()
    extra_payment_default = models.CharField(max_length=12, default="reduce_term")
    ledger_account = models.OneToOneField(
        LedgerAccount, null=True, blank=True, on_delete=models.PROTECT
    )
    archived_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "debt"
        ordering = ["kind", "creditor"]

    def __str__(self) -> str:
        return f"{self.creditor}: {self.description}"
