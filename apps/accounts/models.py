"""Contas financeiras (database-design.md §5.1). Cada uma é uma conta contábil de ativo."""

from django.db import models

from apps.ledger.models import LedgerAccount


class AccountType(models.TextChoices):
    CHECKING = "checking", "Conta corrente"
    DIGITAL = "digital", "Conta digital"
    CASH = "cash", "Dinheiro em espécie"
    RESERVE = "reserve", "Reserva"
    BENEFIT = "benefit", "Benefício (VR/VA)"
    OTHER = "other", "Outra"


class AssetClassChoice(models.TextChoices):
    FREE = "free", "Livre"
    RESERVE = "reserve", "Reserva"
    BENEFIT = "benefit", "Benefício"


DEFAULT_CLASS = {
    AccountType.CHECKING: AssetClassChoice.FREE,
    AccountType.DIGITAL: AssetClassChoice.FREE,
    AccountType.CASH: AssetClassChoice.FREE,
    AccountType.RESERVE: AssetClassChoice.RESERVE,
    AccountType.BENEFIT: AssetClassChoice.BENEFIT,
    AccountType.OTHER: AssetClassChoice.FREE,
}


class FinancialAccount(models.Model):
    name = models.CharField(max_length=60)
    account_type = models.CharField(max_length=16, choices=AccountType.choices)
    asset_class = models.CharField(max_length=16, choices=AssetClassChoice.choices)
    institution = models.CharField(max_length=60, blank=True, default="")
    ledger_account = models.OneToOneField(LedgerAccount, on_delete=models.PROTECT)
    opening_date = models.DateField()
    archived_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "financial_account"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name
