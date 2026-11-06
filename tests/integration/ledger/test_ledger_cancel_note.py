"""Cancelamento, notas e versão otimista (RN-013, RN-125, RN-172)."""

import pytest

from apps.ledger import services
from apps.ledger.errors import ConcurrentEditError, InvalidStateError, InvalidTransactionError
from apps.ledger.models import AuditLog, TransactionStatus

from .helpers import day, simple

pytestmark = pytest.mark.usefixtures("on_20_11")


def test_cancela_pendente_com_motivo(accounts):
    pending = simple(
        accounts.mercado, accounts.corrente, 18000, status=TransactionStatus.PENDING, on=day(22)
    )
    cancelled = services.cancel(pending, reason="conta veio em débito automático")
    assert cancelled.status == TransactionStatus.CANCELLED
    assert cancelled.cancel_reason == "conta veio em débito automático"
    assert cancelled.version == 2
    assert AuditLog.objects.filter(entity_id=pending.pk, action="cancel").exists()


def test_cancelar_exige_motivo(accounts):
    pending = simple(accounts.mercado, accounts.corrente, 100, status=TransactionStatus.PENDING)
    with pytest.raises(InvalidTransactionError, match="motivo"):
        services.cancel(pending, reason="")


def test_confirmado_nao_pode_ser_cancelado(accounts):
    confirmed = simple(accounts.mercado, accounts.corrente, 100)
    with pytest.raises(InvalidStateError, match="Estornar ou Corrigir"):
        services.cancel(confirmed, reason="x")


def test_cancelado_nao_volta(accounts):
    pending = simple(
        accounts.mercado, accounts.corrente, 100, status=TransactionStatus.FORECAST, on=day(25)
    )
    services.cancel(pending, reason="x")
    with pytest.raises(InvalidStateError):
        services.cancel(pending, reason="de novo")


def test_versao_desatualizada_e_recusada(accounts):
    pending = simple(accounts.mercado, accounts.corrente, 100, status=TransactionStatus.PENDING)
    with pytest.raises(ConcurrentEditError, match="outro aparelho"):
        services.cancel(pending, reason="x", expected_version=pending.version + 1)


def test_nota_acrescentada_sem_alterar_transacao(accounts):
    txn = simple(accounts.mercado, accounts.corrente, 100, description="Mercado")
    services.add_note(txn, "Compra do mês")
    txn.refresh_from_db()
    assert txn.description == "Mercado"
    assert [n.text for n in txn.notes.all()] == ["Compra do mês"]
    with pytest.raises(InvalidTransactionError):
        services.add_note(txn, "  ")
