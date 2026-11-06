"""Categorias de receita e despesa (database-design.md §5.2)."""

from django.db import models
from django.db.models import Q

from apps.ledger.models import LedgerAccount


class CategoryKind(models.TextChoices):
    INCOME = "income", "Receita"
    EXPENSE = "expense", "Despesa"


class Category(models.Model):
    name = models.CharField(max_length=60)
    kind = models.CharField(max_length=8, choices=CategoryKind.choices)
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="children"
    )
    is_system = models.BooleanField(default=False)
    system_key = models.CharField(max_length=40, null=True, blank=True, unique=True)
    accepts_benefit = models.BooleanField(default=False)
    sort_order = models.PositiveIntegerField(default=0)
    ledger_account = models.OneToOneField(LedgerAccount, on_delete=models.PROTECT)
    archived_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "category"
        ordering = ["kind", "sort_order", "name"]
        constraints = [
            models.CheckConstraint(
                name="category_system_not_archived",
                condition=Q(is_system=False) | Q(archived_at__isnull=True),
            )
        ]

    def __str__(self) -> str:
        return f"{self.parent.name} › {self.name}" if self.parent_id else self.name
