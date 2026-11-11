"""Telas da Fase 1C: cartões, a receber, dívidas, abertura, conciliação e "de onde vem"."""

import datetime

import pytest

from apps.accounts.models import FinancialAccount
from apps.cards import services as cards
from apps.cards.models import Card
from apps.ledger.models import LedgerTransaction, TransactionType
from apps.ledger.services import account_balance
from apps.money import Money
from apps.persons.models import Person
from apps.receivables import services as receivables

pytestmark = pytest.mark.usefixtures("on_20_11")


def test_paginas_abrem(web, fin, card_a, ana):
    from apps.debts import services as debts

    loan = debts.create_loan(
        creditor="Banco", description="Empréstimo", balance=Money(100000), due_day=15
    )
    for path in [
        "/cartoes/",
        "/cartoes/novo/",
        f"/cartoes/{card_a.pk}/",
        "/a-receber/",
        f"/a-receber/{ana.pk}/",
        "/dividas/",
        "/dividas/nova-divida/",
        "/dividas/novo-consorcio/",
        f"/dividas/{loan.pk}/",
        "/abertura/contas/",
        "/abertura/cartoes/",
        "/abertura/dividas/",
        "/abertura/receber/",
        "/abertura/revisao/",
        "/mais/",
    ] + [
        f"/origem/{s}/"
        for s in ("bancario", "livre", "guardado", "beneficios", "cartoes", "dividas", "a-receber")
    ]:
        assert web.get(path).status_code == 200, path
    assert web.get("/origem/inexistente/").status_code == 404


def test_compra_no_cartao_dividida_pela_tela(web, card_a, cats):
    response = web.post(
        "/movimentacoes/lancar/",
        {
            "kind": "card",
            "amount": "250,00",
            "card": card_a.pk,
            "installments": "1",
            "expense_category": cats.get("Restaurantes").pk,
            "share_person": "Ana",
            "share_amount": "150,00",
            "on": "2026-11-14",
            "idempotency_key": "K-card",
        },
    )
    assert response.status_code == 302, response.content.decode()[:500]
    ana = Person.objects.get(name="Ana")
    assert receivables.open_total(ana) == Money(15000)
    assert cards.liability(card_a) == Money(25000)
    page = web.get(response["Location"]).content.decode()
    assert "Compra no cartão de R$ 250,00 em Cartão A salvo" in page


def test_compra_no_cartao_exige_cartao_e_categoria(web, card_a):
    response = web.post(
        "/movimentacoes/lancar/",
        {
            "kind": "card",
            "amount": "50,00",
            "installments": "1",
            "on": "2026-11-14",
            "idempotency_key": "K-x",
        },
    )
    body = response.content.decode()
    assert response.status_code == 200
    assert "Escolha o cartão" in body and "Escolha a categoria da sua parte" in body


def test_estorno_comercial_parcial_pela_tela(web, card_a, cats):
    txn = cards.record_purchase(
        cards.PurchaseInput(
            card=card_a,
            total=Money(20000),
            on=datetime.date(2026, 11, 15),
            category=cats.eletronicos,
        )
    )
    web.post(
        f"/movimentacoes/{txn.pk}/estornar/",
        {"reason": "troca", "mode": "commercial", "amount": "50,00"},
    )
    assert cards.liability(card_a) == Money(15000)
    page = web.post(
        f"/movimentacoes/{txn.pk}/estornar/",
        {"reason": "x", "mode": "commercial", "amount": "abc"},
        follow=True,
    )
    assert "Valor do estorno inválido" in page.content.decode()


def test_pagar_cartao_pela_tela(web, card_a, fin, cats):
    cards.record_purchase(
        cards.PurchaseInput(
            card=card_a,
            total=Money(20000),
            on=datetime.date(2026, 11, 15),
            category=cats.eletronicos,
        )
    )
    web.post(
        f"/cartoes/{card_a.pk}/pagar/",
        {
            "account": fin.corrente.pk,
            "amount": "200,00",
            "on": "2026-11-20",
            "idempotency_key": "K-pay",
        },
    )
    assert cards.liability(card_a) == Money(0)
    body = web.get(f"/cartoes/{card_a.pk}/").content.decode()
    assert "R$ 200,00" in body and "Nada em aberto" in body


def test_item_de_abertura_pela_tela_do_cartao(web, card_a):
    web.post(
        f"/cartoes/{card_a.pk}/item-de-abertura/",
        {
            "kind": "remaining_installments",
            "description": "TV",
            "purchase_date": "2026-06-15",
            "total": "2.400,00",
            "installments": "10",
            "billed": "5",
            "due_date": "2026-12-05",
        },
    )
    assert cards.liability(card_a) == Money(120000)


def test_emprestar_e_receber_pela_tela(web, fin):
    web.post(
        "/a-receber/",
        {
            "person": "Bruno",
            "account": fin.digital.pk,
            "amount": "500,00",
            "on": "2026-11-12",
            "due_date": "2026-12-10",
            "idempotency_key": "K-lend",
        },
    )
    bruno = Person.objects.get(name="Bruno")
    web.post(
        f"/a-receber/{bruno.pk}/receber/",
        {
            "account": fin.digital.pk,
            "amount": "100,00",
            "on": "2026-11-20",
            "idempotency_key": "K-r",
        },
    )
    assert receivables.open_total(bruno) == Money(40000)
    assert "R$ 400,00" in web.get("/a-receber/").content.decode()


def test_divida_e_consorcio_pela_tela(web, fin):
    from apps.debts.models import Debt

    web.post(
        "/dividas/nova-divida/",
        {"creditor": "Banco", "balance": "10.000,00", "monthly_rate_percent": "2", "due_day": "15"},
    )
    loan = Debt.objects.get(kind="loan")
    web.post(
        f"/dividas/{loan.pk}/pagar/",
        {
            "account": fin.corrente.pk,
            "principal": "745,60",
            "interest": "200,00",
            "on": "2026-11-16",
            "idempotency_key": "K-loan",
        },
    )
    assert account_balance(loan.ledger_account) == Money(-925440)
    web.post(
        "/dividas/novo-consorcio/",
        {
            "description": "Consórcio",
            "installment": "650,00",
            "remaining_installments": "40",
            "due_day": "20",
        },
    )
    cons = Debt.objects.get(kind="consortium")
    web.post(
        f"/dividas/{cons.pk}/pagar/",
        {
            "account": fin.corrente.pk,
            "amount": "650,00",
            "on": "2026-11-20",
            "idempotency_key": "K-cons",
        },
    )
    assert (
        LedgerTransaction.objects.filter(type=TransactionType.CONSORTIUM_INSTALLMENT).count() == 1
    )


def test_assistente_de_abertura_completo(web):
    web.post(
        "/abertura/contas/",
        {
            "action": "add:accounts",
            "accounts-name": "Corrente",
            "accounts-account_type": "checking",
            "accounts-balance": "2.500,00",
        },
    )
    web.post(
        "/abertura/contas/",
        {
            "action": "add:accounts",
            "accounts-name": "Errada",
            "accounts-account_type": "cash",
            "accounts-balance": "1,00",
        },
    )
    web.post("/abertura/contas/", {"action": "remove:accounts", "index": "1"})
    web.post(
        "/abertura/cartoes/",
        {
            "action": "add:cards",
            "cards-name": "Cartão A",
            "cards-credit_limit": "5.000,00",
            "cards-closing_day": "25",
            "cards-due_day": "5",
        },
    )
    web.post(
        "/abertura/cartoes/",
        {
            "action": "add:items",
            "items-card": "0",
            "items-kind": "closed_invoice",
            "items-amount": "1.230,00",
            "items-due_date": "2026-11-05",
        },
    )
    review = web.get("/abertura/revisao/").content.decode()
    assert "R$ 2.500,00" in review and "R$ 1.230,00" in review and "R$ 1.270,00" in review
    response = web.post("/abertura/revisao/", {"action": "commit"})
    assert response["Location"] == "/"
    assert FinancialAccount.objects.get().name == "Corrente"
    assert cards.liability(Card.objects.get()) == Money(123000)
    assert web.get("/abertura/contas/")["Location"] == "/"  # só uma vez


def test_assistente_mostra_erro_do_formulario(web):
    response = web.post(
        "/abertura/cartoes/",
        {
            "action": "add:cards",
            "cards-name": "X",
            "cards-credit_limit": "100,00",
            "cards-closing_day": "5",
            "cards-due_day": "5",
        },
    )
    assert "mesmo dia" in response.content.decode()


def test_conciliacao_pela_tela_e_aviso_no_lancamento(web, fin, cats):
    page = web.post(
        f"/contas/{fin.corrente.pk}/conferir/",
        {"on": "2026-11-20", "informed": "-5,00"},
        follow=True,
    )
    assert "Diferença de" in page.content.decode()
    page = web.post(
        f"/contas/{fin.corrente.pk}/conferir/",
        {"on": "2026-11-20", "informed": "-5,00", "adjust": "on", "notes": "tarifa"},
        follow=True,
    )
    assert "Ajuste de" in page.content.decode()
    response = web.post(
        "/movimentacoes/lancar/",
        {
            "kind": "expense",
            "amount": "10,00",
            "account": fin.corrente.pk,
            "expense_category": cats.mercado.pk,
            "on": "2026-11-18",
            "idempotency_key": "K-rec",
        },
    )
    assert response.status_code == 200 and "foi conciliada" in response.content.decode()


def test_inicio_mostra_banner_de_abertura_e_totais(web, card_a, cats):
    cards.record_purchase(
        cards.PurchaseInput(
            card=card_a,
            total=Money(20000),
            on=datetime.date(2026, 11, 15),
            category=cats.eletronicos,
        )
    )
    body = web.get("/").content.decode()
    assert "Comece pela abertura" in body and '<span class="cur">R$</span>200,00' in body
    origin = web.get("/origem/cartoes/").content.decode()
    assert "Cartão A" in origin and "R$ 200,00" in origin


@pytest.mark.parametrize(("cents", "used"), [(20000, 4), (900000, 100)])
def test_barra_do_limite_fica_entre_0_e_100(web, card_a, cats, monkeypatch, cents, used):
    monkeypatch.setattr("apps.cards.services.liability", lambda card: Money(cents))
    body = web.get(f"/cartoes/{card_a.pk}/").content.decode()
    assert f'aria-label="Limite: {used}% usado, {100 - used}% livre"><i class="wp-{used}"' in body
