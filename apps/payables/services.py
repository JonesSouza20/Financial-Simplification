"""Contas a pagar e receitas previstas (business-rules.md §3.3, §3.4, §5, §6; ADR-032).

Compromisso nunca vira confirmado: todo pagamento é uma transação confirmada nova, ligada a
ele por uma liquidação. Valor em aberto é sempre calculado.
"""

from __future__ import annotations

import datetime
import re
import uuid

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.accounts.models import FinancialAccount
from apps.calendar_br import services as calendar
from apps.categories.models import Category, CategoryKind
from apps.categories.services import by_key
from apps.debts.models import Debt, DebtKind
from apps.debts.services import consortium_legs
from apps.entries import services as entries
from apps.entries.services import EXPENSE, INCOME, EntryInput
from apps.ledger import audit
from apps.ledger import services as ledger
from apps.ledger.errors import (
    ConcurrentEditError,
    InvalidStateError,
    InvalidTransactionError,
)
from apps.ledger.models import LedgerTransaction, TransactionStatus, TransactionType
from apps.ledger.services import Leg
from apps.money import Money, split_installments

from .models import (
    Commitment,
    CommitmentKind,
    Direction,
    ExcessKind,
    Settlement,
    ValueType,
)

PLANNED = (TransactionStatus.FORECAST, TransactionStatus.PENDING)
DIRECTIONS = {
    CommitmentKind.BILL: Direction.OUT,
    CommitmentKind.CONSORTIUM: Direction.OUT,
    CommitmentKind.INCOME: Direction.IN,
}
MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")

# Status exibidos (business-rules.md §3.4). Atrasado e pago parcialmente nunca são gravados.
FORECAST, PENDING, SCHEDULED, OVERDUE, PARTIAL, PAID, CANCELLED = (
    "forecast",
    "pending",
    "scheduled",
    "overdue",
    "partial",
    "paid",
    "cancelled",
)


# Leitura -----------------------------------------------------------------------------


def _live_settlements(commitment: Commitment):
    return commitment.settlements.filter(transaction__status=TransactionStatus.CONFIRMED)


def settled_cents(commitment: Commitment) -> int:
    return sum(s.amount_cents for s in _live_settlements(commitment))


def open_amount(commitment: Commitment) -> Money:
    """Valor em aberto (RN-041). Cancelado ou encerrado não tem nada em aberto (RN-042)."""
    if commitment.transaction.status not in PLANNED or commitment.closed_at:
        return Money(0)
    return Money(commitment.planned_amount_cents - settled_cents(commitment))


def status(commitment: Commitment, today: datetime.date | None = None) -> str:
    """Status exibido. Atrasado vem antes de pago parcialmente, por ser o que exige ação."""
    today = today or ledger.today()
    if commitment.transaction.status == TransactionStatus.CANCELLED:
        return CANCELLED
    if not open_amount(commitment).is_positive:
        return PAID
    if commitment.transaction.status == TransactionStatus.FORECAST:
        return PARTIAL if settled_cents(commitment) else FORECAST
    if commitment.effective_due_date < today:
        return OVERDUE
    if settled_cents(commitment):
        return PARTIAL
    return SCHEDULED if commitment.scheduled_debit_date else PENDING


def is_open(commitment: Commitment) -> bool:
    return open_amount(commitment).is_positive


def open_on_account(ledger_account) -> bool:
    """Há previsto ou pendente em aberto nesta conta contábil? (RN-185; I-10)."""
    planned = LedgerTransaction.objects.filter(
        postings__account=ledger_account, status__in=PLANNED
    ).select_related("commitment")
    for txn in planned:
        commitment = Commitment.objects.filter(transaction=txn).first()
        if commitment is None or is_open(commitment):
            return True
    return False


def late_incomes(today: datetime.date | None = None) -> list[Commitment]:
    """Receitas previstas cuja data passou sem recebimento (RN-023)."""
    today = today or ledger.today()
    candidates = Commitment.objects.filter(
        direction=Direction.IN,
        transaction__status__in=PLANNED,
        closed_at__isnull=True,
        due_date__lt=today,
    ).select_related("transaction")
    return [c for c in candidates if is_open(c)]


def category_of(commitment: Commitment) -> Category:
    """A categoria está nas pernas pretendidas; não é copiada para o compromisso."""
    for posting in commitment.transaction.postings.select_related("account"):
        if posting.account.owner_type == "category":
            return Category.objects.get(ledger_account=posting.account)
    raise InvalidStateError("Compromisso sem categoria nas pernas pretendidas.")


# Criação -----------------------------------------------------------------------------


def _reference_date(reference_month: str | None, due_date: datetime.date) -> datetime.date:
    if reference_month is None:
        return due_date
    if not MONTH_RE.match(reference_month):
        raise InvalidTransactionError("Competência inválida. Use AAAA-MM.")
    year, month = reference_month.split("-")
    return datetime.date(int(year), int(month), 1)


def build_legs(
    kind: str,
    *,
    category: Category | None,
    account: FinancialAccount | None,
    amount: Money,
    on: datetime.date,
    debt: Debt | None = None,
    description: str = "",
) -> tuple[str, list[Leg], str]:
    """Tipo, pernas e descrição: os mesmos para o planejado e para a liquidação."""
    if account is None:
        raise InvalidTransactionError("Escolha a conta prevista.")
    if kind == CommitmentKind.CONSORTIUM:
        if debt is None or debt.kind != DebtKind.CONSORTIUM:
            raise InvalidTransactionError("Escolha o consórcio desta parcela.")
        return (
            TransactionType.CONSORTIUM_INSTALLMENT,
            consortium_legs(debt, account, amount),
            description or f"Parcela: {debt.description}",
        )
    if kind not in (CommitmentKind.BILL, CommitmentKind.INCOME):
        raise InvalidTransactionError("Este tipo de compromisso ainda não está disponível.")
    entry_kind = INCOME if kind == CommitmentKind.INCOME else EXPENSE
    entry = EntryInput(
        kind=entry_kind,
        amount=amount,
        account=account,
        on=on,
        category=category,
        description=description,
    )
    return entries.build(entry)


def _create(
    *,
    kind: str,
    description: str,
    category: Category | None,
    account: FinancialAccount | None,
    amount: Money,
    due_date: datetime.date,
    txn_status: str,
    value_type: str = ValueType.FIXED,
    reference_month: str | None = None,
    payment_method: str | None = None,
    anticipates: bool = False,
    recurrence=None,
    debt: Debt | None = None,
    installment_group: str | None = None,
    installment_number: int | None = None,
    idempotency_key: str | None = None,
) -> Commitment:
    if not amount.is_positive:
        raise InvalidTransactionError("Informe um valor maior que zero.")
    if value_type not in ValueType.values:
        raise InvalidTransactionError("Tipo de valor inválido.")
    txn_type, legs, label = build_legs(
        kind,
        category=category,
        account=account,
        amount=amount,
        on=due_date,
        debt=debt,
        description=description,
    )
    with transaction.atomic():
        txn = ledger.record(
            type=txn_type,
            legs=legs,
            operation_date=due_date,
            competence_date=_reference_date(reference_month, due_date),
            description=label,
            status=txn_status,
            idempotency_key=idempotency_key,
        )
        existing = Commitment.objects.filter(transaction=txn).first()
        if existing is not None:
            return existing
        return Commitment.objects.create(
            transaction=txn,
            kind=kind,
            direction=DIRECTIONS[kind],
            due_date=due_date,
            effective_due_date=calendar.effective_due(due_date, anticipate=anticipates),
            planned_amount_cents=amount.cents,
            value_type=value_type,
            reference_month=reference_month,
            expected_account=account,
            payment_method=payment_method,
            anticipates=anticipates,
            recurrence=recurrence,
            debt=debt,
            installment_group=installment_group,
            installment_number=installment_number,
        )


def create_bill(
    *,
    description: str,
    category: Category,
    account: FinancialAccount,
    amount: Money,
    due_date: datetime.date,
    value_type: str = ValueType.FIXED,
    reference_month: str | None = None,
    payment_method: str | None = None,
    anticipates: bool = False,
    idempotency_key: str | None = None,
) -> Commitment:
    """Conta a pagar (RN-031). Valor conhecido nasce pendente; estimado nasce previsto."""
    return _create(
        kind=CommitmentKind.BILL,
        description=description,
        category=category,
        account=account,
        amount=amount,
        due_date=due_date,
        txn_status=(
            TransactionStatus.PENDING
            if value_type == ValueType.FIXED
            else TransactionStatus.FORECAST
        ),
        value_type=value_type,
        reference_month=reference_month,
        payment_method=payment_method,
        anticipates=anticipates,
        idempotency_key=idempotency_key,
    )


def create_installments(
    *,
    description: str,
    category: Category,
    account: FinancialAccount,
    total: Money,
    count: int,
    first_due: datetime.date,
    payment_method: str | None = None,
    anticipates: bool = False,
    idempotency_key: str | None = None,
) -> list[Commitment]:
    """Parcelamento fora do cartão: N compromissos do mesmo grupo (RN-037; rateio RN-005)."""
    if not total.is_positive or count < 1:
        raise InvalidTransactionError("Informe o total e o número de parcelas.")
    parts = split_installments(total, count)
    group = str(uuid.uuid4())
    created = []
    with transaction.atomic():
        for number, part in enumerate(parts, start=1):
            created.append(
                _create(
                    kind=CommitmentKind.BILL,
                    description=f"{description.strip()} ({number}/{count})",
                    category=category,
                    account=account,
                    amount=part,
                    due_date=calendar.add_months(first_due, number - 1),
                    txn_status=TransactionStatus.PENDING,
                    payment_method=payment_method,
                    anticipates=anticipates,
                    installment_group=group,
                    installment_number=number,
                    idempotency_key=f"{idempotency_key}:{number}" if idempotency_key else None,
                )
            )
    return created


def create_income(
    *,
    description: str,
    category: Category,
    account: FinancialAccount,
    amount: Money,
    due_date: datetime.date,
    value_type: str = ValueType.FIXED,
    idempotency_key: str | None = None,
) -> Commitment:
    """Receita prevista (RN-020): não entra em saldo real, disponível nem comprometido."""
    if category.kind != CategoryKind.INCOME:
        raise InvalidTransactionError("Escolha uma categoria de receita.")
    return _create(
        kind=CommitmentKind.INCOME,
        description=description,
        category=category,
        account=account,
        amount=amount,
        due_date=due_date,
        txn_status=TransactionStatus.FORECAST,
        value_type=value_type,
        idempotency_key=idempotency_key,
    )


# Operações -----------------------------------------------------------------------------


def _locked(commitment: Commitment, expected_version: int | None) -> Commitment:
    current = Commitment.objects.select_related("transaction").get(pk=commitment.pk)
    if expected_version is not None and current.version != expected_version:
        raise ConcurrentEditError(
            "Este item foi alterado em outro aparelho. Os dados foram recarregados."
        )
    return current


def _update(commitment: Commitment, **fields) -> Commitment:
    updated = Commitment.objects.filter(pk=commitment.pk, version=commitment.version).update(
        version=F("version") + 1, **fields
    )
    if not updated:
        raise ConcurrentEditError(
            "Este item foi alterado em outro aparelho. Os dados foram recarregados."
        )
    commitment.refresh_from_db()
    return commitment


def _settlement_transaction(
    current: Commitment,
    *,
    principal: Money,
    late_fee: Money,
    account: FinancialAccount,
    on: datetime.date,
    idempotency_key: str | None,
) -> LedgerTransaction:
    txn_type, legs, label = build_legs(
        current.kind,
        category=category_of(current),
        account=account,
        amount=principal,
        on=on,
        debt=current.debt,
        description=current.transaction.description,
    )
    if late_fee.is_positive:
        if current.direction != Direction.OUT:
            raise InvalidTransactionError("Juros e multa só existem em contas a pagar.")
        if account.asset_class == "benefit":
            raise InvalidTransactionError("Juros e multa não podem ser pagos com benefício.")
        fee_leg = Leg(by_key("late_fees").ledger_account, late_fee, "juros e multa por atraso")
        account_id = account.ledger_account_id
        legs = [
            Leg(leg.account, leg.amount - late_fee, leg.memo)
            if leg.account.pk == account_id
            else leg
            for leg in legs
        ] + [fee_leg]
    return ledger.record(
        type=txn_type,
        legs=legs,
        operation_date=on,
        competence_date=current.transaction.competence_date,
        description=label,
        idempotency_key=idempotency_key,
    )


def pay(
    commitment: Commitment,
    *,
    amount: Money,
    account: FinancialAccount | None = None,
    on: datetime.date | None = None,
    late_fee: Money | None = None,
    excess_kind: str | None = None,
    close_reason: str | None = None,
    idempotency_key: str | None = None,
    expected_version: int | None = None,
) -> Settlement:
    """Pagar ou receber (RN-033, RN-034, RN-040, RN-042, RN-043).

    Juros e multa entram em perna separada, na mesma transação; a liquidação guarda só a
    parte aplicada ao compromisso. Acima do aberto, exige classificar o excedente.
    """
    on = on or ledger.today()
    fee = late_fee or Money(0)
    with transaction.atomic():
        repeated = ledger.find_idempotent(idempotency_key, "record")
        if repeated is not None:
            return Settlement.objects.get(commitment=commitment, transaction=repeated)
        current = _locked(commitment, expected_version)
        if current.transaction.status not in PLANNED:
            raise InvalidStateError("Este compromisso foi cancelado.")
        if not amount.is_positive:
            raise InvalidTransactionError("Informe o valor pago.")
        if fee.is_negative:
            raise InvalidTransactionError("Juros e multa não podem ser negativos.")
        remaining = open_amount(current)
        if not remaining.is_positive:
            raise InvalidStateError("Este compromisso já está liquidado.")
        excess = amount - remaining if amount.cents > remaining.cents else Money(0)
        if excess.is_positive and excess_kind not in ExcessKind.values:
            raise InvalidTransactionError(
                f"O valor passa do aberto em {excess}. Classifique o excedente "
                "como juros e multa ou como valor real maior."
            )
        settled = amount - excess
        principal = settled
        if excess.is_positive:
            if excess_kind == ExcessKind.LATE_FEE:
                fee = fee + excess
            else:
                principal = amount
        txn = _settlement_transaction(
            current,
            principal=principal,
            late_fee=fee,
            account=account or current.expected_account,
            on=on,
            idempotency_key=idempotency_key,
        )
        settlement = Settlement.objects.create(
            commitment=current,
            transaction=txn,
            amount_cents=settled.cents,
            excess_kind=excess_kind if excess.is_positive else None,
        )
        audit.log(
            "settle",
            current,
            after={
                "transaction": str(txn.uuid),
                "amount_cents": settled.cents,
                "late_fee_cents": fee.cents,
                "excess_kind": settlement.excess_kind,
            },
        )
        if close_reason is not None and is_open(current):
            _close(current, close_reason)
    return settlement


def _close(current: Commitment, reason: str) -> Commitment:
    reason = (reason or "").strip()
    if not reason:
        raise InvalidTransactionError("Informe o motivo do encerramento.")
    before = open_amount(current).cents
    current = _update(current, closed_at=timezone.now(), closed_reason=reason[:200])
    audit.log("close", current, after={"open_cents_dropped": before}, reason=reason)
    return current


def close(
    commitment: Commitment, *, reason: str, expected_version: int | None = None
) -> Commitment:
    """Pago com valor diferente: a diferença é encerrada e não gera perna (RN-042)."""
    with transaction.atomic():
        current = _locked(commitment, expected_version)
        if not settled_cents(current):
            raise InvalidStateError("Sem pagamento registrado. Use cancelar.")
        if not is_open(current):
            raise InvalidStateError("Este compromisso já está liquidado.")
        return _close(current, reason)


def cancel(
    commitment: Commitment, *, reason: str, expected_version: int | None = None
) -> Commitment:
    """Cancela com motivo. Com liquidação, só encerrando (RN-036)."""
    with transaction.atomic():
        current = _locked(commitment, expected_version)
        if settled_cents(current):
            raise InvalidStateError("Conta com pagamento não pode ser cancelada. Use encerrar.")
        ledger.cancel(current.transaction, reason=reason)
        return _update(current, scheduled_debit_date=None)


def schedule(
    commitment: Commitment, *, debit_date: datetime.date, expected_version: int | None = None
) -> Commitment:
    """Agendado: pendente com data de débito. Nunca confirma sozinho (RN-035)."""
    with transaction.atomic():
        current = _locked(commitment, expected_version)
        if current.transaction.status != TransactionStatus.PENDING or not is_open(current):
            raise InvalidStateError("Só contas pendentes em aberto podem ser agendadas.")
        if debit_date < ledger.today():
            raise InvalidTransactionError("A data de débito não pode estar no passado.")
        current = _update(current, scheduled_debit_date=debit_date)
        audit.log("schedule", current, after={"debit_date": debit_date.isoformat()})
        return current


def unschedule(commitment: Commitment, *, expected_version: int | None = None) -> Commitment:
    """O débito agendado não aconteceu: volta a pendente (F-032)."""
    with transaction.atomic():
        current = _locked(commitment, expected_version)
        current = _update(current, scheduled_debit_date=None)
        audit.log("unschedule", current)
        return current


def replace(
    commitment: Commitment,
    *,
    amount: Money,
    reason: str,
    txn_status: str | None = None,
    expected_version: int | None = None,
) -> Commitment:
    """Troca o valor: as pernas são imutáveis, então cancela e cria outro (database-design §15)."""
    with transaction.atomic():
        current = _locked(commitment, expected_version)
        if current.transaction.status not in PLANNED or current.closed_at:
            raise InvalidStateError("Este compromisso não pode mais ser alterado.")
        if settled_cents(current):
            raise InvalidStateError("Conta com pagamento não pode mudar de valor.")
        category = category_of(current)
        ledger.cancel(current.transaction, reason=reason)
        return _create(
            kind=current.kind,
            description=current.transaction.description,
            category=category,
            account=current.expected_account,
            amount=amount,
            due_date=current.due_date,
            txn_status=txn_status or current.transaction.status,
            value_type=current.value_type,
            reference_month=current.reference_month,
            payment_method=current.payment_method,
            anticipates=current.anticipates,
            recurrence=current.recurrence,
            debt=current.debt,
            installment_group=current.installment_group,
            installment_number=current.installment_number,
        )


def set_actual_amount(
    commitment: Commitment, *, amount: Money, expected_version: int | None = None
) -> Commitment:
    """Valor real de uma conta variável: passa a pendente (RN-052)."""
    with transaction.atomic():
        current = _locked(commitment, expected_version)
        if current.transaction.status != TransactionStatus.FORECAST:
            raise InvalidStateError("Só compromissos previstos recebem o valor real.")
        if amount.cents == current.planned_amount_cents:
            ledger.promote(current.transaction)
            current.refresh_from_db()
            return current
        return replace(
            current,
            amount=amount,
            reason="valor real informado",
            txn_status=TransactionStatus.PENDING,
        )


def oldest_open_consortium(debt: Debt) -> Commitment | None:
    """Parcela de consórcio em aberto mais antiga, para o pagamento não virar um segundo T19."""
    candidates = Commitment.objects.filter(
        debt=debt,
        kind=CommitmentKind.CONSORTIUM,
        transaction__status__in=PLANNED,
        closed_at__isnull=True,
    ).select_related("transaction")
    return next((c for c in candidates if is_open(c)), None)


def refresh_due_dates() -> int:
    """Feriados mudaram: recalcula vencimentos dos compromissos em aberto (database-design §4.5)."""
    from .models import DayRule

    changed = 0
    candidates = Commitment.objects.filter(
        transaction__status__in=PLANNED, closed_at__isnull=True
    ).select_related("transaction", "recurrence")
    with transaction.atomic():
        for commitment in candidates:
            if not is_open(commitment):
                continue
            due = commitment.due_date
            rule = commitment.recurrence
            if rule is not None and rule.day_rule == DayRule.NTH_BUSINESS_DAY:
                due = calendar.nth_business_day(due.year, due.month, rule.day_value)
            effective = calendar.effective_due(due, anticipate=commitment.anticipates)
            if due == commitment.due_date and effective == commitment.effective_due_date:
                continue
            if due != commitment.due_date:
                ledger.reschedule(commitment.transaction, operation_date=due)
            _update(commitment, due_date=due, effective_due_date=effective)
            changed += 1
    return changed
