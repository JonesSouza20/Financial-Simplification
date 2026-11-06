"""Ciclo de fatura (RN-070 a RN-073). Funções puras, sem banco."""

from __future__ import annotations

import calendar
import datetime


def clamp(year: int, month: int, day: int) -> datetime.date:
    """Dia no mês, limitado ao último dia (ex.: dia 31 em abril vira 30; RN-055)."""
    return datetime.date(year, month, min(day, calendar.monthrange(year, month)[1]))


def add_months(year: int, month: int, n: int) -> tuple[int, int]:
    index = year * 12 + (month - 1) + n
    return index // 12, index % 12 + 1


def closing_date(purchase: datetime.date, closing_day: int, goes_next: bool = True):
    """Fechamento do ciclo em que a compra cai. Compra no dia do fechamento vai para o próximo."""
    candidate = clamp(purchase.year, purchase.month, closing_day)
    if candidate < purchase or (goes_next and candidate == purchase):
        y, m = add_months(purchase.year, purchase.month, 1)
        candidate = clamp(y, m, closing_day)
    return candidate


def due_date_for(closing: datetime.date, closing_day: int, due_day: int) -> datetime.date:
    """Vencimento original: mês do fechamento se o dia de vencimento for maior; senão o seguinte."""
    if due_day > closing_day:
        return clamp(closing.year, closing.month, due_day)
    y, m = add_months(closing.year, closing.month, 1)
    return clamp(y, m, due_day)


def first_due(purchase: datetime.date, closing_day: int, due_day: int, goes_next: bool = True):
    return due_date_for(closing_date(purchase, closing_day, goes_next), closing_day, due_day)


def nth_due(first: datetime.date, k: int, due_day: int) -> datetime.date:
    """Vencimento da parcela k (1..n): k − 1 meses depois da primeira (RN-073)."""
    y, m = add_months(first.year, first.month, k - 1)
    return clamp(y, m, due_day)
