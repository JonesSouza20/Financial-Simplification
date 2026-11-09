"""Previsto e pendente nunca afetam o real (RN-012; testing-plan.md §7.1, §6).

Perfil padrão: 100 exemplos. Porta de validação: HYPOTHESIS_PROFILE=thorough (1.000 exemplos).
"""

import contextlib
import datetime

import pytest
from django.db import transaction
from hypothesis import given
from hypothesis import strategies as st

from apps.accounts.models import FinancialAccount
from apps.accounts.services import balance
from apps.ledger import services as ledger
from apps.ledger.errors import LedgerError
from apps.ledger.invariants import check_all
from apps.ledger.models import LedgerAccount, LedgerPosting, TransactionStatus
from apps.money import Money
from apps.payables import recurrence, services
from apps.payables.models import Commitment, ExcessKind, Settlement

TODAY = datetime.date(2026, 11, 20)

cents = st.integers(min_value=1, max_value=2_000_000)
pick = st.integers(min_value=0, max_value=10_000)
day = st.integers(min_value=0, max_value=60)

planned_only = st.one_of(
    st.tuples(st.just("bill"), cents, day, st.sampled_from(["fixed", "variable"])),
    st.tuples(st.just("income"), cents, day),
    st.tuples(st.just("recurring"), cents, st.integers(1, 28), st.sampled_from(["bill", "income"])),
    st.tuples(st.just("cancel"), pick),
    st.tuples(st.just("schedule"), pick),
    st.tuples(st.just("actual"), pick, cents),
    st.tuples(st.just("renew")),
)

settling = st.one_of(
    planned_only,
    st.tuples(st.just("pay"), pick, cents, st.booleans()),
    st.tuples(st.just("pay_over"), pick, cents),
    st.tuples(st.just("reverse"), pick),
    st.tuples(st.just("close"), pick),
)


def nth(items, index):
    return items[index % len(items)] if items else None


def apply(op, conta, cats):
    name = op[0]
    commitments = list(Commitment.objects.select_related("transaction").order_by("id"))
    if name == "bill":
        services.create_bill(
            description="Conta",
            category=cats.aluguel,
            account=conta,
            amount=Money(op[1]),
            due_date=datetime.date(2026, 11, 1) + datetime.timedelta(days=op[2]),
            value_type=op[3],
        )
    elif name == "income":
        services.create_income(
            description="Receita",
            category=cats.salario,
            account=conta,
            amount=Money(op[1]),
            due_date=datetime.date(2026, 11, 1) + datetime.timedelta(days=op[2]),
        )
    elif name == "recurring":
        recurrence.create_rule(
            name="Regra",
            kind=op[3],
            amount=Money(op[1]),
            frequency="monthly",
            day_rule="fixed_day",
            day_value=op[2],
            start_date=datetime.date(2026, 11, 1),
            account=conta,
            category=cats.aluguel if op[3] == "bill" else cats.salario,
            remaining_count=2,
        )
    elif name == "renew":
        recurrence.renew()
    elif name == "cancel" and commitments:
        services.cancel(nth(commitments, op[1]), reason="x")
    elif name == "schedule" and commitments:
        services.schedule(nth(commitments, op[1]), debit_date=TODAY)
    elif name == "actual" and commitments:
        services.set_actual_amount(nth(commitments, op[1]), amount=Money(op[2]))
    elif name == "pay" and commitments:
        fee = Money(op[2] // 10) if op[3] else None
        services.pay(nth(commitments, op[1]), amount=Money(op[2]), late_fee=fee)
    elif name == "pay_over" and commitments:
        services.pay(
            nth(commitments, op[1]),
            amount=Money(op[2]),
            excess_kind=ExcessKind.HIGHER_ACTUAL,
        )
    elif name == "reverse":
        settlements = list(Settlement.objects.order_by("id"))
        if settlements:
            ledger.reverse(nth(settlements, op[1]).transaction, reason="x")
    elif name == "close" and commitments:
        services.close(nth(commitments, op[1]), reason="x")


def run(ops, conta, cats):
    sid = transaction.savepoint()
    try:
        for op in ops:
            with contextlib.suppress(LedgerError), transaction.atomic():
                apply(op, conta, cats)
        yield
    finally:
        transaction.savepoint_rollback(sid)


@pytest.fixture
def conta(fin):
    fin.make("Base", "checking", "free", 1_000_000)
    return FinancialAccount.objects.get(name="Base")


def real_numbers():
    return {
        account.pk: ledger.account_balance(account).cents for account in LedgerAccount.objects.all()
    }


@pytest.mark.usefixtures("on_20_11")
@given(st.lists(planned_only, max_size=12))
def test_RN_012_sem_pagamento_nada_real_muda(conta, cats, ops):
    before = real_numbers()
    for _ in run(ops, conta, cats):
        after = real_numbers()
        assert {k: v for k, v in after.items() if k in before} == before
        assert all(v == 0 for k, v in after.items() if k not in before)
        assert check_all() == []


@pytest.mark.usefixtures("on_20_11")
@given(st.lists(settling, max_size=14))
def test_aberto_e_invariantes_com_pagamentos(conta, cats, ops):
    for _ in run(ops, conta, cats):
        assert check_all() == []
        for commitment in Commitment.objects.select_related("transaction"):
            remaining = services.open_amount(commitment)
            assert 0 <= remaining.cents <= commitment.planned_amount_cents
        # O saldo real só muda pelo efeito das liquidações vivas.
        live = LedgerPosting.objects.filter(
            account=conta.ledger_account,
            transaction__status=TransactionStatus.CONFIRMED,
            transaction__settlements__isnull=False,
        )
        moved = sum(p.amount_cents for p in live.distinct())
        assert balance(conta).cents == 1_000_000 + moved
