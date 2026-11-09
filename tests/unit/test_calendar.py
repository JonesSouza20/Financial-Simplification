"""Calendário de dias úteis (testing-plan.md §8; RN-090 a RN-094, RN-055)."""

import datetime as dt

import pytest

from apps.calendar_br import defaults, services
from apps.calendar_br.models import Holiday

pytestmark = pytest.mark.django_db

FIFTH = {
    2026: "08/01 06/02 06/03 08/04 08/05 08/06 07/07 07/08 08/09 07/10 09/11 07/12",
    2027: "08/01 05/02 05/03 07/04 07/05 07/06 07/07 06/08 08/09 07/10 08/11 07/12",
}


@pytest.mark.parametrize("year", FIFTH)
def test_RN_091_quinto_dia_util_tabela_exata(year):
    found = [services.nth_business_day(year, m, 5).strftime("%d/%m") for m in range(1, 13)]
    assert found == FIFTH[year].split()


@pytest.mark.parametrize(
    "day",
    [
        dt.date(2026, 2, 16),
        dt.date(2026, 2, 17),
        dt.date(2027, 2, 8),
        dt.date(2027, 2, 9),
        dt.date(2026, 4, 3),
        dt.date(2027, 3, 26),
        dt.date(2026, 6, 4),
        dt.date(2027, 5, 27),
        dt.date(2026, 7, 9),
        dt.date(2026, 1, 26) - dt.timedelta(days=1),
        dt.date(2026, 11, 20),
    ],
)
def test_RN_092_feriados_moveis_e_locais(day):
    assert Holiday.objects.filter(date=day).exists()
    assert not services.is_business_day(day)


def test_pascoa_em_anos_conhecidos():
    assert defaults.easter(2026) == dt.date(2026, 4, 5)
    assert defaults.easter(2027) == dt.date(2027, 3, 28)
    assert defaults.easter(2038) == dt.date(2038, 4, 25)  # data mais tardia possível


def test_RN_090_fim_de_semana_nao_e_util():
    assert not services.is_business_day(dt.date(2026, 11, 7))
    assert not services.is_business_day(dt.date(2026, 11, 8))
    assert services.is_business_day(dt.date(2026, 11, 9))


def test_RN_093_vencimento_em_dia_nao_util():
    sabado = dt.date(2026, 11, 7)
    assert services.effective_due(sabado) == dt.date(2026, 11, 9)
    assert services.effective_due(sabado, anticipate=True) == dt.date(2026, 11, 6)
    # Feriado na sexta e fim de semana em seguida.
    sexta_santa = dt.date(2026, 4, 3)
    assert services.effective_due(sexta_santa) == dt.date(2026, 4, 6)
    assert services.effective_due(sexta_santa, anticipate=True) == dt.date(2026, 4, 2)
    util = dt.date(2026, 11, 10)
    assert services.effective_due(util) == util


def test_feriado_na_virada_de_ano():
    assert services.effective_due(dt.date(2026, 12, 25)) == dt.date(2026, 12, 28)
    assert services.effective_due(dt.date(2027, 1, 1)) == dt.date(2027, 1, 4)


def test_RN_055_dia_inexistente_vai_para_o_ultimo():
    assert services.clamp_day(2026, 4, 31) == dt.date(2026, 4, 30)
    assert services.clamp_day(2027, 2, 31) == dt.date(2027, 2, 28)
    assert services.clamp_day(2028, 2, 30) == dt.date(2028, 2, 29)
    assert services.add_months(dt.date(2026, 12, 31), 2) == dt.date(2027, 2, 28)


def test_ano_sem_calendario_recusa_em_vez_de_errar():
    with pytest.raises(services.CalendarMissingError, match="2099"):
        services.is_business_day(dt.date(2099, 3, 2))
    with pytest.raises(services.CalendarMissingError):
        services.is_business_day(dt.date(2099, 3, 1))  # domingo: confere o ano do mesmo jeito
    with pytest.raises(services.CalendarMissingError):
        services.nth_business_day(2099, 3, 5)


def test_carga_nao_desfaz_edicao():
    services.remove_holiday(dt.date(2026, 1, 25))
    assert services.seed() == 0
    assert not Holiday.objects.filter(date=dt.date(2026, 1, 25)).exists()


def test_feriado_personalizado_muda_dia_util():
    assert services.nth_business_day(2026, 12, 5) == dt.date(2026, 12, 7)
    services.add_holiday(dt.date(2026, 12, 3), "Ponto facultativo")
    assert services.nth_business_day(2026, 12, 5) == dt.date(2026, 12, 8)
    with pytest.raises(services.InvalidStateError, match="Já existe"):
        services.add_holiday(dt.date(2026, 12, 3), "De novo")
    with pytest.raises(services.InvalidTransactionError, match="nome"):
        services.add_holiday(dt.date(2026, 12, 4), " ")


def test_feriado_so_para_salario_ou_so_para_banco():
    services.add_holiday(dt.date(2026, 12, 3), "Só banco", affects_salary=False)
    assert services.nth_business_day(2026, 12, 5) == dt.date(2026, 12, 7)
    assert not services.is_business_day(dt.date(2026, 12, 3))


def test_remover_feriado_inexistente_e_ultimo_do_ano():
    with pytest.raises(services.InvalidStateError, match="não encontrado"):
        services.remove_holiday(dt.date(2026, 3, 3))
    Holiday.objects.filter(date__year=2035).exclude(date=dt.date(2035, 12, 25)).delete()
    with pytest.raises(services.InvalidStateError, match="ao menos um"):
        services.remove_holiday(dt.date(2035, 12, 25))


def test_RN_094_revisao_em_dezembro():
    assert services.needs_yearly_review(dt.date(2026, 12, 1))
    assert not services.needs_yearly_review(dt.date(2026, 11, 30))


def test_dia_util_invalido():
    with pytest.raises(services.InvalidTransactionError):
        services.nth_business_day(2026, 11, 0)
    with pytest.raises(services.InvalidTransactionError, match="dias úteis"):
        services.nth_business_day(2026, 2, 25)
