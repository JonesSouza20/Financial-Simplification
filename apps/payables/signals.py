"""Ligações com o Ledger e o calendário (RN-042, RN-044; I-05, I-10)."""

from __future__ import annotations

from django.dispatch import receiver

from apps.calendar_br.signals import holidays_changed
from apps.ledger import audit
from apps.ledger import services as ledger
from apps.ledger.invariants import EXTRA_CHECKS, Violation
from apps.ledger.models import LedgerTransaction, TransactionStatus
from apps.ledger.signals import transaction_reversed

from . import services
from .models import Commitment, Settlement


@receiver(transaction_reversed)
def _reopen_on_reversal(sender, original, reversal, **kwargs):
    """Estornar a liquidação reabre o aberto; um encerramento anterior deixa de valer (RN-044)."""
    for settlement in Settlement.objects.filter(transaction=original):
        commitment = settlement.commitment
        if commitment.closed_at:
            reason = commitment.closed_reason
            services._update(commitment, closed_at=None, closed_reason=None)
            audit.log("reopen", commitment, before={"closed_reason": reason})


@receiver(holidays_changed)
def _on_holidays(sender, **kwargs):
    services.refresh_due_dates()


def _block_settlement_correction(txn: LedgerTransaction) -> str | None:
    if Settlement.objects.filter(transaction=txn).exists():
        return "Este lançamento é o pagamento de uma conta. Estorne e pague de novo."
    return None


def check() -> list[Violation]:
    """I-05 e I-10 (business-rules.md §21) e pernas pretendidas iguais ao valor planejado."""
    found = []
    today = ledger.today()
    planned = Commitment.objects.select_related("transaction").prefetch_related(
        "transaction__postings__account"
    )
    for commitment in planned:
        settled = services.settled_cents(commitment)
        if settled > commitment.planned_amount_cents:
            found.append(
                Violation("I-05", f"compromisso {commitment.pk} liquidado acima do planejado")
            )
        postings = list(commitment.transaction.postings.all())
        gross = sum(p.amount_cents for p in postings if p.amount_cents > 0)
        if gross != commitment.planned_amount_cents:
            found.append(
                Violation("I-05", f"compromisso {commitment.pk} difere das pernas pretendidas")
            )
        if (
            commitment.transaction.status in services.PLANNED
            and commitment.closed_at is None
            and commitment.due_date >= today
            and settled < commitment.planned_amount_cents
            and any(p.account.archived_at for p in postings)
        ):
            found.append(
                Violation("I-10", f"compromisso {commitment.pk} aponta para conta arquivada")
            )
    for settlement in Settlement.objects.exclude(
        transaction__status__in=[TransactionStatus.CONFIRMED, TransactionStatus.REVERSED]
    ):
        found.append(Violation("I-05", f"liquidação {settlement.pk} sem transação confirmada"))
    return found


if check not in EXTRA_CHECKS:
    EXTRA_CHECKS.append(check)
if _block_settlement_correction not in ledger.CORRECTION_GUARDS:
    ledger.CORRECTION_GUARDS.append(_block_settlement_correction)
