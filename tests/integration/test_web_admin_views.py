"""Telas de contas e categorias: criar, renomear, arquivar e erros (F-020; RF-CAT)."""

import datetime

import pytest

from apps.categories.models import Category
from apps.ledger.models import TransactionStatus, TransactionType
from apps.ledger.services import Leg, record
from apps.money import Money

pytestmark = pytest.mark.usefixtures("on_20_11")


def test_criar_renomear_e_arquivar_categoria(web):
    lazer = Category.objects.get(name="Lazer")
    assert (
        web.post(
            "/categorias/", {"name": "Cinema", "kind": "expense", "parent": lazer.pk}
        ).status_code
        == 302
    )
    cinema = Category.objects.get(name="Cinema")
    web.post(f"/categorias/{cinema.pk}/renomear/", {"name": "Cinema e teatro"})
    cinema.refresh_from_db()
    assert cinema.name == "Cinema e teatro"
    web.post(f"/categorias/{cinema.pk}/arquivar/")
    cinema.refresh_from_db()
    assert cinema.archived_at is not None


def test_categoria_invalida_mostra_erro(web):
    lazer = Category.objects.get(name="Lazer")
    response = web.post("/categorias/", {"name": "X", "kind": "income", "parent": lazer.pk})
    assert response.status_code == 200 and "mesmo tipo" in response.content.decode()


def test_categoria_de_sistema_nao_muda_pela_tela(web):
    juros = Category.objects.get(system_key="late_fees")
    page = web.post(f"/categorias/{juros.pk}/renomear/", {"name": "X"}, follow=True)
    assert "não podem ser renomeadas" in page.content.decode()
    page = web.post(f"/categorias/{juros.pk}/arquivar/", follow=True)
    assert "não podem ser arquivadas" in page.content.decode()


def test_arquivar_conta_pela_tela(web, fin):
    response = web.post(f"/contas/{fin.digital.pk}/arquivar/")
    assert response["Location"] == "/contas/"
    fin.digital.refresh_from_db()
    assert fin.digital.archived_at is not None


def test_arquivar_conta_com_pendente_mostra_erro(web, fin, cats):
    record(
        type=TransactionType.EXPENSE_PAID,
        legs=[
            Leg(cats.aluguel.ledger_account, Money(1000)),
            Leg(fin.corrente.ledger_account, Money(-1000)),
        ],
        operation_date=datetime.date(2026, 12, 10),
        description="Aluguel",
        status=TransactionStatus.PENDING,
    )
    page = web.post(f"/contas/{fin.corrente.pk}/arquivar/", follow=True)
    assert "pendentes" in page.content.decode()


def test_conta_com_data_invalida_mostra_erro(web):
    response = web.post(
        "/contas/nova/",
        {
            "name": "X",
            "account_type": "checking",
            "opening_balance": "",
            "opening_date": "2026-10-01",
        },
    )
    assert response.status_code == 200 and "01/11/2026" in response.content.decode()


def test_estornar_sem_motivo_e_estorno_repetido(web, fin, cats):
    txn = record(
        type=TransactionType.EXPENSE_PAID,
        legs=[
            Leg(cats.mercado.ledger_account, Money(500)),
            Leg(fin.corrente.ledger_account, Money(-500)),
        ],
        operation_date=datetime.date(2026, 11, 18),
        description="Mercado",
    )
    page = web.post(f"/movimentacoes/{txn.pk}/estornar/", {"reason": ""}, follow=True)
    assert "Informe o motivo" in page.content.decode()
    web.post(f"/movimentacoes/{txn.pk}/estornar/", {"reason": "erro"})
    page = web.post(f"/movimentacoes/{txn.pk}/estornar/", {"reason": "de novo"}, follow=True)
    assert "já foi estornada" in page.content.decode()
