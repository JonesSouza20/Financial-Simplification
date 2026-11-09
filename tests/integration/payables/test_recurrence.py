"""Recorrências, horizonte H e feriados (RN-050 a RN-055, RN-140, RN-022; testing-plan.md §6)."""

import datetime as dt

import pytest

from apps.accounts.models import FinancialAccount
from apps.accounts.services import balance
from apps.calendar_br import services as calendar
from apps.debts import services as debts
from apps.ledger.errors import ConcurrentEditError, InvalidTransactionError
from apps.ledger.invariants import check_all
from apps.ledger.models import TransactionStatus
from apps.money import Money
from apps.payables import horizon, recurrence, services
from apps.payables.models import Commitment, DayRule, Frequency, RecurrenceRule
from apps.ui import models as prefs
from tests.conftest import travel_to

pytestmark = pytest.mark.usefixtures("on_20_11")

TODAY = dt.date(2026, 11, 20)
START = dt.date(2026, 11, 1)


@pytest.fixture
def conta(fin):
    fin.make("Base", "checking", "free", 1_000_000)
    return FinancialAccount.objects.get(name="Base")


def monthly(conta, cats, **extra):
    data = {
        "name": "Internet",
        "kind": "bill",
        "amount": Money(10000),
        "frequency": Frequency.MONTHLY,
        "day_rule": DayRule.FIXED_DAY,
        "day_value": 25,
        "start_date": START,
        "account": conta,
        "category": cats.aluguel,
    }
    data.update(extra)
    return recurrence.create_rule(**data)


def live(rule):
    return list(
        rule.commitments.filter(transaction__status__in=services.PLANNED).order_by("due_date")
    )


# Materialização --------------------------------------------------------------------------


def test_RN_051_janela_de_13_meses(conta, cats):
    rule = monthly(conta, cats)
    dates = [c.due_date for c in live(rule)]
    assert dates[0] == dt.date(2026, 11, 25)
    assert dates[-1] == dt.date(2027, 11, 25)  # 20/12/2027 é o limite da janela
    assert len(dates) == 13
    assert rule.generated_until == dt.date(2027, 12, 20)
    assert balance(conta) == Money(1_000_000)
    assert check_all() == []


def test_RN_051_renovacao_diaria_sem_duplicar(conta, cats):
    rule = monthly(conta, cats)
    recurrence.renew()
    assert len(live(rule)) == 13
    with travel_to(dt.date(2027, 1, 26)):
        recurrence.renew()
    assert len(live(rule)) == 16
    assert live(rule)[-1].due_date == dt.date(2028, 2, 25)


def test_ocorrencia_cancelada_nao_volta(conta, cats):
    rule = monthly(conta, cats)
    victim = live(rule)[3]
    services.cancel(victim, reason="não haverá")
    recurrence.renew()
    assert victim.due_date not in [c.due_date for c in live(rule)]


def test_RN_055_dia_31_em_meses_curtos(conta, cats):
    rule = monthly(conta, cats, day_value=31)
    assert [c.due_date for c in live(rule)][:4] == [
        dt.date(2026, 11, 30),
        dt.date(2026, 12, 31),
        dt.date(2027, 1, 31),
        dt.date(2027, 2, 28),
    ]


@pytest.mark.parametrize(
    ("extra", "expected"),
    [
        (
            {"frequency": Frequency.WEEKLY, "start_date": dt.date(2026, 11, 2), "end_date": None},
            [dt.date(2026, 11, 23), dt.date(2026, 11, 30), dt.date(2026, 12, 7)],
        ),
        (
            {"frequency": Frequency.YEARLY},
            [dt.date(2026, 11, 25), dt.date(2027, 11, 25)],
        ),
        (
            {"frequency": Frequency.EVERY_N_MONTHS, "interval": 3},
            [dt.date(2026, 11, 25), dt.date(2027, 2, 25), dt.date(2027, 5, 25)],
        ),
        (
            {"day_rule": DayRule.LAST_DAY, "day_value": None},
            [dt.date(2026, 11, 30), dt.date(2026, 12, 31), dt.date(2027, 1, 31)],
        ),
    ],
)
def test_RN_050_periodicidades(conta, cats, extra, expected):
    rule = monthly(conta, cats, **extra)
    assert [c.due_date for c in live(rule)][: len(expected)] == expected


def test_RN_050_fim_e_numero_de_ocorrencias(conta, cats):
    assert len(live(monthly(conta, cats, remaining_count=3))) == 3
    assert len(live(monthly(conta, cats, end_date=dt.date(2027, 1, 25)))) == 3


def test_primeira_ocorrencia_nao_antecede_o_inicio(conta, cats):
    rule = monthly(conta, cats, day_value=10, start_date=dt.date(2026, 11, 15))
    assert live(rule)[0].due_date == dt.date(2026, 12, 10)


def test_RN_051_inicio_no_passado_nao_cria_ocorrencia_vencida(conta, cats):
    rule = monthly(conta, cats, day_value=10)  # início 01/11, hoje 20/11: 10/11 já passou
    assert live(rule)[0].due_date == dt.date(2026, 12, 10)


def test_RN_051_ocorrencia_de_hoje_entra(conta, cats):
    rule = monthly(conta, cats, day_value=20)
    assert live(rule)[0].due_date == TODAY


def test_nada_antes_de_01_11_2026(conta, cats):
    rule = monthly(conta, cats, start_date=dt.date(2026, 9, 1))
    assert live(rule)[0].due_date == dt.date(2026, 11, 25)


def test_F033_previa_das_proximas_datas(conta, cats):
    rule = RecurrenceRule(
        name="Salário",
        kind="income",
        frequency=Frequency.MONTHLY,
        day_rule=DayRule.NTH_BUSINESS_DAY,
        day_value=5,
        amount_cents=1,
        value_type="fixed",
        category=cats.salario,
        financial_account=conta,
        start_date=START,
    )
    dates = recurrence.preview(rule)
    assert len(dates) == 12
    assert dates[0] == dt.date(2026, 12, 7) and dates[1] == dt.date(2027, 1, 8)
    rule.remaining_count = 2
    assert len(recurrence.preview(rule)) == 2
    rule.remaining_count = None
    rule.end_date = dt.date(2026, 12, 10)
    assert recurrence.preview(rule) == [dt.date(2026, 12, 7)]


@pytest.mark.parametrize(
    ("bad", "message"),
    [
        ({"name": " "}, "nome"),
        ({"amount": Money(0)}, "maior que zero"),
        ({"value_type": "x"}, "Tipo de valor"),
        ({"frequency": "x"}, "Periodicidade"),
        ({"interval": 0}, "Periodicidade"),
        ({"account": None}, "conta prevista"),
        ({"category": None}, "categoria"),
        ({"end_date": dt.date(2026, 1, 1)}, "fim"),
        ({"remaining_count": 0}, "ocorrências"),
        ({"day_value": 32}, "Dia do mês"),
        ({"day_rule": DayRule.NTH_BUSINESS_DAY, "day_value": 24}, "Dia útil"),
        ({"day_rule": "x"}, "Regra de dia"),
        ({"kind": "planned_transfer"}, "ainda não"),
    ],
)
def test_validacao_da_regra(conta, cats, bad, message):
    with pytest.raises(InvalidTransactionError, match=message):
        monthly(conta, cats, **bad)
    assert not RecurrenceRule.objects.exists()


# Alterar e encerrar ------------------------------------------------------------------------


def test_RN_053_mudanca_so_altera_o_futuro(conta, cats):
    rule = monthly(conta, cats)
    jan = dt.date(2027, 1, 1)
    updated = recurrence.update_rule(rule, from_date=jan, amount_cents=15000)
    amounts = {c.due_date: c.planned_amount_cents for c in live(updated)}
    assert amounts[dt.date(2026, 12, 25)] == 10000
    assert amounts[dt.date(2027, 1, 25)] == 15000
    assert amounts[dt.date(2027, 11, 25)] == 15000
    assert len(amounts) == 13
    assert check_all() == []


def test_RN_053_ocorrencia_paga_nao_muda_nem_duplica(conta, cats):
    rule = monthly(conta, cats)
    paid = live(rule)[1]
    services.pay(paid, amount=Money(4000))
    updated = recurrence.update_rule(rule, amount_cents=15000)
    occurrences = [c for c in live(updated) if c.due_date == paid.due_date]
    assert occurrences == [paid]
    assert occurrences[0].planned_amount_cents == 10000


def test_RN_053_passado_nao_muda(conta, cats):
    rule = monthly(conta, cats)
    with pytest.raises(InvalidTransactionError, match="de hoje em diante"):
        recurrence.update_rule(rule, from_date=dt.date(2026, 11, 1), amount_cents=1)


def test_mudanca_de_dia_cancela_datas_antigas(conta, cats):
    rule = monthly(conta, cats)
    updated = recurrence.update_rule(rule, day_value=10)
    assert live(updated)[0].due_date == dt.date(2026, 12, 10)
    assert len(live(updated)) == 13


def test_atualizacao_invalida_e_atomica(conta, cats):
    rule = monthly(conta, cats)
    with pytest.raises(InvalidTransactionError, match="não editável"):
        recurrence.update_rule(rule, start_date=TODAY)
    with pytest.raises(InvalidTransactionError):
        recurrence.update_rule(rule, amount_cents=0)
    assert len(live(rule)) == 13
    with pytest.raises(ConcurrentEditError):
        recurrence.update_rule(rule, expected_version=99, amount_cents=2)


def test_RN_054_encerrar(conta, cats):
    rule = monthly(conta, cats)
    paid = live(rule)[0]
    services.pay(paid, amount=Money(10000))
    ended = recurrence.end_rule(rule)
    assert live(ended) == [paid]
    cancelled = ended.commitments.filter(transaction__status=TransactionStatus.CANCELLED).first()
    assert cancelled.transaction.cancel_reason == "recorrência encerrada"
    assert not ended.active
    recurrence.renew()
    assert live(ended) == [paid]
    with pytest.raises(InvalidTransactionError, match="encerrada"):
        recurrence.update_rule(ended, amount_cents=1)
    with pytest.raises(ConcurrentEditError):
        recurrence.end_rule(ended, expected_version=99)


# Horizonte e previsto → pendente -----------------------------------------------------------


def salary(conta, start=START):
    return recurrence.create_salary(account=conta, amount=Money(500000), start_date=start)


def test_RN_022_salario_no_quinto_dia_util(conta):
    rule = salary(conta)
    assert [c.due_date for c in live(rule)][:3] == [
        dt.date(2026, 12, 7),  # 09/11 já passou: o salário de novembro não vira "atrasado"
        dt.date(2027, 1, 8),
        dt.date(2027, 2, 5),
    ]
    assert all(c.transaction.status == TransactionStatus.FORECAST for c in live(rule))


def test_RN_140_sem_salario_usa_fim_do_mes(db):
    assert horizon.horizon().date == dt.date(2026, 12, 1)


def test_RN_140_proximo_salario(conta):
    salary(conta)
    h = horizon.horizon()
    assert h.date == dt.date(2026, 12, 7) and not h.salary_late


def test_RN_140_cadastrar_salario_com_inicio_passado_nao_atrasa(conta):
    salary(conta)
    assert not horizon.horizon().salary_late


def test_RN_140_salario_atrasado_e_h_amanha(conta):
    salary(conta)
    with travel_to(dt.date(2026, 12, 8)):
        h = horizon.horizon()
    assert h.date == dt.date(2026, 12, 9) and h.salary_late


def test_RN_140_dia_do_salario_antes_e_depois_do_recebi(conta):
    rule = salary(conta)
    with travel_to(dt.date(2026, 12, 7)):
        assert horizon.horizon().date == dt.date(2026, 12, 7)
        services.pay(live(rule)[0], amount=Money(500000))
        assert horizon.horizon().date == dt.date(2027, 1, 8)


def test_RN_140_modo_fim_do_mes(conta):
    salary(conta)
    prefs.put("horizon_mode", "month_end")
    assert horizon.horizon().date == dt.date(2026, 12, 1)


def test_RN_052_fixa_vira_pendente_ao_entrar_em_h(conta, cats):
    salary(conta)  # H = 07/12
    rule = monthly(conta, cats, day_value=5)
    occurrences = live(rule)
    assert occurrences[0].due_date == dt.date(2026, 12, 5)
    assert occurrences[0].transaction.status == TransactionStatus.PENDING
    assert occurrences[1].transaction.status == TransactionStatus.FORECAST


def test_RN_052_exclusivo_vencimento_igual_a_h_fica_previsto(conta, cats):
    salary(conta)
    rule = monthly(conta, cats, day_value=7)
    assert live(rule)[0].transaction.status == TransactionStatus.FORECAST


def test_RN_052_variavel_entrando_em_h_continua_prevista(conta, cats):
    salary(conta)
    rule = monthly(conta, cats, day_value=5, value_type="variable")
    assert live(rule)[0].transaction.status == TransactionStatus.FORECAST


def test_RN_020_receita_nunca_vira_pendente_sozinha(conta, cats):
    rule = monthly(conta, cats, kind="income", category=cats.salario, name="Aluguel recebido")
    recurrence.renew()
    assert live(rule)[0].transaction.status == TransactionStatus.FORECAST


def test_renovacao_promove_quando_h_avanca(conta, cats):
    salary(conta)
    rule = monthly(conta, cats, day_value=5)
    assert live(rule)[1].transaction.status == TransactionStatus.FORECAST
    with travel_to(dt.date(2026, 12, 7)):
        services.pay(horizon.oldest_open_salary(), amount=Money(500000))
        recurrence.renew()
    assert live(rule)[1].transaction.status == TransactionStatus.PENDING


def test_renovacao_registra_falha_e_segue(conta, cats):
    from apps.categories.models import Category

    ok = monthly(conta, cats)
    monthly(conta, cats, name="Outra", category=cats.eletronicos)
    Category.objects.filter(pk=cats.eletronicos.pk).update(
        archived_at=dt.datetime(2026, 11, 20, tzinfo=dt.UTC)
    )
    with travel_to(dt.date(2027, 1, 26)), pytest.raises(InvalidTransactionError, match="Outra"):
        recurrence.renew()
    assert len(live(ok)) == 16


def test_consorcio_recorrencia_fixa(conta):
    debt = debts.create_consortium(
        description="Carro", installment=Money(50000), due_day=31, remaining_installments=40
    )
    rule = recurrence.create_consortium(
        debt=debt,
        account=conta,
        amount=Money(50000),
        start_date=START,
        remaining_count=40,
    )
    assert rule.value_type == "fixed"
    first = live(rule)[0]
    assert first.kind == "consortium" and first.due_date == dt.date(2026, 11, 30)
    assert first.transaction.type == "T19_consortium_installment"
    with pytest.raises(InvalidTransactionError, match="consórcio"):
        recurrence.create_rule(
            name="X",
            kind="consortium",
            amount=Money(1),
            frequency=Frequency.MONTHLY,
            day_rule=DayRule.FIXED_DAY,
            day_value=1,
            start_date=START,
            account=conta,
        )


# Feriados que mudam ---------------------------------------------------------------------------


def test_feriado_novo_recalcula_vencimentos_em_aberto(conta, cats):
    rule = monthly(conta, cats, day_value=25)
    target = next(c for c in live(rule) if c.due_date == dt.date(2026, 12, 25))
    assert target.effective_due_date == dt.date(2026, 12, 28)
    calendar.add_holiday(dt.date(2026, 12, 28), "Recesso")
    target.refresh_from_db()
    assert target.effective_due_date == dt.date(2026, 12, 29)
    assert target.due_date == dt.date(2026, 12, 25)  # vencimento original não muda


def test_feriado_novo_move_o_salario(conta):
    rule = salary(conta)
    first = live(rule)[0]
    assert first.due_date == dt.date(2026, 12, 7)
    calendar.add_holiday(dt.date(2026, 12, 3), "Ponto facultativo")
    current = Commitment.objects.select_related("transaction").get(pk=first.pk)
    assert current.due_date == current.effective_due_date == dt.date(2026, 12, 8)
    assert current.transaction.operation_date == dt.date(2026, 12, 8)
    calendar.remove_holiday(dt.date(2026, 12, 3))
    current.refresh_from_db()
    assert current.due_date == dt.date(2026, 12, 7)
    assert check_all() == []


def test_feriado_nao_mexe_em_conta_paga(conta, cats):
    rule = monthly(conta, cats)
    paid = live(rule)[0]
    services.pay(paid, amount=Money(10000))
    calendar.add_holiday(paid.effective_due_date, "Novo")
    before = paid.effective_due_date
    paid.refresh_from_db()
    assert paid.effective_due_date == before
