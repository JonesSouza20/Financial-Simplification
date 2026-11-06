"""Registro de transações (RN-001 a RN-014, RN-180, RN-181)."""

import datetime

import pytest

from apps.ledger import services
from apps.ledger.errors import InvalidTransactionError
from apps.ledger.invariants import check_all
from apps.ledger.models import AuditLog, LedgerTransaction, TransactionStatus, TransactionType
from apps.ledger.services import Leg
from apps.money import Money

from .helpers import balance, day, simple

pytestmark = pytest.mark.usefixtures("on_20_11")


def test_despesa_paga_gera_duas_pernas_que_somam_zero(accounts):
    txn = simple(accounts.mercado, accounts.corrente, 23000)
    assert txn.status == TransactionStatus.CONFIRMED
    assert sorted(p.amount_cents for p in txn.postings.all()) == [-23000, 23000]
    assert balance(accounts.corrente) == -23000
    assert balance(accounts.mercado) == 23000
    assert check_all() == []


def test_saldo_exibido_inverte_passivo_e_receita(accounts):
    simple(accounts.eletronicos, accounts.cartao_a, 60000, type=TransactionType.CARD_PURCHASE)
    simple(accounts.corrente, accounts.salario, 500000, type=TransactionType.INCOME_RECEIVED)
    assert services.display_balance(accounts.cartao_a) == Money(60000)
    assert services.display_balance(accounts.salario) == Money(500000)
    assert services.display_balance(accounts.corrente) == Money(500000)


def test_compra_mista_tres_pernas(accounts):
    txn = services.record(
        type=TransactionType.CARD_MIXED,
        legs=[
            Leg(accounts.restaurantes, Money(10000)),
            Leg(accounts.ana, Money(15000)),
            Leg(accounts.cartao_a, Money(-25000)),
        ],
        operation_date=day(14),
        description="Jantar",
    )
    assert txn.postings.count() == 3
    assert balance(accounts.ana) == 15000
    assert balance(accounts.restaurantes) == 10000


def test_pendente_e_previsto_nao_afetam_saldo_real(accounts):
    simple(accounts.mercado, accounts.corrente, 18000, status=TransactionStatus.PENDING, on=day(22))
    simple(
        accounts.mercado,
        accounts.corrente,
        18000,
        status=TransactionStatus.FORECAST,
        on=datetime.date(2026, 12, 22),
    )
    assert balance(accounts.corrente) == 0
    assert check_all() == []


def test_saldo_ate_uma_data(accounts):
    simple(accounts.mercado, accounts.corrente, 1000, on=day(3))
    simple(accounts.mercado, accounts.corrente, 2000, on=day(10))
    assert services.account_balance(accounts.corrente, as_of=day(5)) == Money(-1000)


def test_auditoria_registra_criacao(accounts):
    txn = simple(accounts.mercado, accounts.corrente, 500)
    log = AuditLog.objects.get(entity_type="ledger_transaction", entity_id=txn.pk)
    assert log.action == "create"
    assert log.after_json["legs"][0]["amount_cents"] == 500


@pytest.mark.parametrize(
    ("legs_cents", "message"),
    [
        ([1000, -999], "não somam zero"),
        ([1000], "duas pernas"),
        ([0, 0], "zero"),
    ],
)
def test_pernas_invalidas_sao_recusadas(accounts, legs_cents, message):
    pool = [accounts.mercado, accounts.corrente]
    legs = [Leg(pool[i], Money(c)) for i, c in enumerate(legs_cents)]
    with pytest.raises(InvalidTransactionError, match=message):
        services.record(
            type=TransactionType.EXPENSE_PAID, legs=legs, operation_date=day(3), description="x"
        )
    assert LedgerTransaction.objects.count() == 0


def test_mesma_conta_duas_vezes_recusada(accounts):
    with pytest.raises(InvalidTransactionError, match="duas vezes"):
        services.record(
            type=TransactionType.EXPENSE_PAID,
            legs=[Leg(accounts.mercado, Money(5)), Leg(accounts.mercado, Money(-5))],
            operation_date=day(3),
            description="x",
        )


def test_confirmado_com_data_futura_recusado(accounts):
    with pytest.raises(InvalidTransactionError, match="futura"):
        simple(accounts.mercado, accounts.corrente, 100, on=day(21))


def test_data_anterior_ao_inicio_so_para_abertura(accounts):
    with pytest.raises(InvalidTransactionError, match="01/11/2026"):
        simple(accounts.mercado, accounts.corrente, 100, on=datetime.date(2026, 10, 31))
    opening = simple(
        accounts.corrente,
        accounts.abertura,
        250000,
        type=TransactionType.OPENING_BALANCE,
        on=datetime.date(2026, 10, 31),
    )
    assert opening.status == TransactionStatus.CONFIRMED
    assert check_all() == []


def test_valor_maximo_por_lancamento(accounts):
    simple(accounts.mercado, accounts.corrente, 999_999_999)
    with pytest.raises(InvalidTransactionError, match="máximo"):
        simple(accounts.mercado, accounts.corrente, 1_000_000_000)


def test_conta_arquivada_recusa_lancamento(accounts):
    from django.utils import timezone

    accounts.digital.archived_at = timezone.now()
    accounts.digital.save()
    with pytest.raises(InvalidTransactionError, match="arquivada"):
        simple(accounts.mercado, accounts.digital, 100)


def test_descricao_e_tipo_obrigatorios(accounts):
    with pytest.raises(InvalidTransactionError, match="descrição"):
        simple(accounts.mercado, accounts.corrente, 100, description="  ")
    with pytest.raises(InvalidTransactionError, match="Tipo"):
        simple(accounts.mercado, accounts.corrente, 100, type="T99_inexistente")


def test_estado_inicial_invalido(accounts):
    with pytest.raises(InvalidTransactionError, match="Estado inicial"):
        simple(accounts.mercado, accounts.corrente, 100, status=TransactionStatus.REVERSED)
