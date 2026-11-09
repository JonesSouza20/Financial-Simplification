"""Compromissos e liquidação (business-rules.md §3.3, §3.4, §5, §6; testing-plan.md §6)."""

import datetime as dt

import pytest
from django.db import IntegrityError, connection, transaction

from apps.accounts import services as accounts
from apps.accounts.services import balance
from apps.categories import services as categories
from apps.debts import services as debts
from apps.entries import services as entries
from apps.entries.services import EXPENSE, EntryInput
from apps.ledger import services as ledger
from apps.ledger.errors import ConcurrentEditError, InvalidStateError, InvalidTransactionError
from apps.ledger.invariants import check_all
from apps.ledger.models import LedgerPosting, LedgerTransaction, TransactionStatus
from apps.money import Money
from apps.payables import services
from apps.payables.models import Commitment, ExcessKind, Settlement

pytestmark = pytest.mark.usefixtures("on_20_11")

DUE = dt.date(2026, 11, 25)
TODAY = dt.date(2026, 11, 20)


@pytest.fixture
def conta(fin):
    fin.make("Base", "checking", "free", 1_000_000)
    from apps.accounts.models import FinancialAccount

    return FinancialAccount.objects.get(name="Base")


@pytest.fixture
def bill(conta, cats):
    return services.create_bill(
        description="Luz", category=cats.aluguel, account=conta, amount=Money(10000), due_date=DUE
    )


def fresh(commitment):
    return Commitment.objects.select_related("transaction").get(pk=commitment.pk)


def legs(txn):
    return {p.account.name: p.amount_cents for p in txn.postings.select_related("account")}


# Criação e efeito no saldo ---------------------------------------------------------------


def test_RN_012_pendente_e_previsto_nao_afetam_saldo_real(conta, cats, bill):
    services.create_income(
        description="Extra",
        category=cats.salario,
        account=conta,
        amount=Money(5000),
        due_date=DUE,
    )
    assert balance(conta) == Money(1_000_000)
    assert ledger.account_balance(cats.aluguel.ledger_account) == Money(0)
    assert bill.transaction.status == TransactionStatus.PENDING
    assert check_all() == []


def test_RN_031_valor_estimado_nasce_previsto(conta, cats):
    c = services.create_bill(
        description="Água",
        category=cats.aluguel,
        account=conta,
        amount=Money(100),
        due_date=DUE,
        value_type="variable",
    )
    assert c.transaction.status == TransactionStatus.FORECAST
    assert services.status(c) == services.FORECAST


def test_previstos_nao_aparecem_em_movimentacoes(conta, cats, bill):
    txn = entries.record(
        EntryInput(kind=EXPENSE, amount=Money(1), account=conta, on=TODAY, category=cats.mercado)
    )
    assert bill.transaction not in entries.movements(show_all=True)
    assert txn in entries.movements()


def test_RN_093_vencimento_efetivo_gravado(conta, cats):
    sabado = dt.date(2026, 11, 28)
    normal = services.create_bill(
        description="A", category=cats.aluguel, account=conta, amount=Money(1), due_date=sabado
    )
    antecipa = services.create_bill(
        description="B",
        category=cats.aluguel,
        account=conta,
        amount=Money(1),
        due_date=sabado,
        anticipates=True,
    )
    assert normal.effective_due_date == dt.date(2026, 11, 30)
    assert antecipa.effective_due_date == dt.date(2026, 11, 27)


def test_RN_032_competencia_vai_para_o_pagamento(conta, cats):
    c = services.create_bill(
        description="Luz de outubro",
        category=cats.aluguel,
        account=conta,
        amount=Money(100),
        due_date=DUE,
        reference_month="2026-10",
    )
    assert c.transaction.competence_date == dt.date(2026, 10, 1)
    paid = services.pay(c, amount=Money(100))
    assert paid.transaction.competence_date == dt.date(2026, 10, 1)
    assert paid.transaction.operation_date == TODAY


def test_competencia_invalida(conta, cats):
    with pytest.raises(InvalidTransactionError, match="AAAA-MM"):
        services.create_bill(
            description="X",
            category=cats.aluguel,
            account=conta,
            amount=Money(100),
            due_date=DUE,
            reference_month="10/2026",
        )


def test_criacao_invalida(conta, cats):
    base = {"description": "X", "category": cats.aluguel, "due_date": DUE}
    with pytest.raises(InvalidTransactionError, match="maior que zero"):
        services.create_bill(**base, account=conta, amount=Money(0))
    with pytest.raises(InvalidTransactionError, match="conta prevista"):
        services.create_bill(**base, account=None, amount=Money(1))
    with pytest.raises(InvalidTransactionError, match="Tipo de valor"):
        services.create_bill(**base, account=conta, amount=Money(1), value_type="x")
    with pytest.raises(InvalidTransactionError, match="receita"):
        services.create_income(**base, account=conta, amount=Money(1))


def test_RN_170_criacao_idempotente(conta, cats):
    kwargs = {
        "description": "X",
        "category": cats.aluguel,
        "account": conta,
        "amount": Money(1),
        "due_date": DUE,
        "idempotency_key": "chave",
    }
    assert services.create_bill(**kwargs).pk == services.create_bill(**kwargs).pk
    assert Commitment.objects.count() == 1


def test_RN_037_parcelamento_fora_do_cartao(conta, cats):
    parts = services.create_installments(
        description="Boleto",
        category=cats.aluguel,
        account=conta,
        total=Money(10000),
        count=3,
        first_due=dt.date(2026, 12, 31),
    )
    assert [p.planned_amount_cents for p in parts] == [3334, 3333, 3333]
    assert [p.due_date for p in parts] == [
        dt.date(2026, 12, 31),
        dt.date(2027, 1, 31),
        dt.date(2027, 2, 28),
    ]
    assert len({p.installment_group for p in parts}) == 1
    assert [p.installment_number for p in parts] == [1, 2, 3]
    assert parts[1].transaction.competence_date == dt.date(2027, 1, 31)
    assert parts[0].transaction.description == "Boleto (1/3)"
    with pytest.raises(InvalidTransactionError):
        services.create_installments(
            description="B",
            category=cats.aluguel,
            account=conta,
            total=Money(100),
            count=0,
            first_due=DUE,
        )


# Pagamento ---------------------------------------------------------------------------


def test_RN_040_pagar_total_cria_transacao_nova(conta, cats, bill):
    settlement = services.pay(bill, amount=Money(10000))
    assert settlement.transaction.pk != bill.transaction.pk
    assert settlement.transaction.status == TransactionStatus.CONFIRMED
    assert fresh(bill).transaction.status == TransactionStatus.PENDING  # nunca vira confirmado
    assert services.open_amount(fresh(bill)) == Money(0)
    assert services.status(fresh(bill)) == services.PAID
    assert balance(conta) == Money(990_000)
    assert ledger.account_balance(cats.aluguel.ledger_account) == Money(10000)
    assert check_all() == []


def test_RN_033_pagamento_parcial_em_partes(conta, bill):
    services.pay(bill, amount=Money(3000))
    assert services.open_amount(fresh(bill)) == Money(7000)
    assert services.status(fresh(bill)) == services.PARTIAL
    services.pay(bill, amount=Money(7000))
    assert services.status(fresh(bill)) == services.PAID
    assert balance(conta) == Money(990_000)


def test_paga_em_outra_conta(conta, fin, bill):
    services.pay(bill, amount=Money(10000), account=fin.digital)
    assert balance(conta) == Money(1_000_000)
    assert balance(fin.digital) == Money(-10000)


def test_RN_034_juros_em_perna_separada(conta, cats, bill):
    services.pay(bill, amount=Money(10000), late_fee=Money(250))
    fees = categories.by_key("late_fees").ledger_account
    assert ledger.account_balance(fees) == Money(250)
    assert ledger.account_balance(cats.aluguel.ledger_account) == Money(10000)
    assert balance(conta) == Money(989_750)
    assert services.open_amount(fresh(bill)) == Money(0)
    assert Settlement.objects.get().amount_cents == 10000


def test_RN_043_acima_do_aberto_sem_classificar_e_recusado(conta, bill):
    with pytest.raises(InvalidTransactionError, match="Classifique"):
        services.pay(bill, amount=Money(10001))
    assert balance(conta) == Money(1_000_000)
    assert not Settlement.objects.exists()


def test_RN_043_excedente_como_juros(conta, cats, bill):
    services.pay(bill, amount=Money(12000), excess_kind=ExcessKind.LATE_FEE)
    fees = categories.by_key("late_fees").ledger_account
    assert ledger.account_balance(fees) == Money(2000)
    assert ledger.account_balance(cats.aluguel.ledger_account) == Money(10000)
    settlement = Settlement.objects.get()
    assert settlement.amount_cents == 10000 and settlement.excess_kind == "late_fee"


def test_RN_043_excedente_como_valor_real_maior(conta, cats, bill):
    services.pay(bill, amount=Money(12000), excess_kind=ExcessKind.HIGHER_ACTUAL)
    assert ledger.account_balance(cats.aluguel.ledger_account) == Money(12000)
    assert balance(conta) == Money(988_000)
    assert Settlement.objects.get().amount_cents == 10000
    assert check_all() == []


def test_RN_043_pagamento_duplicado_e_barrado(bill):
    services.pay(bill, amount=Money(10000))
    with pytest.raises(InvalidStateError, match="já está liquidado"):
        services.pay(bill, amount=Money(10000))


def test_RN_170_pagar_com_duplo_toque(conta, bill):
    first = services.pay(bill, amount=Money(10000), idempotency_key="toque")
    second = services.pay(bill, amount=Money(10000), idempotency_key="toque")
    assert first.pk == second.pk
    assert balance(conta) == Money(990_000)


def test_pagamento_invalido(conta, cats, fin, bill):
    with pytest.raises(InvalidTransactionError, match="valor pago"):
        services.pay(bill, amount=Money(0))
    with pytest.raises(InvalidTransactionError, match="negativos"):
        services.pay(bill, amount=Money(1), late_fee=Money(-1))
    with pytest.raises(InvalidTransactionError, match="futura"):
        services.pay(bill, amount=Money(1), on=dt.date(2026, 12, 1))
    with pytest.raises(InvalidTransactionError, match="benefício"):
        services.pay(bill, amount=Money(1), account=fin.vr, late_fee=Money(1))


def test_RF_LAN_02_receita_prevista_recebida(conta, cats):
    c = services.create_income(
        description="Bônus",
        category=cats.salario,
        account=conta,
        amount=Money(5000),
        due_date=TODAY,
    )
    services.pay(c, amount=Money(5000))
    assert balance(conta) == Money(1_005_000)
    with pytest.raises(InvalidTransactionError, match="Juros"):
        other = services.create_income(
            description="B2",
            category=cats.salario,
            account=conta,
            amount=Money(5000),
            due_date=TODAY,
        )
        services.pay(other, amount=Money(5000), late_fee=Money(1))


def test_RN_021_receita_com_valor_diferente_encerra(conta, cats):
    c = services.create_income(
        description="Bônus",
        category=cats.salario,
        account=conta,
        amount=Money(5000),
        due_date=TODAY,
    )
    services.pay(c, amount=Money(4000), close_reason="veio menor")
    assert services.status(fresh(c)) == services.PAID
    assert balance(conta) == Money(1_004_000)


def test_RN_023_receita_atrasada(conta, cats):
    c = services.create_income(
        description="Bônus",
        category=cats.salario,
        account=conta,
        amount=Money(5000),
        due_date=dt.date(2026, 11, 10),
    )
    assert services.late_incomes() == [c]
    services.pay(c, amount=Money(5000))
    assert services.late_incomes() == []


# Encerrar, cancelar, agendar -------------------------------------------------------------


def test_RN_042_encerrar_com_valor_diferente_nao_gera_perna(conta, bill):
    services.pay(bill, amount=Money(8000))
    before = LedgerPosting.objects.count()
    closed = services.close(bill, reason="conta veio menor")
    assert LedgerPosting.objects.count() == before
    assert services.status(closed) == services.PAID
    assert balance(conta) == Money(992_000)


def test_RN_042_encerrar_exige_pagamento_e_motivo(bill):
    with pytest.raises(InvalidStateError, match="cancelar"):
        services.close(bill, reason="x")
    services.pay(bill, amount=Money(1))
    with pytest.raises(InvalidTransactionError, match="motivo"):
        services.close(bill, reason=" ")
    services.close(bill, reason="ok")
    with pytest.raises(InvalidStateError, match="já está liquidado"):
        services.close(bill, reason="de novo")


def test_RN_036_cancelar(bill):
    with pytest.raises(InvalidTransactionError, match="motivo"):
        services.cancel(bill, reason="")
    c = services.cancel(bill, reason="não vou usar")
    assert services.status(fresh(c)) == services.CANCELLED
    assert services.open_amount(fresh(c)) == Money(0)
    with pytest.raises(InvalidStateError, match="cancelado"):
        services.pay(c, amount=Money(1))


def test_RN_036_conta_com_pagamento_nao_cancela(bill):
    services.pay(bill, amount=Money(1))
    with pytest.raises(InvalidStateError, match="encerrar"):
        services.cancel(bill, reason="x")


def test_RN_035_agendar_e_desfazer(bill):
    scheduled = services.schedule(bill, debit_date=DUE)
    assert services.status(scheduled) == services.SCHEDULED
    back = services.unschedule(scheduled)
    assert services.status(back) == services.PENDING
    assert back.transaction.status == TransactionStatus.PENDING


def test_agendar_invalido(conta, cats, bill):
    with pytest.raises(InvalidTransactionError, match="passado"):
        services.schedule(bill, debit_date=dt.date(2026, 11, 19))
    forecast = services.create_bill(
        description="V",
        category=cats.aluguel,
        account=conta,
        amount=Money(1),
        due_date=DUE,
        value_type="variable",
    )
    with pytest.raises(InvalidStateError, match="pendentes"):
        services.schedule(forecast, debit_date=DUE)


def test_status_atrasado(conta, cats):
    c = services.create_bill(
        description="Velha",
        category=cats.aluguel,
        account=conta,
        amount=Money(100),
        due_date=dt.date(2026, 11, 10),
    )
    assert services.status(c) == services.OVERDUE
    services.pay(c, amount=Money(40))
    assert services.status(fresh(c)) == services.OVERDUE  # parcial, mas ainda atrasada
    assert services.status(fresh(c), dt.date(2026, 11, 5)) == services.PARTIAL


def test_vencimento_efetivo_decide_o_atraso(conta, cats):
    sabado = dt.date(2026, 11, 14)
    c = services.create_bill(
        description="S", category=cats.aluguel, account=conta, amount=Money(1), due_date=sabado
    )
    assert services.status(c, dt.date(2026, 11, 16)) == services.PENDING
    assert services.status(c, dt.date(2026, 11, 17)) == services.OVERDUE


def test_RN_172_versao_desatualizada(bill):
    services.schedule(bill, debit_date=DUE)
    with pytest.raises(ConcurrentEditError):
        services.cancel(bill, reason="x", expected_version=1)
    with pytest.raises(ConcurrentEditError):
        services.pay(bill, amount=Money(1), expected_version=1)


def test_RN_052_valor_real_de_conta_variavel(conta, cats):
    c = services.create_bill(
        description="Água",
        category=cats.aluguel,
        account=conta,
        amount=Money(100),
        due_date=DUE,
        value_type="variable",
    )
    novo = services.set_actual_amount(c, amount=Money(130))
    assert novo.pk != c.pk
    assert novo.planned_amount_cents == 130
    assert novo.transaction.status == TransactionStatus.PENDING
    assert fresh(c).transaction.status == TransactionStatus.CANCELLED
    assert fresh(c).transaction.cancel_reason == "valor real informado"
    assert check_all() == []
    with pytest.raises(InvalidStateError, match="previstos"):
        services.set_actual_amount(novo, amount=Money(1))


def test_RN_052_valor_real_igual_so_promove(conta, cats):
    c = services.create_bill(
        description="Água",
        category=cats.aluguel,
        account=conta,
        amount=Money(100),
        due_date=DUE,
        value_type="variable",
    )
    same = services.set_actual_amount(c, amount=Money(100))
    assert same.pk == c.pk
    assert fresh(c).transaction.status == TransactionStatus.PENDING


def test_trocar_valor_de_conta_paga_e_recusado(bill):
    services.pay(bill, amount=Money(1))
    with pytest.raises(InvalidStateError, match="não pode mudar"):
        services.replace(bill, amount=Money(2), reason="x")
    services.close(bill, reason="fim")
    with pytest.raises(InvalidStateError, match="não pode mais"):
        services.replace(bill, amount=Money(2), reason="x")


# Estorno e Corrigir ------------------------------------------------------------------


def test_RN_044_estornar_liquidacao_reabre(conta, bill):
    settlement = services.pay(bill, amount=Money(4000))
    ledger.reverse(settlement.transaction, reason="errado")
    assert services.open_amount(fresh(bill)) == Money(10000)
    assert balance(conta) == Money(1_000_000)
    assert services.status(fresh(bill)) == services.PENDING
    assert check_all() == []


def test_parcial_juros_e_estorno_reabre_certo(conta, cats, bill):
    """Combinação obrigatória (testing-plan.md §6): juros não entram na categoria original."""
    fees = categories.by_key("late_fees").ledger_account
    services.pay(bill, amount=Money(3000))
    second = services.pay(bill, amount=Money(2000), late_fee=Money(150))
    assert ledger.account_balance(cats.aluguel.ledger_account) == Money(5000)
    assert ledger.account_balance(fees) == Money(150)
    ledger.reverse(second.transaction, reason="errado")
    assert services.open_amount(fresh(bill)) == Money(7000)
    assert ledger.account_balance(fees) == Money(0)
    assert ledger.account_balance(cats.aluguel.ledger_account) == Money(3000)
    assert balance(conta) == Money(997_000)
    assert check_all() == []


def test_estornar_depois_de_encerrar_reabre(bill):
    settlement = services.pay(bill, amount=Money(8000), close_reason="veio menor")
    assert fresh(bill).closed_at is not None
    ledger.reverse(settlement.transaction, reason="errado")
    current = fresh(bill)
    assert current.closed_at is None and current.closed_reason is None
    assert services.open_amount(current) == Money(10000)


def test_depois_do_estorno_pode_cancelar(bill):
    settlement = services.pay(bill, amount=Money(1))
    ledger.reverse(settlement.transaction, reason="errado")
    services.cancel(fresh(bill), reason="não vou pagar")
    assert services.status(fresh(bill)) == services.CANCELLED


def test_corrigir_pagamento_e_bloqueado(conta, cats, bill):
    """Corrigir criaria transação sem liquidação e reabriria a conta em silêncio."""
    settlement = services.pay(bill, amount=Money(10000))
    with pytest.raises(InvalidStateError, match="pagamento de uma conta"):
        entries.correct(
            settlement.transaction,
            EntryInput(
                kind=EXPENSE, amount=Money(9000), account=conta, on=TODAY, category=cats.aluguel
            ),
            reason="errei",
        )
    assert services.open_amount(fresh(bill)) == Money(0)
    assert not entries.describe(settlement.transaction).editable


# Consórcio ------------------------------------------------------------------------------


def test_pagar_consorcio_previsto_nao_duplica(conta):
    from apps.payables import recurrence

    debt = debts.create_consortium(
        description="Carro", installment=Money(50000), due_day=25, remaining_installments=2
    )
    recurrence.create_consortium(
        debt=debt,
        account=conta,
        amount=Money(50000),
        start_date=dt.date(2026, 11, 1),
        remaining_count=2,
    )
    planned = services.oldest_open_consortium(debt)
    assert planned.transaction.status == TransactionStatus.PENDING
    services.pay(planned, amount=Money(50000))
    assert balance(conta) == Money(950_000)
    assert len(debts.history(debt)) == 1  # só o pago; o previsto não aparece no histórico
    assert services.oldest_open_consortium(debt).due_date == dt.date(2026, 12, 25)
    assert check_all() == []


def test_tela_de_consorcio_liquida_a_parcela_prevista(web, conta):
    from apps.payables import recurrence

    debt = debts.create_consortium(
        description="Carro", installment=Money(50000), due_day=25, remaining_installments=1
    )
    recurrence.create_consortium(
        debt=debt,
        account=conta,
        amount=Money(50000),
        start_date=dt.date(2026, 11, 1),
        remaining_count=1,
    )
    url = f"/dividas/{debt.pk}/pagar/"
    response = web.post(
        url,
        {"account": conta.pk, "amount": "500,00", "on": "20/11/2026", "idempotency_key": "tela"},
    )
    assert response.status_code == 302
    assert services.oldest_open_consortium(debt) is None
    assert len(debts.history(debt)) == 1


# Arquivamento e invariantes ---------------------------------------------------------------


def test_RN_185_conta_paga_nao_trava_arquivamento(fin, cats):
    c = services.create_bill(
        description="X", category=cats.aluguel, account=fin.digital, amount=Money(1), due_date=DUE
    )
    with pytest.raises(InvalidStateError, match="previstos ou pendentes"):
        accounts.archive(fin.digital)
    services.pay(c, amount=Money(1))
    accounts.archive(fin.digital)


def test_I10_categoria_com_previsto_nao_arquiva(conta, cats, bill):
    with pytest.raises(InvalidStateError, match="previstas ou pendentes"):
        categories.archive(cats.aluguel)
    services.cancel(bill, reason="x")
    categories.archive(cats.aluguel)


def test_conciliacao_ignora_pendente_com_data_passada(conta, cats):
    """Conta atrasada lançada agora não invalida a conciliação (RN-012)."""
    from apps.accounts.reconciliation import reconcile

    day = dt.date(2026, 11, 15)
    rec = reconcile(account=conta, on=day, informed=Money(1_000_000))
    services.create_bill(
        description="Atrasada",
        category=cats.aluguel,
        account=conta,
        amount=Money(100),
        due_date=dt.date(2026, 11, 10),
    )
    rec.refresh_from_db()
    assert rec.status == "reconciled"


def test_I05_detecta_liquidacao_acima_do_planejado(conta, cats, bill):
    txn = entries.record(
        EntryInput(
            kind=EXPENSE, amount=Money(20000), account=conta, on=TODAY, category=cats.aluguel
        )
    )
    Settlement.objects.create(commitment=bill, transaction=txn, amount_cents=20000)
    assert any(v.code == "I-05" and "acima" in v.detail for v in check_all())


def test_I05_detecta_diferenca_com_as_pernas(bill):
    Commitment.objects.filter(pk=bill.pk).update(planned_amount_cents=999)
    assert any(v.code == "I-05" and "pernas" in v.detail for v in check_all())


def test_I10_detecta_conta_arquivada(conta, bill):
    from apps.ledger.models import LedgerAccount

    LedgerAccount.objects.filter(pk=conta.ledger_account_id).update(
        archived_at=dt.datetime(2026, 11, 20, tzinfo=dt.UTC)
    )
    assert any(v.code == "I-10" for v in check_all())


# Gatilhos ---------------------------------------------------------------------------------


def _sql(statement, params=()):
    with transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(statement, params)


def test_gatilho_liquidacao_exige_confirmada(bill):
    with pytest.raises(IntegrityError, match="confirmada"):
        Settlement.objects.create(commitment=bill, transaction=bill.transaction, amount_cents=1)


def test_gatilhos_imutabilidade(bill):
    settlement = services.pay(bill, amount=Money(1))
    with pytest.raises(IntegrityError, match="imutáveis"):
        _sql("UPDATE settlement SET amount_cents = 2 WHERE id = %s", [settlement.pk])
    with pytest.raises(IntegrityError, match="excluídas"):
        _sql("DELETE FROM settlement WHERE id = %s", [settlement.pk])
    with pytest.raises(IntegrityError, match="excluídos"):
        _sql("DELETE FROM commitment WHERE id = %s", [bill.pk])


def test_gatilho_impede_previsto_virar_confirmado(bill):
    with pytest.raises(IntegrityError, match="inválida"):
        _sql(
            "UPDATE ledger_transaction SET status = 'confirmed' WHERE id = %s",
            [bill.transaction_id],
        )
    assert LedgerTransaction.objects.get(pk=bill.transaction_id).status == "pending"


# Ledger: promover e remarcar ---------------------------------------------------------------


def test_promover_so_previsto(bill):
    with pytest.raises(InvalidStateError, match="previstos"):
        ledger.promote(bill.transaction)


def test_remarcar_so_nao_confirmado(conta, cats, bill):
    moved = ledger.reschedule(bill.transaction, operation_date=dt.date(2026, 11, 26))
    assert moved.operation_date == moved.competence_date == dt.date(2026, 11, 26)
    settlement = services.pay(bill, amount=Money(1))
    with pytest.raises(InvalidStateError, match="mudam de data"):
        ledger.reschedule(settlement.transaction, operation_date=TODAY)
