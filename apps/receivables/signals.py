from django.dispatch import receiver

from apps.ledger.invariants import EXTRA_CHECKS
from apps.ledger.signals import transaction_reversed

from . import services


@receiver(transaction_reversed)
def reduce_receivable(sender, original, reversal, **kwargs):
    services.on_reversal(original, reversal)


if services.check not in EXTRA_CHECKS:
    EXTRA_CHECKS.append(services.check)
