"""Invariantes do Ledger sob sequências aleatórias de operações (testing-plan.md §7.1).

Perfil padrão: 100 exemplos. Porta de validação: HYPOTHESIS_PROFILE=thorough (1.000 exemplos).
"""

import contextlib
import datetime

import pytest
from django.db import transaction
from hypothesis import given
from hypothesis import strategies as st

from apps.ledger import services
from apps.ledger.errors import LedgerError
from apps.ledger.invariants import check_all
from apps.ledger.models import (
    CARD_PURCHASE_TYPES,
    LedgerTransaction,
    LinkKind,
    TransactionStatus,
    TransactionType,
)
from apps.ledger.services import Leg
from apps.money import Money

TODAY = datetime.date(2026, 11, 20)
START = datetime.date(2026, 11, 1)

# (débito, crédito, tipo) por nome de conta do fixture `accounts`.
PAIRS = [
    ("mercado", "corrente", TransactionType.EXPENSE_PAID),
    ("corrente", "salario", TransactionType.INCOME_RECEIVED),
    ("digital", "corrente", TransactionType.TRANSFER),
    ("reserva", "corrente", TransactionType.RESERVE_DEPOSIT),
    ("eletronicos", "cartao_a", TransactionType.CARD_PURCHASE),
    ("ana", "cartao_a", TransactionType.CARD_THIRD_PARTY),
    ("cartao_a", "corrente", TransactionType.INVOICE_PAYMENT),
    ("mercado", "vr", TransactionType.EXPENSE_BENEFIT),
]

cents = st.integers(min_value=1, max_value=5_000_000)
pick = st.integers(min_value=0, max_value=10_000)

operations = st.one_of(
    st.tuples(
        st.just("record"),
        st.integers(0, len(PAIRS) - 1),
        cents,
        st.sampled_from(["confirmed", "confirmed", "pending", "forecast"]),
        st.integers(0, 40),
    ),
    st.tuples(st.just("mixed"), cents, cents, st.integers(0, 19)),
    st.tuples(st.just("cancel"), pick),
    st.tuples(st.just("reverse"), pick, st.sampled_from(["technical", "commercial"])),
    st.tuples(st.just("partial"), pick, st.integers(1, 100)),
    st.tuples(st.just("correct"), pick, cents),
)


def _apply(op, acc):
    kind = op[0]
    txns = list(LedgerTransaction.objects.order_by("id"))
    if kind == "record":
        _, i, value, status, offset = op
        debit, credit, txn_type = PAIRS[i]
        on = START + datetime.timedelta(days=offset)
        if status == "confirmed" and on > TODAY:
            on = TODAY
        services.record(
            type=txn_type,
            legs=[Leg(getattr(acc, debit), Money(value)), Leg(getattr(acc, credit), Money(-value))],
            operation_date=on,
            description="gerado",
            status=status,
        )
    elif kind == "mixed":
        _, own, third, offset = op
        services.record(
            type=TransactionType.CARD_MIXED,
            legs=[
                Leg(acc.restaurantes, Money(own)),
                Leg(acc.ana, Money(third)),
                Leg(acc.cartao_a, Money(-(own + third))),
            ],
            operation_date=START + datetime.timedelta(days=offset),
            description="mista",
        )
    elif not txns:
        return
    elif kind == "cancel":
        services.cancel(txns[op[1] % len(txns)], reason="teste")
    elif kind == "reverse":
        services.reverse(txns[op[1] % len(txns)], reason="teste", mode=op[2])
    elif kind == "partial":
        target = txns[op[1] % len(txns)]
        gross = sum(p.amount_cents for p in target.postings.all() if p.amount_cents > 0)
        amount = max(1, gross * op[2] // 100)
        services.reverse_partially(target, amount=Money(amount), reason="teste")
    elif kind == "correct":
        target = txns[op[1] % len(txns)]
        legs = [Leg(p.account, Money(p.amount_cents)) for p in target.postings.all()]
        if len(legs) == 2:
            value = op[2]
            legs = [
                Leg(legs[0].account, Money(value if legs[0].amount.is_positive else -value)),
                Leg(legs[1].account, Money(-value if legs[0].amount.is_positive else value)),
            ]
        services.correct(target, legs=legs, reason="teste")


def _reverse_everything():
    for txn in LedgerTransaction.objects.filter(status=TransactionStatus.CONFIRMED):
        is_reversal = txn.links_out.filter(
            kind__in=[LinkKind.REVERSES, LinkKind.PARTIALLY_REVERSES]
        ).exists()
        if not is_reversal:
            services.reverse(txn, reason="limpeza")


@pytest.mark.usefixtures("on_20_11")
@given(ops=st.lists(operations, max_size=15))
def test_invariantes_valem_apos_qualquer_sequencia(accounts, ops):
    with transaction.atomic():
        for op in ops:
            # Recusas são esperadas pelas regras; o estado não pode ter mudado.
            with contextlib.suppress(LedgerError):
                _apply(op, accounts)
            assert check_all() == [], op
        # Reversibilidade: estornar tudo devolve todos os saldos a zero.
        _reverse_everything()
        assert check_all() == []
        for account in vars(accounts).values():
            assert services.account_balance(account) == Money(0), account.code
        # Compras no cartão nunca geram receita.
        assert services.account_balance(accounts.salario) == Money(0)
        transaction.set_rollback(True)


def test_tipos_de_compra_no_cartao_conhecidos():
    assert TransactionType.CARD_MIXED in CARD_PURCHASE_TYPES
