"""Fluxos principais no navegador, em tela de celular (testing-plan.md §12)."""

import re

import pytest
from playwright.sync_api import expect

from apps.ledger.models import LedgerTransaction, TransactionStatus
from apps.ledger.services import account_balance
from apps.money import Money

pytestmark = pytest.mark.e2e


def open_quick(page):
    page.goto(f"{page.base}/movimentacoes/lancar/")
    for key in "4590":
        page.get_by_role("group", name="Teclado numérico").get_by_role(
            "button", name=key, exact=True
        ).click()
    expect(page.locator("[x-ref=display]")).to_have_text("R$ 45,90")
    page.get_by_label("Categoria").first.select_option(label="Alimentação › Mercado")


def test_lancamento_rapido_e_desfazer(app, fin):
    open_quick(app)
    app.get_by_role("button", name="Salvar").click()
    expect(app.get_by_text(re.compile(r"Gasto de R\$ 45,90 em Corrente salvo"))).to_be_visible()
    assert account_balance(fin.corrente.ledger_account) == Money(-4590)
    app.get_by_role("button", name="Desfazer").click()
    expect(app.get_by_text("Lançamento desfeito.")).to_be_visible()
    assert account_balance(fin.corrente.ledger_account) == Money(0)
    assert app.app_errors == []


def test_duplo_toque_grava_uma_vez(app, fin):
    open_quick(app)
    app.get_by_role("button", name="Salvar").dblclick()
    expect(app.get_by_text(re.compile("salvo"))).to_be_visible()
    assert LedgerTransaction.objects.filter(type="T02_expense_paid").count() == 1
    assert app.app_errors == []


def test_corrigir_lancamento(app, fin):
    open_quick(app)
    app.get_by_role("button", name="Salvar").click()
    txn = LedgerTransaction.objects.get(type="T02_expense_paid")
    app.goto(f"{app.base}/movimentacoes/{txn.pk}/")
    app.get_by_role("link", name="Corrigir").click()
    app.get_by_label("Valor").fill("58,00")
    app.get_by_role("button", name="Corrigir lançamento").click()
    expect(app.get_by_text("Lançamento corrigido.")).to_be_visible()
    assert account_balance(fin.corrente.ledger_account) == Money(-5800)
    txn.refresh_from_db()
    assert txn.status == TransactionStatus.REVERSED
    assert app.app_errors == []


def test_paginas_sem_erro_de_script_nos_dois_temas(app, fin, cats, on_20_11):
    from apps.entries import services as entries
    from apps.entries.services import EXPENSE, EntryInput

    entries.record(
        EntryInput(
            kind=EXPENSE,
            amount=Money(23000),
            account=fin.corrente,
            on=on_20_11,
            category=cats.mercado,
            description="Descrição longa o bastante para testar o corte",
        )
    )
    for theme in ("light", "dark"):
        app.evaluate(f"localStorage.setItem('fin-theme', '{theme}')")
        for path in (
            "/",
            "/movimentacoes/",
            "/movimentacoes/lancar/",
            "/contas/",
            "/categorias/",
            "/aparencia/",
        ):
            app.goto(app.base + path)
            assert app.evaluate("document.documentElement.dataset.theme") == theme
            assert app.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), path
    assert app.app_errors == []
