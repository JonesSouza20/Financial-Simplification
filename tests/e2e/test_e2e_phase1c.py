"""Ponta a ponta da Fase 1C (testing-plan.md §12): dividir com alguém, conciliação, abertura."""

import re

import pytest
from playwright.sync_api import expect

from apps.accounts.models import FinancialAccount
from apps.cards import services as cards
from apps.money import Money
from apps.persons.models import Person
from apps.receivables import services as receivables

pytestmark = pytest.mark.e2e


def test_dividir_compra_no_cartao(app, card_a):
    app.goto(f"{app.base}/movimentacoes/lancar/")
    for key in "25000":
        app.get_by_role("group", name="Teclado numérico").get_by_role(
            "button", name=key, exact=True
        ).click()
    app.locator("fieldset").get_by_text("Cartão", exact=True).click()
    app.get_by_label("Categoria").first.select_option(label="Alimentação › Restaurantes")
    app.get_by_text("Dividir com alguém").click()
    app.get_by_label("Dividir com (nome)").fill("Ana")
    app.get_by_label("Parte da outra pessoa").fill("150,00")
    app.get_by_role("button", name="Salvar").click()
    expect(
        app.get_by_text(re.compile(r"Compra no cartão de R\$ 250,00 em Cartão A"))
    ).to_be_visible()
    assert receivables.open_total(Person.objects.get(name="Ana")) == Money(15000)
    assert cards.liability(card_a) == Money(25000)
    assert app.app_errors == []


def test_conciliar_com_ajuste(app, fin):
    app.goto(f"{app.base}/contas/{fin.corrente.pk}/")
    app.get_by_label("Saldo que o banco mostra").fill("-5,00")
    app.get_by_label("Não achei a diferença: registrar ajuste").check()
    app.get_by_label("Motivo do ajuste").fill("tarifa")
    app.get_by_role("button", name="Conferir").click()
    expect(app.get_by_text(re.compile(r"Ajuste de −R\$ 5,00 registrado"))).to_be_visible()
    assert app.app_errors == []


def test_assistente_de_abertura(app):
    FinancialAccount.objects.all().update(archived_at=None)
    app.goto(f"{app.base}/abertura/contas/")
    app.get_by_label("Nome da conta").fill("Nubank")
    app.get_by_label("Tipo").select_option(label="Conta digital")
    app.get_by_label("Saldo em 01/11/2026").fill("800,00")
    app.get_by_role("button", name="Adicionar conta").click()
    expect(app.get_by_text("Nubank")).to_be_visible()
    app.goto(f"{app.base}/abertura/revisao/")
    app.get_by_role("button", name="Confirmar abertura").click()
    expect(app.get_by_text("Abertura gravada.")).to_be_visible()
    assert FinancialAccount.objects.filter(name="Nubank").exists()
    assert app.app_errors == []


def test_telas_da_fase_1c_sem_rolagem_lateral(app, card_a, ana):
    for theme in ("light", "dark"):
        app.evaluate(f"localStorage.setItem('fin-theme', '{theme}')")
        for path in (
            "/cartoes/",
            f"/cartoes/{card_a.pk}/",
            "/a-receber/",
            "/dividas/",
            "/abertura/cartoes/",
            "/origem/bancario/",
            "/movimentacoes/lancar/",
        ):
            app.goto(app.base + path)
            assert app.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), path
    assert app.app_errors == []


def test_trocar_tipo_mostra_os_campos_certos(app, card_a):
    """Regressão: na Fase 1B os campos não mudavam ao trocar o tipo de lançamento."""
    app.goto(f"{app.base}/movimentacoes/lancar/")
    seg = app.locator("fieldset")
    expect(app.get_by_label("Pago com")).to_be_visible()
    seg.get_by_text("Transferência", exact=True).click()
    expect(app.get_by_label("Para a conta")).to_be_visible()
    expect(app.get_by_text("Dividir com alguém")).to_be_hidden()
    seg.get_by_text("Recebimento", exact=True).click()
    expect(app.get_by_label("Para a conta")).to_be_hidden()
    expect(app.locator("#id_income_category")).to_be_visible()
    expect(app.locator("#id_expense_category")).to_be_hidden()
    seg.get_by_text("Cartão", exact=True).click()
    expect(app.get_by_label("Parcelas")).to_be_visible()
    expect(app.locator("#id_account")).to_be_hidden()
    assert app.app_errors == []
