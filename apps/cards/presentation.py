"""Cartão desenhado na tela: aparência, fatura que vem e limite livre (ADR-043)."""

from __future__ import annotations

import datetime

from . import brands, services


def card_view(card, today: datetime.date) -> dict:
    estimates = services.estimate(card, today)
    upcoming = next((e for e in estimates if e.due_date >= today and e.amount.is_positive), None)
    return {
        "card": card,
        **brands.face(card),
        "owed": services.liability(card),
        "available": services.available_limit(card),
        "next": upcoming,
        "estimates": estimates,
    }
