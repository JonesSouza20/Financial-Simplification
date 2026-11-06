"""Capturas para revisão visual: FIN_SCREENSHOTS=1 uv run pytest -m e2e -k screens"""

import os
from pathlib import Path

import pytest

from apps.entries import services as entries
from apps.entries.services import EXPENSE, INCOME, EntryInput
from apps.money import Money

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(not os.environ.get("FIN_SCREENSHOTS"), reason="só sob demanda"),
]

OUT = Path(__file__).resolve().parents[2] / "var" / "screens"


def test_screens(app, fin, cats, on_20_11):
    entries.record(
        EntryInput(
            kind=INCOME,
            amount=Money(500000),
            account=fin.corrente,
            on=on_20_11,
            category=cats.salario,
        )
    )
    entries.record(
        EntryInput(
            kind=EXPENSE,
            amount=Money(23000),
            account=fin.corrente,
            on=on_20_11,
            category=cats.mercado,
        )
    )
    OUT.mkdir(parents=True, exist_ok=True)
    for theme in ("light", "dark"):
        app.evaluate(f"localStorage.setItem('fin-theme', '{theme}')")
        for name, path in (
            ("home", "/"),
            ("lancar", "/movimentacoes/lancar/"),
            ("movimentacoes", "/movimentacoes/"),
        ):
            app.goto(app.base + path)
            app.screenshot(path=str(OUT / f"{name}-{theme}.png"), full_page=True)
