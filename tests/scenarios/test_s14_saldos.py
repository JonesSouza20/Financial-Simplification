"""S14 — saldos em 20/11/2026 (reference-scenarios.md; RN-140 a RN-148, RN-154; ADR-041)."""

import datetime

import pytest

from apps.accounts.models import FinancialAccount
from apps.balances import services as balances
from apps.cards import services as cards
from apps.cards.models import Card
from apps.cards.services import PurchaseInput
from apps.debts import services as debts
from apps.debts.models import Debt
from apps.entries import services as entries
from apps.entries.services import EXPENSE, INCOME, TRANSFER, EntryInput
from apps.ledger import services as ledger
from apps.ledger.invariants import check_all
from apps.money import Money
from apps.opening import services as opening
from apps.payables import horizon, recurrence
from apps.payables import services as payables
from apps.payables.models import Commitment
from apps.persons import services as persons
from apps.receivables import services as receivables
from tests.conftest import travel_to
from tests.scenarios.test_s00_abertura import S00_DRAFT

pytestmark = pytest.mark.usefixtures("on_20_11")
D = datetime.date


def acc(name):
    return FinancialAccount.objects.get(name=name)


@pytest.fixture
def s14(db, cats):
    """Eventos de 01/11 a 20/11 do S14."""
    opening.commit(S00_DRAFT)
    corrente, digital = acc("Corrente"), acc("Digital")
    card = Card.objects.get(name="Cartão A")
    loan = Debt.objects.get(kind="loan")
    consortium = Debt.objects.get(kind="consortium")
    expense = lambda cents, account, day, cat: entries.record(  # noqa: E731
        EntryInput(
            kind=EXPENSE, amount=Money(cents), account=account, on=D(2026, 11, day), category=cat
        )
    )
    expense(23000, corrente, 3, cats.mercado)
    cards.pay(card=card, account=corrente, amount=Money(123000), on=D(2026, 11, 5))
    entries.record(
        EntryInput(
            kind=INCOME,
            amount=Money(500000),
            account=corrente,
            on=D(2026, 11, 9),
            category=cats.salario,
        )
    )
    expense(150000, corrente, 10, cats.aluguel)
    cards.record_purchase(
        PurchaseInput(
            card=card,
            total=Money(60000),
            on=D(2026, 11, 10),
            installments=6,
            category=cats.eletronicos,
        )
    )
    entries.record(
        EntryInput(
            kind=TRANSFER,
            amount=Money(100000),
            account=corrente,
            destination=acc("Reserva"),
            on=D(2026, 11, 12),
        )
    )
    ana = persons.get_or_create("Ana")
    cards.record_purchase(
        PurchaseInput(
            card=card,
            total=Money(25000),
            on=D(2026, 11, 14),
            category=cats.get("Restaurantes"),
            shares=((ana, Money(15000)),),
        )
    )
    debts.pay_loan(
        debt=loan,
        account=corrente,
        principal=Money(74560),
        interest=Money(20000),
        on=D(2026, 11, 16),
    )
    expense(12000, corrente, 16, cats.get("Internet"))
    receivables.receive(person=ana, amount=Money(5000), account=digital, on=D(2026, 11, 16))
    expense(3500, digital, 18, cats.get("Transporte"))
    expense(4500, acc("VR/VA"), 18, cats.mercado)

    # Compromissos em 20/11
    recurrence.create_salary(account=corrente, amount=Money(500000), start_date=D(2026, 12, 1))
    payables._create(
        kind="consortium",
        description="Consórcio novembro",
        category=None,
        account=corrente,
        amount=Money(65000),
        due_date=D(2026, 11, 20),
        txn_status="pending",
        debt=consortium,
    )
    payables._create(
        kind="bill",
        description="Luz novembro",
        category=cats.get("Luz"),
        account=corrente,
        amount=Money(18000),
        due_date=D(2026, 11, 22),
        txn_status="forecast",
        value_type="variable",
    )
    return card


def test_s14_comprometido_e_disponivel(s14):
    p = balances.position()
    assert p.horizon == D(2026, 12, 7) and not p.salary_late
    assert p.free == Money(343940)
    assert p.reserve == Money(100000)
    assert p.benefit == Money(37500)
    assert [line.amount for line in p.invoices] == [Money(93000)]
    assert [line.amount for line in p.pending] == [Money(65000)]
    assert p.committed == Money(158000)
    assert p.available == Money(185940)
    assert check_all() == []


def test_RN_143_luz_prevista_fica_fora_do_comprometido(s14):
    p = balances.position()
    assert [line.label for line in p.estimates] == ["Luz novembro"]
    assert p.committed == Money(158000)


def test_RN_154_pode_gastar_sem_minimo(s14):
    p = balances.position()
    assert p.can_spend == Money(167940)
    assert p.state == balances.OK


def test_RN_154_pode_gastar_com_minimo(s14):
    balances.set_minimum(Money(30000))
    p = balances.position()
    assert p.available == Money(185940)  # RN-145 não muda
    assert p.can_spend == Money(137940)
    assert p.days_to_horizon == 17


@pytest.mark.parametrize(
    ("minimum", "state", "spend", "shortfall"),
    [
        (167940, balances.AT_LIMIT, 0, 0),
        (185940, balances.BELOW_MINIMUM, -18000, 18000),
    ],
)
def test_RN_154_estados_do_minimo(s14, minimum, state, spend, shortfall):
    balances.set_minimum(Money(minimum))
    p = balances.position()
    assert (p.state, p.can_spend, p.shortfall) == (state, Money(spend), Money(shortfall))


def test_RN_154_sem_cobertura(s14, cats):
    entries.record(
        EntryInput(
            kind=EXPENSE,
            amount=Money(200000),
            account=acc("Corrente"),
            on=D(2026, 11, 20),
            category=cats.mercado,
        )
    )
    p = balances.position()
    assert p.state == balances.UNCOVERED
    assert p.shortfall == Money(32060)  # 1.859,40 − 2.000,00 − 180,00


def test_estimativa_paga_sai_da_conta(s14):
    luz = Commitment.objects.get(transaction__description="Luz novembro")
    payables.set_actual_amount(luz, amount=Money(21000))
    p = balances.position()
    assert p.estimates == ()
    assert p.committed == Money(179000)


def test_pagar_conta_pendente_nao_muda_o_disponivel(s14):
    consorcio = Commitment.objects.get(transaction__description="Consórcio novembro")
    before = balances.position().available
    payables.pay(consorcio, amount=Money(65000))
    p = balances.position()
    assert p.available == before
    assert p.committed == Money(93000)
    assert p.free == Money(278940)


def test_previsto_pendente_nao_mexem_no_saldo_real(s14):
    assert ledger.account_balance(acc("Corrente").ledger_account) == Money(247440)


def test_RN_140_salario_atrasado_encolhe_o_horizonte(s14):
    with travel_to(D(2026, 12, 8)):
        p = balances.position()
    assert p.salary_late
    assert p.horizon == D(2026, 12, 9)


def test_sem_salario_vai_ate_o_fim_do_mes(db):
    p = balances.position()
    assert p.horizon == D(2026, 12, 1)
    assert p.can_spend == Money(0)
    assert p.state == balances.AT_LIMIT


def test_minimo_negativo_recusado(db):
    with pytest.raises(Exception, match="negativo"):
        balances.set_minimum(Money(-1))


def test_recebi_o_salario_promove_na_hora(s14, cats):
    """Ao confirmar o salário, H avança: contas fixas da nova janela viram pendentes já."""
    rule = recurrence.create_rule(
        name="Aluguel",
        kind="bill",
        amount=Money(150000),
        frequency="monthly",
        day_rule="fixed_day",
        day_value=10,
        start_date=D(2026, 12, 1),
        account=acc("Corrente"),
        category=cats.aluguel,
    )
    aluguel = rule.commitments.get(due_date=D(2026, 12, 10))
    assert aluguel.transaction.status == "forecast"
    with travel_to(D(2026, 12, 7)):
        payables.pay(horizon.oldest_open_salary(), amount=Money(500000))
    aluguel.refresh_from_db()
    aluguel.transaction.refresh_from_db()
    assert aluguel.transaction.status == "pending"
