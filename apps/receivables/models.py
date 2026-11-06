"""Valores a receber (database-design.md §7; ADR-007, ADR-034).

Parcelas e recebimentos são alocações sobre o ativo "A receber" da pessoa: não criam pernas.
No MVP-1 cada valor a receber tem uma única parcela.
"""

from django.db import models
from django.db.models import Q

from apps.ledger.models import LedgerTransaction
from apps.persons.models import Person


class Receivable(models.Model):
    person = models.ForeignKey(Person, on_delete=models.PROTECT, related_name="receivables")
    origin_kind = models.CharField(max_length=16)  # loan, card_share, opening
    origin_transaction = models.ForeignKey(LedgerTransaction, on_delete=models.PROTECT)
    total_cents = models.BigIntegerField()
    description = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "receivable"

    def __str__(self) -> str:
        return f"{self.person}: {self.description}"


class ReceivableInstallment(models.Model):
    receivable = models.ForeignKey(
        Receivable, on_delete=models.PROTECT, related_name="installments"
    )
    number = models.PositiveSmallIntegerField(default=1)
    due_date = models.DateField()
    amount_cents = models.BigIntegerField()

    class Meta:
        db_table = "receivable_installment"
        constraints = [
            models.UniqueConstraint(fields=["receivable", "number"], name="receivable_inst_unique"),
            models.CheckConstraint(
                name="receivable_inst_positive", condition=Q(amount_cents__gt=0)
            ),
        ]

    def __str__(self) -> str:
        return f"{self.receivable} #{self.number}"


class ReceivableAllocation(models.Model):
    installment = models.ForeignKey(
        ReceivableInstallment, on_delete=models.PROTECT, related_name="allocations"
    )
    transaction = models.ForeignKey(LedgerTransaction, on_delete=models.PROTECT)
    kind = models.CharField(max_length=20)  # receipt, write_off, purchase_reversal
    amount_cents = models.BigIntegerField()

    class Meta:
        db_table = "receivable_allocation"
        constraints = [
            models.CheckConstraint(
                name="receivable_alloc_positive", condition=Q(amount_cents__gt=0)
            )
        ]

    def __str__(self) -> str:
        return f"{self.kind} {self.amount_cents}"
