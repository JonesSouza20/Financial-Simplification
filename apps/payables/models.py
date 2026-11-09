"""Compromissos, liquidações e recorrências (database-design.md §4.5 a §4.7; ADR-032).

Um compromisso é a extensão 1:1 de uma transação prevista ou pendente. As pernas pretendidas
são imutáveis: trocar valor, categoria ou conta cancela o compromisso e cria outro.
"""

from django.db import models
from django.db.models import Q

from apps.accounts.models import FinancialAccount
from apps.categories.models import Category
from apps.debts.models import Debt
from apps.ledger.models import LedgerTransaction


class CommitmentKind(models.TextChoices):
    BILL = "bill", "Conta a pagar"
    INCOME = "income", "Receita prevista"
    DEBT_INSTALLMENT = "debt_installment", "Parcela de dívida"
    CONSORTIUM = "consortium", "Parcela de consórcio"
    PLANNED_TRANSFER = "planned_transfer", "Aporte planejado"


class Direction(models.TextChoices):
    OUT = "out", "Saída"
    IN = "in", "Entrada"
    INTERNAL = "internal", "Interna"


class ValueType(models.TextChoices):
    FIXED = "fixed", "Fixo"
    VARIABLE = "variable", "Variável"


class PaymentMethod(models.TextChoices):
    DEBIT = "debit", "Débito"
    PIX = "pix", "Pix"
    BOLETO = "boleto", "Boleto"
    CASH = "cash", "Dinheiro"
    AUTO_DEBIT = "auto_debit", "Débito automático"
    OTHER = "other", "Outro"


class ExcessKind(models.TextChoices):
    LATE_FEE = "late_fee", "Juros e multa"
    HIGHER_ACTUAL = "higher_actual", "Valor real maior"


class Frequency(models.TextChoices):
    WEEKLY = "weekly", "Semanal"
    MONTHLY = "monthly", "Mensal"
    YEARLY = "yearly", "Anual"
    EVERY_N_MONTHS = "every_n_months", "A cada N meses"


class DayRule(models.TextChoices):
    FIXED_DAY = "fixed_day", "Dia fixo"
    NTH_BUSINESS_DAY = "nth_business_day", "N-ésimo dia útil"
    LAST_DAY = "last_day", "Último dia do mês"


class RecurrenceRule(models.Model):
    name = models.CharField(max_length=120)
    kind = models.CharField(max_length=20, choices=CommitmentKind.choices)
    frequency = models.CharField(max_length=16, choices=Frequency.choices)
    interval = models.PositiveSmallIntegerField(default=1)
    day_rule = models.CharField(max_length=18, choices=DayRule.choices)
    day_value = models.PositiveSmallIntegerField(null=True, blank=True)
    amount_cents = models.BigIntegerField()
    value_type = models.CharField(max_length=10, choices=ValueType.choices)
    category = models.ForeignKey(Category, null=True, blank=True, on_delete=models.PROTECT)
    financial_account = models.ForeignKey(
        FinancialAccount, null=True, blank=True, on_delete=models.PROTECT
    )
    debt = models.ForeignKey(Debt, null=True, blank=True, on_delete=models.PROTECT)
    payment_method = models.CharField(
        max_length=12, choices=PaymentMethod.choices, null=True, blank=True
    )
    anticipates = models.BooleanField(default=False)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    remaining_count = models.PositiveSmallIntegerField(null=True, blank=True)
    # Até onde já foi materializada. Ocorrência cancelada à mão não volta na próxima renovação.
    generated_until = models.DateField(null=True, blank=True)
    active = models.BooleanField(default=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "recurrence_rule"
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(
                condition=Q(amount_cents__gt=0), name="recurrence_amount_positive"
            ),
            models.CheckConstraint(condition=Q(interval__gte=1), name="recurrence_interval_min"),
        ]

    def __str__(self) -> str:
        return self.name


class Commitment(models.Model):
    transaction = models.OneToOneField(
        LedgerTransaction, on_delete=models.PROTECT, related_name="commitment"
    )
    kind = models.CharField(max_length=20, choices=CommitmentKind.choices)
    direction = models.CharField(max_length=10, choices=Direction.choices)
    due_date = models.DateField()
    effective_due_date = models.DateField()
    planned_amount_cents = models.BigIntegerField()
    value_type = models.CharField(max_length=10, choices=ValueType.choices)
    reference_month = models.CharField(max_length=7, null=True, blank=True)  # AAAA-MM
    expected_account = models.ForeignKey(
        FinancialAccount, null=True, blank=True, on_delete=models.PROTECT
    )
    payment_method = models.CharField(
        max_length=12, choices=PaymentMethod.choices, null=True, blank=True
    )
    anticipates = models.BooleanField(default=False)
    scheduled_debit_date = models.DateField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_reason = models.CharField(max_length=200, null=True, blank=True)
    recurrence = models.ForeignKey(
        RecurrenceRule,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="commitments",
    )
    installment_group = models.CharField(max_length=36, null=True, blank=True)
    installment_number = models.PositiveSmallIntegerField(null=True, blank=True)
    debt = models.ForeignKey(Debt, null=True, blank=True, on_delete=models.PROTECT)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "commitment"
        ordering = ["due_date", "id"]
        indexes = [
            models.Index(fields=["effective_due_date"], name="commitment_effective_due"),
            models.Index(fields=["due_date"], name="commitment_due"),
            models.Index(fields=["recurrence", "due_date"], name="commitment_recurrence_due"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(planned_amount_cents__gt=0), name="commitment_amount_positive"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.transaction.description} ({self.due_date:%d/%m/%Y})"


class Settlement(models.Model):
    commitment = models.ForeignKey(Commitment, on_delete=models.PROTECT, related_name="settlements")
    transaction = models.ForeignKey(
        LedgerTransaction, on_delete=models.PROTECT, related_name="settlements"
    )
    # Parte aplicada ao compromisso, nunca acima do aberto; excedente fica em `excess_kind`.
    amount_cents = models.BigIntegerField()
    excess_kind = models.CharField(max_length=14, choices=ExcessKind.choices, null=True, blank=True)

    class Meta:
        db_table = "settlement"
        constraints = [
            models.UniqueConstraint(
                fields=["commitment", "transaction"], name="settlement_unique_pair"
            ),
            models.CheckConstraint(
                condition=Q(amount_cents__gt=0), name="settlement_amount_positive"
            ),
        ]

    def __str__(self) -> str:
        return f"liquidação {self.amount_cents} do compromisso {self.commitment_id}"
