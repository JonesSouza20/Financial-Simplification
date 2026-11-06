"""Contas financeiras e categorias (RF-CON-01 a 06, RF-CAT-01 a 03, T23, RN-185, RN-186)."""

import datetime

import pytest

from apps.accounts import services as accounts
from apps.categories import services as categories
from apps.categories.models import Category
from apps.ledger.errors import InvalidStateError, InvalidTransactionError
from apps.ledger.invariants import check_all
from apps.ledger.models import TransactionStatus, TransactionType
from apps.ledger.services import Leg, record
from apps.money import Money

pytestmark = pytest.mark.usefixtures("on_20_11")


def test_saldo_de_abertura_vira_transacao_t23(fin):
    conta = fin.make("Nubank", "digital", "free", 80000)
    assert accounts.balance(conta) == Money(80000)
    txn = conta.ledger_account.postings.get().transaction
    assert txn.type == TransactionType.OPENING_BALANCE
    assert txn.operation_date == datetime.date(2026, 11, 1)
    assert check_all() == []


def test_saldo_de_abertura_negativo(fin):
    conta = fin.make("Cheque especial", "checking", "free", -15000)
    assert accounts.balance(conta) == Money(-15000)


def test_saldo_zero_nao_gera_transacao(fin):
    assert not fin.corrente.ledger_account.postings.exists()


def test_abertura_antes_do_inicio_recusada(db):
    with pytest.raises(InvalidTransactionError, match="01/11/2026"):
        accounts.create_account(
            name="X",
            account_type="checking",
            asset_class="free",
            opening_balance=Money(0),
            opening_date=datetime.date(2026, 10, 31),
        )


def test_arquivar_conta(fin, cats):
    accounts.archive(fin.digital)
    fin.digital.refresh_from_db()
    assert fin.digital.archived_at is not None
    assert fin.digital not in accounts.active_accounts()


def test_arquivar_bloqueado_com_pendente(fin, cats):
    record(
        type=TransactionType.EXPENSE_PAID,
        legs=[
            Leg(cats.aluguel.ledger_account, Money(150000)),
            Leg(fin.corrente.ledger_account, Money(-150000)),
        ],
        operation_date=datetime.date(2026, 12, 10),
        description="Aluguel",
        status=TransactionStatus.PENDING,
    )
    with pytest.raises(InvalidStateError, match="pendentes"):
        accounts.archive(fin.corrente)


def test_lista_padrao_carregada(db):
    assert (
        Category.objects.filter(kind="expense", parent__isnull=True, is_system=False).count() == 14
    )
    assert set(Category.objects.filter(accepts_benefit=True).values_list("name", flat=True)) == {
        "Mercado",
        "Restaurantes",
        "Delivery",
    }
    for key in (
        "card_charges",
        "debt_interest",
        "late_fees",
        "receivable_losses",
        "consortium",
        "benefit_income",
        "reserve_yield",
    ):
        assert categories.by_key(key).is_system


def test_categorias_selecionaveis_sao_folhas_ativas_e_nao_de_sistema(db):
    names = set(categories.selectable("expense").values_list("name", flat=True))
    assert "Mercado" in names and "Educação" in names
    assert "Alimentação" not in names  # tem subcategorias
    assert "Encargos de cartão" not in names  # sistema
    assert set(categories.selectable("expense", benefit=True).values_list("name", flat=True)) == {
        "Mercado",
        "Restaurantes",
        "Delivery",
    }


def test_categoria_de_sistema_protegida(db):
    with pytest.raises(InvalidStateError):
        categories.archive(categories.by_key("late_fees"))
    with pytest.raises(InvalidStateError):
        categories.rename(categories.by_key("late_fees"), "Outra")


def test_renomear_e_arquivar_preservam_historico(cats):
    categories.rename(cats.mercado, "Supermercado")
    cats.mercado.refresh_from_db()
    assert cats.mercado.ledger_account.name == "Supermercado"
    pai = cats.mercado.parent
    categories.archive(pai)
    assert Category.objects.filter(parent=pai, archived_at__isnull=True).count() == 0


def test_nova_subcategoria_valida_tipo(db):
    pai = Category.objects.get(name="Lazer")
    sub = categories.create(name="Cinema", kind="expense", parent=pai)
    assert sub.parent == pai
    with pytest.raises(InvalidTransactionError):
        categories.create(name="X", kind="income", parent=pai)
