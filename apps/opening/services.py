"""Assistente de abertura (F-002; ADR-031; RN-089; S00).

O rascunho fica na sessão. A confirmação final grava tudo numa única transação de banco:
ou entra tudo, ou nada.
"""

from __future__ import annotations

import datetime

from django.conf import settings
from django.db import transaction

from apps.accounts import services as accounts
from apps.accounts.models import DEFAULT_CLASS
from apps.cards import services as cards
from apps.cards.models import OpeningKind
from apps.debts import services as debts
from apps.ledger import services as ledger
from apps.ledger.errors import InvalidStateError
from apps.ledger.models import TransactionType
from apps.ledger.services import Leg
from apps.money import Money, split_installments
from apps.persons import services as persons
from apps.receivables import services as receivables
from apps.ui import models as prefs

SECTIONS = ("accounts", "cards", "items", "debts", "receivables")
SESSION_KEY = "opening_draft"


def empty() -> dict:
    return {key: [] for key in SECTIONS}


def load(session) -> dict:
    draft = session.get(SESSION_KEY) or empty()
    for key in SECTIONS:
        draft.setdefault(key, [])
    return draft


def save(session, draft: dict) -> None:
    session[SESSION_KEY] = draft
    session.modified = True


def done() -> bool:
    return bool(prefs.get("opening_done", False))


def item_amount(item: dict) -> int:
    """Valor de abertura do item de cartão, em centavos (RN-089)."""
    if item["kind"] == OpeningKind.REMAINING:
        parts = split_installments(Money(item["total"]), item["installments"])
        return Money.sum(parts[item["billed"] :]).cents
    return item["amount"]


def summary(draft: dict) -> dict:
    accs = draft["accounts"]
    by_class = {"free": 0, "reserve": 0, "benefit": 0}
    for a in accs:
        by_class[a["asset_class"]] += a["balance"]
    card_rows = []
    third_party = 0
    for index, card in enumerate(draft["cards"]):
        items = [i for i in draft["items"] if i["card"] == index]
        owed = sum(item_amount(i) for i in items)
        third_party += sum(item_amount(i) for i in items if i.get("person"))
        card_rows.append(
            {
                "name": card["name"],
                "owed": Money(owed),
                "available": Money(card["limit"] - owed),
                "items": len(items),
            }
        )
    cards_total = sum(r["owed"].cents for r in card_rows)
    debts_total = sum(d["balance"] or 0 for d in draft["debts"] if d["kind"] == "loan")
    receivable_total = sum(r["amount"] for r in draft["receivables"]) + third_party
    assets = by_class["free"] + by_class["reserve"] + by_class["benefit"] + receivable_total
    liabilities = cards_total + debts_total
    return {
        "bank": Money(by_class["free"] + by_class["reserve"]),
        "benefit": Money(by_class["benefit"]),
        "cards": card_rows,
        "cards_total": Money(cards_total),
        "debts_total": Money(debts_total),
        "receivable_total": Money(receivable_total),
        "equity": Money(assets - liabilities),
    }


def _date(text: str | None) -> datetime.date | None:
    return datetime.date.fromisoformat(text) if text else None


@transaction.atomic
def commit(draft: dict) -> None:
    """Grava a abertura inteira, atomicamente (F-002)."""
    if done():
        raise InvalidStateError("A abertura já foi feita.")
    start = settings.FINANCAS_START_DATE
    for a in draft["accounts"]:
        accounts.create_account(
            name=a["name"],
            account_type=a["account_type"],
            asset_class=a["asset_class"] or DEFAULT_CLASS[a["account_type"]],
            institution=a.get("institution", ""),
            opening_balance=Money(a["balance"]),
            opening_date=start,
        )
    created_cards = []
    for c in draft["cards"]:
        created_cards.append(
            cards.create_card(
                name=c["name"],
                issuer=c.get("issuer", ""),
                credit_limit=Money(c["limit"]),
                closing_day=c["closing_day"],
                due_day=c["due_day"],
            )
        )
    for i in draft["items"]:
        person = persons.get_or_create(i["person"]) if i.get("person") else None
        cards.record_opening_item(
            card=created_cards[i["card"]],
            kind=i["kind"],
            description=i.get("description", ""),
            amount=Money(i["amount"]) if i.get("amount") else None,
            due_date=_date(i.get("due_date")),
            purchase_date=_date(i.get("purchase_date")),
            total=Money(i["total"]) if i.get("total") else None,
            installments=i.get("installments") or 1,
            billed=i.get("billed") or 0,
            person=person,
        )
    for d in draft["debts"]:
        if d["kind"] == "loan":
            debts.create_loan(
                creditor=d["creditor"],
                description=d.get("description", ""),
                balance=Money(d["balance"]),
                due_day=d["due_day"],
                monthly_rate_percent=d.get("rate") or None,
                remaining_installments=d.get("remaining") or None,
                contract_installment=Money(d["installment"]) if d.get("installment") else None,
            )
        else:
            debts.create_consortium(
                description=d.get("description") or "Consórcio",
                installment=Money(d["installment"]),
                due_day=d["due_day"],
                remaining_installments=d["remaining"],
                creditor=d.get("creditor") or "Consórcio",
            )
    equity = ledger.system_account("equity:opening")
    for r in draft["receivables"]:
        person = persons.get_or_create(r["person"])
        amount = Money(r["amount"])
        txn = ledger.record(
            type=TransactionType.OPENING_BALANCE,
            legs=[Leg(person.ledger_account, amount), Leg(equity, -amount)],
            operation_date=start,
            description=f"Abertura: {person.name} devia {amount}",
        )
        receivables.create(
            person=person,
            origin_kind="opening",
            origin_transaction=txn,
            total=amount,
            due_date=_date(r["due_date"]),
            description=r.get("description") or "Saldo de abertura",
        )
    prefs.put("opening_done", True)
