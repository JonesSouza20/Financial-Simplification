"""Modelos do Livro-Razão (database-design.md §4).

Nada aqui é excluído nem sobrescrito: os gatilhos de `db_triggers.py` garantem isso no banco,
e `services.py` é a única porta de escrita.
"""

import uuid

from django.db import models
from django.db.models import Q


class AccountKind(models.TextChoices):
    ASSET = "asset", "Ativo"
    LIABILITY = "liability", "Passivo"
    INCOME = "income", "Receita"
    EXPENSE = "expense", "Despesa"
    EQUITY = "equity", "Patrimônio"


class AssetClass(models.TextChoices):
    FREE = "free", "Livre"
    RESERVE = "reserve", "Reserva"
    BENEFIT = "benefit", "Benefício"
    RECEIVABLE = "receivable", "A receber"


class TransactionType(models.TextChoices):
    """Tipos T01 a T28 de business-rules.md §4."""

    INCOME_RECEIVED = "T01_income_received", "Receita recebida"
    EXPENSE_PAID = "T02_expense_paid", "Despesa paga"
    EXPENSE_BENEFIT = "T03_expense_benefit", "Despesa paga com benefício"
    BENEFIT_CREDIT = "T04_benefit_credit", "Crédito de benefício"
    TRANSFER = "T05_transfer", "Transferência entre contas"
    RESERVE_DEPOSIT = "T06_reserve_deposit", "Aporte em reserva"
    RESERVE_WITHDRAWAL = "T07_reserve_withdrawal", "Retirada de reserva"
    CARD_PURCHASE = "T08_card_purchase", "Compra no cartão"
    CARD_THIRD_PARTY = "T09_card_third_party", "Compra de terceiro no cartão"
    CARD_MIXED = "T10_card_mixed", "Compra mista no cartão"
    INVOICE_PAYMENT = "T11_invoice_payment", "Pagamento de fatura"
    CARD_CHARGE = "T12_card_charge", "Encargo do cartão"
    CARD_COMMERCIAL_REVERSAL = "T13_card_commercial_reversal", "Estorno comercial no cartão"
    LOAN_TO_PERSON = "T14_loan_to_person", "Empréstimo a terceiro"
    PERSON_RECEIPT = "T15_person_receipt", "Recebimento de terceiro"
    RECEIVABLE_WRITE_OFF = "T16_receivable_write_off", "Baixa de valor a receber"
    DEBT_INSTALLMENT = "T17_debt_installment", "Parcela de dívida"
    DEBT_EXTRA_PAYMENT = "T18_debt_extra_payment", "Amortização extraordinária"
    CONSORTIUM_INSTALLMENT = "T19_consortium_installment", "Parcela de consórcio"
    REFUND = "T20_refund", "Reembolso"
    LATE_FEE = "T21_late_fee", "Juros e multa por atraso"
    RESERVE_YIELD = "T22_reserve_yield", "Rendimento de reserva"
    OPENING_BALANCE = "T23_opening_balance", "Saldo de abertura"
    OPENING_CARD_ITEM = "T24_opening_card_item", "Item de abertura de cartão"
    OPENING_CARD_THIRD_PARTY = "T25_opening_card_third_party", "Item de abertura de terceiro"
    OPENING_DEBT = "T26_opening_debt", "Abertura de dívida"
    RECONCILIATION_ADJUSTMENT = "T27_reconciliation_adjustment", "Ajuste de conciliação"
    TECHNICAL_REVERSAL = "T28_technical_reversal", "Estorno técnico"


OPENING_TYPES = frozenset(
    {
        TransactionType.OPENING_BALANCE,
        TransactionType.OPENING_CARD_ITEM,
        TransactionType.OPENING_CARD_THIRD_PARTY,
        TransactionType.OPENING_DEBT,
    }
)

# Compras no cartão: únicas que aceitam estorno comercial e estorno parcial (RN-121, RN-083).
CARD_PURCHASE_TYPES = frozenset(
    {
        TransactionType.CARD_PURCHASE,
        TransactionType.CARD_THIRD_PARTY,
        TransactionType.CARD_MIXED,
    }
)


class TransactionStatus(models.TextChoices):
    DRAFT = "draft", "Rascunho (interno)"
    FORECAST = "forecast", "Previsto"
    PENDING = "pending", "Pendente"
    CONFIRMED = "confirmed", "Confirmado"
    CANCELLED = "cancelled", "Cancelado"
    REVERSED = "reversed", "Estornado"


# Estados cujas pernas contam nos saldos reais (RN-011).
EFFECTIVE_STATUSES = (TransactionStatus.CONFIRMED, TransactionStatus.REVERSED)


class TransactionOrigin(models.TextChoices):
    MANUAL = "manual", "Manual"
    SYSTEM = "system", "Sistema"
    IMPORT = "import", "Importação"


class LinkKind(models.TextChoices):
    REVERSES = "reverses", "Estorna"
    PARTIALLY_REVERSES = "partially_reverses", "Estorna parcialmente"
    CORRECTS = "corrects", "Corrige"
    REFUNDS = "refunds", "Reembolsa"


class LedgerAccount(models.Model):
    code = models.CharField(max_length=64, unique=True)
    kind = models.CharField(max_length=16, choices=AccountKind.choices)
    asset_class = models.CharField(max_length=16, choices=AssetClass.choices, null=True, blank=True)
    name = models.CharField(max_length=120)
    owner_type = models.CharField(max_length=32, null=True, blank=True)
    owner_id = models.BigIntegerField(null=True, blank=True)
    is_system = models.BooleanField(default=False)
    archived_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "ledger_account"
        constraints = [
            models.CheckConstraint(
                name="ledger_account_asset_class_required",
                condition=(Q(kind="asset") & Q(asset_class__isnull=False))
                | (~Q(kind="asset") & Q(asset_class__isnull=True)),
            ),
            models.UniqueConstraint(
                fields=["owner_type", "owner_id"],
                condition=Q(owner_type__isnull=False),
                name="ledger_account_unique_owner",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.get_kind_display()})"


class LedgerTransaction(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    type = models.CharField(max_length=40, choices=TransactionType.choices)
    status = models.CharField(
        max_length=16, choices=TransactionStatus.choices, default=TransactionStatus.DRAFT
    )
    operation_date = models.DateField()
    competence_date = models.DateField()
    description = models.CharField(max_length=200)
    cancel_reason = models.CharField(max_length=200, null=True, blank=True)
    origin = models.CharField(
        max_length=16, choices=TransactionOrigin.choices, default=TransactionOrigin.MANUAL
    )
    external_id = models.CharField(max_length=120, null=True, blank=True)
    dedup_hash = models.CharField(max_length=64, null=True, blank=True)
    review_status = models.CharField(max_length=16, null=True, blank=True)
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "ledger_transaction"
        indexes = [
            models.Index(fields=["status", "operation_date"], name="txn_status_opdate"),
            models.Index(fields=["status", "competence_date"], name="txn_status_compdate"),
            models.Index(fields=["dedup_hash"], name="txn_dedup_hash"),
        ]
        constraints = [
            models.CheckConstraint(
                name="ledger_transaction_cancel_reason",
                condition=~Q(status="cancelled") | Q(cancel_reason__isnull=False),
            ),
            models.UniqueConstraint(
                fields=["origin", "external_id"],
                condition=Q(external_id__isnull=False),
                name="ledger_transaction_unique_external",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.get_type_display()} · {self.description} ({self.get_status_display()})"


class LedgerPosting(models.Model):
    transaction = models.ForeignKey(
        LedgerTransaction, on_delete=models.PROTECT, related_name="postings"
    )
    account = models.ForeignKey(LedgerAccount, on_delete=models.PROTECT, related_name="postings")
    amount_cents = models.BigIntegerField()
    memo = models.CharField(max_length=120, blank=True, default="")

    class Meta:
        db_table = "ledger_posting"
        indexes = [models.Index(fields=["account", "transaction"], name="posting_account_txn")]
        constraints = [
            models.CheckConstraint(name="ledger_posting_nonzero", condition=~Q(amount_cents=0)),
        ]

    def __str__(self) -> str:
        return f"conta {self.account_id}: {self.amount_cents} centavos"


class TransactionLink(models.Model):
    kind = models.CharField(max_length=24, choices=LinkKind.choices)
    from_transaction = models.ForeignKey(
        LedgerTransaction, on_delete=models.PROTECT, related_name="links_out"
    )
    to_transaction = models.ForeignKey(
        LedgerTransaction, on_delete=models.PROTECT, related_name="links_in"
    )
    amount_cents = models.BigIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "transaction_link"
        constraints = [
            models.UniqueConstraint(
                fields=["to_transaction"],
                condition=Q(kind="reverses"),
                name="transaction_link_single_reversal",
            ),
            models.CheckConstraint(
                name="transaction_link_not_self",
                condition=~Q(from_transaction=models.F("to_transaction")),
            ),
        ]

    def __str__(self) -> str:
        return f"{self.from_transaction_id} {self.kind} {self.to_transaction_id}"


class TransactionNote(models.Model):
    transaction = models.ForeignKey(
        LedgerTransaction, on_delete=models.PROTECT, related_name="notes"
    )
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "transaction_note"

    def __str__(self) -> str:
        return self.text[:60]


class IdempotencyRecord(models.Model):
    key = models.CharField(max_length=64, primary_key=True)
    operation = models.CharField(max_length=40)
    result_type = models.CharField(max_length=40)
    result_id = models.BigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "idempotency_record"

    def __str__(self) -> str:
        return f"{self.operation}: {self.key}"


class AuditLog(models.Model):
    at = models.DateTimeField(auto_now_add=True)
    device_id = models.BigIntegerField(null=True, blank=True)
    action = models.CharField(max_length=40)
    entity_type = models.CharField(max_length=40)
    entity_id = models.BigIntegerField()
    before_json = models.JSONField(null=True, blank=True)
    after_json = models.JSONField(null=True, blank=True)
    reason = models.CharField(max_length=200, null=True, blank=True)

    class Meta:
        db_table = "audit_log"
        indexes = [models.Index(fields=["entity_type", "entity_id"], name="audit_entity")]

    def __str__(self) -> str:
        return f"{self.action} {self.entity_type}#{self.entity_id}"
