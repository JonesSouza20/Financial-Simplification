"""Telas da Fase 1B pelo cliente HTTP (F-010 a F-014, F-020, F-021)."""

import datetime

import pytest

from apps.accounts.models import FinancialAccount
from apps.ledger.models import LedgerTransaction, TransactionStatus
from apps.ledger.services import account_balance
from apps.money import Money

pytestmark = pytest.mark.usefixtures("on_20_11")


def test_paginas_abrem(web, fin):
    for path in [
        "/",
        "/contas/",
        "/contas/nova/",
        f"/contas/{fin.corrente.pk}/",
        "/categorias/",
        "/movimentacoes/",
        "/movimentacoes/lancar/",
        "/movimentacoes/novo/",
        "/acesso/seguranca/",
        "/aparencia/",
        "/manifest.webmanifest",
        "/sw.js",
    ]:
        assert web.get(path).status_code == 200, path


def test_criar_conta_pela_tela(web):
    response = web.post(
        "/contas/nova/",
        {
            "name": "Nubank",
            "account_type": "digital",
            "asset_class": "",
            "institution": "Nubank",
            "opening_balance": "800,00",
            "opening_date": "2026-11-01",
        },
    )
    assert response.status_code == 302
    conta = FinancialAccount.objects.get(name="Nubank")
    assert conta.asset_class == "free"
    assert account_balance(conta.ledger_account) == Money(80000)


def quick_post(web, fin, cats, key="K-tela", amount="45,90"):
    return web.post(
        "/movimentacoes/lancar/",
        {
            "kind": "expense",
            "amount": amount,
            "account": fin.corrente.pk,
            "expense_category": cats.mercado.pk,
            "on": "2026-11-20",
            "description": "",
            "idempotency_key": key,
        },
    )


def test_lancamento_rapido(web, fin, cats):
    response = quick_post(web, fin, cats)
    assert response.status_code == 302
    assert account_balance(fin.corrente.ledger_account) == Money(-4590)
    page = web.get(response["Location"])
    assert "salvo" in page.content.decode() and "Desfazer" in page.content.decode()


def test_duplo_envio_grava_uma_vez(web, fin, cats):
    quick_post(web, fin, cats, key="K-duplo")
    quick_post(web, fin, cats, key="K-duplo")
    assert LedgerTransaction.objects.filter(type="T02_expense_paid").count() == 1


def test_aviso_de_duplicidade_pede_confirmacao(web, fin, cats):
    quick_post(web, fin, cats, key="K-a")
    again = quick_post(web, fin, cats, key="K-b")
    assert again.status_code == 200 and "Salvar mesmo assim" in again.content.decode()
    data = {
        "kind": "expense",
        "amount": "45,90",
        "account": fin.corrente.pk,
        "expense_category": cats.mercado.pk,
        "on": "2026-11-20",
        "idempotency_key": "K-b",
        "confirm_duplicate": "on",
    }
    assert web.post("/movimentacoes/lancar/", data).status_code == 302
    assert account_balance(fin.corrente.ledger_account) == Money(-9180)


def test_desfazer(web, fin, cats):
    quick_post(web, fin, cats)
    web.post("/movimentacoes/desfazer/", {"next": "/movimentacoes/lancar/"})
    assert account_balance(fin.corrente.ledger_account) == Money(0)


def test_desfazer_nao_redireciona_para_fora(web, fin, cats):
    quick_post(web, fin, cats)
    response = web.post("/movimentacoes/desfazer/", {"next": "https://evil.example/"})
    assert response["Location"] == "/movimentacoes/lancar/"


def test_valor_invalido_mostra_erro(web, fin, cats):
    response = quick_post(web, fin, cats, amount="abc")
    assert response.status_code == 200 and "Valor inválido" in response.content.decode()


def test_corrigir_e_estornar_pela_tela(web, fin, cats):
    quick_post(web, fin, cats, key="K-orig", amount="85,00")
    txn = LedgerTransaction.objects.get(type="T02_expense_paid")
    form = web.get(f"/movimentacoes/{txn.pk}/corrigir/")
    assert "85,00" in form.content.decode()
    response = web.post(
        f"/movimentacoes/{txn.pk}/corrigir/",
        {
            "kind": "expense",
            "amount": "58,00",
            "account": fin.corrente.pk,
            "expense_category": cats.mercado.pk,
            "on": "2026-11-20",
            "idempotency_key": "K-corr",
        },
    )
    assert response.status_code == 302
    assert account_balance(fin.corrente.ledger_account) == Money(-5800)
    new = LedgerTransaction.objects.filter(
        status=TransactionStatus.CONFIRMED, type="T02_expense_paid"
    ).get()
    web.post(f"/movimentacoes/{new.pk}/estornar/", {"reason": "não aconteceu"})
    assert account_balance(fin.corrente.ledger_account) == Money(0)


def test_lista_com_filtro_parcial_htmx(web, fin, cats):
    quick_post(web, fin, cats)
    response = web.get("/movimentacoes/", {"account": fin.corrente.pk}, HTTP_HX_REQUEST="true")
    body = response.content.decode()
    assert "<html" not in body and "Mercado" in body


def test_detalhe_mostra_pernas_e_nota(web, fin, cats):
    quick_post(web, fin, cats)
    txn = LedgerTransaction.objects.get(type="T02_expense_paid")
    web.post(f"/movimentacoes/{txn.pk}/nota/", {"text": "compra do mês"})
    body = web.get(f"/movimentacoes/{txn.pk}/").content.decode()
    assert "compra do mês" in body and "saída" in body and "R$ 45,90" in body


def test_transferencia_pela_tela(web, fin):
    response = web.post(
        "/movimentacoes/novo/",
        {
            "kind": "transfer",
            "amount": "1.000,00",
            "account": fin.corrente.pk,
            "destination": fin.reserva.pk,
            "on": datetime.date(2026, 11, 12).isoformat(),
            "idempotency_key": "K-tr",
        },
    )
    assert response.status_code == 302
    assert account_balance(fin.reserva.ledger_account) == Money(100000)
