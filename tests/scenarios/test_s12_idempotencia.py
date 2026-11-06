"""S12 parte A — duplo envio do pagamento do Cartão A (reference-scenarios.md; RN-170).

As partes B (MVP-2) e C (MVP-3) entram com compromissos e faturas.
"""

import pytest

from apps.ledger import services
from apps.ledger.models import LedgerTransaction, TransactionType
from apps.ledger.services import Leg
from apps.money import Money
from tests.integration.ledger.helpers import day

pytestmark = pytest.mark.usefixtures("on_20_11")


def pay_card(accounts, key):
    return services.record(
        type=TransactionType.INVOICE_PAYMENT,
        legs=[Leg(accounts.cartao_a, Money(123000)), Leg(accounts.corrente, Money(-123000))],
        operation_date=day(5),
        description="Pagamento Cartão A",
        idempotency_key=key,
    )


def test_s12a_duplo_envio(accounts):
    first = pay_card(accounts, "K1")
    second = pay_card(accounts, "K1")
    assert first.pk == second.pk
    assert LedgerTransaction.objects.filter(type=TransactionType.INVOICE_PAYMENT).count() == 1
    assert services.account_balance(accounts.corrente) == Money(-123000)
