"""Estornos totais e parciais (RN-082, RN-083, RN-120, RN-121, I-03; S10-B)."""

import pytest

from apps.ledger import services
from apps.ledger.errors import (
    AlreadyReversedError,
    InvalidStateError,
    InvalidTransactionError,
    ReversalLimitError,
)
from apps.ledger.invariants import check_all
from apps.ledger.models import LinkKind, TransactionStatus, TransactionType
from apps.ledger.services import Leg
from apps.money import Money

from .helpers import balance, day, simple

pytestmark = pytest.mark.usefixtures("on_20_11")


def card_purchase(accounts, cents, on=None):
    return simple(
        accounts.eletronicos,
        accounts.cartao_a,
        cents,
        type=TransactionType.CARD_PURCHASE,
        on=on or day(10),
    )


def test_estorno_tecnico_anula_na_competencia_original(accounts):
    original = simple(accounts.mercado, accounts.corrente, 8500, on=day(3))
    reversal = services.reverse(original, reason="valor errado")
    original.refresh_from_db()
    assert original.status == TransactionStatus.REVERSED
    assert reversal.type == TransactionType.TECHNICAL_REVERSAL
    assert reversal.competence_date == day(3)
    assert reversal.operation_date == day(20)
    assert balance(accounts.corrente) == 0 and balance(accounts.mercado) == 0
    assert original.links_in.get(kind=LinkKind.REVERSES).from_transaction == reversal
    assert check_all() == []


def test_estorno_comercial_vale_na_data_do_estorno(accounts):
    purchase = card_purchase(accounts, 60000)
    reversal = services.reverse(purchase, reason="lojista cancelou", mode="commercial")
    assert reversal.type == TransactionType.CARD_COMMERCIAL_REVERSAL
    assert reversal.competence_date == day(20)
    assert balance(accounts.cartao_a) == 0


def test_estorno_comercial_so_em_compra_no_cartao(accounts):
    expense = simple(accounts.mercado, accounts.corrente, 100)
    with pytest.raises(InvalidStateError, match="só para compras no cartão"):
        services.reverse(expense, reason="x", mode="commercial")


def test_estorno_repetido_e_recusado(accounts):
    original = simple(accounts.mercado, accounts.corrente, 100)
    services.reverse(original, reason="x")
    with pytest.raises(AlreadyReversedError, match="já foi estornada em 20/11/2026"):
        services.reverse(original, reason="de novo")


def test_estorno_do_estorno_e_recusado(accounts):
    original = simple(accounts.mercado, accounts.corrente, 100)
    reversal = services.reverse(original, reason="x")
    with pytest.raises(InvalidStateError, match="não pode ser estornado"):
        services.reverse(reversal, reason="desfazer")


def test_so_confirmado_pode_ser_estornado(accounts):
    pending = simple(accounts.mercado, accounts.corrente, 100, status=TransactionStatus.PENDING)
    with pytest.raises(InvalidStateError, match="cancelados"):
        services.reverse(pending, reason="x")


def test_estorno_exige_motivo(accounts):
    original = simple(accounts.mercado, accounts.corrente, 100)
    with pytest.raises(InvalidTransactionError, match="motivo"):
        services.reverse(original, reason=" ")


def test_s10b_estorno_parcial_a_vista(accounts):
    """S10 parte B (MVP-1): compra 200,00 e estorno parcial de 50,00."""
    purchase = simple(
        accounts.eletronicos,
        accounts.cartao_a,
        20000,
        type=TransactionType.CARD_PURCHASE,
        on=day(15),
    )
    partial = services.reverse_partially(purchase, amount=Money(5000), reason="troca")
    purchase.refresh_from_db()
    assert purchase.status == TransactionStatus.CONFIRMED
    assert partial.competence_date == day(20)
    assert balance(accounts.eletronicos) == 15000
    assert services.display_balance(accounts.cartao_a) == Money(15000)
    assert check_all() == []


def test_estorno_parcial_proporcional_em_compra_mista(accounts):
    mixed = services.record(
        type=TransactionType.CARD_MIXED,
        legs=[
            Leg(accounts.restaurantes, Money(10000)),
            Leg(accounts.ana, Money(15000)),
            Leg(accounts.cartao_a, Money(-25000)),
        ],
        operation_date=day(14),
        description="Jantar",
    )
    services.reverse_partially(mixed, amount=Money(5000), reason="item devolvido")
    assert balance(accounts.restaurantes) == 8000
    assert balance(accounts.ana) == 12000
    assert balance(accounts.cartao_a) == -20000


def test_estornos_parciais_nao_passam_do_total(accounts):
    purchase = card_purchase(accounts, 20000)
    services.reverse_partially(purchase, amount=Money(15000), reason="a")
    with pytest.raises(ReversalLimitError, match="R\\$ 50,00"):
        services.reverse_partially(purchase, amount=Money(6000), reason="b")
    assert check_all() == []


def test_estorno_total_apos_parcial_estorna_so_o_restante(accounts):
    purchase = card_purchase(accounts, 20000)
    services.reverse_partially(purchase, amount=Money(5000), reason="a")
    services.reverse(purchase, reason="cancelada", mode="commercial")
    purchase.refresh_from_db()
    assert purchase.status == TransactionStatus.REVERSED
    assert balance(accounts.cartao_a) == 0 and balance(accounts.eletronicos) == 0
    assert check_all() == []


def test_parciais_que_completam_o_total_viram_estorno_total(accounts):
    purchase = card_purchase(accounts, 20000)
    services.reverse_partially(purchase, amount=Money(12000), reason="a")
    services.reverse_partially(purchase, amount=Money(8000), reason="b")
    purchase.refresh_from_db()
    assert purchase.status == TransactionStatus.REVERSED
    assert balance(accounts.cartao_a) == 0
    with pytest.raises(AlreadyReversedError):
        services.reverse_partially(purchase, amount=Money(1), reason="c")
    assert check_all() == []


def test_estorno_parcial_so_em_compra_no_cartao(accounts):
    expense = simple(accounts.mercado, accounts.corrente, 1000)
    with pytest.raises(InvalidStateError, match="compras no cartão"):
        services.reverse_partially(expense, amount=Money(100), reason="x")


def test_estorno_parcial_exige_valor_positivo(accounts):
    purchase = card_purchase(accounts, 1000)
    with pytest.raises(InvalidTransactionError, match="maior que zero"):
        services.reverse_partially(purchase, amount=Money(0), reason="x")
