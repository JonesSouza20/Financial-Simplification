"""Pessoas que devem ao usuário (database-design.md §5.3)."""

from django.db import models

from apps.ledger.models import LedgerAccount


class Person(models.Model):
    name = models.CharField(max_length=60, unique=True)
    notes = models.CharField(max_length=200, blank=True, default="")
    ledger_account = models.OneToOneField(LedgerAccount, on_delete=models.PROTECT)
    archived_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "person"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name
