"""Interface de escrita do Ledger (architecture.md §5, §6; business-rules.md §3, §12, §18).

Toda gravação de pernas passa por aqui. Cada operação é atômica, e transações nascem em
rascunho: o gatilho do banco confere o equilíbrio na finalização (database-design.md §11).
"""

from __future__ import annotations

import datetime
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

from django.conf import settings
from django.db import transaction
from django.db.models import F, Sum
from django.utils import timezone

from apps.money import Money, scale_legs

from . import audit
from .errors import (
    AlreadyReversedError,
    ConcurrentEditError,
    IdempotencyConflictError,
    InvalidStateError,
    InvalidTransactionError,
    ReversalLimitError,
)
from .models import (
    CARD_PURCHASE_TYPES,
    EFFECTIVE_STATUSES,
    OPENING_TYPES,
    IdempotencyRecord,
    LedgerAccount,
    LedgerPosting,
    LedgerTransaction,
    LinkKind,
    TransactionLink,
    TransactionNote,
    TransactionOrigin,
    TransactionStatus,
    TransactionType,
)
from .signals import transaction_created, transaction_reversed

MAX_TRANSACTION_CENTS = 999_999_999  # R$ 9.999.999,99 (RN-180)
RECORDABLE_STATUSES = frozenset(
    {TransactionStatus.FORECAST, TransactionStatus.PENDING, TransactionStatus.CONFIRMED}
)
REVERSAL_LINK_KINDS = (LinkKind.REVERSES, LinkKind.PARTIALLY_REVERSES)


@dataclass(frozen=True)
class Leg:
    """Uma perna pretendida: valor em uma conta contábil (débito +, crédito −)."""

    account: LedgerAccount
    amount: Money
    memo: str = ""


def _fault_point(name: str) -> None:
    """Ponto de injeção de falha usado só pelos testes de atomicidade (testing-plan.md §7.2)."""


# Leitura -----------------------------------------------------------------------------


def account_balance(account: LedgerAccount, as_of: datetime.date | None = None) -> Money:
    """Soma das pernas efetivas da conta (débito +). RN-003, RN-011."""
    qs = LedgerPosting.objects.filter(account=account, transaction__status__in=EFFECTIVE_STATUSES)
    if as_of is not None:
        qs = qs.filter(transaction__operation_date__lte=as_of)
    return Money(qs.aggregate(total=Sum("amount_cents"))["total"] or 0)


def display_balance(account: LedgerAccount, as_of: datetime.date | None = None) -> Money:
    """Saldo como o usuário lê: passivo, receita e patrimônio com sinal invertido (RN-003)."""
    raw = account_balance(account, as_of)
    return raw if account.kind in ("asset", "expense") else -raw


SYSTEM_ACCOUNTS = {
    "equity:opening": "Patrimônio: Abertura",
    "equity:adjustments": "Patrimônio: Ajustes de conciliação",
}


def system_account(code: str) -> LedgerAccount:
    """Conta de patrimônio do sistema (business-rules.md §2). Recria se faltar."""
    account, _ = LedgerAccount.objects.get_or_create(
        code=code, defaults={"kind": "equity", "name": SYSTEM_ACCOUNTS[code], "is_system": True}
    )
    return account


def today() -> datetime.date:
    return timezone.localdate()


# Escrita -----------------------------------------------------------------------------


def record(
    *,
    type: str,
    legs: Sequence[Leg],
    operation_date: datetime.date,
    description: str,
    status: str = TransactionStatus.CONFIRMED,
    competence_date: datetime.date | None = None,
    origin: str = TransactionOrigin.MANUAL,
    idempotency_key: str | None = None,
    external_id: str | None = None,
    dedup_hash: str | None = None,
) -> LedgerTransaction:
    """Registra uma transação prevista, pendente ou confirmada."""
    with transaction.atomic():
        existing = _idempotent_result(idempotency_key, "record")
        if existing is not None:
            return existing
        txn = _create(
            type=type,
            legs=legs,
            status=status,
            operation_date=operation_date,
            competence_date=competence_date or operation_date,
            description=description,
            origin=origin,
            external_id=external_id,
            dedup_hash=dedup_hash,
        )
        _remember(idempotency_key, "record", txn)
        audit.log("create", txn, after=audit.snapshot_transaction(txn))
    return txn


def cancel(txn: LedgerTransaction, *, reason: str, expected_version: int | None = None):
    """Cancela previsto ou pendente (RN-125, ADR-003). Nunca gera pernas."""
    reason = (reason or "").strip()
    if not reason:
        raise InvalidTransactionError("Informe o motivo do cancelamento.")
    with transaction.atomic():
        current = LedgerTransaction.objects.get(pk=txn.pk)
        _check_version(current, expected_version)
        if current.status not in (TransactionStatus.FORECAST, TransactionStatus.PENDING):
            raise InvalidStateError(
                "Só lançamentos previstos ou pendentes podem ser cancelados. "
                "Para desfazer um lançamento confirmado, use Estornar ou Corrigir."
            )
        before = audit.snapshot_transaction(current)
        updated = LedgerTransaction.objects.filter(pk=current.pk, version=current.version).update(
            status=TransactionStatus.CANCELLED,
            cancel_reason=reason,
            version=F("version") + 1,
            updated_at=timezone.now(),
        )
        if not updated:
            raise ConcurrentEditError(
                "Este item foi alterado em outro aparelho. Os dados foram recarregados."
            )
        current.refresh_from_db()
        audit.log(
            "cancel",
            current,
            before=before,
            after=audit.snapshot_transaction(current),
            reason=reason,
        )
    return current


def reverse(
    txn: LedgerTransaction,
    *,
    reason: str,
    mode: str = "technical",
    operation_date: datetime.date | None = None,
    idempotency_key: str | None = None,
) -> LedgerTransaction:
    """Estorno total (RN-120).

    - técnico: corrige lançamento errado; vale na competência original (RN-082);
    - comercial: devolução do lojista; só compras no cartão; vale na data do estorno (RN-083).

    Se já houver estornos parciais, estorna só o restante (RN-121).
    """
    with transaction.atomic():
        existing = _idempotent_result(idempotency_key, "reverse")
        if existing is not None:
            return existing
        reversal = _reverse(txn, reason=reason, mode=mode, operation_date=operation_date)
        _remember(idempotency_key, "reverse", reversal)
    return reversal


def reverse_partially(
    txn: LedgerTransaction,
    *,
    amount: Money,
    reason: str,
    operation_date: datetime.date | None = None,
    idempotency_key: str | None = None,
) -> LedgerTransaction:
    """Estorno comercial parcial de compra no cartão, proporcional às pernas (RN-085, RN-121)."""
    with transaction.atomic():
        existing = _idempotent_result(idempotency_key, "reverse_partially")
        if existing is not None:
            return existing
        original = _fresh_reversible(txn, reason)
        if original.type not in CARD_PURCHASE_TYPES:
            raise InvalidStateError("Estorno parcial existe só para compras no cartão.")
        if not amount.is_positive:
            raise InvalidTransactionError("O valor do estorno deve ser maior que zero.")
        total = _gross(original)
        already = _partial_reversed_cents(original)
        if already + amount.cents > total:
            remaining = Money(total - already)
            raise ReversalLimitError(
                f"O estorno ultrapassa o valor da compra. Ainda é possível estornar {remaining}."
            )
        if already + amount.cents == total:
            reversal = _reverse(
                original, reason=reason, mode="commercial", operation_date=operation_date
            )
        else:
            amounts = [p.amount_cents for p in original.postings.order_by("id")]
            accounts = [
                p.account for p in original.postings.select_related("account").order_by("id")
            ]
            scaled = scale_legs(amounts, amount.cents, total)
            legs = [
                Leg(account=acc, amount=Money(-cents), memo="estorno parcial")
                for acc, cents in zip(accounts, scaled, strict=True)
                if cents
            ]
            if len(legs) < 2:
                raise InvalidTransactionError("Valor de estorno pequeno demais para dividir.")
            op_date = operation_date or today()
            reversal = _create(
                type=TransactionType.CARD_COMMERCIAL_REVERSAL,
                legs=legs,
                status=TransactionStatus.CONFIRMED,
                operation_date=op_date,
                competence_date=op_date,
                description=f"Estorno parcial: {original.description}",
            )
            TransactionLink.objects.create(
                kind=LinkKind.PARTIALLY_REVERSES,
                from_transaction=reversal,
                to_transaction=original,
                amount_cents=amount.cents,
            )
            transaction_reversed.send(
                sender=LedgerTransaction, original=original, reversal=reversal
            )
            audit.log(
                "reverse_partially",
                original,
                after=audit.snapshot_transaction(reversal),
                reason=reason,
            )
        _remember(idempotency_key, "reverse_partially", reversal)
    return reversal


def correct(
    txn: LedgerTransaction,
    *,
    legs: Sequence[Leg],
    reason: str,
    description: str | None = None,
    operation_date: datetime.date | None = None,
    competence_date: datetime.date | None = None,
    type: str | None = None,
    idempotency_key: str | None = None,
) -> LedgerTransaction:
    """Corrigir = estorno técnico + nova transação, numa única operação atômica (RN-122)."""
    with transaction.atomic():
        existing = _idempotent_result(idempotency_key, "correct")
        if existing is not None:
            return existing
        original = LedgerTransaction.objects.get(pk=txn.pk)
        _reverse(original, reason=reason, mode="technical")
        _fault_point("correct_between")
        new_date = operation_date or original.operation_date
        new = _create(
            type=type or original.type,
            legs=legs,
            status=TransactionStatus.CONFIRMED,
            operation_date=new_date,
            competence_date=competence_date
            or (original.competence_date if operation_date is None else new_date),
            description=description or original.description,
        )
        TransactionLink.objects.create(
            kind=LinkKind.CORRECTS, from_transaction=new, to_transaction=original
        )
        audit.log("correct", original, after=audit.snapshot_transaction(new), reason=reason)
        _remember(idempotency_key, "correct", new)
    return new


def add_note(txn: LedgerTransaction, text: str) -> TransactionNote:
    """Acrescenta nota sem alterar a transação (RN-013)."""
    text = (text or "").strip()
    if not text:
        raise InvalidTransactionError("A nota não pode ficar vazia.")
    with transaction.atomic():
        note = TransactionNote.objects.create(transaction=txn, text=text)
        audit.log("add_note", txn, after={"note": text})
    return note


# Internos ----------------------------------------------------------------------------


def _create(
    *,
    type: str,
    legs: Sequence[Leg],
    status: str,
    operation_date: datetime.date,
    competence_date: datetime.date,
    description: str,
    origin: str = TransactionOrigin.MANUAL,
    external_id: str | None = None,
    dedup_hash: str | None = None,
) -> LedgerTransaction:
    description = (description or "").strip()
    _validate(type, legs, status, operation_date, competence_date, description)
    txn = LedgerTransaction.objects.create(
        type=type,
        status=TransactionStatus.DRAFT,
        operation_date=operation_date,
        competence_date=competence_date,
        description=description,
        origin=origin,
        external_id=external_id,
        dedup_hash=dedup_hash,
    )
    for index, leg in enumerate(legs):
        LedgerPosting.objects.create(
            transaction=txn, account=leg.account, amount_cents=leg.amount.cents, memo=leg.memo
        )
        if index == 0:
            _fault_point("after_first_posting")
    _fault_point("before_finalize")
    LedgerTransaction.objects.filter(pk=txn.pk).update(status=status, updated_at=timezone.now())
    txn.refresh_from_db()
    transaction_created.send(sender=LedgerTransaction, transaction=txn)
    return txn


def _validate(type, legs, status, operation_date, competence_date, description) -> None:
    if type not in TransactionType.values:
        raise InvalidTransactionError(f"Tipo de transação desconhecido: {type}.")
    if status not in RECORDABLE_STATUSES:
        raise InvalidTransactionError("Estado inicial deve ser previsto, pendente ou confirmado.")
    if not description:
        raise InvalidTransactionError("Informe uma descrição.")
    if not isinstance(operation_date, datetime.date) or not isinstance(
        competence_date, datetime.date
    ):
        raise InvalidTransactionError("Datas inválidas.")
    if len(legs) < 2:
        raise InvalidTransactionError("Uma transação precisa de pelo menos duas pernas.")
    seen = set()
    for leg in legs:
        if not isinstance(leg.amount, Money):
            raise InvalidTransactionError("Valores precisam ser do tipo Money.")
        if leg.amount.is_zero:
            raise InvalidTransactionError("Nenhuma perna pode ter valor zero.")
        if leg.account.pk is None:
            raise InvalidTransactionError("Conta contábil não gravada.")
        if leg.account.archived_at is not None:
            raise InvalidTransactionError(
                f"A conta {leg.account.name} está arquivada e não aceita lançamentos."
            )
        if leg.account.pk in seen:
            raise InvalidTransactionError("A mesma conta aparece duas vezes na transação.")
        seen.add(leg.account.pk)
    if sum(leg.amount.cents for leg in legs) != 0:
        raise InvalidTransactionError("As pernas da transação não somam zero.")
    if sum(leg.amount.cents for leg in legs if leg.amount.is_positive) > MAX_TRANSACTION_CENTS:
        raise InvalidTransactionError("Valor acima do máximo de R$ 9.999.999,99 por lançamento.")
    if status == TransactionStatus.CONFIRMED and operation_date > today():
        raise InvalidTransactionError("Lançamento confirmado não pode ter data futura.")
    if operation_date < settings.FINANCAS_START_DATE and type not in OPENING_TYPES:
        raise InvalidTransactionError(
            "Datas anteriores a 01/11/2026 só são aceitas em itens de abertura."
        )


def _fresh_reversible(txn: LedgerTransaction, reason: str) -> LedgerTransaction:
    if not (reason or "").strip():
        raise InvalidTransactionError("Informe o motivo do estorno.")
    current = LedgerTransaction.objects.get(pk=txn.pk)
    if current.status == TransactionStatus.REVERSED:
        reversal = current.links_in.filter(kind=LinkKind.REVERSES).first()
        when = reversal.from_transaction.operation_date.strftime("%d/%m/%Y") if reversal else ""
        raise AlreadyReversedError(f"Esta transação já foi estornada em {when}.".strip())
    if current.status != TransactionStatus.CONFIRMED:
        raise InvalidStateError(
            "Só lançamentos confirmados podem ser estornados. Previstos e pendentes são cancelados."
        )
    if current.links_out.filter(kind__in=REVERSAL_LINK_KINDS).exists():
        raise InvalidStateError(
            "Um estorno não pode ser estornado. Lance a operação original novamente."
        )
    return current


def _reverse(txn, *, reason: str, mode: str, operation_date=None) -> LedgerTransaction:
    original = _fresh_reversible(txn, reason)
    if mode not in ("technical", "commercial"):
        raise InvalidTransactionError("Tipo de estorno inválido.")
    if mode == "commercial" and original.type not in CARD_PURCHASE_TYPES:
        raise InvalidStateError(
            "Estorno comercial existe só para compras no cartão. Use o estorno técnico."
        )
    remainder = _remaining_by_account(original)
    legs = [
        Leg(account=account, amount=Money(-cents), memo="estorno")
        for account, cents in remainder
        if cents
    ]
    if len(legs) < 2:
        raise ReversalLimitError("A compra já foi totalmente estornada por estornos parciais.")
    op_date = operation_date or today()
    if mode == "technical":
        txn_type = TransactionType.TECHNICAL_REVERSAL
        competence = original.competence_date
        label = "Estorno"
    else:
        txn_type = TransactionType.CARD_COMMERCIAL_REVERSAL
        competence = op_date
        label = "Estorno comercial"
    before = audit.snapshot_transaction(original)
    reversal = _create(
        type=txn_type,
        legs=legs,
        status=TransactionStatus.CONFIRMED,
        operation_date=op_date,
        competence_date=competence,
        description=f"{label}: {original.description}",
    )
    TransactionLink.objects.create(
        kind=LinkKind.REVERSES, from_transaction=reversal, to_transaction=original
    )
    LedgerTransaction.objects.filter(pk=original.pk).update(
        status=TransactionStatus.REVERSED, version=F("version") + 1, updated_at=timezone.now()
    )
    original.refresh_from_db()
    transaction_reversed.send(sender=LedgerTransaction, original=original, reversal=reversal)
    audit.log(
        "reverse",
        original,
        before=before,
        after=audit.snapshot_transaction(reversal),
        reason=reason,
    )
    return reversal


def _remaining_by_account(original: LedgerTransaction) -> list[tuple[LedgerAccount, int]]:
    """Efeito ainda vivo da original, por conta: original + estornos parciais (RN-121)."""
    totals: dict[int, int] = defaultdict(int)
    accounts: dict[int, LedgerAccount] = {}
    for p in original.postings.select_related("account").order_by("id"):
        totals[p.account_id] += p.amount_cents
        accounts[p.account_id] = p.account
    partial_ids = original.links_in.filter(kind=LinkKind.PARTIALLY_REVERSES).values_list(
        "from_transaction_id", flat=True
    )
    for p in LedgerPosting.objects.filter(transaction_id__in=list(partial_ids)):
        totals[p.account_id] += p.amount_cents
    return [(accounts[acc_id], cents) for acc_id, cents in totals.items()]


def _gross(txn: LedgerTransaction) -> int:
    return sum(p.amount_cents for p in txn.postings.all() if p.amount_cents > 0)


def _partial_reversed_cents(txn: LedgerTransaction) -> int:
    agg = txn.links_in.filter(kind=LinkKind.PARTIALLY_REVERSES).aggregate(total=Sum("amount_cents"))
    return agg["total"] or 0


def _check_version(current: LedgerTransaction, expected_version: int | None) -> None:
    if expected_version is not None and current.version != expected_version:
        raise ConcurrentEditError(
            "Este item foi alterado em outro aparelho. Os dados foram recarregados."
        )


def _idempotent_result(key: str | None, operation: str) -> LedgerTransaction | None:
    if not key:
        return None
    record = IdempotencyRecord.objects.filter(key=key).first()
    if record is None:
        return None
    if record.operation != operation:
        raise IdempotencyConflictError("Esta chave já foi usada em outra operação.")
    return LedgerTransaction.objects.get(pk=record.result_id)


def _remember(key: str | None, operation: str, txn: LedgerTransaction) -> None:
    if key:
        IdempotencyRecord.objects.create(
            key=key, operation=operation, result_type="ledger_transaction", result_id=txn.pk
        )
