"""Telas de pagamentos e do Início: o que a pessoa faz e o que o sistema grava (F-030 a F-036)."""

import datetime

import pytest
import time_machine
from django.urls import reverse

from apps.balances import services as balances
from apps.entries import services as entries
from apps.entries.services import INCOME, EntryInput
from apps.ledger.invariants import check_all
from apps.ledger.models import TransactionStatus
from apps.money import Money
from apps.payables import presentation, recurrence
from apps.payables import services as payables
from apps.payables.models import Commitment, RecurrenceRule
from apps.ui import models as prefs
from tests.conftest import PASSWORD, SAO_PAULO, travel_to

D = datetime.date
pytestmark = pytest.mark.usefixtures("on_20_11")


@pytest.fixture
def funded(fin, cats):
    entries.record(
        EntryInput(
            kind=INCOME,
            amount=Money(300000),
            account=fin.corrente,
            on=D(2026, 11, 10),
            category=cats.salario,
        )
    )
    return fin


@pytest.fixture
def bill(funded, cats):
    return payables.create_bill(
        description="Aluguel",
        category=cats.aluguel,
        account=funded.corrente,
        amount=Money(100000),
        due_date=D(2026, 11, 25),
    )


@pytest.fixture
def salary(funded):
    return recurrence.create_salary(
        account=funded.corrente, amount=Money(500000), start_date=D(2026, 12, 1)
    )


def pay_data(account, **extra):
    return {"account": account.pk, "on": "2026-11-20", "idempotency_key": "k1", **extra}


def url(name, *args):
    return reverse(f"payables:{name}", args=args)


def relogin(web):
    """O relógio avançou dias: a sessão antiga expirou, como no uso real."""
    assert web.post("/acesso/entrar/", {"password": PASSWORD}).status_code == 302


def test_central_agrupa_e_soma(web, bill, salary):
    html = web.get(url("central")).content.decode()
    assert "Esta semana" in html and "Aluguel" in html
    assert "R$ 1.000,00" in html
    assert "Salário, 07/12" in html
    assert 'style="' not in html


def test_pagar_valor_cheio_ignora_outro_valor_digitado(web, bill, funded):
    response = web.post(
        url("pay", bill.pk), pay_data(funded.corrente, full="1", amount="1,00", late_fee="abc")
    )
    assert response.status_code == 302 and response.url == url("done", bill.pk)
    assert not payables.is_open(bill)
    assert payables.settled_cents(bill) == 100000
    check_all()


def test_pagar_parcial_e_depois_o_resto(web, bill, funded):
    web.post(url("pay", bill.pk), pay_data(funded.corrente, custom="1", amount="400,00"))
    assert payables.open_amount(bill) == Money(60000)
    html = web.get(url("central")).content.decode()
    assert "Pago em parte" in html and "600,00" in html
    done = web.get(url("done", bill.pk)).content.decode()
    assert "pago em parte" in done and "Faltam R$ 600,00" in done
    web.post(url("pay", bill.pk), pay_data(funded.corrente, full="1", idempotency_key="k2"))
    assert not payables.is_open(bill)
    check_all()


def test_duplo_toque_nao_paga_duas_vezes(web, bill, funded):
    data = pay_data(funded.corrente, custom="1", amount="100,00")
    web.post(url("pay", bill.pk), data)
    web.post(url("pay", bill.pk), data)
    assert payables.settled_cents(bill) == 10000


def test_excedente_exige_classificar(web, bill, funded):
    response = web.post(
        url("pay", bill.pk), pay_data(funded.corrente, custom="1", amount="1.100,00")
    )
    assert response.status_code == 200
    assert "Classifique o excedente" in response.content.decode()
    assert payables.settled_cents(bill) == 0
    web.post(
        url("pay", bill.pk),
        pay_data(funded.corrente, custom="1", amount="1.100,00", excess_kind="late_fee"),
    )
    assert not payables.is_open(bill)
    check_all()


def test_juros_entram_a_parte(web, bill, funded):
    web.post(
        url("pay", bill.pk),
        pay_data(funded.corrente, custom="1", amount="1.000,00", late_fee="12,30"),
    )
    assert payables.settled_cents(bill) == 100000
    settlement = bill.settlements.get()
    assert any(p.amount_cents == 1230 for p in settlement.transaction.postings.all())
    check_all()


def test_desfazer_reabre_a_conta(web, bill, funded):
    web.post(url("pay", bill.pk), pay_data(funded.corrente, full="1"))
    assert "Desfazer" in web.get(url("done", bill.pk)).content.decode()
    web.post(reverse("entries:undo"), {"next": url("central")})
    assert payables.open_amount(bill) == Money(100000)
    check_all()


def test_desfazer_some_depois_de_dois_minutos(web, bill, funded):
    web.post(url("pay", bill.pk), pay_data(funded.corrente, full="1"))
    later = datetime.datetime(2026, 11, 20, 12, 3, tzinfo=SAO_PAULO)
    with time_machine.travel(later, tick=False):
        assert "Desfazer" not in web.get(url("done", bill.pk)).content.decode()


def test_receber_salario_move_o_horizonte(web, salary, funded):
    commitment = Commitment.objects.filter(recurrence=salary).order_by("due_date").first()
    before = balances.position().horizon
    web.post(url("pay", commitment.pk), pay_data(funded.corrente, full="1"))
    assert balances.position().horizon > before
    assert "recebido" in web.get(url("done", commitment.pk)).content.decode()
    check_all()


def test_informar_valor_real(web, funded, cats):
    light = payables.create_bill(
        description="Luz",
        category=cats.aluguel,
        account=funded.corrente,
        amount=Money(18000),
        due_date=D(2026, 11, 22),
        value_type="variable",
    )
    assert "Informar" in web.get(url("central")).content.decode()
    web.post(url("actual", light.pk), {"amount": "200,00", "version": light.version})
    novo = Commitment.objects.exclude(pk=light.pk).get(transaction__description="Luz")
    assert novo.planned_amount_cents == 20000
    assert novo.transaction.status == TransactionStatus.PENDING


def test_agendar_pergunta_no_dia_e_desagendar(web, bill):
    web.post(url("schedule", bill.pk), {"debit_date": "2026-11-23", "version": bill.version})
    bill.refresh_from_db()
    assert bill.scheduled_debit_date == D(2026, 11, 23)
    with travel_to(D(2026, 11, 23)):
        relogin(web)
        assert "aconteceu?" in web.get(reverse("ui:home")).content.decode()
    web.post(url("unschedule", bill.pk), {"version": bill.version})
    bill.refresh_from_db()
    assert bill.scheduled_debit_date is None


def test_cancelar_e_encerrar(web, bill, funded):
    web.post(url("pay", bill.pk), pay_data(funded.corrente, custom="1", amount="100,00"))
    response = web.post(url("cancel", bill.pk), {"reason": "engano"})
    assert "Use encerrar" in response.content.decode()
    web.post(url("close", bill.pk), {"reason": "veio menor"})
    bill.refresh_from_db()
    assert not payables.is_open(bill)


def test_nova_conta_parcelada(web, funded, cats):
    web.post(
        url("new_bill"),
        {
            "description": "Geladeira",
            "amount": "100,00",
            "due_date": "2026-12-01",
            "category": cats.aluguel.pk,
            "account": funded.corrente.pk,
            "value_type": "fixed",
            "installments": 3,
            "idempotency_key": "p1",
        },
    )
    parts = Commitment.objects.filter(installment_group__isnull=False).order_by("due_date")
    assert [p.planned_amount_cents for p in parts] == [3334, 3333, 3333]


def rule_data(funded, category, **extra):
    return {
        "name": "Internet",
        "kind": "bill",
        "amount": "120,00",
        "frequency": "monthly",
        "day_rule": "fixed_day",
        "day_value": 15,
        "category": category.pk,
        "account": funded.corrente.pk,
        "start_date": "2026-12-01",
        "value_type": "fixed",
        "interval": 1,
        **extra,
    }


def test_recorrencia_mostra_datas_antes_de_salvar(web, funded, cats):
    data = rule_data(funded, cats.aluguel)
    first = web.post(url("recurrence_new"), data)
    html = first.content.decode()
    assert "15/12/26" in html and not RecurrenceRule.objects.exists()
    previewed = first.context["signature"]
    web.post(url("recurrence_new"), {**data, "save": "1", "previewed": previewed})
    assert RecurrenceRule.objects.get().name == "Internet"


def test_recorrencia_alterada_depois_da_previa_nao_salva(web, funded, cats):
    data = rule_data(funded, cats.aluguel)
    previewed = web.post(url("recurrence_new"), data).context["signature"]
    changed = {**data, "day_value": 20, "save": "1", "previewed": previewed}
    html = web.post(url("recurrence_new"), changed).content.decode()
    assert "21/12/26" in html or "20/12/26" in html
    assert not RecurrenceRule.objects.exists()


def test_recorrencia_recusa_categoria_do_tipo_errado(web, funded, cats):
    data = rule_data(funded, cats.salario)
    html = web.post(url("recurrence_new"), data).content.decode()
    assert "categoria de despesa" in html


def test_alterar_e_encerrar_recorrencia(web, funded, cats):
    rule = recurrence.create_rule(
        name="Internet",
        kind="bill",
        amount=Money(12000),
        frequency="monthly",
        day_rule="fixed_day",
        day_value=15,
        start_date=D(2026, 12, 1),
        account=funded.corrente,
        category=cats.aluguel,
    )
    data = {
        **rule_data(funded, cats.aluguel, amount="150,00"),
        "from_date": "2026-11-20",
        "version": rule.version,
    }
    data.pop("start_date")
    previewed = web.post(url("recurrence_edit", rule.pk), data).context["signature"]
    web.post(url("recurrence_edit", rule.pk), {**data, "save": "1", "previewed": previewed})
    rule.refresh_from_db()
    assert rule.amount_cents == 15000
    live = rule.commitments.filter(transaction__status__in=payables.PLANNED)
    assert {c.planned_amount_cents for c in live} == {15000}
    web.post(url("recurrence_end", rule.pk), {"version": rule.version})
    rule.refresh_from_db()
    assert not rule.active
    assert not rule.commitments.filter(transaction__status__in=payables.PLANNED).exists()
    check_all()


def test_ajustes_mudam_o_calculo(web, funded):
    assert balances.position().can_spend == Money(300000)
    response = web.post(
        url("money_settings"), {"minimum": "500,00", "horizon_mode": "month_end"}, follow=True
    )
    assert "R$ 500,00 a menos" in response.content.decode()
    assert balances.get_minimum() == Money(50000)
    assert prefs.get("horizon_mode") == "month_end"


def test_feriado_incluir_e_remover(web, funded):
    web.post(
        url("holidays"),
        {
            "date": "2026-11-24",
            "name": "Ponto facultativo",
            "affects_salary": "on",
            "affects_banking": "on",
        },
    )
    assert "Ponto facultativo" in web.get(url("holidays") + "?ano=2026").content.decode()
    web.post(url("holiday_remove", "2026-11-24"))
    assert "Ponto facultativo" not in web.get(url("holidays") + "?ano=2026").content.decode()


@pytest.mark.parametrize(
    "path",
    [
        "central",
        "new_bill",
        "new_income",
        "calendar",
        "recurrences",
        "recurrence_new",
        "money_settings",
        "holidays",
    ],
)
def test_telas_sem_estilo_inline(web, funded, path):
    response = web.get(url(path))
    assert response.status_code == 200
    assert 'style="' not in response.content.decode()


def test_calendario_mostra_o_dia(web, bill):
    html = web.get(url("calendar") + "?mes=2026-11&dia=25").content.decode()
    assert "Novembro de 2026" in html and "Aluguel" in html and "R$ 1.000,00" in html


def test_calendario_ignora_mes_invalido(web, funded):
    for bad in ("x", "2026-13", "1900-01"):
        assert "Novembro de 2026" in web.get(url("calendar") + f"?mes={bad}").content.decode()


# Início --------------------------------------------------------------------------------


def home(web):
    return web.get(reverse("ui:home")).content.decode()


def test_inicio_com_folga(web, bill, salary):
    balances.set_minimum(Money(30000))
    html = home(web)
    assert "Pode gastar até o salário" in html
    assert "1.700,00" in html and "Com folga" in html and "Salário em 17 dias" in html
    assert "Como calculamos" in html and 'style="' not in html


def test_inicio_sem_minimo_oferece_definir(web, bill, salary):
    assert "Definir mínimo de segurança" in home(web)


def test_inicio_sem_salario_vai_ate_o_fim_do_mes(web, funded):
    html = home(web)
    assert "até o fim do mês" in html and "Cadastrar salário" in html


def test_inicio_no_limite(web, funded, salary):
    balances.set_minimum(Money(300000))
    assert "No limite" in home(web)


def test_inicio_abaixo_do_minimo(web, bill, salary):
    balances.set_minimum(Money(250000))
    html = home(web)
    assert "Abaixo do mínimo em R$ 500,00" in html
    assert "Restam R$ 2.000,00 depois das contas" in html
    p = balances.position()
    assert "Resta" in [s["name"] for s in presentation.money_bar(p)]
    names = [s["name"] for s in [*presentation.money_bar(p), *presentation.legend(p)]]
    assert "Mínimo" not in names


def test_inicio_sem_cobertura(web, funded, cats, salary):
    payables.create_bill(
        description="Conserto",
        category=cats.aluguel,
        account=funded.corrente,
        amount=Money(340000),
        due_date=D(2026, 11, 25),
    )
    html = home(web)
    assert "Faltam R$ 400,00 até o salário" in html and "Veja o que pode esperar" in html


def test_inicio_salario_atrasado(web, salary):
    with travel_to(D(2026, 12, 8)):
        relogin(web)
        html = home(web)
    assert "Pode gastar até amanhã" in html and "Salário atrasado" in html


def test_inicio_mostra_conta_atrasada(web, bill):
    with travel_to(D(2026, 11, 26)):
        relogin(web)
        assert "1 conta atrasada" in home(web)


def test_cadastrar_salario_preenche_o_formulario(web, funded):
    html = web.get(url("recurrence_new") + "?tipo=salario").content.decode()
    assert 'value="Salário"' in html


def test_linha_do_tempo_nao_sobrepoe_etiquetas(funded, cats, salary):
    for day in (23, 24, 25, 26):
        payables.create_bill(
            description=f"Conta {day}",
            category=cats.aluguel,
            account=funded.corrente,
            amount=Money(1000 * day),
            due_date=D(2026, 11, day),
        )
    p = balances.position()
    points = presentation.timeline(p, None, "o fim do mês")["points"]
    tops = [pt["top"] for pt in points]
    assert len(set(tops)) == len(tops)
    assert all(pt["top"] % 4 == 0 and pt["height"] % 4 == 0 for pt in points)


def test_barra_cabe_em_100(funded, cats, salary):
    balances.set_minimum(Money(30000))
    payables.create_bill(
        description="Conta",
        category=cats.aluguel,
        account=funded.corrente,
        amount=Money(100000),
        due_date=D(2026, 11, 25),
    )
    bar = presentation.money_bar(balances.position())
    assert 98 <= sum(s["percent"] for s in bar) <= 102
    assert [s["css"] for s in bar] == ["seg-comp", "seg-min", "seg-free"]


def test_barra_sem_cobertura_mostra_o_que_falta(funded, cats, salary):
    payables.create_bill(
        description="Conserto",
        category=cats.aluguel,
        account=funded.corrente,
        amount=Money(340000),
        due_date=D(2026, 11, 25),
    )
    p = balances.position()
    assert [s["css"] for s in presentation.money_bar(p)] == ["seg-comp", "seg-crit"]
    assert presentation.legend(p)[-1] == {"css": "seg-crit", "name": "Faltam", "value": "400,00"}


@pytest.mark.parametrize(
    ("changes", "expected"),
    [
        ({"frequency": "weekly"}, "Toda semana"),
        ({"frequency": "weekly", "interval": 2}, "A cada 2 semanas"),
        ({"day_rule": "last_day"}, "Todo último dia"),
        ({"day_rule": "nth_business_day", "day_value": 5}, "Todo 5º dia útil"),
        ({"frequency": "yearly", "day_value": 10}, "Todo dia 10, uma vez por ano"),
        ({"frequency": "every_n_months", "interval": 3}, "Todo dia 10, a cada 3 meses"),
        ({"remaining_count": 40}, "Todo dia 10 · 40 ocorrências"),
    ],
)
def test_regra_em_uma_frase(changes, expected):
    base = {"frequency": "monthly", "interval": 1, "day_rule": "fixed_day", "day_value": 10}
    assert presentation.describe_rule(RecurrenceRule(**{**base, **changes})) == expected
