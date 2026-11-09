"""Pagamentos de ponta a ponta no celular: pagar uma parte e depois o resto (F-031)."""

import datetime

import pytest

from apps.money import Money
from apps.payables import services as payables

pytestmark = [pytest.mark.e2e]


@pytest.fixture
def bill(fin, cats, on_20_11):
    return payables.create_bill(
        description="Aluguel",
        category=cats.aluguel,
        account=fin.corrente,
        amount=Money(100000),
        due_date=datetime.date(2026, 11, 25),
    )


def test_pagar_parte_depois_o_resto_e_desfazer(app, bill):
    app.goto(f"{app.base}/pagamentos/")
    app.get_by_role("link", name="Pagar", exact=True).click()
    app.get_by_text("Pagar outro valor ou com juros").click()
    app.get_by_label("Valor", exact=True).fill("400,00")
    app.get_by_role("button", name="Pagar este valor").click()
    app.get_by_text("pago em parte").wait_for()
    app.get_by_text("Faltam R$ 600,00").wait_for()

    app.get_by_role("link", name="Voltar para Pagamentos").click()
    app.get_by_text("Pago em parte").wait_for()
    app.get_by_role("link", name="Pagar", exact=True).click()
    app.get_by_role("button", name="Pagar R$ 600,00").click()
    app.get_by_role("heading", name="Aluguel pago").wait_for()

    app.get_by_role("button", name="Desfazer").click()
    app.get_by_text("Pago em parte").wait_for()
    assert not app.app_errors
