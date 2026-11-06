"""Lançamentos do usuário (RF-LAN, RF-CON-04, RN-061, RN-171, RN-186)."""

import datetime

import pytest
import time_machine
from django.utils import timezone

from apps.entries import services as entries
from apps.entries.services import EXPENSE, INCOME, TRANSFER, EntryInput
from apps.ledger.errors import InvalidStateError, InvalidTransactionError
from apps.ledger.invariants import check_all
from apps.ledger.models import TransactionStatus, TransactionType
from apps.ledger.services import account_balance
from apps.money import Money

pytestmark = pytest.mark.usefixtures("on_20_11")
D = datetime.date(2026, 11, 18)


def entry(kind, cents, account, **kw):
    return EntryInput(kind=kind, amount=Money(cents), account=account, on=kw.pop("on", D), **kw)


def test_gasto_no_debito(fin, cats):
    txn = entries.record(entry(EXPENSE, 23000, fin.corrente, category=cats.mercado))
    assert txn.type == TransactionType.EXPENSE_PAID
    assert account_balance(fin.corrente.ledger_account) == Money(-23000)
    assert account_balance(cats.mercado.ledger_account) == Money(23000)
    assert txn.description == "Alimentação › Mercado"


def test_gasto_com_vr_so_em_categoria_aceita(fin, cats):
    txn = entries.record(entry(EXPENSE, 4500, fin.vr, category=cats.mercado))
    assert txn.type == TransactionType.EXPENSE_BENEFIT
    with pytest.raises(InvalidTransactionError, match="não aceita pagamento com benefício"):
        entries.record(entry(EXPENSE, 100, fin.vr, category=cats.eletronicos))


def test_recebimento_e_credito_de_beneficio(fin, cats):
    salario = entries.record(entry(INCOME, 500000, fin.corrente, category=cats.salario))
    assert salario.type == TransactionType.INCOME_RECEIVED
    vr = entries.record(entry(INCOME, 60000, fin.vr, category=cats.beneficios))
    assert vr.type == TransactionType.BENEFIT_CREDIT
    with pytest.raises(InvalidTransactionError, match="Benefícios"):
        entries.record(entry(INCOME, 100, fin.vr, category=cats.salario))


def test_categoria_do_tipo_errado(fin, cats):
    with pytest.raises(InvalidTransactionError, match="despesa"):
        entries.record(entry(EXPENSE, 100, fin.corrente, category=cats.salario))
    with pytest.raises(InvalidTransactionError, match="receita"):
        entries.record(entry(INCOME, 100, fin.corrente, category=cats.mercado))


def test_transferencias_classificadas(fin):
    t = entries.record(entry(TRANSFER, 40000, fin.corrente, destination=fin.digital))
    a = entries.record(entry(TRANSFER, 100000, fin.corrente, destination=fin.reserva))
    r = entries.record(entry(TRANSFER, 30000, fin.reserva, destination=fin.digital))
    assert [t.type, a.type, r.type] == [
        TransactionType.TRANSFER,
        TransactionType.RESERVE_DEPOSIT,
        TransactionType.RESERVE_WITHDRAWAL,
    ]


def test_transferencia_invalida(fin):
    with pytest.raises(InvalidTransactionError, match="diferentes"):
        entries.record(entry(TRANSFER, 100, fin.corrente, destination=fin.corrente))
    with pytest.raises(InvalidTransactionError, match="Benefícios"):
        entries.record(entry(TRANSFER, 100, fin.vr, destination=fin.corrente))


def test_valor_zero_recusado(fin, cats):
    with pytest.raises(InvalidTransactionError, match="maior que zero"):
        entries.record(entry(EXPENSE, 0, fin.corrente, category=cats.mercado))


def test_aviso_de_duplicidade(fin, cats):
    first = entries.record(entry(EXPENSE, 4590, fin.corrente, category=cats.mercado))
    assert (
        entries.possible_duplicate(entry(EXPENSE, 4590, fin.corrente, category=cats.mercado))
        == first
    )
    assert (
        entries.possible_duplicate(entry(EXPENSE, 4591, fin.corrente, category=cats.mercado))
        is None
    )


def test_corrigir_pela_tela_de_lancamento(fin, cats):
    original = entries.record(
        entry(EXPENSE, 8500, fin.corrente, category=cats.mercado, on=datetime.date(2026, 11, 3))
    )
    new = entries.correct(
        original,
        entry(EXPENSE, 5800, fin.corrente, category=cats.mercado, on=datetime.date(2026, 11, 3)),
        reason="valor",
    )
    assert account_balance(fin.corrente.ledger_account) == Money(-5800)
    original.refresh_from_db()
    assert original.status == TransactionStatus.REVERSED
    assert new.status == TransactionStatus.CONFIRMED
    assert check_all() == []


def test_desfazer_dentro_do_prazo(fin, cats):
    txn = entries.record(entry(EXPENSE, 1000, fin.corrente, category=cats.mercado))
    entries.undo(txn)
    assert account_balance(fin.corrente.ledger_account) == Money(0)


def test_desfazer_fora_do_prazo(fin, cats):
    txn = entries.record(entry(EXPENSE, 1000, fin.corrente, category=cats.mercado))
    with (
        time_machine.travel(timezone.now() + datetime.timedelta(minutes=3), tick=False),
        pytest.raises(InvalidStateError, match="prazo"),
    ):
        entries.undo(txn)


def test_lista_oculta_estornos_por_padrao(fin, cats):
    kept = entries.record(entry(EXPENSE, 1000, fin.corrente, category=cats.mercado))
    gone = entries.record(entry(EXPENSE, 2000, fin.corrente, category=cats.mercado))
    entries.undo(gone)
    assert list(entries.movements()) == [kept]
    assert len(entries.movements(show_all=True)) == 3


def test_filtros_da_lista(fin, cats):
    a = entries.record(
        entry(
            EXPENSE,
            1000,
            fin.corrente,
            category=cats.mercado,
            on=datetime.date(2026, 11, 3),
            description="Feira",
        )
    )
    b = entries.record(entry(INCOME, 500000, fin.digital, category=cats.salario))
    assert list(entries.movements(account=fin.digital)) == [b]
    assert list(entries.movements(category=cats.mercado)) == [a]
    assert list(entries.movements(text="feira")) == [a]
    assert list(entries.movements(start=datetime.date(2026, 11, 10))) == [b]


def test_descricao_para_a_tela(fin, cats):
    txn = entries.record(entry(TRANSFER, 40000, fin.corrente, destination=fin.digital))
    view = entries.describe(txn)
    assert (view.label, view.account, view.destination, view.amount) == (
        "Transferência",
        "Corrente",
        "Digital",
        Money(40000),
    )
    expense = entries.describe(
        entries.record(entry(EXPENSE, 100, fin.corrente, category=cats.mercado))
    )
    assert expense.signed == Money(-100) and expense.editable
